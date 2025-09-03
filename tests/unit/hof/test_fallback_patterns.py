"""
Tests for fallback patterns in HOF library

PR에서 요구된 fallback 패턴들의 테스트:
- with_fallback (동기)
- async_with_fallback (비동기)
- safe_call, retry_with_fallback 등 관련 함수들
"""

import asyncio
import pytest
import time
from typing import Any

from rfs.hof.combinators import with_fallback, safe_call, retry_with_fallback
from rfs.hof.async_hof import async_with_fallback, async_safe_call, async_retry_with_fallback, async_timeout_with_fallback


class TestSyncFallbackPatterns:
    """동기 fallback 패턴들 테스트"""
    
    def test_with_fallback_success_case(self):
        """성공하는 주 함수의 경우 fallback이 호출되지 않는지 테스트"""
        def primary_function():
            return "primary_result"
        
        def fallback_function(error):
            # 이 함수는 호출되지 않아야 함
            return "fallback_result"
        
        safe_function = with_fallback(primary_function, fallback_function)
        result = safe_function()
        
        assert result == "primary_result"
    
    def test_with_fallback_failure_case(self):
        """실패하는 주 함수의 경우 fallback이 호출되는지 테스트"""
        def primary_function():
            raise ValueError("primary failed")
        
        def fallback_function(error):
            assert isinstance(error, ValueError)
            assert "primary failed" in str(error)
            return "fallback_result"
        
        safe_function = with_fallback(primary_function, fallback_function)
        result = safe_function()
        
        assert result == "fallback_result"
    
    def test_with_fallback_with_arguments(self):
        """인자가 있는 함수들에 대한 with_fallback 테스트"""
        def primary_function(x, y, multiplier=2):
            if x < 0:
                raise ValueError("x must be positive")
            return (x + y) * multiplier
        
        def fallback_function(error):
            return 0  # 기본값 반환
        
        safe_function = with_fallback(primary_function, fallback_function)
        
        # 성공 케이스
        result = safe_function(5, 3, multiplier=2)
        assert result == 16  # (5 + 3) * 2
        
        # 실패 케이스 (fallback 호출)
        result = safe_function(-1, 3)
        assert result == 0
    
    def test_safe_call_with_default(self):
        """safe_call이 예외 발생 시 기본값을 반환하는지 테스트"""
        def risky_function():
            raise RuntimeError("something went wrong")
        
        safe_function = safe_call(risky_function, "default_value")
        result = safe_function()
        
        assert result == "default_value"
    
    def test_safe_call_with_specific_exceptions(self):
        """safe_call이 특정 예외만 처리하는지 테스트"""
        def risky_function():
            raise ValueError("specific error")
        
        # ValueError만 처리
        safe_function = safe_call(risky_function, "handled", (ValueError,))
        result = safe_function()
        assert result == "handled"
        
        # RuntimeError는 처리하지 않음
        def another_risky_function():
            raise RuntimeError("not handled")
        
        not_safe_function = safe_call(another_risky_function, "default", (ValueError,))
        
        with pytest.raises(RuntimeError):
            not_safe_function()
    
    def test_retry_with_fallback_success_after_retries(self):
        """재시도 후 성공하는 경우 테스트"""
        attempt_count = 0
        
        def flaky_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ConnectionError("not ready yet")
            return "success_after_retries"
        
        def fallback_function(error):
            return "fallback_result"
        
        reliable_function = retry_with_fallback(
            flaky_function, 
            fallback_function, 
            max_attempts=5,
            delay=0.01  # 빠른 테스트를 위해 짧은 지연
        )
        
        result = reliable_function()
        assert result == "success_after_retries"
        assert attempt_count == 3
    
    def test_retry_with_fallback_all_attempts_fail(self):
        """모든 재시도가 실패한 경우 fallback 호출 테스트"""
        attempt_count = 0
        
        def always_failing_function():
            nonlocal attempt_count
            attempt_count += 1
            raise ConnectionError(f"failed attempt {attempt_count}")
        
        def fallback_function(error):
            assert isinstance(error, ConnectionError)
            assert "failed attempt 3" in str(error)  # 마지막 시도의 에러
            return "fallback_after_all_retries"
        
        reliable_function = retry_with_fallback(
            always_failing_function,
            fallback_function,
            max_attempts=3,
            delay=0.01
        )
        
        result = reliable_function()
        assert result == "fallback_after_all_retries"
        assert attempt_count == 3


class TestAsyncFallbackPatterns:
    """비동기 fallback 패턴들 테스트"""
    
    def test_async_with_fallback_success_case(self):
        """비동기에서 성공하는 주 함수의 경우 테스트"""
        async def primary_function():
            await asyncio.sleep(0.01)
            return "async_primary_result"
        
        async def fallback_function(error):
            return "async_fallback_result"
        
        async def test():
            safe_function = async_with_fallback(primary_function, fallback_function)
            result = await safe_function()
            assert result == "async_primary_result"
        
        asyncio.run(test())
    
    def test_async_with_fallback_failure_case(self):
        """비동기에서 실패하는 주 함수의 경우 테스트"""
        async def primary_function():
            await asyncio.sleep(0.01)
            raise ValueError("async primary failed")
        
        async def fallback_function(error):
            assert isinstance(error, ValueError)
            assert "async primary failed" in str(error)
            await asyncio.sleep(0.01)
            return "async_fallback_result"
        
        async def test():
            safe_function = async_with_fallback(primary_function, fallback_function)
            result = await safe_function()
            assert result == "async_fallback_result"
        
        asyncio.run(test())
    
    def test_async_safe_call(self):
        """async_safe_call 기본 동작 테스트"""
        async def risky_async_function():
            await asyncio.sleep(0.01)
            raise RuntimeError("async error")
        
        async def test():
            result = await async_safe_call(risky_async_function, "async_default")
            assert result == "async_default"
        
        asyncio.run(test())
    
    def test_async_retry_with_fallback_success(self):
        """비동기 재시도에서 성공하는 경우 테스트"""
        attempt_count = 0
        
        async def flaky_async_function():
            nonlocal attempt_count
            attempt_count += 1
            await asyncio.sleep(0.01)
            if attempt_count < 3:
                raise ConnectionError("async not ready yet")
            return "async_success_after_retries"
        
        async def fallback_function(error):
            return "async_fallback_result"
        
        async def test():
            reliable_function = async_retry_with_fallback(
                flaky_async_function,
                fallback_function,
                max_attempts=5,
                delay=0.01
            )
            
            result = await reliable_function()
            assert result == "async_success_after_retries"
            assert attempt_count == 3
        
        asyncio.run(test())
    
    def test_async_timeout_with_fallback(self):
        """타임아웃과 fallback 조합 테스트"""
        async def slow_function():
            await asyncio.sleep(0.1)  # 100ms 지연
            return "slow_result"
        
        async def fast_fallback(error):
            assert isinstance(error, asyncio.TimeoutError)
            return "timeout_fallback"
        
        async def test():
            fast_function = async_timeout_with_fallback(
                slow_function,
                fast_fallback,
                timeout=0.05  # 50ms 타임아웃
            )
            
            result = await fast_function()
            assert result == "timeout_fallback"
        
        asyncio.run(test())


class TestFallbackPatternsIntegration:
    """Fallback 패턴들의 통합 사용 테스트"""
    
    def test_nested_fallback_patterns(self):
        """중첩된 fallback 패턴 사용 테스트"""
        def unreliable_function():
            raise ConnectionError("connection failed")
        
        def first_fallback(error):
            # 첫 번째 fallback도 실패
            raise RuntimeError("first fallback failed")
        
        def final_fallback(error):
            return "final_fallback_result"
        
        # 중첩된 fallback
        safe_function = with_fallback(
            with_fallback(unreliable_function, first_fallback),
            final_fallback
        )
        
        result = safe_function()
        assert result == "final_fallback_result"
    
    def test_mixing_sync_and_async_patterns(self):
        """동기와 비동기 패턴을 함께 사용하는 경우 테스트"""
        def sync_function():
            return "sync_result"
        
        # 동기 함수를 비동기에서 사용
        async def test():
            result = sync_function()
            assert result == "sync_result"
            
            # 비동기 fallback 패턴
            async def async_function():
                await asyncio.sleep(0.01)
                return "async_result"
            
            async def async_fallback(error):
                return "async_fallback"
            
            safe_async = async_with_fallback(async_function, async_fallback)
            async_result = await safe_async()
            assert async_result == "async_result"
        
        asyncio.run(test())
    
    def test_fallback_with_complex_data_flow(self):
        """복잡한 데이터 흐름에서의 fallback 패턴 테스트"""
        class ServiceA:
            def get_data(self):
                raise ValueError("Service A is down")
        
        class ServiceB:
            def get_data(self):
                return {"source": "service_b", "data": [1, 2, 3]}
        
        class ServiceC:
            def get_data(self):
                return {"source": "service_c", "data": [4, 5, 6]}
        
        service_a = ServiceA()
        service_b = ServiceB()
        service_c = ServiceC()
        
        # 체이닝된 fallback
        def try_service_a():
            return service_a.get_data()
        
        def fallback_to_service_b(error):
            try:
                return service_b.get_data()
            except:
                raise  # service_b가 실패하면 다음 레벨로
        
        def final_fallback_to_service_c(error):
            return service_c.get_data()
        
        resilient_service = with_fallback(
            with_fallback(try_service_a, fallback_to_service_b),
            final_fallback_to_service_c
        )
        
        result = resilient_service()
        assert result["source"] == "service_b"
        assert result["data"] == [1, 2, 3]


class TestPRCompatibilityRequirements:
    """PR에서 요구된 정확한 동작 검증"""
    
    def test_pr_with_fallback_signature(self):
        """PR에 명시된 with_fallback 함수 시그니처 테스트"""
        # PR 예제: async def with_fallback(primary_fn, fallback_fn)
        def primary_fn():
            raise FileNotFoundError("Config not found")
        
        def fallback_fn(error):
            assert "Config not found" in str(error)
            return {"debug": True}
        
        safe_load = with_fallback(primary_fn, fallback_fn)
        config = safe_load()
        
        assert config == {"debug": True}
    
    def test_pr_async_with_fallback_usage(self):
        """PR 문서의 비동기 with_fallback 사용 패턴 테스트"""
        async def load_remote_config():
            await asyncio.sleep(0.01)
            raise ConnectionError("Remote server unavailable")
        
        async def default_config(error):
            assert "Remote server unavailable" in str(error)
            return {"debug": True, "mode": "fallback"}
        
        async def test():
            safe_load = async_with_fallback(load_remote_config, default_config)
            config = await safe_load()
            assert config["debug"] is True
            assert config["mode"] == "fallback"
        
        asyncio.run(test())
    
    def test_server_initialization_use_case(self):
        """서버 초기화에서의 실제 사용 사례 테스트"""
        def load_external_config():
            # 외부 설정 로드 실패 시뮬레이션
            raise ConnectionError("External config service unavailable")
        
        def use_default_config(error):
            return {
                "host": "localhost",
                "port": 8000,
                "debug": True,
                "fallback_reason": str(error)
            }
        
        def initialize_with_retry():
            # 재시도 + fallback 조합
            return retry_with_fallback(
                load_external_config,
                use_default_config,
                max_attempts=3,
                delay=0.01
            )
        
        config_loader = initialize_with_retry()
        config = config_loader()
        
        # 외부 설정 로드는 실패했지만 기본 설정으로 서버는 시작 가능
        assert config["host"] == "localhost"
        assert config["debug"] is True
        assert "unavailable" in config["fallback_reason"]