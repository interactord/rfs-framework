# Phase 2: FastAPI 통합 헬퍼 구현

**Phase 시작일**: 2025-09-03  
**예상 완료일**: 2025-09-05 (3일)  
**현재 상태**: 🟡 계획 수립 중

---

## 📋 Phase 2 목표

Phase 1에서 완성된 MonoResult/FluxResult를 기반으로 FastAPI와의 완벽한 통합을 위한 헬퍼 시스템을 구현합니다. 실제 웹 애플리케이션에서 Result 패턴을 자연스럽게 활용할 수 있도록 지원합니다.

### 🎯 핵심 성과 목표
- [ ] FastAPI Response 변환 헬퍼 완성 (Result → HTTP Response)
- [ ] 의존성 주입 통합 (Dependency Injection with Result pattern)
- [ ] 미들웨어 통합 (에러 처리, 로깅, 모니터링)
- [ ] 예외 처리 표준화 (Exception → Result 자동 변환)
- [ ] 실제 API 엔드포인트에서 적용 가능한 패턴 완성

---

## 🎯 대상 사용 패턴

### 기존 문제점 (px 프로젝트에서 발견)
```python
# 현재의 복잡한 FastAPI 패턴
@app.get("/users/{user_id}")
async def get_user(user_id: str):
    try:
        user = await user_service.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return JSONResponse(content=user.dict())
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DatabaseError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

### 목표 패턴 (Phase 2 구현 후)
```python
# 🎯 구현할 우아한 FastAPI + Result 패턴
@app.get("/users/{user_id}")
@handle_result  # 데코레이터가 Result → HTTP Response 자동 변환
async def get_user(user_id: str) -> Result[UserResponse, APIError]:
    return await (
        MonoResult.from_async_result(lambda: user_service.get_user_async(user_id))
        .bind_result(lambda user: validate_user_response(user))
        .map_error(lambda e: APIError.from_service_error(e))
        .timeout(5.0)
        .to_result()
    )

# 또는 더 간단한 패턴
@app.get("/users/{user_id}")
async def get_user(user_id: str) -> FastAPIResult[UserResponse]:
    return await user_service.get_user_with_result(user_id)
```

### 배치 처리 패턴
```python
# 🎯 구현할 FluxResult + FastAPI 패턴
@app.post("/users/batch")
@handle_flux_result  # FluxResult → HTTP Response 배치 변환
async def process_users_batch(user_data: List[UserCreateRequest]) -> FluxResult[UserResponse, APIError]:
    return await (
        FluxResult.from_values(user_data)
        .parallel_map_async(lambda data: user_service.create_user_async(data))
        .filter_success()
        .map_error(lambda e: APIError.from_validation_error(e))
    )
```

---

## 🏗️ 구현 계획

### 1단계: 핵심 응답 변환기 (1일)
**파일**: `src/rfs/web/fastapi/response_helpers.py`

#### 핵심 기능
- `@handle_result` 데코레이터: Result → JSONResponse/HTTPException
- `@handle_flux_result` 데코레이터: FluxResult → 배치 응답
- 커스텀 APIError 클래스 체계
- HTTP 상태 코드 자동 매핑

#### 고급 기능
- 다국어 에러 메시지 지원
- Response 스키마 자동 생성
- OpenAPI 문서 자동 업데이트

### 2단계: 의존성 주입 통합 (1일)
**파일**: `src/rfs/web/fastapi/dependencies.py`

#### 핵심 기능
- `ResultDependency` 클래스: DI + Result 패턴
- `async_inject_result()` 헬퍼 함수
- 서비스 레이어 통합 패턴

### 3단계: 미들웨어 및 통합 (1일)
**파일**: `src/rfs/web/fastapi/middleware.py`

#### 핵심 기능
- Result 로깅 미들웨어
- 성능 모니터링 통합
- 예외 → Result 자동 변환

---

## 📊 기술 사양

### APIError 클래스 구조
```python
@dataclass
class APIError:
    code: str           # "USER_NOT_FOUND", "VALIDATION_ERROR"
    message: str        # 사용자 친화적 메시지
    details: Optional[dict] = None  # 추가 세부사항
    status_code: int = 500  # HTTP 상태 코드
    
    @classmethod
    def not_found(cls, resource: str) -> "APIError":
        return cls(
            code="NOT_FOUND",
            message=f"{resource}을(를) 찾을 수 없습니다",
            status_code=404
        )
    
    @classmethod
    def validation_error(cls, details: dict) -> "APIError":
        return cls(
            code="VALIDATION_ERROR", 
            message="입력값이 유효하지 않습니다",
            details=details,
            status_code=400
        )
```

### FastAPIResult 타입 별칭
```python
# 편의를 위한 타입 별칭
FastAPIResult = Result[T, APIError]
FastAPIFluxResult = FluxResult[T, APIError]

# 사용 예시
async def get_user(user_id: str) -> FastAPIResult[User]:
    # 구현
    pass
```

---

## 🧪 테스트 전략

### 단위 테스트
- 각 데코레이터 동작 검증
- APIError 클래스 기능 테스트
- 응답 변환 로직 정확성 확인

### 통합 테스트
- 실제 FastAPI 애플리케이션 통합 테스트
- MonoResult/FluxResult와의 완전한 호환성 검증
- 성능 벤치마크 (응답 시간, 메모리 사용량)

### 실제 시나리오 테스트
- px 프로젝트 Health Check 엔드포인트 리팩토링
- 사용자 관리 API 구현 예제
- 배치 처리 API 구현 예제

---

## 📈 성공 지표

### 정량적 지표
- [ ] FastAPI 엔드포인트 코드 50% 감소 (기존 try-catch 대비)
- [ ] 응답 시간 <10ms 오버헤드
- [ ] 타입 에러 0개 (mypy 검증)
- [ ] API 문서 자동 생성 완료

### 정성적 지표
- [ ] 개발자 경험 대폭 향상 (Result 패턴 자연스러운 사용)
- [ ] 에러 처리 일관성 확보
- [ ] API 응답 형식 표준화
- [ ] px 프로젝트 실제 적용 가능

---

## 🚨 위험 요소 및 대응

### 주요 위험 요소
1. **FastAPI 호환성**: FastAPI 버전별 호환성 이슈
2. **성능 오버헤드**: 추가 래핑으로 인한 성능 저하
3. **복잡성 증가**: 너무 많은 추상화로 인한 학습 곡선

### 대응 방안
1. **호환성 테스트**: 다양한 FastAPI 버전에서 테스트
2. **벤치마크**: 성능 오버헤드 <10ms 유지
3. **단계적 도입**: 기본 패턴부터 고급 기능까지 선택적 사용

---

## 📂 파일 구조

```
src/rfs/web/
├── __init__.py
├── fastapi/
│   ├── __init__.py
│   ├── response_helpers.py    # @handle_result, @handle_flux_result
│   ├── dependencies.py        # ResultDependency, async_inject_result
│   ├── middleware.py          # Result 로깅, 성능 모니터링
│   ├── errors.py              # APIError 클래스 체계
│   └── types.py               # FastAPIResult 타입 별칭
└── examples/
    ├── basic_api.py           # 기본 API 구현 예제
    ├── user_management.py     # 사용자 관리 API 예제
    └── batch_processing.py    # 배치 처리 API 예제
```

---

**Phase 2 성공 기준**: FastAPI + Result 패턴 완전 통합 + px 프로젝트 Health Check 리팩토링 완료

*이 문서는 구현 진행 상황에 따라 업데이트됩니다.*