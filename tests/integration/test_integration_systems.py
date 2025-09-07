"""
Integration Systems Tests
"""

import asyncio
import json
from typing import Any, Dict

import pytest

from rfs.core import Failure, Success
from rfs.integration import (
    AuthenticationMethod,
    Backend,
    CacheBackend,
    CacheConfig,
    EvictionPolicy,
    LoadBalanceStrategy,
    RateLimitStrategy,
    RequestContext,
    Route,
    WebhookConfig,
    get_api_gateway,
    get_distributed_cache_manager,
    get_web_integration_manager,
)


@pytest.mark.asyncio
class TestWebIntegration:
    """웹 통합 테스트"""

    async def test_web_integration_manager(self):
        """웹 통합 관리자 테스트"""
        manager = get_web_integration_manager()

        # 관리자 시작
        start_result = await manager.start()
        assert isinstance(start_result, Success)

        # Webhook 추가
        webhook = WebhookConfig(
            id="webhook_1",
            name="Test Webhook",
            url="http://localhost:8080/webhook",
            events=["user.created", "user.updated"],
            secret="test_secret",
        )

        webhook_result = manager.add_webhook(webhook)
        assert isinstance(webhook_result, Success)

        # Webhook 트리거 (실제 전송은 실패할 수 있음)
        trigger_result = await manager.trigger_webhook(
            webhook_id="webhook_1",
            event="user.created",
            data={"user_id": "123", "name": "Test User"},
        )
        # URL이 없으므로 실패 예상

        # WebSocket 연결 (실제 연결은 실패할 수 있음)
        # ws_result = await manager.connect_websocket(
        #     connection_id="ws_1",
        #     url="ws://localhost:8080/ws"
        # )

        # 관리자 중지
        await manager.stop()

    async def test_oauth_integration(self):
        """OAuth 통합 테스트"""
        from rfs.integration import OAuthConfig

        manager = get_web_integration_manager()

        # OAuth 설정 추가
        oauth_config = OAuthConfig(
            client_id="test_client",
            client_secret="test_secret",
            authorization_url="https://oauth.example.com/authorize",
            token_url="https://oauth.example.com/token",
            redirect_uri="http://localhost:8000/callback",
            scopes=["read", "write"],
        )

        oauth_result = manager.add_oauth_config("oauth_1", oauth_config)
        assert isinstance(oauth_result, Success)

        # 인증 URL 생성
        auth_url_result = manager.get_oauth_authorization_url(
            "oauth_1", state="random_state"
        )
        assert isinstance(auth_url_result, Success)

        auth_url = auth_url_result.value
        assert "client_id=test_client" in auth_url
        assert "redirect_uri=" in auth_url


@pytest.mark.asyncio
class TestDistributedCache:
    """분산 캐시 테스트"""

    async def test_cache_manager(self):
        """캐시 관리자 테스트"""
        config = CacheConfig(
            backend=CacheBackend.MEMORY,
            eviction_policy=EvictionPolicy.LRU,
            max_size=100,
            max_memory_mb=10,
            default_ttl=60,
        )

        manager = get_distributed_cache_manager(config)

        # 캐시 관리자 시작
        start_result = await manager.start()
        assert isinstance(start_result, Success)

        # 캐시 저장
        set_result = await manager.set("test_key", {"data": "test_value"})
        assert isinstance(set_result, Success)

        # 캐시 조회
        get_result = await manager.get("test_key")
        assert isinstance(get_result, Success)
        assert get_result.value == {"data": "test_value"}

        # 캐시 통계
        stats = manager.get_statistics()
        assert stats.hits == 1
        assert stats.misses == 0

        # 캐시 삭제
        delete_result = await manager.delete("test_key")
        assert isinstance(delete_result, Success)

        # 삭제 후 조회
        get_result = await manager.get("test_key")
        assert isinstance(get_result, Success)
        assert get_result.value is None

        # 캐시 관리자 중지
        await manager.stop()

    async def test_cache_partitions(self):
        """캐시 파티션 테스트"""
        manager = get_distributed_cache_manager()

        await manager.start()

        # 파티션 생성
        partition_result = manager.create_partition(
            partition_id="user_cache",
            name="User Cache",
            config=CacheConfig(
                backend=CacheBackend.MEMORY,
                eviction_policy=EvictionPolicy.LFU,
                max_size=50,
                max_memory_mb=5,
                default_ttl=300,
            ),
        )
        assert isinstance(partition_result, Success)

        # 파티션에 데이터 저장
        await manager.set(
            "user:123", {"id": "123", "name": "Test User"}, partition_id="user_cache"
        )

        # 파티션에서 데이터 조회
        result = await manager.get("user:123", partition_id="user_cache")
        assert isinstance(result, Success)
        assert result.value["id"] == "123"

        # 파티션 클리어
        clear_result = await manager.clear(partition_id="user_cache")
        assert isinstance(clear_result, Success)

        await manager.stop()

    async def test_cache_invalidation(self):
        """캐시 무효화 테스트"""
        manager = get_distributed_cache_manager()

        await manager.start()

        # 태그와 함께 캐시 저장
        await manager.set(
            "product:1",
            {"id": "1", "name": "Product 1"},
            tags={"products", "category:electronics"},
        )

        await manager.set(
            "product:2",
            {"id": "2", "name": "Product 2"},
            tags={"products", "category:books"},
        )

        # 태그 기반 무효화
        invalidate_result = await manager.invalidate_by_tags({"category:electronics"})
        assert isinstance(invalidate_result, Success)
        assert invalidate_result.value >= 1

        # product:1은 무효화됨
        result1 = await manager.get("product:1")
        assert result1.value is None

        # product:2는 유지됨
        result2 = await manager.get("product:2")
        assert result2.value is not None

        await manager.stop()


@pytest.mark.asyncio
class TestAPIGateway:
    """API Gateway 테스트"""

    async def test_api_gateway(self):
        """API 게이트웨이 테스트"""
        gateway = get_api_gateway()

        # 게이트웨이 시작
        start_result = await gateway.start()
        assert isinstance(start_result, Success)

        # 백엔드 추가
        backend1 = Backend(id="backend_1", host="localhost", port=8001, weight=2)

        backend2 = Backend(id="backend_2", host="localhost", port=8002, weight=1)

        # 라우트 추가
        route = Route(
            id="api_route",
            path="/api/users",
            methods=["GET", "POST"],
            backends=[backend1, backend2],
            authentication=AuthenticationMethod.API_KEY,
            timeout=30,
        )

        route_result = gateway.add_route(route)
        assert isinstance(route_result, Success)

        # 요청 컨텍스트 생성
        context = RequestContext(
            request_id="req_123",
            client_ip="127.0.0.1",
            method="GET",
            path="/api/users",
            headers={"X-API-Key": "test_key"},
            query_params={"page": 1},
        )

        # API 키 추가
        from rfs.integration import APIKey

        api_key = APIKey(
            key="test_key",
            name="Test API Key",
            owner="test_user",
            created_at=datetime.now(),
        )

        key_result = gateway.add_api_key(api_key)
        assert isinstance(key_result, Success)

        # 요청 처리 (백엔드가 실제로 없으므로 실패할 수 있음)
        response_result = await gateway.handle_request(context)
        # 백엔드 호출은 시뮬레이션이므로 성공 예상
        assert isinstance(response_result, Success)

        # 통계 조회
        stats = gateway.get_statistics()
        assert stats["total_requests"] >= 1

        # 게이트웨이 중지
        await gateway.stop()

    async def test_load_balancing(self):
        """로드 밸런싱 테스트"""
        gateway = get_api_gateway()

        # 다른 전략으로 로드 밸런서 설정
        from rfs.integration.api_gateway import LoadBalancer

        gateway.load_balancer = LoadBalancer(LoadBalanceStrategy.LEAST_CONNECTIONS)

        # 백엔드 설정
        backends = [
            Backend("b1", "localhost", 8001, active_connections=5),
            Backend("b2", "localhost", 8002, active_connections=2),
            Backend("b3", "localhost", 8003, active_connections=8),
        ]

        # 최소 연결 전략으로 선택
        selected = gateway.load_balancer.select_backend(
            "route_1", backends, "127.0.0.1"
        )

        assert selected.id == "b2"  # 가장 적은 연결

    async def test_rate_limiting(self):
        """속도 제한 테스트"""
        from rfs.integration import RateLimitRule

        gateway = get_api_gateway()

        # 속도 제한 규칙 추가
        rule = RateLimitRule(
            id="api_limit",
            name="API Rate Limit",
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            requests_per_second=10,
            burst_size=20,
            scope="ip",
        )

        rule_result = gateway.add_rate_limit_rule(rule)
        assert isinstance(rule_result, Success)

        # 요청 시뮬레이션
        for i in range(25):
            allowed = gateway.rate_limiter.check_rate_limit(rule, "127.0.0.1")

            if i < 20:  # 버스트 크기 내
                assert allowed
            else:  # 버스트 초과
                assert not allowed

    async def test_api_documentation(self):
        """API 문서 생성 테스트"""
        gateway = get_api_gateway()

        # 라우트 추가
        route = Route(
            id="doc_route",
            path="/api/v1/products",
            methods=["GET", "POST", "PUT", "DELETE"],
            backends=[Backend("b1", "localhost", 8001)],
            authentication=AuthenticationMethod.JWT,
        )

        gateway.add_route(route)

        # OpenAPI 문서 생성
        doc = await gateway.generate_api_documentation()

        assert "openapi" in doc
        assert doc["openapi"] == "3.0.0"
        assert "paths" in doc
        assert "/api/v1/products" in doc["paths"]

        # 각 메소드 확인
        path_item = doc["paths"]["/api/v1/products"]
        assert "get" in path_item
        assert "post" in path_item
        assert "put" in path_item
        assert "delete" in path_item


@pytest.mark.asyncio
class TestIntegratedFlow:
    """통합 플로우 테스트"""

    async def test_api_gateway_with_cache(self):
        """API Gateway와 캐시 통합"""
        gateway = get_api_gateway()
        cache_manager = get_distributed_cache_manager()

        await gateway.start()
        await cache_manager.start()

        # 캐시 설정이 있는 라우트
        route = Route(
            id="cached_route",
            path="/api/data",
            methods=["GET"],
            backends=[Backend("b1", "localhost", 8001)],
            authentication=AuthenticationMethod.NONE,
            cache_config={"ttl": 60},
        )

        gateway.add_route(route)

        # 첫 번째 요청
        context1 = RequestContext(
            request_id="req_1",
            client_ip="127.0.0.1",
            method="GET",
            path="/api/data",
            headers={},
            query_params={},
        )

        response1 = await gateway.handle_request(context1)
        assert isinstance(response1, Success)
        assert not response1.value.cached

        # 두 번째 요청 (캐시됨)
        context2 = RequestContext(
            request_id="req_2",
            client_ip="127.0.0.1",
            method="GET",
            path="/api/data",
            headers={},
            query_params={},
        )

        response2 = await gateway.handle_request(context2)
        assert isinstance(response2, Success)
        assert response2.value.cached

        await gateway.stop()
        await cache_manager.stop()
