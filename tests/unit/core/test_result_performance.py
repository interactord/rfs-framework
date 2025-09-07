"""
RFS Core Result Performance Tests (RFS v4.3)

Result 패턴 성능 테스트
"""

import pytest

from rfs.core.result import Failure, Success, sequence


class TestResultPerformance:
    """Result 성능 테스트"""

    def test_result_creation_performance(self, performance_timer):
        """Result 생성 성능 테스트"""
        performance_timer.start()

        for i in range(10000):
            Success(i)
            Failure(f"error_{i}")

        performance_timer.stop()

        # 10,000번 생성이 100ms 미만이어야 함
        assert performance_timer.elapsed < 0.1

    def test_result_chaining_performance(self, performance_timer):
        """Result 체이닝 성능 테스트"""

        def add_one(x):
            return Success(x + 1)

        performance_timer.start()

        result = Success(0)
        for _ in range(1000):
            result = result.bind(add_one)

        performance_timer.stop()

        # 1,000번 체이닝이 10ms 미만이어야 함
        assert performance_timer.elapsed < 0.01
        assert result.is_success()
        assert result.unwrap() == 1000

    def test_sequence_performance(self, performance_timer):
        """sequence 함수 성능 테스트"""
        results = [Success(i) for i in range(1000)]

        performance_timer.start()
        sequenced = sequence(results)
        performance_timer.stop()

        # 1,000개 시퀀스가 10ms 미만이어야 함
        assert performance_timer.elapsed < 0.01
        assert sequenced.is_success()
        assert len(sequenced.unwrap()) == 1000
