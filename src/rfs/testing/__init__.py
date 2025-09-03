"""
RFS Framework 테스팅 시스템

Result 패턴 전용 테스팅 도구와 유틸리티를 제공합니다.
Phase 3 구현: 테스트 작성 효율성 극대화
"""

from .result_helpers import (
    # 모킹 시스템
    ResultServiceMocker,
    mock_result_service,
    
    # 어설션 함수들
    assert_result_success,
    assert_result_failure,
    assert_result_value,
    assert_result_error,
    
    # MonoResult 어설션
    assert_mono_result_success,
    assert_mono_result_failure,
    assert_mono_result_value,
    
    # FluxResult 어설션
    assert_flux_success_count,
    assert_flux_failure_count,
    assert_flux_total_count,
    assert_flux_success_rate,
    assert_flux_success_values,
    
    # 테스트 데이터 팩토리
    ResultTestDataFactory,
    
    # 성능 테스트 헬퍼
    PerformanceTestHelper,
    
    # 통합 테스트 컨텍스트
    result_test_context,
    
    # 커스텀 마커
    result_test,
    mono_test,
    flux_test,
    performance_test
)

__all__ = [
    # 모킹 시스템
    "ResultServiceMocker",
    "mock_result_service",
    
    # 어설션 함수들
    "assert_result_success",
    "assert_result_failure", 
    "assert_result_value",
    "assert_result_error",
    
    # MonoResult 어설션
    "assert_mono_result_success",
    "assert_mono_result_failure",
    "assert_mono_result_value",
    
    # FluxResult 어설션
    "assert_flux_success_count",
    "assert_flux_failure_count",
    "assert_flux_total_count",
    "assert_flux_success_rate",
    "assert_flux_success_values",
    
    # 테스트 데이터 팩토리
    "ResultTestDataFactory",
    
    # 성능 테스트 헬퍼
    "PerformanceTestHelper",
    
    # 통합 테스트 컨텍스트
    "result_test_context",
    
    # 커스텀 마커
    "result_test",
    "mono_test",
    "flux_test",
    "performance_test"
]

__version__ = "3.0.0"
__author__ = "RFS Framework Team"
__description__ = "Result 패턴 전용 테스팅 시스템"