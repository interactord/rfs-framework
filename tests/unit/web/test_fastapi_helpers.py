"""
RFS Framework FastAPI 헬퍼 단위 테스트

AsyncResult FastAPI 통합 헬퍼의 모든 기능을 포괄적으로 테스트합니다.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch

# FastAPI 의존성이 없는 환경에서도 테스트할 수 있도록 처리
try:
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    HTTPException = None
    JSONResponse = None
    FASTAPI_AVAILABLE = False

from rfs.async_pipeline import AsyncResult
from rfs.core.result import Success, Failure

# FastAPI가 있는 경우에만 헬퍼 임포트
if FASTAPI_AVAILABLE:
    from rfs.web.fastapi_helpers import (
        async_result_to_response,
        async_result_to_paginated_response,
        AsyncResultRouter,
        create_async_result_router,
        AsyncResultEndpoint,
        create_error_mapper,
        batch_async_results_to_response,
        AsyncResultHTTPError
    )


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestAsyncResultToResponse:
    """async_result_to_response 함수 테스트"""
    
    @pytest.mark.asyncio
    async def test_success_response(self):
        """성공 응답 변환 테스트"""
        # Given: 성공하는 AsyncResult
        test_data = {"user_id": 123, "name": "test_user"}
        async_result = AsyncResult.from_value(test_data)
        
        # When: 응답으로 변환
        response = await async_result_to_response(async_result)
        
        # Then: 성공 응답 확인
        assert isinstance(response, JSONResponse)
        assert response.status_code == 200
        assert response.body.decode() == '{"user_id":123,"name":"test_user"}'
    
    @pytest.mark.asyncio
    async def test_success_response_with_custom_status(self):
        """커스텀 상태 코드로 성공 응답 테스트"""
        # Given
        async_result = AsyncResult.from_value("created")
        
        # When
        response = await async_result_to_response(
            async_result, 
            success_status=201
        )
        
        # Then
        assert response.status_code == 201
        assert '"created"' in response.body.decode()
    
    @pytest.mark.asyncio
    async def test_success_response_with_headers(self):
        """성공 헤더 포함 응답 테스트"""
        # Given
        async_result = AsyncResult.from_value("data")
        headers = {"X-Custom-Header": "custom_value"}
        
        # When
        response = await async_result_to_response(
            async_result,
            success_headers=headers
        )
        
        # Then
        assert response.headers["X-Custom-Header"] == "custom_value"
    
    @pytest.mark.asyncio
    async def test_success_response_with_metadata_extractor(self):
        """메타데이터 추출기가 있는 성공 응답 테스트"""
        # Given
        test_data = {"items": [1, 2, 3]}
        async_result = AsyncResult.from_value(test_data)
        
        def metadata_extractor(value):
            return {"count": len(value["items"])}
        
        # When
        response = await async_result_to_response(
            async_result,
            metadata_extractor=metadata_extractor
        )
        
        # Then
        response_data = response.body.decode()
        assert '"data":{"items":[1,2,3]}' in response_data
        assert '"metadata":{"count":3}' in response_data
    
    @pytest.mark.asyncio
    async def test_failure_response_with_error_mapper(self):
        """에러 매핑을 통한 실패 응답 테스트"""
        # Given
        async_result = AsyncResult.from_error("User not found")
        
        def error_mapper(error):
            return HTTPException(status_code=404, detail=str(error))
        
        # When & Then
        with pytest.raises(HTTPException) as exc_info:
            await async_result_to_response(async_result, error_mapper=error_mapper)
        
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "User not found"
    
    @pytest.mark.asyncio
    async def test_failure_response_default_error_handling(self):
        """기본 에러 처리 테스트"""
        # Given
        async_result = AsyncResult.from_error(ValueError("Invalid input"))
        
        # When & Then
        with pytest.raises(AsyncResultHTTPError) as exc_info:
            await async_result_to_response(async_result)
        
        assert exc_info.value.status_code == 400  # ValueError -> 400
        assert "Invalid input" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_failure_response_various_error_types(self):
        """다양한 에러 타입별 상태 코드 테스트"""
        test_cases = [
            (ValueError("Bad value"), 400),
            (PermissionError("Access denied"), 403),
            (FileNotFoundError("Not found"), 404),
            (TimeoutError("Timeout"), 408),
            (RuntimeError("Runtime error"), 500),
        ]
        
        for error, expected_status in test_cases:
            async_result = AsyncResult.from_error(error)
            
            with pytest.raises(AsyncResultHTTPError) as exc_info:
                await async_result_to_response(async_result)
            
            assert exc_info.value.status_code == expected_status
    
    @pytest.mark.asyncio
    async def test_metadata_extractor_error_handling(self):
        """메타데이터 추출기 에러 처리 테스트"""
        # Given
        async_result = AsyncResult.from_value("data")
        
        def failing_extractor(value):
            raise Exception("Extractor failed")
        
        # When: 메타데이터 추출 실패해도 응답은 성공해야 함
        response = await async_result_to_response(
            async_result,
            metadata_extractor=failing_extractor
        )
        
        # Then
        assert response.status_code == 200
        assert '"data"' in response.body.decode()
    
    @pytest.mark.asyncio
    async def test_error_mapper_exception_handling(self):
        """에러 매핑 함수 자체 에러 처리 테스트"""
        # Given
        async_result = AsyncResult.from_error("original error")
        
        def failing_mapper(error):
            raise Exception("Mapper failed")
        
        # When & Then
        with pytest.raises(HTTPException) as exc_info:
            await async_result_to_response(async_result, error_mapper=failing_mapper)
        
        assert exc_info.value.status_code == 500
        assert "에러 처리 중 문제가 발생했습니다" in exc_info.value.detail


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestAsyncResultToPaginatedResponse:
    """async_result_to_paginated_response 함수 테스트"""
    
    @pytest.mark.asyncio
    async def test_paginated_response_with_list(self):
        """리스트 데이터의 페이지네이션 응답 테스트"""
        # Given
        test_data = [1, 2, 3, 4, 5]
        async_result = AsyncResult.from_value(test_data)
        
        # When
        response = await async_result_to_paginated_response(
            async_result,
            page=1,
            page_size=2,
            total_count=10
        )
        
        # Then
        response_data = response.body.decode()
        assert '"data":[1,2,3,4,5]' in response_data
        assert '"pagination"' in response_data
        assert '"page":1' in response_data
        assert '"page_size":2' in response_data
        assert '"total_count":10' in response_data
        assert '"total_pages":5' in response_data
    
    @pytest.mark.asyncio
    async def test_paginated_response_auto_count(self):
        """자동 카운트 계산 테스트"""
        # Given
        test_data = [1, 2, 3]
        async_result = AsyncResult.from_value(test_data)
        
        # When: total_count를 지정하지 않음
        response = await async_result_to_paginated_response(
            async_result,
            page=1,
            page_size=2
        )
        
        # Then: 자동으로 길이를 계산해야 함
        response_data = response.body.decode()
        assert '"total_count":3' in response_data
        assert '"total_pages":2' in response_data
    
    @pytest.mark.asyncio
    async def test_paginated_response_has_next_prev(self):
        """다음/이전 페이지 플래그 테스트"""
        test_cases = [
            (1, 3, 10, False, True),   # 첫 페이지: prev=False, next=True
            (2, 3, 10, True, True),    # 중간 페이지: prev=True, next=True
            (4, 3, 10, True, False),   # 마지막 페이지: prev=True, next=False
        ]
        
        for page, page_size, total_count, expected_has_prev, expected_has_next in test_cases:
            # Given
            async_result = AsyncResult.from_value([])
            
            # When
            response = await async_result_to_paginated_response(
                async_result,
                page=page,
                page_size=page_size,
                total_count=total_count
            )
            
            # Then
            response_data = response.body.decode()
            assert f'"has_prev":{str(expected_has_prev).lower()}' in response_data
            assert f'"has_next":{str(expected_has_next).lower()}' in response_data


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestAsyncResultRouter:
    """AsyncResultRouter 클래스 테스트"""
    
    def test_router_creation(self):
        """라우터 생성 테스트"""
        # Given & When
        router = create_async_result_router(
            prefix="/api/v1",
            tags=["test"],
            include_request_id=True
        )
        
        # Then
        assert isinstance(router, AsyncResultRouter)
        assert router.prefix == "/api/v1"
        assert "test" in router.tags
        assert router.auto_convert_responses is True


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestErrorMapper:
    """create_error_mapper 함수 테스트"""
    
    def test_error_mapper_creation(self):
        """에러 매퍼 생성 테스트"""
        # Given
        error_map = {
            ValueError: 400,
            PermissionError: 403,
            FileNotFoundError: 404,
        }
        
        # When
        mapper = create_error_mapper(error_map)
        
        # Then
        assert callable(mapper)
    
    def test_error_mapper_with_mapped_error(self):
        """매핑된 에러 처리 테스트"""
        # Given
        error_map = {ValueError: 400}
        mapper = create_error_mapper(error_map)
        test_error = ValueError("Test error")
        
        # When
        http_exception = mapper(test_error)
        
        # Then
        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == 400
        assert "Test error" in str(http_exception.detail)
    
    def test_error_mapper_with_unmapped_error(self):
        """매핑되지 않은 에러 처리 테스트"""
        # Given
        error_map = {ValueError: 400}
        mapper = create_error_mapper(error_map, default_status=500)
        test_error = RuntimeError("Runtime error")
        
        # When
        http_exception = mapper(test_error)
        
        # Then
        assert http_exception.status_code == 500
        assert "Runtime error" in str(http_exception.detail)
    
    def test_error_mapper_without_details(self):
        """세부사항 없는 에러 매퍼 테스트"""
        # Given
        error_map = {ValueError: 400}
        mapper = create_error_mapper(error_map, include_error_details=False)
        test_error = ValueError("Test error")
        
        # When
        http_exception = mapper(test_error)
        
        # Then
        assert http_exception.detail == "Test error"  # 문자열만 반환


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestBatchAsyncResults:
    """batch_async_results_to_response 함수 테스트"""
    
    @pytest.mark.asyncio
    async def test_batch_all_success(self):
        """모든 AsyncResult가 성공하는 경우 테스트"""
        # Given
        async_results = [
            AsyncResult.from_value(f"data_{i}")
            for i in range(3)
        ]
        
        # When
        response = await batch_async_results_to_response(async_results)
        
        # Then
        assert response.status_code == 200
        response_data = response.body.decode()
        assert '"successful":3' in response_data
        assert '"failed":0' in response_data
    
    @pytest.mark.asyncio
    async def test_batch_all_failure(self):
        """모든 AsyncResult가 실패하는 경우 테스트"""
        # Given
        async_results = [
            AsyncResult.from_error(f"error_{i}")
            for i in range(3)
        ]
        
        # When
        response = await batch_async_results_to_response(async_results)
        
        # Then
        assert response.status_code == 500  # 모든 요청 실패
        response_data = response.body.decode()
        assert '"successful":0' in response_data
        assert '"failed":3' in response_data
    
    @pytest.mark.asyncio
    async def test_batch_mixed_results(self):
        """성공과 실패가 섞인 경우 테스트"""
        # Given
        async_results = [
            AsyncResult.from_value("success_1"),
            AsyncResult.from_error("error_1"),
            AsyncResult.from_value("success_2"),
        ]
        
        # When
        response = await batch_async_results_to_response(async_results)
        
        # Then
        assert response.status_code == 207  # 부분적 성공
        response_data = response.body.decode()
        assert '"successful":2' in response_data
        assert '"failed":1' in response_data
    
    @pytest.mark.asyncio
    async def test_batch_concurrency_control(self):
        """동시성 제어 테스트"""
        # Given: 지연된 AsyncResult들
        async def delayed_operation(delay):
            await asyncio.sleep(delay)
            return f"result_after_{delay}"
        
        async_results = [
            AsyncResult.from_async(lambda d=i*0.1: delayed_operation(d))
            for i in range(5)
        ]
        
        # When: 낮은 동시성으로 실행
        start_time = asyncio.get_event_loop().time()
        response = await batch_async_results_to_response(
            async_results, 
            max_concurrency=2
        )
        end_time = asyncio.get_event_loop().time()
        
        # Then: 동시성 제어로 인한 실행 시간 확인
        execution_time = end_time - start_time
        assert execution_time > 0.2  # 최소한의 지연은 있어야 함
        assert response.status_code == 200


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestAsyncResultHTTPError:
    """AsyncResultHTTPError 클래스 테스트"""
    
    def test_error_creation(self):
        """에러 객체 생성 테스트"""
        # Given
        original_error = ValueError("Original error")
        
        # When
        http_error = AsyncResultHTTPError(
            status_code=400,
            detail="Bad request",
            original_error=original_error
        )
        
        # Then
        assert http_error.status_code == 400
        assert http_error.detail == "Bad request"
        assert http_error.original_error == original_error
    
    def test_error_inheritance(self):
        """HTTPException 상속 확인"""
        # Given & When
        http_error = AsyncResultHTTPError(500, "Internal error")
        
        # Then
        assert isinstance(http_error, HTTPException)


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestIntegrationScenarios:
    """통합 시나리오 테스트"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_success_flow(self):
        """전체 성공 플로우 테스트"""
        # Given: 복잡한 데이터 처리 시뮬레이션
        async def complex_operation():
            await asyncio.sleep(0.01)  # 네트워크 지연 시뮬레이션
            return {
                "user_id": 123,
                "profile": {
                    "name": "Test User",
                    "email": "test@example.com"
                },
                "settings": {
                    "theme": "dark",
                    "notifications": True
                }
            }
        
        async_result = AsyncResult.from_async(complex_operation)
        
        # When: 메타데이터 추출기와 함께 변환
        def extract_metadata(data):
            return {
                "user_id": data["user_id"],
                "profile_complete": bool(data["profile"]["name"] and data["profile"]["email"]),
                "theme": data["settings"]["theme"]
            }
        
        response = await async_result_to_response(
            async_result,
            success_status=200,
            success_headers={"X-API-Version": "1.0"},
            metadata_extractor=extract_metadata
        )
        
        # Then: 전체 응답 구조 검증
        assert response.status_code == 200
        assert response.headers["X-API-Version"] == "1.0"
        
        response_body = response.body.decode()
        assert '"user_id":123' in response_body
        assert '"data"' in response_body
        assert '"metadata"' in response_body
        assert '"profile_complete":true' in response_body
    
    @pytest.mark.asyncio
    async def test_end_to_end_error_flow(self):
        """전체 에러 플로우 테스트"""
        # Given: 체인된 에러 시뮬레이션
        async def failing_operation():
            await asyncio.sleep(0.01)
            raise PermissionError("사용자 권한이 없습니다")
        
        async_result = AsyncResult.from_async(failing_operation)
        
        # When: 커스텀 에러 매핑 사용
        error_mapper = create_error_mapper({
            PermissionError: 403,
            ValueError: 400,
            FileNotFoundError: 404,
        }, include_error_details=True)
        
        # Then: 적절한 HTTP 에러 발생 확인
        with pytest.raises(HTTPException) as exc_info:
            await async_result_to_response(async_result, error_mapper=error_mapper)
        
        assert exc_info.value.status_code == 403
        assert "사용자 권한이 없습니다" in str(exc_info.value.detail)


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestEdgeCases:
    """엣지 케이스 테스트"""
    
    @pytest.mark.asyncio
    async def test_empty_data_response(self):
        """빈 데이터 응답 테스트"""
        test_cases = [
            None,
            "",
            [],
            {},
            0,
            False,
        ]
        
        for empty_data in test_cases:
            async_result = AsyncResult.from_value(empty_data)
            response = await async_result_to_response(async_result)
            
            assert response.status_code == 200
            # 모든 값이 JSON으로 직렬화 가능해야 함
            response_body = response.body.decode()
            assert len(response_body) > 0  # 빈 응답이 아니어야 함
    
    @pytest.mark.asyncio
    async def test_large_data_response(self):
        """큰 데이터 응답 테스트"""
        # Given: 큰 데이터 생성
        large_data = {
            "items": [{"id": i, "data": f"item_{i}" * 100} for i in range(1000)]
        }
        async_result = AsyncResult.from_value(large_data)
        
        # When
        response = await async_result_to_response(async_result)
        
        # Then: 큰 데이터도 처리 가능해야 함
        assert response.status_code == 200
        assert len(response.body) > 10000  # 상당한 크기의 응답
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """동시 요청 처리 테스트"""
        # Given: 여러 AsyncResult 동시 처리
        async def simulate_request(request_id):
            await asyncio.sleep(0.01)  # 약간의 지연
            return {"request_id": request_id, "result": f"processed_{request_id}"}
        
        async_results = [
            AsyncResult.from_async(lambda rid=i: simulate_request(rid))
            for i in range(10)
        ]
        
        # When: 모든 요청 동시 처리
        responses = await asyncio.gather(*[
            async_result_to_response(ar) for ar in async_results
        ])
        
        # Then: 모든 응답이 성공해야 함
        assert len(responses) == 10
        for response in responses:
            assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_timeout_behavior(self):
        """타임아웃 동작 테스트"""
        # Given: 긴 시간이 걸리는 작업
        async def slow_operation():
            await asyncio.sleep(2.0)
            return "slow_result"
        
        async_result = AsyncResult.from_async(slow_operation)
        
        # When: 짧은 타임아웃으로 처리 시도
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                async_result_to_response(async_result),
                timeout=0.1
            )


# === 픽스처 및 헬퍼 함수 ===

@pytest.fixture
def sample_user_data():
    """테스트용 사용자 데이터"""
    return {
        "user_id": 123,
        "name": "Test User",
        "email": "test@example.com",
        "active": True,
        "created_at": "2024-01-01T00:00:00Z"
    }


@pytest.fixture
def sample_error_mapper():
    """테스트용 에러 매퍼"""
    return create_error_mapper({
        ValueError: 400,
        PermissionError: 403,
        FileNotFoundError: 404,
        TimeoutError: 408,
    })


@pytest.fixture
async def sample_async_results(sample_user_data):
    """테스트용 AsyncResult 샘플들"""
    return {
        "success": AsyncResult.from_value(sample_user_data),
        "failure": AsyncResult.from_error("Test error"),
        "delayed_success": AsyncResult.from_async(
            lambda: asyncio.sleep(0.1) or sample_user_data
        ),
        "delayed_failure": AsyncResult.from_async(
            lambda: asyncio.sleep(0.1) or (_ for _ in ()).throw(ValueError("Delayed error"))
        ),
    }


# === 실행 시 모듈 검증 ===

if __name__ == "__main__":
    if FASTAPI_AVAILABLE:
        print("✅ FastAPI 헬퍼 테스트 모듈 로드 완료")
        print("pytest tests/unit/web/test_fastapi_helpers.py 실행하여 테스트")
    else:
        print("⚠️ FastAPI가 설치되지 않아 테스트를 건너뜁니다")
        print("pip install fastapi 후 다시 실행해주세요")