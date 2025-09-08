# RFS Framework ResultAsync 체이닝 버그 상세 분석 보고서

## 📌 개요
- **발견 일자**: 2025-09-08
- **영향 버전**: RFS Framework 4.6.2
- **심각도**: 🔴 Critical
- **영향 범위**: ResultAsync를 사용하는 모든 비동기 체이닝 코드

## 🐛 버그 상세 설명

### 문제 증상
ResultAsync의 체이닝 메서드들이 Python의 `await` 구문과 호환되지 않아 런타임 에러가 발생합니다.

```python
# 에러가 발생하는 코드
result = await (
    ResultAsync.from_value(10)
    .bind_async(lambda x: ResultAsync.from_value(x * 2))
    .map_async(lambda x: x + 5)
)
```

### 에러 메시지
```
TypeError: object ResultAsync can't be used in 'await' expression
RuntimeWarning: coroutine 'ResultAsync.from_value.<locals>.create_success' was never awaited
RuntimeWarning: coroutine 'ResultAsync.bind_async.<locals>.bound' was never awaited
RuntimeWarning: coroutine 'ResultAsync.map_async.<locals>.mapped' was never awaited
```

## 🔍 근본 원인 분석

### 1. ResultAsync 클래스 구현 문제
ResultAsync 클래스가 Python의 awaitable 프로토콜을 제대로 구현하지 않았습니다.

```python
# 현재 RFS 4.6.2의 ResultAsync 메서드 시그니처
bind_async(self, func: Callable[[T], Awaitable[Result[U, E]]]) -> 'ResultAsync[U, E]'
map_async(self, func: Callable[[T], Awaitable[U]]) -> 'ResultAsync[U, E]'
```

### 2. 체이닝 메커니즘 결함
- `bind_async()`, `map_async()` 등의 메서드가 `ResultAsync` 객체를 반환
- 반환된 `ResultAsync` 객체가 `__await__()` 메서드를 올바르게 구현하지 않음
- 체이닝된 전체 표현식을 `await` 할 수 없음

### 3. 코루틴 생성 문제
- `from_value()`, `from_error()` 메서드가 내부적으로 코루틴을 생성
- 하지만 이 코루틴들이 제대로 await되지 않아 RuntimeWarning 발생

## 🧪 재현 테스트 코드

```python
import asyncio
from rfs import ResultAsync

async def test_resultasync_chaining():
    """ResultAsync 체이닝 버그 재현 테스트"""
    
    # 테스트 1: 기본 체이닝 (실패)
    try:
        result = await (
            ResultAsync.from_value(10)
            .map_async(lambda x: asyncio.coroutine(lambda: x * 2)())
            .bind_async(lambda x: ResultAsync.from_value(x + 5))
        )
        print(f"테스트 1 성공: {result}")
    except TypeError as e:
        print(f"테스트 1 실패: {e}")
    
    # 테스트 2: 직접 await (실패)
    try:
        result_async = ResultAsync.from_value(5)
        result = await result_async  # 여기서 에러 발생
        print(f"테스트 2 성공: {result}")
    except TypeError as e:
        print(f"테스트 2 실패: {e}")

# 실행 결과:
# 테스트 1 실패: object ResultAsync can't be used in 'await' expression
# 테스트 2 실패: object ResultAsync can't be used in 'await' expression
```

## 💊 임시 해결 방법

### 1. 체이닝 대신 단계별 처리

```python
# ❌ 작동하지 않는 코드 (체이닝)
async def process_with_chaining(action):
    return await (
        ResultAsync.from_value(action)
        .bind_async(self._validate_action)
        .bind_async(self._update_state_by_action)
        .bind_async(self._save_updated_state)
        .map_async(self._notify_subscribers)
    )

# ✅ 작동하는 코드 (단계별 처리)
async def process_without_chaining(action):
    # 1단계: 검증
    validation_result = await self._validate_action(action)
    if validation_result.is_failure():
        return ResultAsync.from_value(validation_result)
    
    # 2단계: 상태 업데이트
    update_result = await self._update_state_by_action(
        validation_result.unwrap()
    )
    if update_result.is_failure():
        return ResultAsync.from_value(update_result)
    
    # 3단계: 저장
    save_result = await self._save_updated_state(
        update_result.unwrap()
    )
    if save_result.is_failure():
        return ResultAsync.from_value(save_result)
    
    # 4단계: 알림
    final_state = save_result.unwrap()
    await self._notify_subscribers(final_state)
    
    return ResultAsync.from_value(Success(final_state))
```

### 2. Result 패턴으로 대체

```python
# ResultAsync 대신 일반 Result 사용
from rfs import Result, Success, Failure

async def process_with_result(action) -> Result[State, str]:
    # 각 단계를 await하고 Result 반환
    validation_result = await self._validate_action(action)
    if validation_result.is_failure():
        return validation_result
    
    # 이후 단계들...
    return Success(final_state)
```

## 📊 영향 분석

### 영향받는 파일들
1. `src/document_processor/infrastructure/state/flux_store.py`
   - `_fallback_dispatch_action()` 메서드
   - `dispatch_action()` 메서드

2. `src/document_processor/domain/services/saga/progress_tracker.py`
   - 모든 `update_*` 메서드들

3. 기타 ResultAsync 체이닝을 사용하는 모든 코드

### 성능 영향
- 체이닝을 풀어서 작성하므로 코드가 길어짐
- 하지만 실행 성능에는 영향 없음
- RuntimeWarning이 사라져 로그가 깨끗해짐

## 🔧 권장 수정 사항

### RFS Framework 팀에 보고할 내용

1. **버그 설명**
   - ResultAsync가 Python의 awaitable 프로토콜을 제대로 구현하지 않음
   - 체이닝 메서드들이 await 가능한 객체를 반환하지 않음

2. **예상 동작**
   ```python
   # 이렇게 작동해야 함
   result = await (
       ResultAsync.from_value(10)
       .bind_async(async_function)
       .map_async(another_async_function)
   )
   ```

3. **제안 해결책**
   - ResultAsync 클래스에 `__await__()` 메서드 구현
   - 또는 체이닝 메서드들이 코루틴을 직접 반환하도록 수정

### 프로젝트 내 대응 방안

1. **단기 (즉시)**
   - 모든 ResultAsync 체이닝을 단계별 처리로 변경
   - RuntimeWarning 제거

2. **중기 (1-2주)**
   - ResultAsync 사용을 최소화
   - 가능한 곳은 일반 Result 패턴으로 대체

3. **장기 (RFS 업데이트 후)**
   - RFS Framework 업데이트 모니터링
   - 버그 수정 확인 후 체이닝 방식으로 복원

## 📝 관련 이슈 및 참조

### GitHub 이슈
- RFS Framework 저장소에 이슈 등록 필요
- 제목: "ResultAsync chaining is not awaitable in Python 3.13"

### 테스트 환경
- Python: 3.13.2
- RFS Framework: 4.6.2
- OS: macOS Darwin 24.6.0

### 관련 코드 위치
- 문제 발생 지점: `flux_store.py:198-204`
- 수정 적용 파일: 
  - `flux_store.py`
  - `progress_tracker.py`

## ✅ 검증 체크리스트

- [x] 버그 재현 확인
- [x] 근본 원인 분석
- [x] 임시 해결 방법 구현
- [x] 테스트 통과 확인
- [ ] RFS Framework 팀에 이슈 보고
- [ ] 프로덕션 배포 전 전체 테스트

## 📅 업데이트 이력

- 2025-09-08: 최초 발견 및 분석
- 2025-09-08: 임시 해결 방법 적용
- 2025-09-08: 분석 보고서 작성

---

*이 문서는 RFS Framework의 ResultAsync 체이닝 버그에 대한 상세 분석과 해결 방안을 담고 있습니다.*