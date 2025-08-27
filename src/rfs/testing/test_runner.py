"""
RFS Test Runner (RFS v4.1)

테스트 러너 및 테스트 케이스 관리
"""

import asyncio
import glob
import importlib.util
import inspect
import os
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success

logger = get_logger(__name__)


class TestStatus(Enum):
    """테스트 상태"""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    """테스트 결과"""

    test_name: str
    status: TestStatus
    duration: float
    message = None
    error = None
    traceback = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_passed(self) -> bool:
        return self.status == TestStatus.PASSED

    def is_failed(self) -> bool:
        return self.status in [TestStatus.FAILED, TestStatus.ERROR]


@dataclass
class TestMetrics:
    """테스트 메트릭스"""

    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    error_tests: int
    total_duration: float
    average_duration: float

    @property
    def success_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return self.passed_tests / self.total_tests * 100

    @property
    def failure_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.failed_tests + self.error_tests) / self.total_tests * 100


@dataclass
class TestReport:
    """테스트 보고서"""

    suite_name: str
    results: List[TestResult]
    metrics: TestMetrics
    start_time: float
    end_time: float

    def get_failed_tests(self) -> List[TestResult]:
        return [r for r in self.results if r.is_failed()]

    def get_passed_tests(self) -> List[TestResult]:
        return [r for r in self.results if r.is_passed()]

    def generate_summary(self) -> str:
        """테스트 요약 생성"""
        summary = [
            f"Test Suite: {self.suite_name}",
            f"Total Tests: {self.metrics.total_tests}",
            f"Passed: {self.metrics.passed_tests} ({self.metrics.success_rate:.1f}%)",
            f"Failed: {self.metrics.failed_tests + self.metrics.error_tests} ({self.metrics.failure_rate:.1f}%)",
            f"Skipped: {self.metrics.skipped_tests}",
            f"Duration: {self.metrics.total_duration:.3f}s",
            f"Average: {self.metrics.average_duration:.3f}s per test",
        ]
        if self.get_failed_tests():
            summary = summary + ["\nFailed Tests:"]
            for result in self.get_failed_tests():
                summary = summary + [f"  - {result.test_name}: {result.message}"]
        return "\n".join(summary)


class TestCase(ABC):
    """테스트 케이스 기본 클래스"""

    def __init__(self, name=None):
        self.name = name or self.__class__.__name__
        self.setup_done = False
        self.teardown_done = False

    async def setup(self):
        """테스트 설정"""
        pass

    async def teardown(self):
        """테스트 정리"""
        pass

    @abstractmethod
    async def run(self) -> Result[Any, str]:
        """테스트 실행"""
        pass


class AsyncTestCase(TestCase):
    """비동기 테스트 케이스"""

    @abstractmethod
    async def run(self) -> Result[Any, str]:
        """비동기 테스트 실행"""
        pass


class FunctionTestCase(TestCase):
    """함수 기반 테스트 케이스"""

    def __init__(self, test_function: Callable, name=None):
        super().__init__(name or test_function.__name__)
        self.test_function = test_function

    async def run(self) -> Result[Any, str]:
        """함수 실행"""
        try:
            if asyncio.iscoroutinefunction(self.test_function):
                result = await self.test_function()
            else:
                result = self.test_function()
            return Success(result)
        except Exception as e:
            return Failure(f"테스트 실행 실패: {str(e)}")


class TestSuite:
    """테스트 스위트"""

    def __init__(self, name: str):
        self.name = name
        self.test_cases = []
        self.setup_hooks = []
        self.teardown_hooks = []

    def add_test(self, test_case: Union[TestCase, Callable]):
        """테스트 추가"""
        if type(test_case).__name__ == "TestCase":
            self.test_cases = self.test_cases + [test_case]
        elif callable(test_case):
            wrapped_case = FunctionTestCase(test_case)
            self.test_cases = self.test_cases + [wrapped_case]
        else:
            raise ValueError(
                "테스트는 TestCase 인스턴스 또는 호출 가능 객체여야 합니다"
            )

    def add_setup_hook(self, hook: Callable):
        """설정 훅 추가"""
        self.setup_hooks = self.setup_hooks + [hook]

    def add_teardown_hook(self, hook: Callable):
        """정리 훅 추가"""
        self.teardown_hooks = self.teardown_hooks + [hook]

    async def run_setup_hooks(self):
        """설정 훅 실행"""
        for hook in self.setup_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()
            except Exception as e:
                await logger.log_warning(f"설정 훅 실행 실패: {str(e)}")

    async def run_teardown_hooks(self):
        """정리 훅 실행"""
        for hook in self.teardown_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()
            except Exception as e:
                await logger.log_warning(f"정리 훅 실행 실패: {str(e)}")


class TestRunner:
    """테스트 러너"""

    def __init__(self, verbose=True, stop_on_failure=False):
        self.verbose = verbose
        self.stop_on_failure = stop_on_failure
        self.results = []

    async def run_test_case(self, test_case: TestCase) -> TestResult:
        """단일 테스트 케이스 실행"""
        start_time = time.time()
        if self.verbose:
            await logger.log_info(f"테스트 시작: {test_case.name}")
        try:
            await test_case.setup()
            test_case.setup_done = True
            result = await test_case.run()
            if result.is_success():
                status = TestStatus.PASSED
                message = "테스트 통과"
                error = None
                tb = None
            else:
                status = TestStatus.FAILED
                message = result.unwrap_err()
                error = None
                tb = None
        except AssertionError as e:
            status = TestStatus.FAILED
            message = f"어설션 실패: {str(e)}"
            error = e
            tb = traceback.format_exc()
        except Exception as e:
            status = TestStatus.ERROR
            message = f"테스트 오류: {str(e)}"
            error = e
            tb = traceback.format_exc()
        finally:
            if test_case.setup_done:
                try:
                    await test_case.teardown()
                    test_case.teardown_done = True
                except Exception as e:
                    await logger.log_warning(
                        f"테스트 정리 실패: {test_case.name} - {str(e)}"
                    )
        duration = time.time() - start_time
        test_result = TestResult(
            test_name=test_case.name,
            status=status,
            duration=duration,
            message=message,
            error=error,
            traceback=tb,
        )
        if self.verbose:
            if test_result.is_passed():
                await logger.log_info(f"✅ {test_case.name} ({duration:.3f}s)")
            else:
                await logger.log_error(
                    f"❌ {test_case.name} ({duration:.3f}s): {message}"
                )
        return test_result

    async def run_test_suite(self, test_suite: TestSuite) -> TestReport:
        """테스트 스위트 실행"""
        start_time = time.time()
        if self.verbose:
            await logger.log_info(f"테스트 스위트 시작: {test_suite.name}")
        await test_suite.run_setup_hooks()
        results = []
        try:
            for test_case in test_suite.test_cases:
                test_result = await self.run_test_case(test_case)
                results = results + [test_result]
                if self.stop_on_failure and test_result.is_failed():
                    await logger.log_info("실패로 인한 테스트 중단")
                    break
        finally:
            await test_suite.run_teardown_hooks()
        end_time = time.time()
        total_tests = len(results)
        passed_tests = sum((1 for r in results if r.status == TestStatus.PASSED))
        failed_tests = sum((1 for r in results if r.status == TestStatus.FAILED))
        error_tests = sum((1 for r in results if r.status == TestStatus.ERROR))
        skipped_tests = sum((1 for r in results if r.status == TestStatus.SKIPPED))
        total_duration = end_time - start_time
        average_duration = total_duration / total_tests if total_tests > 0 else 0
        metrics = TestMetrics(
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            error_tests=error_tests,
            total_duration=total_duration,
            average_duration=average_duration,
        )
        report = TestReport(
            suite_name=test_suite.name,
            results=results,
            metrics=metrics,
            start_time=start_time,
            end_time=end_time,
        )
        if self.verbose:
            await logger.log_info(f"테스트 스위트 완료: {test_suite.name}")
            await logger.log_info(report.generate_summary())
        return report


def discover_tests(directory: str, pattern="test_*.py") -> List[TestCase]:
    """테스트 파일에서 테스트 케이스 발견"""
    test_cases = []
    test_files = glob.glob(os.path.join(directory, pattern))
    for test_file in test_files:
        try:
            spec = importlib.util.spec_from_file_location("test_module", test_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                for name in dir(module):
                    obj = getattr(module, name)
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, TestCase)
                        and (obj != TestCase)
                    ):
                        test_cases = test_cases + [obj()]
                    elif callable(obj) and name.startswith("test_"):
                        test_cases = test_cases + [FunctionTestCase(obj, name)]
        except Exception as e:
            print(f"테스트 파일 로드 실패 {test_file}: {str(e)}")
    return test_cases


async def run_test(test_case: Union[TestCase, Callable], verbose=True) -> TestResult:
    """단일 테스트 실행"""
    runner = TestRunner(verbose=verbose)
    if not type(test_case).__name__ == "TestCase":
        test_case = FunctionTestCase(test_case)
    return await runner.run_test_case(test_case)


async def run_test_suite(
    test_suite: TestSuite, verbose=True, stop_on_failure=False
) -> TestReport:
    """테스트 스위트 실행"""
    runner = TestRunner(verbose=verbose, stop_on_failure=stop_on_failure)
    return await runner.run_test_suite(test_suite)


async def coverage_report(test_suite: TestSuite) -> Dict[str, Any]:
    """커버리지 보고서 생성 (기본 구현)"""
    report = await run_test_suite(test_suite, verbose=False)
    return {
        "suite_name": report.suite_name,
        "coverage": {
            "line_coverage": 0.0,
            "branch_coverage": 0.0,
            "function_coverage": 0.0,
        },
        "test_metrics": report.metrics,
        "timestamp": time.time(),
    }
