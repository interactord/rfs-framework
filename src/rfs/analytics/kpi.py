"""
RFS Advanced Analytics - KPI Management System (RFS v4.1)

KPI 계산 및 관리 시스템
"""

import asyncio
import json
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from functools import lru_cache
from typing import Any, Callable, ClassVar, Dict, List, Optional, Tuple, Union
from weakref import WeakKeyDictionary

from ..core.result import Failure, Result, Success
from .data_source import DataQuery, DataSource


class KPIType(Enum):
    COUNT = "count"
    AVERAGE = "average"
    SUM = "sum"
    PERCENTAGE = "percentage"
    RATIO = "ratio"
    TREND = "trend"
    CUSTOM = "custom"


class ThresholdType(Enum):
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    GREATER_EQUAL = "gte"
    LESS_EQUAL = "lte"
    EQUAL = "eq"
    NOT_EQUAL = "ne"
    BETWEEN = "between"
    NOT_BETWEEN = "not_between"


class KPIStatus(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    NORMAL = "normal"
    EXCELLENT = "excellent"
    UNKNOWN = "unknown"


@dataclass
class KPIThreshold:
    """KPI 임계값"""

    threshold_id: str
    name: str
    threshold_type: ThresholdType
    values: List[float]
    status: KPIStatus
    message: str = ""

    def evaluate(self, value: float) -> bool:
        """임계값 평가"""
        match self.threshold_type:
            case ThresholdType.GREATER_THAN:
                return value > self.values[0]
            case ThresholdType.LESS_THAN:
                return value < self.values[0]
            case ThresholdType.GREATER_EQUAL:
                return value >= self.values[0]
            case ThresholdType.LESS_EQUAL:
                return value <= self.values[0]
            case ThresholdType.EQUAL:
                return value == self.values[0]
            case ThresholdType.NOT_EQUAL:
                return value != self.values[0]
            case ThresholdType.BETWEEN:
                return self.values[0] <= value <= self.values[1]
            case ThresholdType.NOT_BETWEEN:
                return not self.values[0] <= value <= self.values[1]
        return False


@dataclass
class KPIValue:
    """KPI 값"""

    value: float
    timestamp: datetime
    status: KPIStatus
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "metadata": self.metadata,
        }


@dataclass
class KPITarget:
    """KPI 목표"""

    target_value: float
    target_date: Optional[datetime] = None
    description: str = ""


class KPI(ABC):
    """KPI 추상 클래스"""

    def __init__(
        self,
        kpi_id: str,
        name: str,
        description="",
        unit="",
        data_source=None,
    ):
        self.kpi_id = kpi_id
        self.name = name
        self.description = description
        self.unit = unit
        self.data_source = data_source
        self.thresholds = []
        self.targets = []
        self.history = []
        self.metadata = {}
        self._cache = {}
        self._cache_timestamp = None
        self._cache_ttl = 300  # 5분 캐시

    def _is_cache_valid(self) -> bool:
        """캐시 유효성 검사"""
        if self._cache_timestamp is None:
            return False
        return (datetime.now() - self._cache_timestamp).seconds < self._cache_ttl

    def _get_cache_key(self, operation: str, **kwargs) -> str:
        """캐시 키 생성"""
        params = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return f"{self.kpi_id}_{operation}_{params}"

    async def _execute_query(
        self, query: DataQuery, cache_key=None
    ) -> Result[Any, str]:
        """데이터 쿼리 실행 (캐싱 지원)

        Args:
            query: 실행할 쿼리
            cache_key: 캐시 키 (옵션)

        Returns:
            Result[Any, str]: 쿼리 결과 또는 오류
        """
        # 캐시 확인
        if cache_key and self._is_cache_valid() and cache_key in self._cache:
            return Success(self._cache[cache_key])

        if not self.data_source:
            return Failure("Data source not configured")

        try:
            from ..analytics.data_source import DataSourceManager

            # 데이터 소스 매니저 사용
            manager = DataSourceManager()

            # 데이터 소스가 문자열인 경우 ID로 찾기
            if isinstance(self.data_source, str):
                source_result = manager.get_source(self.data_source)
                if source_result.is_failure():
                    return Failure(f"Data source '{self.data_source}' not found")
                data_source = source_result.value
            else:
                data_source = self.data_source

            # 쿼리 실행 (테스트 호환성을 위해 execute 메서드 사용)
            if hasattr(data_source, "execute"):
                result = await data_source.execute(query)
            else:
                result = await data_source.execute_query(query)

            # 결과 캐시 저장
            if result.is_success() and cache_key:
                self._cache[cache_key] = result.value
                self._cache_timestamp = datetime.now()

            return result
        except Exception as e:
            return Failure(f"Query execution failed: {str(e)}")

    @abstractmethod
    async def calculate(self, **kwargs) -> Result[float, str]:
        """KPI 값 계산

        Args:
            **kwargs: 계산에 필요한 추가 매개변수

        Returns:
            Result[float, str]: 계산된 KPI 값 또는 오류
        """
        raise NotImplementedError("Subclasses must implement calculate method")

    def add_threshold(self, threshold: KPIThreshold) -> Result[bool, str]:
        """임계값 추가 (중복 방지)"""
        try:
            # 중복 임계값 확인
            existing_ids = {t.threshold_id for t in self.thresholds}
            if threshold.threshold_id in existing_ids:
                return Failure(f"Threshold '{threshold.threshold_id}' already exists")

            self.thresholds.append(threshold)
            self.thresholds.sort(
                key=lambda t: {
                    KPIStatus.CRITICAL: 0,
                    KPIStatus.WARNING: 1,
                    KPIStatus.NORMAL: 2,
                    KPIStatus.EXCELLENT: 3,
                }.get(t.status, 4)
            )
            # 캐시 무효화
            self._cache.clear()
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add threshold: {str(e)}")

    def add_target(self, target: KPITarget) -> Result[bool, str]:
        """목표 추가"""
        try:
            self.targets.append(target)
            # 캐시 무효화
            self._cache.clear()
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add target: {str(e)}")

    def evaluate_status(self, value: float) -> KPIStatus:
        """값에 대한 상태 평가"""
        for threshold in self.thresholds:
            if threshold.evaluate(value):
                return threshold.status
        return KPIStatus.NORMAL

    async def update_value(self, **kwargs) -> Result[KPIValue, str]:
        """KPI 값 업데이트"""
        try:
            calc_result = await self.calculate(**kwargs)
            if calc_result.is_failure():
                return calc_result
            value = calc_result.unwrap()
            status = self.evaluate_status(value)
            kpi_value = KPIValue(
                value=value, timestamp=datetime.now(), status=status, metadata=kwargs
            )
            self.history.append(kpi_value)
            # 메모리 효율성을 위해 최대 1000개로 제한
            if len(self.history) > 1000:
                self.history = self.history[-1000:]
            return Success(kpi_value)
        except Exception as e:
            return Failure(f"Value update failed: {str(e)}")

    def get_current_value(self) -> Optional[KPIValue]:
        """현재 값 조회"""
        return self.history[-1] if self.history else None

    @lru_cache(maxsize=32)
    def _get_cached_history(self, days: int, cache_timestamp: str) -> List[KPIValue]:
        """히스토리 캐시 (내부 사용)"""
        cutoff_date = datetime.strptime(cache_timestamp, "%Y%m%d%H") - timedelta(
            days=days
        )
        return [v for v in self.history if v.timestamp >= cutoff_date]

    def get_history(self, days=30) -> List[KPIValue]:
        """히스토리 조회 (캐시 지원)"""
        # 1시간 단위로 캐시
        cache_timestamp = datetime.now().strftime("%Y%m%d%H")
        return self._get_cached_history(days, cache_timestamp)

    @lru_cache(maxsize=16)
    def _calculate_trend(self, values_hash: int, days: int) -> str:
        """트렌드 계산 (내부 사용)"""
        recent_values = self.get_history(days)
        if len(recent_values) < 2:
            return "unknown"
        values = [v.value for v in recent_values]
        n = len(values)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        numerator = sum(((x[i] - x_mean) * (values[i] - y_mean) for i in range(n)))
        denominator = sum(((x[i] - x_mean) ** 2 for i in range(n)))
        if denominator == 0:
            return "stable"
        slope = numerator / denominator
        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"

    def get_trend(self, days=7) -> Optional[str]:
        """트렌드 분석 (캐시 지원)"""
        recent_values = self.get_history(days)
        if len(recent_values) < 2:
            return None
        values_hash = hash(
            tuple(v.value for v in recent_values[-20:])
        )  # 최근 20개 값만 사용
        return self._calculate_trend(values_hash, days)


class CountKPI(KPI):
    """카운트 KPI"""

    def __init__(self, kpi_id: str, name: str, query: str, **kwargs) -> None:
        super().__init__(kpi_id, name, **kwargs)
        self.query = query

    async def calculate(self, **kwargs) -> Result[float, str]:
        """카운트 계산 (캐싱 지원)"""
        try:
            from ..analytics.data_source import DataQuery

            # 캐시 키 생성
            cache_key = self._get_cache_key("count", **kwargs)

            data_query = DataQuery(query=self.query, parameters=kwargs)
            result = await self._execute_query(data_query, cache_key)
            if result.is_failure():
                return Failure(f"Failed to calculate count: {result.error}")

            data = result.value
            if not data:
                return Success(0.0)

            # 카운트 계산 로직 최적화
            if isinstance(data, list):
                count = float(len(data))
            elif isinstance(data, dict) and "count" in data:
                count = float(data["count"])
            elif isinstance(data, (int, float)):
                count = float(data)
            else:
                # 첫 번째 행의 첫 번째 값을 카운트로 사용
                if data and isinstance(data, list) and data[0]:
                    if isinstance(data[0], dict):
                        # 첫 번째 키의 값 사용
                        first_value = list(data[0].values())[0] if data[0] else 0
                        count = float(first_value)
                    else:
                        count = float(data[0])
                else:
                    count = 0.0

            return Success(count)
        except Exception as e:
            return Failure(f"Failed to calculate count: {str(e)}")


class AverageKPI(KPI):
    """평균 KPI"""

    def __init__(self, kpi_id: str, name: str, query: str, column: str, **kwargs) -> None:
        super().__init__(kpi_id, name, **kwargs)
        self.query = query
        self.column = column

    async def calculate(self, **kwargs) -> Result[float, str]:
        """평균 계산"""
        try:
            import statistics

            from ..analytics.data_source import DataQuery

            data_query = DataQuery(query=self.query, parameters=kwargs)
            result = await self._execute_query(data_query)
            if result.is_failure():
                return Failure(f"Failed to calculate average: {result.error}")

            data = result.value
            if not data:
                return Success(0.0)

            values = []
            if isinstance(data, list):
                for row in data:
                    if isinstance(row, dict) and self.column in row:
                        value = row[self.column]
                        if value is not None:
                            try:
                                values.append(float(value))
                            except (ValueError, TypeError):
                                continue
                    elif isinstance(row, (int, float)):
                        try:
                            values.append(float(row))
                        except (ValueError, TypeError):
                            continue
            elif isinstance(data, dict) and self.column in data:
                try:
                    values = [float(data[self.column])]
                except (ValueError, TypeError):
                    pass

            if not values:
                return Success(0.0)

            # None 값 제거
            values = [v for v in values if v is not None]

            if not values:
                return Success(0.0)

            average = statistics.mean(values)
            return Success(float(average))
        except Exception as e:
            return Failure(f"Failed to calculate average: {str(e)}")


class PercentageKPI(KPI):
    """퍼센티지 KPI"""

    def __init__(
        self,
        kpi_id: str,
        name: str,
        numerator_query: str,
        denominator_query: str,
        **kwargs,
    ):
        super().__init__(kpi_id, name, **kwargs)
        self.numerator_query = numerator_query
        self.denominator_query = denominator_query

    async def calculate(self, **kwargs) -> Result[float, str]:
        """퍼센티지 계산"""
        if not self.data_source:
            return Failure("Data source not configured")
        try:
            num_query = DataQuery(query=self.numerator_query, parameters=kwargs)
            num_result = await self.data_source.execute_query(num_query)
            if num_result.is_failure():
                return num_result
            numerator = float(len(num_result.unwrap()))
            den_query = DataQuery(query=self.denominator_query, parameters=kwargs)
            den_result = await self.data_source.execute_query(den_query)
            if den_result.is_failure():
                return den_result
            denominator = float(len(den_result.unwrap()))
            if denominator == 0:
                return Success(0.0)
            percentage = numerator / denominator * 100.0
            percentage = float(
                Decimal(str(percentage)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            )
            return Success(percentage)
        except Exception as e:
            return Failure(f"Percentage calculation failed: {str(e)}")


class TrendKPI(KPI):
    """트렌드 KPI (시계열 분석)"""

    def __init__(
        self,
        kpi_id: str,
        name: str,
        query: str,
        time_column: str,
        value_column: str,
        **kwargs,
    ):
        super().__init__(kpi_id, name, **kwargs)
        self.query = query
        self.time_column = time_column
        self.value_column = value_column

    async def calculate(self, **kwargs) -> Result[float, str]:
        """트렌드 계산 (기울기 반환)"""
        if not self.data_source:
            return Failure("Data source not configured")
        try:
            data_query = DataQuery(query=self.query, parameters=kwargs)
            result = await self.data_source.execute_query(data_query)
            if result.is_failure():
                return result
            data = result.unwrap()
            if len(data) < 2:
                return Success(0.0)
            try:
                data.sort(
                    key=lambda x: (
                        datetime.fromisoformat(
                            x[self.time_column].replace("Z", "+00:00")
                        )
                        if hasattr(x[self.time_column], "__class__")
                        and x[self.time_column].__class__.__name__ == "str"
                        else x[self.time_column]
                    )
                )
            except Exception:
                pass
            values = []
            for i, row in enumerate(data):
                try:
                    value = float(row[self.value_column])
                    values = values + [(i, value)]
                except (ValueError, TypeError):
                    continue
            if len(values) < 2:
                return Success(0.0)
            n = len(values)
            x_values = [v[0] for v in values]
            y_values = [v[1] for v in values]
            x_mean = sum(x_values) / n
            y_mean = sum(y_values) / n
            numerator = sum(
                ((x_values[i] - x_mean) * (y_values[i] - y_mean) for i in range(n))
            )
            denominator = sum(((x_values[i] - x_mean) ** 2 for i in range(n)))
            if denominator == 0:
                return Success(0.0)
            slope = numerator / denominator
            return Success(slope)
        except Exception as e:
            return Failure(f"Trend calculation failed: {str(e)}")


class KPICalculator:
    """KPI 계산기"""

    def __init__(self) -> None:
        self._kpis = {}
        self._calculation_cache = {}
        self._cache_ttl = 300

    def register_kpi(self, kpi: KPI) -> Result[bool, str]:
        """KPI 등록"""
        try:
            self._kpis = {**self._kpis, kpi.kpi_id: kpi}
            return Success(True)
        except Exception as e:
            return Failure(f"KPI registration failed: {str(e)}")

    def unregister_kpi(self, kpi_id: str) -> Result[bool, str]:
        """KPI 등록 해제"""
        try:
            if kpi_id in self._kpis:
                del self._kpis[kpi_id]
            if kpi_id in self._calculation_cache:
                del self._calculation_cache[kpi_id]
            return Success(True)
        except Exception as e:
            return Failure(f"KPI unregistration failed: {str(e)}")

    def get_kpi(self, kpi_id: str) -> Result[KPI, str]:
        """KPI 조회"""
        if kpi_id not in self._kpis:
            return Failure(f"KPI not found: {kpi_id}")
        return Success(self._kpis[kpi_id])

    def list_kpis(self) -> Dict[str, KPI]:
        """모든 KPI 목록"""
        return self._kpis.copy()

    async def calculate_kpi(
        self, kpi_id: str, use_cache=True, **kwargs
    ) -> Result[KPIValue, str]:
        """KPI 계산"""
        if kpi_id not in self._kpis:
            return Failure(f"KPI not found: {kpi_id}")
        if use_cache and kpi_id in self._calculation_cache:
            cached_value = self._calculation_cache[kpi_id]
            if (datetime.now() - cached_value.timestamp).seconds < self._cache_ttl:
                return Success(cached_value)
        kpi = self._kpis[kpi_id]
        result = await kpi.update_value(**kwargs)
        if result.is_success():
            self._calculation_cache = {
                **self._calculation_cache,
                kpi_id: result.unwrap(),
            }
        return result

    async def calculate_all_kpis(
        self, use_cache=True, **kwargs
    ) -> Dict[str, Result[KPIValue, str]]:
        """모든 KPI 계산"""
        results = {}
        tasks = []
        for kpi_id in self._kpis.keys():
            task = self.calculate_kpi(kpi_id, use_cache, **kwargs)
            tasks = tasks + [(kpi_id, task)]
        for kpi_id, task in tasks:
            results[kpi_id] = {kpi_id: await task}
        return results

    def get_kpi_summary(self) -> Dict[str, Any]:
        """KPI 요약 정보"""
        summary = {
            "total_kpis": len(self._kpis),
            "by_type": {},
            "by_status": {},
            "last_updated": None,
        }
        for kpi in self._kpis.values():
            kpi_type = type(kpi).__name__
            summary = {
                **summary,
                "by_type": {
                    **summary["by_type"],
                    kpi_type: summary["by_type"].get(kpi_type, 0) + 1,
                },
            }
            current_value = kpi.get_current_value()
            if current_value:
                status = current_value.status.value
                summary = {
                    **summary,
                    "by_status": {
                        **summary["by_status"],
                        status: summary["by_status"].get(status, 0) + 1,
                    },
                }
                if (
                    summary["last_updated"] is None
                    or current_value.timestamp > summary["last_updated"]
                ):
                    summary = {
                        **summary,
                        "last_updated": current_value.timestamp,
                    }
        return summary


class KPIDashboard:
    """KPI 대시보드"""

    def __init__(self, dashboard_id: str, name: str, calculator: KPICalculator) -> None:
        self.dashboard_id = dashboard_id
        self.name = name
        self.calculator = calculator
        self.kpi_ids = []
        self.refresh_interval = 60
        self.auto_refresh = False
        self._last_refresh = None

    def add_kpi(self, kpi_id: str) -> Result[bool, str]:
        """KPI 추가"""
        if kpi_id not in self.calculator.list_kpis():
            return Failure(f"KPI not found: {kpi_id}")
        if kpi_id not in self.kpi_ids:
            self.kpi_ids = self.kpi_ids + [kpi_id]
        return Success(True)

    def remove_kpi(self, kpi_id: str) -> Result[bool, str]:
        """KPI 제거"""
        if kpi_id in self.kpi_ids:
            self.kpi_ids = [i for i in self.kpi_ids if i != kpi_id]
        return Success(True)

    async def refresh(self, **kwargs) -> Result[Dict[str, Any], str]:
        """대시보드 새로고침"""
        try:
            dashboard_data = {
                "dashboard_id": self.dashboard_id,
                "name": self.name,
                "refresh_time": datetime.now().isoformat(),
                "kpis": {},
            }
            for kpi_id in self.kpi_ids:
                result = await self.calculator.calculate_kpi(kpi_id, **kwargs)
                if result.is_success():
                    kpi_value = result.unwrap()
                    kpi = self.calculator.get_kpi(kpi_id).unwrap()
                    dashboard_data = {
                        **dashboard_data,
                        "kpis": {
                            **dashboard_data["kpis"],
                            kpi_id: {
                                "name": kpi.name,
                                "value": kpi_value.value,
                                "unit": kpi.unit,
                                "status": kpi_value.status.value,
                                "timestamp": kpi_value.timestamp.isoformat(),
                                "trend": kpi.get_trend(),
                                "targets": [
                                    {
                                        "value": t.target_value,
                                        "date": (
                                            t.target_date.isoformat()
                                            if t.target_date
                                            else None
                                        ),
                                        "description": t.description,
                                    }
                                    for t in kpi.targets
                                ],
                            },
                        },
                    }
                else:
                    dashboard_data = {
                        **dashboard_data,
                        "kpis": {
                            **dashboard_data["kpis"],
                            kpi_id: {"error": result.error},
                        },
                    }
            self._last_refresh = datetime.now()
            return Success(dashboard_data)
        except Exception as e:
            return Failure(f"Dashboard refresh failed: {str(e)}")

    def get_status_summary(self) -> Dict[str, int]:
        """상태 요약"""
        summary = {status.value: 0 for status in KPIStatus}
        for kpi_id in self.kpi_ids:
            kpi_result = self.calculator.get_kpi(kpi_id)
            if kpi_result.is_success():
                kpi = kpi_result.unwrap()
                current_value = kpi.get_current_value()
                if current_value:
                    summary = {
                        **summary,
                        current_value.status.value: summary[current_value.status.value]
                        + 1,
                    }
        return summary

    def set_auto_refresh(self, enabled: bool, interval=60) -> Result[bool, str]:
        """자동 새로고침 설정"""
        try:
            self.auto_refresh = enabled
            self.refresh_interval = interval
            if enabled:
                pass
            return Success(True)
        except Exception as e:
            return Failure(f"Auto refresh setup failed: {str(e)}")


async def create_kpi_dashboard(
    dashboard_id: str,
    name: str,
    kpi_configs: List[Dict[str, Any]],
    data_sources: Dict[str, DataSource],
) -> Result[KPIDashboard, str]:
    """KPI 대시보드 생성 헬퍼 함수"""
    try:
        calculator = KPICalculator()
        for config in kpi_configs:
            kpi_type = config.get("type", "count")
            data_source = data_sources.get(config.get("data_source"))
            match kpi_type:
                case "count":
                    kpi = CountKPI(
                        kpi_id=config["id"],
                        name=config["name"],
                        query=config["query"],
                        description=config.get("description", ""),
                        unit=config.get("unit", ""),
                        data_source=data_source,
                    )
                case "average":
                    kpi = AverageKPI(
                        kpi_id=config["id"],
                        name=config["name"],
                        query=config["query"],
                        column=config["column"],
                        description=config.get("description", ""),
                        unit=config.get("unit", ""),
                        data_source=data_source,
                    )
                case "percentage":
                    kpi = PercentageKPI(
                        kpi_id=config["id"],
                        name=config["name"],
                        numerator_query=config["numerator_query"],
                        denominator_query=config["denominator_query"],
                        description=config.get("description", ""),
                        unit=config.get("unit", "%"),
                        data_source=data_source,
                    )
                case "trend":
                    kpi = TrendKPI(
                        kpi_id=config["id"],
                        name=config["name"],
                        query=config["query"],
                        time_column=config["time_column"],
                        value_column=config["value_column"],
                        description=config.get("description", ""),
                        unit=config.get("unit", ""),
                        data_source=data_source,
                    )
                case _:
                    return Failure(f"Unsupported KPI type: {kpi_type}")
            for threshold_config in config.get("thresholds", []):
                threshold = KPIThreshold(
                    threshold_id=threshold_config["id"],
                    name=threshold_config["name"],
                    threshold_type=ThresholdType(threshold_config["type"]),
                    values=threshold_config["values"],
                    status=KPIStatus(threshold_config["status"]),
                    message=threshold_config.get("message", ""),
                )
                kpi.add_threshold(threshold)
            for target_config in config.get("targets", []):
                target = KPITarget(
                    target_value=target_config["value"],
                    target_date=(
                        datetime.fromisoformat(target_config["date"])
                        if target_config.get("date")
                        else None
                    ),
                    description=target_config.get("description", ""),
                )
                kpi.add_target(target)
            calculator.register_kpi(kpi)
        dashboard = KPIDashboard(dashboard_id, name, calculator)
        for config in kpi_configs:
            dashboard.add_kpi(config["id"])
        return Success(dashboard)
    except Exception as e:
        return Failure(f"Dashboard creation failed: {str(e)}")


_global_kpi_calculator = None


def get_kpi_calculator() -> KPICalculator:
    """전역 KPI 계산기 가져오기"""
    global _global_kpi_calculator
    if _global_kpi_calculator is None:
        _global_kpi_calculator = KPICalculator()
    return _global_kpi_calculator


def create_count_kpi(
    kpi_id: str, name: str, query: str, data_source: DataSource
) -> CountKPI:
    """카운트 KPI 생성"""
    return CountKPI(kpi_id, name, query, data_source=data_source)


def create_average_kpi(
    kpi_id: str, name: str, query: str, column: str, data_source: DataSource
) -> AverageKPI:
    """평균 KPI 생성"""
    return AverageKPI(kpi_id, name, query, column, data_source=data_source)


def create_percentage_kpi(
    kpi_id: str, name: str, num_query: str, den_query: str, data_source: DataSource
) -> PercentageKPI:
    """퍼센티지 KPI 생성"""
    return PercentageKPI(kpi_id, name, num_query, den_query, data_source=data_source)


def create_threshold(
    threshold_id: str,
    name: str,
    threshold_type: ThresholdType,
    values: List[float],
    status: KPIStatus,
    message: str = "",
) -> KPIThreshold:
    """임계값 생성"""
    return KPIThreshold(threshold_id, name, threshold_type, values, status, message)
