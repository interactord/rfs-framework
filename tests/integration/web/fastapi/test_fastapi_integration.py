"""
FastAPI 통합 테스트

Phase 2에서 구현한 모든 FastAPI 통합 기능들을 
종합적으로 테스트합니다.
"""

import pytest
import asyncio
from typing import List
from unittest.mock import Mock, AsyncMock

from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

# Phase 1 구현체들
from rfs.core.result import Result, Success, Failure
from rfs.reactive.mono_result import MonoResult
from rfs.reactive.flux_result import FluxResult

# Phase 2 구현체들
from rfs.web.fastapi.errors import APIError, ErrorCode
from rfs.web.fastapi.types import FastAPIResult, FastAPIMonoResult, FastAPIFluxResult
from rfs.web.fastapi.response_helpers import handle_result, handle_flux_result
from rfs.web.fastapi.dependencies import (
    ResultDependency, result_dependency, register_service, inject_result_service
)
from rfs.web.fastapi.middleware import (
    ResultLoggingMiddleware, ExceptionToResultMiddleware, PerformanceMetricsMiddleware,
    setup_result_middleware
)


# 테스트용 모델들
class User(BaseModel):
    id: str
    name: str
    email: str

class UserCreateRequest(BaseModel):
    name: str
    email: str

class UserService:
    """테스트용 사용자 서비스"""
    
    def __init__(self):
        self.users = {
            "user1": User(id="user1", name="김철수", email="kim@test.com"),
            "user2": User(id="user2", name="이영희", email="lee@test.com")
        }
    
    async def get_user(self, user_id: str) -> Result[User, APIError]:
        """사용자 조회"""
        if user_id in self.users:
            return Success(self.users[user_id])
        return Failure(APIError.not_found("사용자", user_id))
    
    async def create_user(self, request: UserCreateRequest) -> Result[User, APIError]:
        """사용자 생성"""
        # 이메일 중복 검사
        for user in self.users.values():
            if user.email == request.email:
                return Failure(APIError.conflict("사용자", "이메일이 이미 존재합니다"))
        
        # 새 사용자 생성
        user_id = f"user{len(self.users) + 1}"
        new_user = User(id=user_id, name=request.name, email=request.email)
        self.users[user_id] = new_user
        
        return Success(new_user)
    
    async def get_users_batch(self, user_ids: List[str]) -> FluxResult[User, APIError]:
        """사용자 배치 조회"""
        results = []
        for user_id in user_ids:
            if user_id in self.users:
                results.append(Success(self.users[user_id]))
            else:
                results.append(Failure(APIError.not_found("사용자", user_id)))
        
        return FluxResult.from_results(results)


@pytest.fixture
def user_service():
    """사용자 서비스 픽스처"""
    return UserService()


@pytest.fixture
def app_with_middleware():
    """미들웨어가 설정된 FastAPI 앱 픽스처"""
    app = FastAPI()
    
    # 미들웨어 설정
    setup_result_middleware(
        app,
        enable_logging=True,
        enable_exception_handling=True,
        enable_metrics=True,
        logging_config={"exclude_paths": ["/health"]},
        exception_config={"debug": True}
    )
    
    return app


@pytest.fixture
def client_with_middleware(app_with_middleware):
    """미들웨어 앱용 테스트 클라이언트"""
    return TestClient(app_with_middleware)


class TestResultDecorators:
    """Result 패턴 데코레이터 테스트"""
    
    def test_handle_result_success(self, user_service):
        """@handle_result 성공 케이스"""
        app = FastAPI()
        
        @app.get("/users/{user_id}")
        @handle_result
        async def get_user(user_id: str) -> Result[User, APIError]:
            return await user_service.get_user(user_id)
        
        with TestClient(app) as client:
            response = client.get("/users/user1")
            
            assert response.status_code == 200
            assert "X-Processing-Time-MS" in response.headers
            
            data = response.json()
            assert data["id"] == "user1"
            assert data["name"] == "김철수"
    
    def test_handle_result_failure(self, user_service):
        """@handle_result 실패 케이스"""
        app = FastAPI()
        
        @app.get("/users/{user_id}")
        @handle_result
        async def get_user(user_id: str) -> Result[User, APIError]:
            return await user_service.get_user(user_id)
        
        with TestClient(app) as client:
            response = client.get("/users/nonexistent")
            
            assert response.status_code == 404
            assert "X-Processing-Time-MS" in response.headers
            
            data = response.json()
            assert data["code"] == "NOT_FOUND"
            assert "사용자을(를) 찾을 수 없습니다" in data["message"]
    
    def test_handle_mono_result(self, user_service):
        """@handle_result with MonoResult"""
        app = FastAPI()
        
        @app.get("/users/{user_id}/mono")
        @handle_result
        async def get_user_mono(user_id: str) -> MonoResult[User, APIError]:
            async def fetch_user():
                return await user_service.get_user(user_id)
            return MonoResult(fetch_user)
        
        with TestClient(app) as client:
            response = client.get("/users/user1/mono")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "user1"
    
    def test_handle_flux_result(self, user_service):
        """@handle_flux_result 테스트"""
        app = FastAPI()
        
        @app.post("/users/batch")
        @handle_flux_result(partial_success=True, include_errors=True)
        async def get_users_batch(user_ids: List[str]) -> FluxResult[User, APIError]:
            return await user_service.get_users_batch(user_ids)
        
        with TestClient(app) as client:
            response = client.post("/users/batch", json=["user1", "nonexistent", "user2"])
            
            assert response.status_code == 207  # Multi-Status (부분 성공)
            
            data = response.json()
            assert data["success"] is True
            assert data["summary"]["total"] == 3
            assert data["summary"]["successful"] == 2
            assert data["summary"]["failed"] == 1
            assert len(data["results"]) == 2  # 성공한 결과들
            assert len(data["errors"]) == 1    # 실패한 결과들


class TestDependencyInjection:
    """의존성 주입 테스트"""
    
    def test_result_dependency_success(self, user_service):
        """ResultDependency 성공 케이스"""
        app = FastAPI()
        
        # 의존성 생성
        user_service_dep = result_dependency(lambda: user_service)
        
        @app.get("/users/{user_id}")
        @handle_result
        async def get_user(
            user_id: str,
            service: UserService = Depends(user_service_dep)
        ) -> Result[User, APIError]:
            return await service.get_user(user_id)
        
        with TestClient(app) as client:
            response = client.get("/users/user1")
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "김철수"
    
    def test_result_dependency_failure(self):
        """ResultDependency 실패 케이스"""
        app = FastAPI()
        
        # 실패하는 의존성 팩토리
        def failing_factory():
            raise Exception("서비스 생성 실패")
        
        failing_dep = result_dependency(failing_factory)
        
        @app.get("/test")
        async def test_endpoint(service = Depends(failing_dep)):
            return {"status": "ok"}
        
        with TestClient(app) as client:
            response = client.get("/test")
            
            assert response.status_code == 500
            data = response.json()
            assert "DEPENDENCY_CREATION_FAILED" in data["code"] or "INTERNAL_SERVER_ERROR" in data["code"]
    
    def test_service_registry(self, user_service):
        """서비스 레지스트리 테스트"""
        app = FastAPI()
        
        # 서비스 등록
        register_service("user_service", lambda: user_service)
        
        @app.get("/users/{user_id}")
        @handle_result
        @inject_result_service("user_service")
        async def get_user(user_id: str, service: UserService) -> Result[User, APIError]:
            return await service.get_user(user_id)
        
        with TestClient(app) as client:
            response = client.get("/users/user1")
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "김철수"


class TestMiddleware:
    """미들웨어 테스트"""
    
    def test_exception_to_result_middleware(self, app_with_middleware):
        """예외 → Result 변환 미들웨어 테스트"""
        @app_with_middleware.get("/error")
        async def error_endpoint():
            raise ValueError("테스트 예외")
        
        client = TestClient(app_with_middleware)
        response = client.get("/error")
        
        assert response.status_code == 500
        data = response.json()
        assert data["code"] == "INTERNAL_SERVER_ERROR"
        assert "테스트 예외" in data["message"]
        assert "timestamp" in data
        assert "path" in data
    
    def test_logging_middleware_headers(self, app_with_middleware):
        """로깅 미들웨어 헤더 추가 테스트"""
        @app_with_middleware.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app_with_middleware)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert "X-Processing-Time-MS" in response.headers
    
    def test_performance_metrics_middleware(self, app_with_middleware):
        """성능 메트릭 미들웨어 테스트"""
        @app_with_middleware.get("/slow")
        async def slow_endpoint():
            await asyncio.sleep(0.1)  # 인위적 지연
            return {"status": "ok"}
        
        client = TestClient(app_with_middleware)
        response = client.get("/slow")
        
        assert response.status_code == 200
        processing_time = int(response.headers["X-Processing-Time-MS"])
        assert processing_time >= 100  # 최소 100ms


class TestEndToEndIntegration:
    """End-to-End 통합 테스트"""
    
    def test_complete_workflow(self, user_service):
        """전체 워크플로우 통합 테스트"""
        app = FastAPI()
        
        # 미들웨어 설정
        setup_result_middleware(app, enable_logging=False)  # 테스트에서는 로깅 최소화
        
        # 서비스 등록
        register_service("user_service", lambda: user_service)
        
        # GET 엔드포인트
        @app.get("/users/{user_id}")
        @handle_result
        @inject_result_service("user_service")
        async def get_user(user_id: str, service: UserService) -> Result[User, APIError]:
            return await service.get_user(user_id)
        
        # POST 엔드포인트
        @app.post("/users")
        @handle_result
        @inject_result_service("user_service")
        async def create_user(
            request: UserCreateRequest, 
            service: UserService
        ) -> Result[User, APIError]:
            return await service.create_user(request)
        
        # 배치 엔드포인트
        @app.post("/users/batch")
        @handle_flux_result(partial_success=True, include_errors=True)
        @inject_result_service("user_service")
        async def get_users_batch(
            user_ids: List[str], 
            service: UserService
        ) -> FluxResult[User, APIError]:
            return await service.get_users_batch(user_ids)
        
        with TestClient(app) as client:
            # 1. 사용자 조회 (성공)
            response = client.get("/users/user1")
            assert response.status_code == 200
            assert response.json()["name"] == "김철수"
            
            # 2. 사용자 조회 (실패)
            response = client.get("/users/nonexistent")
            assert response.status_code == 404
            
            # 3. 사용자 생성 (성공)
            response = client.post("/users", json={
                "name": "박민수",
                "email": "park@test.com"
            })
            assert response.status_code == 200
            assert response.json()["name"] == "박민수"
            
            # 4. 사용자 생성 (실패 - 중복 이메일)
            response = client.post("/users", json={
                "name": "김철수2",
                "email": "kim@test.com"  # 이미 존재하는 이메일
            })
            assert response.status_code == 409
            
            # 5. 배치 조회 (부분 성공)
            response = client.post("/users/batch", json=["user1", "nonexistent", "user2"])
            assert response.status_code == 207
            
            data = response.json()
            assert data["summary"]["successful"] == 2
            assert data["summary"]["failed"] == 1
    
    def test_error_handling_consistency(self, user_service):
        """에러 처리 일관성 테스트"""
        app = FastAPI()
        setup_result_middleware(app, enable_logging=False)
        
        # Result 반환 엔드포인트
        @app.get("/result-error")
        @handle_result
        async def result_error() -> Result[dict, APIError]:
            return Failure(APIError.not_found("리소스", "test"))
        
        # 예외 발생 엔드포인트  
        @app.get("/exception-error")
        async def exception_error():
            raise ValueError("테스트 예외")
        
        # APIError 발생 엔드포인트
        @app.get("/api-error")
        async def api_error():
            raise APIError.forbidden("리소스", "접근")
        
        with TestClient(app) as client:
            # 1. Result 에러 - 404
            response1 = client.get("/result-error")
            assert response1.status_code == 404
            data1 = response1.json()
            
            # 2. 일반 예외 - 500으로 변환
            response2 = client.get("/exception-error")
            assert response2.status_code == 500
            data2 = response2.json()
            
            # 3. APIError 예외 - 403
            response3 = client.get("/api-error")
            assert response3.status_code == 403
            data3 = response3.json()
            
            # 모든 에러 응답이 동일한 구조를 가져야 함
            for data in [data1, data2, data3]:
                assert "code" in data
                assert "message" in data
                assert "details" in data
                assert "timestamp" in data


class TestTypeSystem:
    """타입 시스템 테스트"""
    
    def test_fastapi_result_types(self, user_service):
        """FastAPI 타입 별칭 테스트"""
        app = FastAPI()
        
        @app.get("/result")
        @handle_result
        async def test_result() -> FastAPIResult[dict]:
            return Success({"status": "ok"})
        
        @app.get("/mono-result")
        @handle_result
        async def test_mono_result() -> FastAPIMonoResult[dict]:
            async def get_data():
                return Success({"status": "ok"})
            return MonoResult(get_data)
        
        @app.post("/flux-result")
        @handle_flux_result()
        async def test_flux_result() -> FastAPIFluxResult[dict]:
            results = [Success({"id": i}) for i in range(3)]
            return FluxResult.from_results(results)
        
        with TestClient(app) as client:
            # Result 테스트
            response1 = client.get("/result")
            assert response1.status_code == 200
            
            # MonoResult 테스트
            response2 = client.get("/mono-result")
            assert response2.status_code == 200
            
            # FluxResult 테스트
            response3 = client.post("/flux-result")
            assert response3.status_code == 200
            assert len(response3.json()["results"]) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])