# PR: ResultAsync 런타임 경고 수정

## 문제 설명

RFS Framework 4.6.0의 `ResultAsync` 클래스 사용 시 다음과 같은 런타임 경고가 발생합니다:

```
RuntimeWarning: coroutine 'ResultAsync.is_success' was never awaited
RuntimeWarning: coroutine 'ResultAsync.unwrap_or' was never awaited
RuntimeWarning: coroutine 'ResultAsync.from_value.<locals>.create_success' was never awaited
RuntimeWarning: coroutine 'ResultAsync.bind_async.<locals>.bound' was never awaited
RuntimeWarning: coroutine 'ResultAsync.from_error.<locals>.create_failure' was never awaited
```

### 발생 위치
- `/venv/lib/python3.13/site-packages/rfs/hof/async_hof.py:202`
- 사용자 코드에서 `ResultAsync` 메서드 호출 시

## 근본 원인

`ResultAsync` 클래스의 일부 메서드들이 일관성 없는 async/sync 패턴을 사용하고 있습니다:

1. `from_value()`와 `from_error()`는 코루틴을 반환하지만 `await` 없이 사용되도록 설계됨
2. `is_success()`, `unwrap_or()` 등의 메서드가 async로 정의되어 있지만 실제로는 sync처럼 사용됨
3. 내부 헬퍼 함수들(`create_success`, `create_failure`)이 불필요하게 async로 정의됨

## 제안하는 해결책

### 옵션 1: ResultAsync 클래스 리팩토링 (권장)

```python
class ResultAsync:
    """비동기 Result 모나드"""
    
    @classmethod
    def from_value(cls, value: T) -> 'ResultAsync[T, E]':
        """값으로부터 성공 ResultAsync 생성 (동기 메서드)"""
        instance = cls()
        instance._value = value
        instance._is_success = True
        return instance
    
    @classmethod
    def from_error(cls, error: E) -> 'ResultAsync[T, E]':
        """에러로부터 실패 ResultAsync 생성 (동기 메서드)"""
        instance = cls()
        instance._error = error
        instance._is_success = False
        return instance
    
    def is_success(self) -> bool:
        """성공 여부 확인 (동기 메서드)"""
        return self._is_success
    
    def is_failure(self) -> bool:
        """실패 여부 확인 (동기 메서드)"""
        return not self._is_success
    
    def unwrap_or(self, default: T) -> T:
        """값 또는 기본값 반환 (동기 메서드)"""
        return self._value if self._is_success else default
    
    async def to_result(self) -> Result[T, E]:
        """ResultAsync를 Result로 변환 (비동기 유지)"""
        if self._is_success:
            return Success(self._value)
        return Failure(self._error)
    
    async def bind_async(self, func: Callable[[T], Awaitable['ResultAsync[U, E]']]) -> 'ResultAsync[U, E]':
        """비동기 바인드 연산"""
        if not self._is_success:
            return ResultAsync.from_error(self._error)
        try:
            result = await func(self._value)
            return result
        except Exception as e:
            return ResultAsync.from_error(str(e))
```

### 옵션 2: 새로운 AsyncResult 클래스 도입

기존 `ResultAsync`를 deprecated로 표시하고 새로운 `AsyncResult` 클래스 도입:

```python
class AsyncResult:
    """
    개선된 비동기 Result 모나드
    명확한 sync/async 경계를 가진 새로운 구현
    """
    
    def __init__(self, value=None, error=None):
        self._value = value
        self._error = error
        self._is_success = error is None
    
    @classmethod
    def success(cls, value: T) -> 'AsyncResult[T, E]':
        """성공 AsyncResult 생성"""
        return cls(value=value)
    
    @classmethod
    def failure(cls, error: E) -> 'AsyncResult[T, E]':
        """실패 AsyncResult 생성"""
        return cls(error=error)
    
    # 동기 메서드들
    def is_ok(self) -> bool:
        return self._is_success
    
    def is_err(self) -> bool:
        return not self._is_success
    
    def unwrap_or(self, default: T) -> T:
        return self._value if self._is_success else default
    
    # 비동기 메서드들
    async def map_async(self, func: Callable[[T], Awaitable[U]]) -> 'AsyncResult[U, E]':
        """비동기 매핑"""
        if not self._is_success:
            return AsyncResult.failure(self._error)
        try:
            new_value = await func(self._value)
            return AsyncResult.success(new_value)
        except Exception as e:
            return AsyncResult.failure(str(e))
    
    async def and_then_async(self, func: Callable[[T], Awaitable['AsyncResult[U, E]']]) -> 'AsyncResult[U, E]':
        """비동기 체이닝 (flatMap)"""
        if not self._is_success:
            return AsyncResult.failure(self._error)
        return await func(self._value)
```

## 마이그레이션 가이드

### 현재 사용 패턴
```python
# 문제가 있는 현재 코드
result = await ResultAsync.from_value(data)  # 불필요한 await
if result.is_success():  # RuntimeWarning 발생
    value = result.unwrap_or(None)  # RuntimeWarning 발생
```

### 개선된 사용 패턴
```python
# 옵션 1: 개선된 ResultAsync
result = ResultAsync.from_value(data)  # await 없음
if result.is_success():  # 동기 메서드
    value = result.unwrap_or(None)  # 동기 메서드

# 옵션 2: 새로운 AsyncResult
result = AsyncResult.success(data)
if result.is_ok():
    value = result.unwrap_or(None)
```

## 영향 범위

### 영향받는 모듈
- `rfs.hof.async_hof`
- `rfs.core.result`
- `rfs.stdlib`

### 하위 호환성
- **옵션 1**: 기존 코드에서 불필요한 `await` 제거 필요
- **옵션 2**: 기존 `ResultAsync` 유지, 새 코드는 `AsyncResult` 사용 권장

## 테스트 계획

```python
# tests/test_async_result.py
import pytest
from rfs import AsyncResult  # 또는 개선된 ResultAsync

class TestAsyncResult:
    def test_sync_methods_no_await(self):
        """동기 메서드가 await 없이 작동하는지 확인"""
        result = AsyncResult.success(42)
        assert result.is_ok()  # RuntimeWarning 없어야 함
        assert result.unwrap_or(0) == 42
    
    @pytest.mark.asyncio
    async def test_async_methods_with_await(self):
        """비동기 메서드가 await와 함께 작동하는지 확인"""
        result = AsyncResult.success(42)
        
        async def double(x):
            return x * 2
        
        new_result = await result.map_async(double)
        assert new_result.is_ok()
        assert new_result.unwrap_or(0) == 84
    
    def test_no_runtime_warnings(self):
        """런타임 경고가 발생하지 않는지 확인"""
        import warnings
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            result = AsyncResult.success(42)
            _ = result.is_ok()
            _ = result.unwrap_or(0)
            
            assert len(w) == 0, "런타임 경고가 발생하지 않아야 함"
```

## 성능 개선

동기 메서드를 실제 동기로 만들면:
- 불필요한 코루틴 생성 오버헤드 제거
- 이벤트 루프 스케줄링 오버헤드 감소
- 약 15-20% 성능 향상 예상

## 체크리스트

- [ ] `ResultAsync` 클래스의 sync/async 메서드 분리
- [ ] 불필요한 내부 코루틴 제거
- [ ] 문서 업데이트 (동기/비동기 메서드 명확히 구분)
- [ ] 단위 테스트 작성
- [ ] 런타임 경고 테스트 추가
- [ ] 마이그레이션 가이드 작성
- [ ] 하위 호환성 테스트

## 참고 자료

- Python 3.13 asyncio 문서: https://docs.python.org/3/library/asyncio.html
- PEP 492 – Coroutines with async and await syntax
- 유사한 이슈: Rust의 Future/Result 패턴

## 예상 타임라인

- 구현: 2-3일
- 테스트: 1-2일
- 문서화: 1일
- 총 예상: 1주일

## 기대 효과

1. **런타임 경고 제거**: 깔끔한 콘솔 출력
2. **성능 향상**: 불필요한 비동기 오버헤드 제거
3. **개발자 경험 개선**: 명확한 sync/async 경계
4. **유지보수성 향상**: 일관된 API 패턴