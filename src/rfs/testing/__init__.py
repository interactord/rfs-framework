"""
RFS Testing Framework (RFS v4.1)

테스트 프레임워크 - 단위/통합 테스트 도구
"""

from .test_runner import (
    # 테스트 러너
    TestRunner,
    TestSuite,
    TestResult,
    TestStatus,
    
    # 테스트 케이스
    TestCase,
    AsyncTestCase,
    
    # 테스트 실행
    run_test,
    run_test_suite,
    discover_tests,
    
    # 테스트 결과
    TestReport,
    TestMetrics,
    coverage_report
)

from .fixtures import (
    # 픽스처 관리
    fixture,
    setup_fixture,
    teardown_fixture,
    
    # 픽스처 스코프
    FixtureScope,
    
    # 데이터베이스 픽스처
    database_fixture,
    redis_fixture,
    
    # 웹 픽스처
    web_client_fixture,
    mock_server_fixture
)

from .assertions import (
    # 기본 어설션
    assert_equal,
    assert_not_equal,
    assert_true,
    assert_false,
    assert_none,
    assert_not_none,
    
    # 컬렉션 어설션
    assert_in,
    assert_not_in,
    assert_empty,
    assert_not_empty,
    assert_length,
    
    # 예외 어설션
    assert_raises,
    assert_not_raises,
    
    # Result 어설션
    assert_success,
    assert_failure,
    assert_result_value,
    assert_result_error,
    
    # 비동기 어설션
    assert_eventually,
    assert_timeout,
    
    # 커스텀 어설션
    AssertionError,
    create_assertion
)

from .mocks import (
    # Mock 객체
    Mock,
    AsyncMock,
    MagicMock,
    
    # Mock 헬퍼
    patch,
    patch_object,
    patch_method,
    
    # Mock 검증
    assert_called,
    assert_called_with,
    assert_called_once,
    assert_not_called,
    
    # Stub 객체
    Stub,
    create_stub,
    
    # Fake 객체
    FakeDatabase,
    FakeRedis,
    FakeMessageBroker
)

from .integration import (
    # 통합 테스트
    IntegrationTest,
    DatabaseIntegrationTest,
    WebIntegrationTest,
    MessageIntegrationTest,
    
    # 테스트 환경
    TestEnvironment,
    setup_test_environment,
    cleanup_test_environment,
    
    # 테스트 데이터
    TestDataFactory,
    create_test_data,
    cleanup_test_data
)

from .performance import (
    # 성능 테스트
    PerformanceTest,
    LoadTest,
    StressTest,
    
    # 성능 측정
    measure_performance,
    benchmark,
    profile_function,
    
    # 성능 어설션
    assert_performance,
    assert_response_time,
    assert_throughput,
    assert_memory_usage
)

from .coverage import (
    # 커버리지 측정
    CoverageCollector,
    start_coverage,
    stop_coverage,
    get_coverage_report,
    
    # 커버리지 분석
    CoverageReport,
    analyze_coverage,
    generate_coverage_html
)

__all__ = [
    # Test Runner
    "TestRunner",
    "TestSuite", 
    "TestResult",
    "TestStatus",
    "TestCase",
    "AsyncTestCase",
    "run_test",
    "run_test_suite",
    "discover_tests",
    "TestReport",
    "TestMetrics",
    "coverage_report",
    
    # Fixtures
    "fixture",
    "setup_fixture",
    "teardown_fixture",
    "FixtureScope",
    "database_fixture",
    "redis_fixture",
    "web_client_fixture",
    "mock_server_fixture",
    
    # Assertions
    "assert_equal",
    "assert_not_equal",
    "assert_true",
    "assert_false",
    "assert_none",
    "assert_not_none",
    "assert_in",
    "assert_not_in",
    "assert_empty",
    "assert_not_empty",
    "assert_length",
    "assert_raises",
    "assert_not_raises",
    "assert_success",
    "assert_failure",
    "assert_result_value",
    "assert_result_error",
    "assert_eventually",
    "assert_timeout",
    "AssertionError",
    "create_assertion",
    
    # Mocks
    "Mock",
    "AsyncMock", 
    "MagicMock",
    "patch",
    "patch_object",
    "patch_method",
    "assert_called",
    "assert_called_with",
    "assert_called_once",
    "assert_not_called",
    "Stub",
    "create_stub",
    "FakeDatabase",
    "FakeRedis",
    "FakeMessageBroker",
    
    # Integration Testing
    "IntegrationTest",
    "DatabaseIntegrationTest",
    "WebIntegrationTest",
    "MessageIntegrationTest",
    "TestEnvironment",
    "setup_test_environment",
    "cleanup_test_environment",
    "TestDataFactory",
    "create_test_data",
    "cleanup_test_data",
    
    # Performance Testing
    "PerformanceTest",
    "LoadTest",
    "StressTest",
    "measure_performance",
    "benchmark",
    "profile_function",
    "assert_performance",
    "assert_response_time",
    "assert_throughput",
    "assert_memory_usage",
    
    # Coverage
    "CoverageCollector",
    "start_coverage",
    "stop_coverage", 
    "get_coverage_report",
    "CoverageReport",
    "analyze_coverage",
    "generate_coverage_html"
]