"""
RFS Testing Framework - Coverage Module
테스트 커버리지 측정 및 분석 도구
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import coverage

from ..core.result import Failure, Result, Success


@dataclass
class CoverageReport:
    """커버리지 리포트"""

    total_lines = 0
    covered_lines = 0
    missed_lines = 0
    coverage_percentage: float = 0.0
    files: Dict[str, Dict[str, any]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """딕셔너리 변환"""
        return {
            "total_lines": self.total_lines,
            "covered_lines": self.covered_lines,
            "missed_lines": self.missed_lines,
            "coverage_percentage": self.coverage_percentage,
            "files": self.files,
        }


class CoverageCollector:
    """커버리지 수집기"""

    def __init__(self, source_paths: Optional[List[str]] = None):
        """초기화"""
        self.cov = coverage.Coverage(source=source_paths)
        self.is_running = False

    def start(self) -> Result[None, str]:
        """커버리지 측정 시작"""
        try:
            if self.is_running:
                return Failure("Coverage is already running")

            self.cov.start()
            self.is_running = True
            return Success(None)
        except Exception as e:
            return Failure(f"Failed to start coverage: {str(e)}")

    def stop(self) -> Result[None, str]:
        """커버리지 측정 중지"""
        try:
            if not self.is_running:
                return Failure("Coverage is not running")

            self.cov.stop()
            self.is_running = False
            return Success(None)
        except Exception as e:
            return Failure(f"Failed to stop coverage: {str(e)}")

    def save(self) -> Result[None, str]:
        """커버리지 데이터 저장"""
        try:
            self.cov.save()
            return Success(None)
        except Exception as e:
            return Failure(f"Failed to save coverage: {str(e)}")

    def report(self) -> Result[CoverageReport, str]:
        """커버리지 리포트 생성"""
        try:
            if self.is_running:
                self.stop()

            # 리포트 생성
            report = CoverageReport()

            # 파일별 통계 수집
            file_data = {}
            analysis = self.cov.get_data()

            for filename in analysis.measured_files():
                try:
                    file_analysis = self.cov.analysis2(filename)
                    executed = file_analysis[1]
                    missing = file_analysis[3]

                    if file_analysis[0]:  # statements가 있는 경우
                        total = len(file_analysis[0])
                        covered = len(executed) if executed else 0
                        missed = len(missing) if missing else 0

                        file_data[filename] = {
                            "total_lines": total,
                            "covered_lines": covered,
                            "missed_lines": missed,
                            "coverage_percentage": (
                                (covered / total * 100) if total > 0 else 0
                            ),
                            "missing_lines": list(missing) if missing else [],
                        }

                        report.total_lines += total
                        report.covered_lines += covered
                        report.missed_lines += missed
                except Exception:
                    continue

            report.files = file_data
            if report.total_lines > 0:
                report.coverage_percentage = (
                    report.covered_lines / report.total_lines
                ) * 100

            return Success(report)
        except Exception as e:
            return Failure(f"Failed to generate report: {str(e)}")

    def html_report(self, directory="htmlcov") -> Result[str, str]:
        """HTML 리포트 생성"""
        try:
            self.cov.html_report(directory=directory)
            return Success(f"HTML report generated at {directory}")
        except Exception as e:
            return Failure(f"Failed to generate HTML report: {str(e)}")


# Global coverage instance
_coverage_collector = None


def start_coverage(source_paths: Optional[List[str]] = None) -> Result[None, str]:
    """커버리지 측정 시작"""
    global _coverage_collector

    if _coverage_collector is None:
        _coverage_collector = CoverageCollector(source_paths)

    return _coverage_collector.start()


def stop_coverage() -> Result[None, str]:
    """커버리지 측정 중지"""
    global _coverage_collector

    if _coverage_collector is None:
        return Failure("Coverage collector not initialized")

    return _coverage_collector.stop()


def get_coverage_report() -> Result[CoverageReport, str]:
    """커버리지 리포트 획득"""
    global _coverage_collector

    if _coverage_collector is None:
        return Failure("Coverage collector not initialized")

    return _coverage_collector.report()


def analyze_coverage(
    report: CoverageReport, threshold: float = 80.0
) -> Result[dict, str]:
    """커버리지 분석"""
    try:
        analysis = {
            "passed": report.coverage_percentage >= threshold,
            "coverage": report.coverage_percentage,
            "threshold": threshold,
            "summary": {
                "total_lines": report.total_lines,
                "covered_lines": report.covered_lines,
                "missed_lines": report.missed_lines,
            },
            "low_coverage_files": [],
        }

        # 낮은 커버리지 파일 찾기
        for filename, data in report.files.items():
            if data["coverage_percentage"] < threshold:
                analysis["low_coverage_files"].append(
                    {
                        "file": filename,
                        "coverage": data["coverage_percentage"],
                        "missing_lines": data["missing_lines"][:10],  # 처음 10개만
                    }
                )

        # 가장 낮은 커버리지 파일들 정렬
        analysis["low_coverage_files"].sort(key=lambda x: x["coverage"])

        return Success(analysis)
    except Exception as e:
        return Failure(f"Failed to analyze coverage: {str(e)}")


def generate_coverage_html(directory="htmlcov") -> Result[str, str]:
    """HTML 커버리지 리포트 생성"""
    global _coverage_collector

    if _coverage_collector is None:
        return Failure("Coverage collector not initialized")

    return _coverage_collector.html_report(directory)


__all__ = [
    "CoverageCollector",
    "CoverageReport",
    "start_coverage",
    "stop_coverage",
    "get_coverage_report",
    "analyze_coverage",
    "generate_coverage_html",
]
