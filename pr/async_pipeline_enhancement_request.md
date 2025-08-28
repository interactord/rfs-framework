# 🚀 RFS Framework 비동기 파이프라인 개선 요청서

**생성일**: 2025-08-28  
**우선순위**: High (중요도 높음)  
**카테고리**: Core Enhancement  
**영향 범위**: rfs.async_pipeline (신규), rfs.core.result (확장)

## 📋 요약

현재 RFS Framework의 비동기 코드에서 MonadResult 패턴이 우아하지 않은 문제를 해결하기 위해, 전용 AsyncResult 모나드와 통합 비동기 파이프라인 시스템을 구현합니다.

## 🎯 배경 및 문제 상황

### 현재 문제점
1. **우아하지 않은 비동기 패턴**:
   ```python
   # ❌ 현재: 복잡하고 에러 발생하기 쉬운 패턴
   result = await (
       MonadResult.from_try(lambda: async_func())
       .bind(lambda x: MonadResult.from_try(lambda: another_async_func(x)))
       .to_result()  # AttributeError 발생 위험
   )
   ```

2. **비동기/동기 함수 혼재 처리의 복잡성**:
   - 파이프라인에서 동기와 비동기 함수를 섞어 사용할 때의 복잡성
   - 타입 안전성 부족으로 인한 런타임 에러

3. **에러 컨텍스트 손실**:
   - 비동기 체인에서 어느 단계에서 에러가 발생했는지 추적 어려움
   - 에러 복구 메커니즘 부재

4. **성능 최적화 부족**:
   - 병렬 처리 기회 놓침
   - 백프레셔(backpressure) 처리 미흡

## 🏗️ 제안하는 해결 방안

### 1. AsyncResult 모나드 도입

**파일**: `src/rfs/async_pipeline/async_result.py`

```python
from typing import Awaitable, Callable, Generic, TypeVar, Union
from ..core.result import Result

T = TypeVar('T')
U = TypeVar('U')
E = TypeVar('E')

class AsyncResult(Generic[T, E]):
    """비동기 전용 Result 모나드"""
    
    def __init__(self, coro: Awaitable[Result[T, E]]):
        self._coro = coro
    
    @classmethod
    def from_async(cls, async_func: Callable[[], Awaitable[T]]) -> 'AsyncResult[T, Exception]':
        """비동기 함수로부터 AsyncResult 생성"""
        async def wrapper():
            try:
                result = await async_func()
                return Success(result)
            except Exception as e:
                return Failure(e)
        return cls(wrapper())
    
    @classmethod
    def from_value(cls, value: T) -> 'AsyncResult[T, E]':
        """값으로부터 AsyncResult 생성"""
        async def wrapper():
            return Success(value)
        return cls(wrapper())
    
    @classmethod
    def from_error(cls, error: E) -> 'AsyncResult[T, E]':
        """에러로부터 AsyncResult 생성"""
        async def wrapper():
            return Failure(error)
        return cls(wrapper())
    
    async def bind_async(self, func: Callable[[T], 'AsyncResult[U, E]']) -> 'AsyncResult[U, E]':
        """비동기 함수와 바인딩"""
        result = await self._coro
        if result.is_success():
            return func(result.unwrap())
        else:
            return AsyncResult.from_error(result.unwrap_error())
    
    async def map_async(self, func: Callable[[T], Awaitable[U]]) -> 'AsyncResult[U, E]':
        """비동기 함수로 매핑"""
        result = await self._coro
        if result.is_success():
            try:
                new_value = await func(result.unwrap())
                return AsyncResult.from_value(new_value)
            except Exception as e:
                return AsyncResult.from_error(e)
        else:
            return AsyncResult.from_error(result.unwrap_error())
    
    def map_sync(self, func: Callable[[T], U]) -> 'AsyncResult[U, E]':
        """동기 함수로 매핑"""
        async def wrapper():
            result = await self._coro
            return result.map(func)
        return AsyncResult(wrapper())
    
    async def unwrap_async(self) -> T:
        """결과 추출"""
        result = await self._coro
        return result.unwrap()
    
    async def unwrap_or_else_async(self, default_func: Callable[[E], Awaitable[T]]) -> T:
        """실패 시 기본값 함수 실행"""
        result = await self._coro
        if result.is_success():
            return result.unwrap()
        else:
            return await default_func(result.unwrap_error())
    
    async def to_result(self) -> Result[T, E]:
        """일반 Result로 변환"""
        return await self._coro
```

### 2. 통합 비동기 파이프라인

**파일**: `src/rfs/async_pipeline/core.py`

```python
from typing import Any, Awaitable, Callable, List, Union
from .async_result import AsyncResult

class AsyncPipeline:
    """비동기/동기 함수 혼재 파이프라인"""
    
    def __init__(self, operations: List[Callable]):
        self.operations = operations
    
    async def execute(self, initial_value: Any) -> AsyncResult:
        """파이프라인 실행"""
        current = AsyncResult.from_value(initial_value)
        
        for op in self.operations:
            if self._is_async_function(op):
                current = await current.bind_async(
                    lambda x: AsyncResult.from_async(lambda: op(x))
                )
            else:
                current = current.map_sync(op)
        
        return current
    
    def _is_async_function(self, func: Callable) -> bool:
        """함수가 비동기인지 확인"""
        import inspect
        return inspect.iscoroutinefunction(func)

def async_pipe(*operations) -> AsyncPipeline:
    """비동기 파이프라인 생성"""
    return AsyncPipeline(list(operations))

# 편의 함수
async def execute_async_pipeline(
    operations: List[Callable], 
    initial_value: Any
) -> AsyncResult:
    """파이프라인 직접 실행"""
    pipeline = async_pipe(*operations)
    return await pipeline.execute(initial_value)
```

### 3. 고급 에러 처리

**파일**: `src/rfs/async_pipeline/error_handling.py`

```python
import asyncio
from typing import Awaitable, Callable, Optional, Type
from .async_result import AsyncResult

class AsyncErrorContext:
    """비동기 에러 컨텍스트"""
    
    def __init__(self, operation_name: str, step: int, error: Exception):
        self.operation_name = operation_name
        self.step = step
        self.error = error
        self.timestamp = asyncio.get_event_loop().time()

class AsyncRetryWrapper:
    """비동기 재시도 래퍼"""
    
    def __init__(self, 
                 attempts: int = 3, 
                 backoff: float = 1.0, 
                 exceptions: tuple = (Exception,)):
        self.attempts = attempts
        self.backoff = backoff
        self.exceptions = exceptions
    
    async def __call__(self, func: Callable[[], Awaitable]) -> AsyncResult:
        """재시도 실행"""
        last_error = None
        current_backoff = self.backoff
        
        for attempt in range(self.attempts):
            try:
                result = await func()
                return AsyncResult.from_value(result)
            except self.exceptions as e:
                last_error = e
                if attempt < self.attempts - 1:
                    await asyncio.sleep(current_backoff)
                    current_backoff *= 2  # 지수 백오프
        
        return AsyncResult.from_error(last_error)

def with_retry(attempts: int = 3, backoff: float = 1.0) -> AsyncRetryWrapper:
    """재시도 데코레이터 팩토리"""
    return AsyncRetryWrapper(attempts, backoff)

class AsyncFallbackWrapper:
    """비동기 폴백 래퍼"""
    
    def __init__(self, fallback_func: Callable):
        self.fallback_func = fallback_func
    
    async def __call__(self, primary_func: Callable[[], Awaitable]) -> AsyncResult:
        """주 함수 실행, 실패 시 폴백"""
        try:
            result = await primary_func()
            return AsyncResult.from_value(result)
        except Exception as primary_error:
            try:
                fallback_result = await self.fallback_func()
                return AsyncResult.from_value(fallback_result)
            except Exception as fallback_error:
                return AsyncResult.from_error(f"Primary: {primary_error}, Fallback: {fallback_error}")

def with_fallback(fallback_func: Callable) -> AsyncFallbackWrapper:
    """폴백 래퍼 팩토리"""
    return AsyncFallbackWrapper(fallback_func)
```

### 4. 성능 최적화 도구

**파일**: `src/rfs/async_pipeline/performance.py`

```python
import asyncio
from typing import Awaitable, Callable, List, TypeVar
from .async_result import AsyncResult

T = TypeVar('T')
U = TypeVar('U')

async def parallel_map(
    func: Callable[[T], Awaitable[U]], 
    items: List[T], 
    concurrency: int = 10
) -> List[AsyncResult[U, Exception]]:
    """병렬 매핑 (동시성 제한)"""
    semaphore = asyncio.Semaphore(concurrency)
    
    async def bounded_func(item):
        async with semaphore:
            return await AsyncResult.from_async(lambda: func(item)).to_result()
    
    tasks = [bounded_func(item) for item in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return [
        AsyncResult.from_value(result) if not isinstance(result, Exception)
        else AsyncResult.from_error(result)
        for result in results
    ]

class AsyncBackpressureWrapper:
    """백프레셔 처리 래퍼"""
    
    def __init__(self, buffer_size: int = 100):
        self.buffer_size = buffer_size
        self.queue = asyncio.Queue(buffer_size)
    
    async def process_stream(self, 
                           producer: Callable[[], Awaitable], 
                           processor: Callable[[T], Awaitable[U]]) -> AsyncResult:
        """스트림 처리 (백프레셔 적용)"""
        async def produce():
            async for item in producer():
                await self.queue.put(item)
            await self.queue.put(None)  # 종료 신호
        
        async def consume():
            results = []
            while True:
                item = await self.queue.get()
                if item is None:
                    break
                result = await processor(item)
                results.append(result)
            return results
        
        producer_task = asyncio.create_task(produce())
        consumer_task = asyncio.create_task(consume())
        
        try:
            results = await consumer_task
            return AsyncResult.from_value(results)
        except Exception as e:
            producer_task.cancel()
            return AsyncResult.from_error(e)

def with_backpressure(buffer_size: int = 100) -> AsyncBackpressureWrapper:
    """백프레셔 래퍼 팩토리"""
    return AsyncBackpressureWrapper(buffer_size)
```

### 5. 패키지 초기화

**파일**: `src/rfs/async_pipeline/__init__.py`

```python
"""
RFS Framework Async Pipeline
비동기 함수형 프로그래밍을 위한 고급 파이프라인 도구
"""

from .async_result import AsyncResult
from .core import AsyncPipeline, async_pipe, execute_async_pipeline
from .error_handling import (
    AsyncErrorContext,
    AsyncRetryWrapper,
    AsyncFallbackWrapper,
    with_retry,
    with_fallback
)
from .performance import parallel_map, AsyncBackpressureWrapper, with_backpressure

__all__ = [
    # Core
    'AsyncResult',
    'AsyncPipeline',
    'async_pipe',
    'execute_async_pipeline',
    
    # Error Handling
    'AsyncErrorContext',
    'AsyncRetryWrapper', 
    'AsyncFallbackWrapper',
    'with_retry',
    'with_fallback',
    
    # Performance
    'parallel_map',
    'AsyncBackpressureWrapper',
    'with_backpressure',
]

# 버전 정보
__version__ = '1.0.0'
```

## 📚 사용 예시

### 기본 사용법
```python
from rfs.async_pipeline import AsyncResult, async_pipe

# 1. AsyncResult 기본 사용
async def fetch_user_data(user_id: str) -> dict:
    # DB에서 사용자 데이터 조회
    return {"id": user_id, "name": "John"}

async def validate_user(user_data: dict) -> dict:
    if not user_data.get("name"):
        raise ValueError("Name is required")
    return user_data

# AsyncResult 체이닝
result = await (
    AsyncResult.from_async(lambda: fetch_user_data("123"))
    .bind_async(lambda data: AsyncResult.from_async(lambda: validate_user(data)))
    .map_sync(lambda data: {**data, "validated": True})
)

user = await result.unwrap_async()
print(user)  # {"id": "123", "name": "John", "validated": True}
```

### 통합 파이프라인
```python
from rfs.async_pipeline import async_pipe

# 동기/비동기 혼재 파이프라인
def format_name(data: dict) -> dict:
    return {**data, "name": data["name"].upper()}

async def save_to_cache(data: dict) -> dict:
    await cache.set(data["id"], data)
    return data

pipeline = async_pipe(
    fetch_user_data,    # async
    validate_user,      # async  
    format_name,        # sync
    save_to_cache       # async
)

result = await pipeline.execute("123")
final_data = await result.unwrap_async()
```

### 에러 처리 및 재시도
```python
from rfs.async_pipeline import with_retry, with_fallback

# 재시도가 있는 API 호출
@with_retry(attempts=3, backoff=1.0)
async def unreliable_api_call():
    # 가끔 실패할 수 있는 API 호출
    pass

# 폴백이 있는 처리
async def primary_service():
    raise Exception("Service unavailable")

async def fallback_service():
    return {"source": "fallback", "data": "default"}

result = await with_fallback(fallback_service)(primary_service)
```

## 📋 구현 체크리스트

### Phase 1: 핵심 AsyncResult (2주)
- [ ] AsyncResult 클래스 기본 구현
- [ ] bind_async, map_async, map_sync 메서드
- [ ] 타입 안전성 보장
- [ ] 기본 테스트 작성

### Phase 2: 파이프라인 시스템 (2주) 
- [ ] AsyncPipeline 클래스 구현
- [ ] async_pipe 팩토리 함수
- [ ] 동기/비동기 함수 자동 감지
- [ ] 파이프라인 실행 엔진

### Phase 3: 에러 처리 (1주)
- [ ] AsyncRetryWrapper 구현
- [ ] AsyncFallbackWrapper 구현  
- [ ] 에러 컨텍스트 추적
- [ ] 데코레이터 팩토리 함수들

### Phase 4: 성능 최적화 (1주)
- [ ] parallel_map 구현
- [ ] AsyncBackpressureWrapper 구현
- [ ] 동시성 제어 메커니즘
- [ ] 메모리 효율성 최적화

### Phase 5: 통합 및 문서화 (1주)
- [ ] 패키지 초기화 및 export
- [ ] 포괄적인 단위 테스트
- [ ] 사용 예시 및 문서
- [ ] stdlib 통합

## 🎯 성공 기준

1. **기능적 요구사항**:
   - ✅ 비동기 함수 체이닝이 우아하고 읽기 쉬워야 함
   - ✅ 동기/비동기 함수 혼재 파이프라인 지원
   - ✅ 타입 안전한 에러 처리
   - ✅ 성능 최적화 도구 제공

2. **품질 요구사항**:
   - ✅ 95% 이상 테스트 커버리지
   - ✅ mypy strict 모드 통과
   - ✅ 기존 RFS Framework 규칙 준수
   - ✅ 한글 주석 및 문서화

3. **성능 요구사항**:
   - ✅ 기존 MonadResult 대비 30% 이상 성능 향상
   - ✅ 메모리 사용량 최적화
   - ✅ 동시성 처리 개선

## 🚀 배포 및 적용 계획

1. **RFS Framework 배포** (1주):
   - 새로운 async_pipeline 모듈 릴리스
   - 버전 업데이트 및 변경 로그
   - PyPI 배포

2. **현재 프로젝트 적용** (1주):
   - 의존성 업데이트
   - 에러 핸들러 미들웨어 리팩토링  
   - 헬스체크 엔드포인트 개선
   - 기존 MonadResult 코드 마이그레이션

## 📞 담당자 및 일정

**구현 담당**: RFS Framework Core Team  
**리뷰어**: Architecture Team  
**예상 완료일**: 2025-10-15  
**우선순위**: High

---

이 구현을 통해 RFS Framework의 비동기 함수형 프로그래밍 지원을 대폭 개선하고, 현재 프로젝트에서 발생하는 MonadResult + async 조합의 문제점을 근본적으로 해결할 수 있습니다.