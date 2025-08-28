"""
RFS Framework AsyncResult 웹 통합 테스트

AsyncResult와 FastAPI의 완전한 통합을 검증하는 종단 간 테스트입니다.
실제 웹 서버 환경에서 모든 기능이 올바르게 작동하는지 확인합니다.
"""

import asyncio
import json
import time
from typing import Dict, Any
import pytest
from unittest.mock import AsyncMock, Mock, patch

# FastAPI 의존성 처리
try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.testclient import TestClient
    from fastapi.responses import JSONResponse
    import httpx
    FASTAPI_AVAILABLE = True
except ImportError:
    FastAPI = None
    TestClient = None
    JSONResponse = None
    HTTPException = None
    httpx = None
    FASTAPI_AVAILABLE = False

from rfs.async_pipeline import AsyncResult
from rfs.core.result import Success, Failure
from rfs.testing.async_result_testing import AsyncResultTestUtils, AsyncResultMockBuilder

# 통합 대상 모듈들 임포트 (FastAPI가 있는 경우만)
if FASTAPI_AVAILABLE:
    from rfs.web.fastapi_helpers import (
        async_result_to_response,
        async_result_to_paginated_response,
        create_async_result_router,
        create_error_mapper,
        batch_async_results_to_response
    )
    from rfs.logging.async_logging import (
        get_async_result_logger,
        configure_async_result_logging,
        log_async_chain
    )


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestAsyncResultFastAPIIntegration:
    """AsyncResult와 FastAPI 통합 테스트"""
    
    @pytest.fixture
    def app(self):
        """테스트용 FastAPI 앱"""
        app = FastAPI(title="AsyncResult Integration Test")
        
        # 기본 라우터 생성
        router = create_async_result_router(prefix="/api/v1", tags=["test"])
        
        @router.get("/users/{user_id}")
        async def get_user(user_id: str):
            """사용자 조회 엔드포인트"""
            async def fetch_user_data():
                await asyncio.sleep(0.01)  # DB 조회 시뮬레이션
                
                if user_id == "404":
                    raise ValueError("User not found")
                elif user_id == "500":
                    raise RuntimeError("Internal server error")
                
                return {
                    "user_id": user_id,
                    "name": f"User {user_id}",
                    "email": f"user{user_id}@example.com",
                    "active": True
                }
            
            user_result = AsyncResult.from_async(fetch_user_data)
            
            error_mapper = create_error_mapper({
                ValueError: 404,
                RuntimeError: 500,
                PermissionError: 403,
            })
            
            return await async_result_to_response(
                user_result,
                error_mapper=error_mapper
            )
        
        @router.get("/users")
        async def list_users(page: int = 1, page_size: int = 10):
            """사용자 목록 조회 (페이지네이션)"""
            async def fetch_users_page():
                await asyncio.sleep(0.02)  # DB 조회 시뮬레이션
                
                # 모의 사용자 데이터 생성
                start = (page - 1) * page_size
                users = [
                    {
                        "user_id": start + i + 1,
                        "name": f"User {start + i + 1}",
                        "email": f"user{start + i + 1}@example.com"
                    }
                    for i in range(page_size)
                ]
                return users
            
            users_result = AsyncResult.from_async(fetch_users_page)
            
            return await async_result_to_paginated_response(
                users_result,
                page=page,
                page_size=page_size,
                total_count=100  # 전체 사용자 수
            )
        
        @router.post("/users")
        async def create_user(user_data: Dict[str, Any]):
            """사용자 생성 엔드포인트"""
            async def create_user_account():
                await asyncio.sleep(0.05)  # 생성 작업 시뮬레이션
                
                # 간단한 검증
                if not user_data.get("name"):
                    raise ValueError("Name is required")
                if not user_data.get("email"):
                    raise ValueError("Email is required")
                
                # 새 사용자 데이터 생성
                new_user = {
                    "user_id": "new_123",
                    "name": user_data["name"],
                    "email": user_data["email"],
                    "active": True,
                    "created_at": "2024-01-01T00:00:00Z"
                }
                return new_user
            
            creation_result = AsyncResult.from_async(create_user_account)
            
            return await async_result_to_response(
                creation_result,
                success_status=201,
                error_mapper=create_error_mapper({ValueError: 400})
            )
        
        @router.get("/batch-test")
        async def batch_operations():
            """배치 연산 테스트 엔드포인트"""
            # 여러 AsyncResult 생성
            async_results = [
                AsyncResult.from_async(lambda i=i: asyncio.sleep(0.01) or f"result_{i}")
                for i in range(5)
            ]
            
            return await batch_async_results_to_response(
                async_results,
                max_concurrency=3
            )
        
        @router.get("/error-test/{error_type}")
        async def error_test(error_type: str):
            """에러 테스트 엔드포인트"""
            async def generate_error():
                await asyncio.sleep(0.01)
                
                error_map = {
                    "value": ValueError("Invalid value"),
                    "permission": PermissionError("Access denied"),
                    "not_found": FileNotFoundError("Resource not found"),
                    "timeout": TimeoutError("Operation timeout"),
                    "runtime": RuntimeError("Runtime error")
                }
                
                if error_type in error_map:
                    raise error_map[error_type]
                else:
                    return {"message": "No error"}
            
            error_result = AsyncResult.from_async(generate_error)
            
            return await async_result_to_response(
                error_result,
                error_mapper=create_error_mapper({
                    ValueError: 400,
                    PermissionError: 403,
                    FileNotFoundError: 404,
                    TimeoutError: 408,
                    RuntimeError: 500,
                })
            )
        
        app.include_router(router)
        return app
    
    @pytest.fixture
    def client(self, app):
        """테스트 클라이언트"""
        return TestClient(app)
    
    def test_get_user_success(self, client):
        """사용자 조회 성공 테스트"""
        # When
        response = client.get("/api/v1/users/123")
        
        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "123"
        assert data["name"] == "User 123"
        assert data["email"] == "user123@example.com"
        assert data["active"] is True
    
    def test_get_user_not_found(self, client):
        """사용자 조회 실패 (404) 테스트"""
        # When
        response = client.get("/api/v1/users/404")
        
        # Then
        assert response.status_code == 404
        data = response.json()
        assert "User not found" in str(data["detail"])
    
    def test_get_user_server_error(self, client):
        """사용자 조회 실패 (500) 테스트"""
        # When
        response = client.get("/api/v1/users/500")
        
        # Then
        assert response.status_code == 500
    
    def test_list_users_pagination(self, client):
        """사용자 목록 페이지네이션 테스트"""
        # When
        response = client.get("/api/v1/users?page=2&page_size=5")
        
        # Then
        assert response.status_code == 200
        data = response.json()
        
        # 사용자 데이터 확인
        assert "data" in data
        assert len(data["data"]) == 5
        
        # 페이지네이션 메타데이터 확인
        assert "metadata" in data
        pagination = data["metadata"]["pagination"]
        assert pagination["page"] == 2
        assert pagination["page_size"] == 5
        assert pagination["total_count"] == 100
        assert pagination["total_pages"] == 20
        assert pagination["has_prev"] is True
        assert pagination["has_next"] is True
    
    def test_list_users_first_page(self, client):
        """첫 페이지 사용자 목록 테스트"""
        # When
        response = client.get("/api/v1/users?page=1&page_size=3")
        
        # Then
        assert response.status_code == 200
        data = response.json()
        pagination = data["metadata"]["pagination"]
        assert pagination["has_prev"] is False
        assert pagination["has_next"] is True
    
    def test_list_users_last_page(self, client):
        """마지막 페이지 사용자 목록 테스트"""
        # When
        response = client.get("/api/v1/users?page=10&page_size=10")
        
        # Then
        assert response.status_code == 200
        data = response.json()
        pagination = data["metadata"]["pagination"]
        assert pagination["has_prev"] is True
        assert pagination["has_next"] is False
    
    def test_create_user_success(self, client):
        """사용자 생성 성공 테스트"""
        # Given
        user_data = {
            "name": "New User",
            "email": "newuser@example.com"
        }
        
        # When
        response = client.post("/api/v1/users", json=user_data)
        
        # Then
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == "new_123"
        assert data["name"] == "New User"
        assert data["email"] == "newuser@example.com"
        assert data["active"] is True
    
    def test_create_user_validation_error(self, client):
        """사용자 생성 검증 에러 테스트"""
        # Given
        invalid_data = {"name": ""}  # 이메일 누락
        
        # When
        response = client.post("/api/v1/users", json=invalid_data)
        
        # Then
        assert response.status_code == 400
        data = response.json()
        assert "Email is required" in str(data["detail"])
    
    def test_batch_operations(self, client):
        """배치 연산 테스트"""
        # When
        response = client.get("/api/v1/batch-test")
        
        # Then
        assert response.status_code == 200
        data = response.json()
        
        assert "successes" in data
        assert "errors" in data
        assert "summary" in data
        
        # 모든 연산이 성공해야 함
        assert data["summary"]["successful"] == 5
        assert data["summary"]["failed"] == 0
        assert len(data["successes"]) == 5
    
    def test_error_mapping(self, client):
        """에러 매핑 테스트"""
        test_cases = [
            ("value", 400),
            ("permission", 403),
            ("not_found", 404),
            ("timeout", 408),
            ("runtime", 500),
        ]
        
        for error_type, expected_status in test_cases:
            # When
            response = client.get(f"/api/v1/error-test/{error_type}")
            
            # Then
            assert response.status_code == expected_status
    
    def test_no_error_case(self, client):
        """에러가 없는 경우 테스트"""
        # When
        response = client.get("/api/v1/error-test/none")
        
        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "No error"


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestAsyncResultLoggingIntegration:
    """AsyncResult 로깅 통합 테스트"""
    
    @pytest.fixture
    def logged_app(self):
        """로깅이 통합된 FastAPI 앱"""
        app = FastAPI(title="Logging Integration Test")
        
        # 로깅 설정
        async_logger = configure_async_result_logging(
            logger_name="test.async_result",
            log_level="INFO",
            enable_json_logging=False
        )
        
        router = create_async_result_router(prefix="/api/v1", tags=["logging"])
        
        @router.get("/logged-operation/{operation_id}")
        async def logged_operation(operation_id: str):
            """로깅이 적용된 연산"""
            # 로그 체인 적용
            logged_fetch = async_logger.log_chain(f"fetch_{operation_id}")
            logged_process = async_logger.log_chain(f"process_{operation_id}")
            
            async def fetch_data():
                await asyncio.sleep(0.01)
                return {"raw_data": f"data_{operation_id}"}
            
            async def process_data(raw_data):
                await asyncio.sleep(0.01)
                return {
                    "processed_data": raw_data["raw_data"].upper(),
                    "timestamp": time.time()
                }
            
            # 체인 실행
            result = await (
                logged_fetch(AsyncResult.from_async(fetch_data))
                .bind_async(lambda data: 
                    logged_process(AsyncResult.from_async(lambda: process_data(data)))
                )
            )
            
            return await async_result_to_response(result)
        
        @router.get("/sensitive-data")
        async def sensitive_data_operation():
            """민감한 데이터 로깅 테스트"""
            logger = log_async_chain("sensitive_operation")
            
            async def fetch_sensitive():
                await asyncio.sleep(0.01)
                return {
                    "user_id": 123,
                    "username": "testuser",
                    "password": "secret123",  # 마스킹되어야 함
                    "api_key": "abc123def456",  # 마스킹되어야 함
                    "email": "test@example.com"
                }
            
            sensitive_result = logger(AsyncResult.from_async(fetch_sensitive))
            
            return await async_result_to_response(sensitive_result)
        
        @router.get("/performance-tracked/{operation_count}")
        async def performance_tracked_operation(operation_count: int):
            """성능 추적 연산"""
            async def multiple_operations():
                results = []
                for i in range(operation_count):
                    logged_op = async_logger.log_chain(f"batch_op_{i}")
                    
                    async def single_op(index=i):
                        await asyncio.sleep(0.01)
                        return f"result_{index}"
                    
                    op_result = await logged_op(
                        AsyncResult.from_async(single_op)
                    ).to_result()
                    
                    if op_result.is_success():
                        results.append(op_result.unwrap())
                
                return results
            
            batch_result = AsyncResult.from_async(multiple_operations)
            response = await async_result_to_response(batch_result)
            
            # 성능 요약 추가
            perf_summary = async_logger.get_performance_summary()
            
            # 응답 헤더에 성능 정보 추가
            if perf_summary:
                response.headers["X-Performance-Summary"] = json.dumps(perf_summary)
            
            return response
        
        app.include_router(router)
        return app, async_logger
    
    @pytest.fixture
    def logged_client(self, logged_app):
        """로깅이 통합된 테스트 클라이언트"""
        app, logger = logged_app
        client = TestClient(app)
        return client, logger
    
    def test_logged_operation_success(self, logged_client):
        """로깅된 연산 성공 테스트"""
        client, logger = logged_client
        
        # When
        response = client.get("/api/v1/logged-operation/test123")
        
        # Then
        assert response.status_code == 200
        data = response.json()
        assert "processed_data" in data
        assert data["processed_data"] == "DATA_TEST123"
        
        # 성능 메트릭 확인
        perf_summary = logger.get_performance_summary()
        assert len(perf_summary) >= 2  # fetch + process 연산
    
    def test_sensitive_data_logging(self, logged_client):
        """민감한 데이터 로깅 테스트"""
        client, logger = logged_client
        
        # When
        response = client.get("/api/v1/sensitive-data")
        
        # Then
        assert response.status_code == 200
        data = response.json()
        
        # 응답에는 민감한 데이터가 포함되어야 함
        assert data["username"] == "testuser"
        assert data["password"] == "secret123"  # 응답 자체는 마스킹되지 않음
        assert data["email"] == "test@example.com"
        
        # 로그에는 마스킹되어 기록됨 (실제 환경에서는 로그 파일 확인 필요)
    
    def test_performance_tracking(self, logged_client):
        """성능 추적 테스트"""
        client, logger = logged_client
        
        # When
        response = client.get("/api/v1/performance-tracked/3")
        
        # Then
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        
        # 성능 헤더 확인
        assert "X-Performance-Summary" in response.headers
        perf_data = json.loads(response.headers["X-Performance-Summary"])
        assert len(perf_data) >= 3  # 3개의 배치 연산


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")  
class TestAsyncResultTestingIntegration:
    """AsyncResult 테스팅 통합 테스트"""
    
    @pytest.fixture
    def testing_app(self):
        """테스팅이 통합된 FastAPI 앱"""
        app = FastAPI(title="Testing Integration")
        
        router = create_async_result_router(prefix="/api/v1", tags=["testing"])
        
        @router.get("/test-endpoint/{scenario}")
        async def test_endpoint(scenario: str):
            """테스트 시나리오별 엔드포인트"""
            if scenario == "success":
                return await async_result_to_response(
                    AsyncResult.from_value({"status": "success"})
                )
            elif scenario == "delayed":
                return await async_result_to_response(
                    AsyncResultMockBuilder.delayed_success_mock("delayed_result", 0.05)
                )
            elif scenario == "intermittent":
                return await async_result_to_response(
                    AsyncResultMockBuilder.intermittent_failure_mock(
                        "intermittent_success", "intermittent_failure", 
                        failure_rate=0.3, seed=42
                    )
                )
            elif scenario == "chain":
                operations = [
                    lambda x: x.upper(),
                    lambda x: f"processed_{x}",
                    lambda x: {"result": x}
                ]
                return await async_result_to_response(
                    AsyncResultMockBuilder.chain_mock(
                        operations, initial_value="test_data"
                    )
                )
            else:
                return await async_result_to_response(
                    AsyncResult.from_error("Unknown scenario")
                )
        
        app.include_router(router)
        return app
    
    @pytest.fixture
    def testing_client(self, testing_app):
        """테스팅 통합 클라이언트"""
        return TestClient(testing_app)
    
    @pytest.mark.asyncio
    async def test_success_scenario_validation(self, testing_client):
        """성공 시나리오 검증 테스트"""
        # When
        response = testing_client.get("/api/v1/test-endpoint/success")
        
        # Then
        assert response.status_code == 200
        
        # AsyncResult 테스트 유틸리티로 검증 (시뮬레이션)
        test_result = AsyncResult.from_value(response.json())
        await AsyncResultTestUtils.assert_success(
            test_result,
            value_matcher=lambda v: v["status"] == "success"
        )
    
    @pytest.mark.asyncio
    async def test_delayed_scenario_timing(self, testing_client):
        """지연된 시나리오 타이밍 테스트"""
        # When
        start_time = time.time()
        response = testing_client.get("/api/v1/test-endpoint/delayed")
        end_time = time.time()
        
        # Then
        assert response.status_code == 200
        execution_time = end_time - start_time
        assert execution_time >= 0.05  # 최소 지연 시간 확인
        
        # AsyncResult로 실행 시간 검증
        async def simulate_response():
            return response.json()
        
        timed_result = AsyncResult.from_async(simulate_response)
        actual_time = await AsyncResultTestUtils.assert_execution_time(
            timed_result, max_seconds=1.0
        )
        assert actual_time < 1.0
    
    def test_intermittent_failure_behavior(self, testing_client):
        """간헐적 실패 동작 테스트"""
        # When: 여러 번 요청하여 간헐적 패턴 확인
        responses = []
        for _ in range(10):
            response = testing_client.get("/api/v1/test-endpoint/intermittent")
            responses.append(response.status_code)
        
        # Then: 성공과 실패가 섞여있어야 함 (시드 고정으로 예측 가능)
        success_count = sum(1 for status in responses if status == 200)
        failure_count = len(responses) - success_count
        
        assert success_count > 0  # 일부 성공
        assert failure_count > 0  # 일부 실패
    
    def test_chain_operation_result(self, testing_client):
        """체인 연산 결과 테스트"""
        # When
        response = testing_client.get("/api/v1/test-endpoint/chain")
        
        # Then
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "processed_TEST_DATA"
    
    def test_error_scenario(self, testing_client):
        """에러 시나리오 테스트"""
        # When
        response = testing_client.get("/api/v1/test-endpoint/unknown")
        
        # Then
        assert response.status_code == 500  # 기본 에러 처리


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestEndToEndWorkflow:
    """전체 워크플로우 종단 간 테스트"""
    
    @pytest.fixture
    def complete_app(self):
        """완전한 통합 앱"""
        app = FastAPI(title="Complete AsyncResult Integration")
        
        # 로깅 설정
        logger = configure_async_result_logging("e2e.test", "INFO")
        
        router = create_async_result_router(prefix="/api/v1", tags=["e2e"])
        
        @router.post("/complete-workflow")
        async def complete_workflow(request_data: Dict[str, Any]):
            """완전한 워크플로우 테스트"""
            # Step 1: 입력 검증
            validation_logger = logger.log_chain("input_validation")
            
            async def validate_input():
                if not request_data.get("user_id"):
                    raise ValueError("user_id is required")
                if not request_data.get("operation"):
                    raise ValueError("operation is required")
                return request_data
            
            # Step 2: 사용자 조회
            user_fetch_logger = logger.log_chain("user_fetch")
            
            async def fetch_user(validated_data):
                user_id = validated_data["user_id"]
                await asyncio.sleep(0.01)  # DB 조회 시뮬레이션
                
                if user_id == "blocked":
                    raise PermissionError("User is blocked")
                
                return {
                    "user_id": user_id,
                    "name": f"User {user_id}",
                    "permissions": ["read", "write"] if user_id != "readonly" else ["read"]
                }
            
            # Step 3: 연산 실행
            operation_logger = logger.log_chain("operation_execution")
            
            async def execute_operation(user_data, operation_type):
                if operation_type == "read":
                    await asyncio.sleep(0.01)
                    return {"data": f"Read data for {user_data['user_id']}"}
                elif operation_type == "write":
                    if "write" not in user_data["permissions"]:
                        raise PermissionError("Write permission denied")
                    await asyncio.sleep(0.02)
                    return {"data": f"Write completed for {user_data['user_id']}"}
                else:
                    raise ValueError("Invalid operation")
            
            # Step 4: 결과 포맷팅
            format_logger = logger.log_chain("result_formatting")
            
            async def format_result(operation_result, user_data):
                await asyncio.sleep(0.005)
                return {
                    "result": operation_result,
                    "user": {
                        "id": user_data["user_id"],
                        "name": user_data["name"]
                    },
                    "timestamp": time.time(),
                    "workflow_id": "wf_" + str(int(time.time()))
                }
            
            # 전체 파이프라인 실행
            try:
                # 검증
                validated = await validation_logger(
                    AsyncResult.from_async(validate_input)
                ).to_result()
                
                if validated.is_failure():
                    return await async_result_to_response(
                        AsyncResult.from_result(validated),
                        error_mapper=create_error_mapper({ValueError: 400})
                    )
                
                # 사용자 조회
                user_data = await user_fetch_logger(
                    AsyncResult.from_async(lambda: fetch_user(validated.unwrap()))
                ).to_result()
                
                if user_data.is_failure():
                    return await async_result_to_response(
                        AsyncResult.from_result(user_data),
                        error_mapper=create_error_mapper({PermissionError: 403})
                    )
                
                # 연산 실행
                operation_result = await operation_logger(
                    AsyncResult.from_async(
                        lambda: execute_operation(
                            user_data.unwrap(), 
                            request_data["operation"]
                        )
                    )
                ).to_result()
                
                if operation_result.is_failure():
                    return await async_result_to_response(
                        AsyncResult.from_result(operation_result),
                        error_mapper=create_error_mapper({
                            ValueError: 400,
                            PermissionError: 403
                        })
                    )
                
                # 결과 포맷팅
                final_result = await format_logger(
                    AsyncResult.from_async(
                        lambda: format_result(
                            operation_result.unwrap(),
                            user_data.unwrap()
                        )
                    )
                ).to_result()
                
                return await async_result_to_response(
                    AsyncResult.from_result(final_result)
                )
                
            except Exception as e:
                # 예상치 못한 에러 처리
                error_result = AsyncResult.from_error(str(e))
                return await async_result_to_response(
                    error_result,
                    error_mapper=create_error_mapper({}, default_status=500)
                )
        
        app.include_router(router)
        return app, logger
    
    @pytest.fixture
    def e2e_client(self, complete_app):
        """종단 간 테스트 클라이언트"""
        app, logger = complete_app
        return TestClient(app), logger
    
    def test_complete_workflow_success(self, e2e_client):
        """완전한 워크플로우 성공 테스트"""
        client, logger = e2e_client
        
        # Given
        request_data = {
            "user_id": "test_user",
            "operation": "read"
        }
        
        # When
        response = client.post("/api/v1/complete-workflow", json=request_data)
        
        # Then
        assert response.status_code == 200
        data = response.json()
        
        assert "result" in data
        assert "user" in data
        assert "timestamp" in data
        assert "workflow_id" in data
        
        assert data["user"]["id"] == "test_user"
        assert data["result"]["data"] == "Read data for test_user"
        
        # 성능 메트릭 확인
        perf_summary = logger.get_performance_summary()
        expected_operations = ["input_validation", "user_fetch", "operation_execution", "result_formatting"]
        
        for op in expected_operations:
            assert op in perf_summary
            assert perf_summary[op]["count"] >= 1
    
    def test_complete_workflow_validation_error(self, e2e_client):
        """워크플로우 검증 에러 테스트"""
        client, logger = e2e_client
        
        # Given: user_id 누락
        request_data = {"operation": "read"}
        
        # When
        response = client.post("/api/v1/complete-workflow", json=request_data)
        
        # Then
        assert response.status_code == 400
        data = response.json()
        assert "user_id is required" in str(data["detail"])
    
    def test_complete_workflow_permission_error(self, e2e_client):
        """워크플로우 권한 에러 테스트"""
        client, logger = e2e_client
        
        # Given: 읽기 전용 사용자가 쓰기 시도
        request_data = {
            "user_id": "readonly",
            "operation": "write"
        }
        
        # When
        response = client.post("/api/v1/complete-workflow", json=request_data)
        
        # Then
        assert response.status_code == 403
        data = response.json()
        assert "Write permission denied" in str(data["detail"])
    
    def test_complete_workflow_blocked_user(self, e2e_client):
        """차단된 사용자 워크플로우 테스트"""
        client, logger = e2e_client
        
        # Given
        request_data = {
            "user_id": "blocked",
            "operation": "read"
        }
        
        # When
        response = client.post("/api/v1/complete-workflow", json=request_data)
        
        # Then
        assert response.status_code == 403
        data = response.json()
        assert "User is blocked" in str(data["detail"])
    
    def test_complete_workflow_invalid_operation(self, e2e_client):
        """잘못된 연산 워크플로우 테스트"""
        client, logger = e2e_client
        
        # Given
        request_data = {
            "user_id": "test_user",
            "operation": "invalid_op"
        }
        
        # When
        response = client.post("/api/v1/complete-workflow", json=request_data)
        
        # Then
        assert response.status_code == 400
        data = response.json()
        assert "Invalid operation" in str(data["detail"])


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestPerformanceIntegration:
    """성능 통합 테스트"""
    
    @pytest.fixture
    def performance_app(self):
        """성능 테스트용 앱"""
        app = FastAPI(title="Performance Test")
        router = create_async_result_router(prefix="/api/v1")
        
        @router.get("/performance-test/{concurrency}/{operations}")
        async def performance_test(concurrency: int, operations: int):
            """성능 테스트 엔드포인트"""
            async def run_concurrent_operations():
                # 동시 AsyncResult 생성
                async_results = [
                    AsyncResult.from_async(lambda i=i: asyncio.sleep(0.001) or f"op_{i}")
                    for i in range(operations)
                ]
                
                # 배치 처리
                return await batch_async_results_to_response(
                    async_results,
                    max_concurrency=concurrency
                )
            
            perf_result = AsyncResult.from_async(run_concurrent_operations)
            return await async_result_to_response(perf_result)
        
        app.include_router(router)
        return app
    
    @pytest.fixture
    def perf_client(self, performance_app):
        """성능 테스트 클라이언트"""
        return TestClient(performance_app)
    
    def test_concurrent_operations_performance(self, perf_client):
        """동시 연산 성능 테스트"""
        # When
        start_time = time.time()
        response = perf_client.get("/api/v1/performance-test/5/20")
        end_time = time.time()
        
        # Then
        assert response.status_code == 200
        execution_time = end_time - start_time
        
        # 동시성 제어로 인한 성능 향상 확인
        # 순차 실행이라면 20 * 0.001 = 0.02초, 
        # 동시성 5라면 대략 20/5 * 0.001 = 0.004초 + 오버헤드
        assert execution_time < 0.1  # 충분한 마진
        
        data = response.json()
        assert data["summary"]["successful"] == 20
        assert data["summary"]["failed"] == 0


# === 테스트 헬퍼 및 픽스처 ===

@pytest.fixture
def mock_database():
    """모의 데이터베이스"""
    return {
        "users": {
            "123": {"name": "Test User", "email": "test@example.com"},
            "456": {"name": "Another User", "email": "another@example.com"}
        }
    }


@pytest.fixture
def integration_test_config():
    """통합 테스트 설정"""
    return {
        "timeout": 5.0,
        "max_retries": 3,
        "log_level": "INFO",
        "performance_threshold": 1.0
    }


# === 실행 시 검증 ===

if __name__ == "__main__":
    if FASTAPI_AVAILABLE:
        print("✅ AsyncResult 웹 통합 테스트 모듈 로드 완료")
        print("pytest tests/integration/test_async_result_web_integration.py 실행하여 테스트")
    else:
        print("⚠️ FastAPI가 설치되지 않아 통합 테스트를 건너뜁니다")
        print("pip install fastapi httpx 후 다시 실행해주세요")