"""
ResultAsync 런타임 경고 방지 테스트

이 테스트는 ResultAsync 클래스가 런타임 경고를 발생시키지 않는지 확인합니다.
"""

import asyncio
import pytest
import warnings
from typing import Any

# 직접 core.result 모듈만 import (전체 초기화 회피)
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))

# 경고 필터 설정
warnings.simplefilter('always')


class TestResultAsyncWarnings:
    """ResultAsync 런타임 경고 테스트"""
    
    @pytest.mark.asyncio
    async def test_no_runtime_warnings_from_value(self):
        """from_value 사용 시 런타임 경고가 발생하지 않는지 확인"""
        from rfs.core.result import ResultAsync, Success, Failure
        
        # 경고 캡처
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # ResultAsync 생성
            result = ResultAsync.from_value("test_value")
            
            # 메서드 호출
            is_success = await result.is_success()
            assert is_success is True
            
            value = await result.unwrap_or("default")
            assert value == "test_value"
            
            # RuntimeWarning이 없어야 함
            runtime_warnings = [warning for warning in w if issubclass(warning.category, RuntimeWarning)]
            assert len(runtime_warnings) == 0, f"런타임 경고 발생: {[str(w.message) for w in runtime_warnings]}"
    
    @pytest.mark.asyncio
    async def test_no_runtime_warnings_from_error(self):
        """from_error 사용 시 런타임 경고가 발생하지 않는지 확인"""
        from rfs.core.result import ResultAsync, Success, Failure
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # ResultAsync 생성
            result = ResultAsync.from_error("test_error")
            
            # 메서드 호출
            is_failure = await result.is_failure()
            assert is_failure is True
            
            value = await result.unwrap_or("default")
            assert value == "default"
            
            # RuntimeWarning이 없어야 함
            runtime_warnings = [warning for warning in w if issubclass(warning.category, RuntimeWarning)]
            assert len(runtime_warnings) == 0, f"런타임 경고 발생: {[str(w.message) for w in runtime_warnings]}"
    
    @pytest.mark.asyncio
    async def test_bind_async_no_warnings(self):
        """bind_async 사용 시 런타임 경고가 발생하지 않는지 확인"""
        from rfs.core.result import ResultAsync, Result, Success, Failure
        
        async def process_data(value: str) -> Result[str, str]:
            """비동기 처리 함수"""
            await asyncio.sleep(0.001)  # 비동기 작업 시뮬레이션
            return Success(f"processed_{value}")
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # ResultAsync 생성 및 bind_async 호출
            result = ResultAsync.from_value("data")
            processed = result.bind_async(process_data)
            final_result = await processed.to_result()
            
            assert final_result.is_success()
            assert final_result.unwrap() == "processed_data"
            
            # RuntimeWarning이 없어야 함
            runtime_warnings = [warning for warning in w if issubclass(warning.category, RuntimeWarning)]
            assert len(runtime_warnings) == 0, f"런타임 경고 발생: {[str(w.message) for w in runtime_warnings]}"
    
    @pytest.mark.asyncio
    async def test_map_async_no_warnings(self):
        """map_async 사용 시 런타임 경고가 발생하지 않는지 확인"""
        from rfs.core.result import ResultAsync, Success, Failure
        
        async def transform_data(value: str) -> str:
            """비동기 변환 함수"""
            await asyncio.sleep(0.001)
            return value.upper()
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # ResultAsync 생성 및 map_async 호출
            result = ResultAsync.from_value("hello")
            transformed = result.map_async(transform_data)
            final_result = await transformed.to_result()
            
            assert final_result.is_success()
            assert final_result.unwrap() == "HELLO"
            
            # RuntimeWarning이 없어야 함
            runtime_warnings = [warning for warning in w if issubclass(warning.category, RuntimeWarning)]
            assert len(runtime_warnings) == 0, f"런타임 경고 발생: {[str(w.message) for w in runtime_warnings]}"
    
    @pytest.mark.asyncio
    async def test_chaining_no_warnings(self):
        """체이닝 연산 시 런타임 경고가 발생하지 않는지 확인"""
        from rfs.core.result import ResultAsync, Result, Success, Failure
        
        async def step1(value: int) -> Result[int, str]:
            return Success(value * 2)
        
        async def step2(value: int) -> Result[str, str]:
            return Success(f"result_{value}")
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # 체이닝 연산
            result = (
                ResultAsync.from_value(5)
                .bind_async(step1)
                .bind_async(step2)
            )
            
            final_result = await result.to_result()
            assert final_result.is_success()
            assert final_result.unwrap() == "result_10"
            
            # RuntimeWarning이 없어야 함
            runtime_warnings = [warning for warning in w if issubclass(warning.category, RuntimeWarning)]
            assert len(runtime_warnings) == 0, f"런타임 경고 발생: {[str(w.message) for w in runtime_warnings]}"
    
    @pytest.mark.asyncio  
    async def test_helper_functions_no_warnings(self):
        """async_success, async_failure 헬퍼 함수 테스트"""
        from rfs.core.result import async_success, async_failure
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # async_success 테스트
            success_result = async_success("success_value")
            success_final = await success_result.to_result()
            assert success_final.is_success()
            assert success_final.unwrap() == "success_value"
            
            # async_failure 테스트
            failure_result = async_failure("error_message")
            failure_final = await failure_result.to_result()
            assert failure_final.is_failure()
            assert failure_final.unwrap_error() == "error_message"
            
            # RuntimeWarning이 없어야 함
            runtime_warnings = [warning for warning in w if issubclass(warning.category, RuntimeWarning)]
            assert len(runtime_warnings) == 0, f"런타임 경고 발생: {[str(w.message) for w in runtime_warnings]}"