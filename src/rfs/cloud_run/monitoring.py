"""
Cloud Monitoring Integration (RFS v4)

Cloud Monitoring 및 로깅 통합
- 커스텀 메트릭 수집 및 전송
- 구조화된 로깅 시스템
- 알림 및 대시보드 자동 생성
- 성능 모니터링 및 분석
"""

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

try:
    from google.cloud import logging as cloud_logging
    from google.cloud import monitoring_v3
    from google.cloud.monitoring_v3 import Point, TimeInterval, TimeSeries, TypedValue
    from google.protobuf.timestamp_pb2 import Timestamp
    from pydantic import BaseModel, ConfigDict, Field, field_validator

    GOOGLE_CLOUD_AVAILABLE = True
    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = object
    Field = lambda default=None, **kwargs: default
    monitoring_v3 = None
    cloud_logging = None
    GOOGLE_CLOUD_AVAILABLE = False
    PYDANTIC_AVAILABLE = False
from ..core.result import Failure, Result, Success
from ..events import Event, get_event_bus
from ..reactive import Flux, Mono

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """메트릭 유형"""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class LogLevel(str, Enum):
    """로그 레벨"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertSeverity(str, Enum):
    """알림 심각도"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


if PYDANTIC_AVAILABLE:

    class MetricDefinition(BaseModel):
        """메트릭 정의 (Pydantic v2)"""

        model_config = ConfigDict(
            str_strip_whitespace=True, validate_default=True, frozen=True
        )
        name: str = Field(
            ...,
            pattern="^[a-zA-Z][a-zA-Z0-9_]*$",
            max_length=100,
            description="메트릭 이름",
        )
        type: MetricType = Field(..., description="메트릭 유형")
        description: str = Field(..., max_length=500, description="메트릭 설명")
        unit: str = Field(default="1", max_length=50, description="측정 단위")
        labels: Dict[str, Any] = field(default_factory=dict)

        @field_validator("name")
        @classmethod
        def validate_metric_name(cls, v: str) -> str:
            """메트릭 이름 검증"""
            if not v.islower():
                raise ValueError("메트릭 이름은 소문자여야 합니다")
            return v

        def get_full_name(self, project_id: str) -> str:
            """전체 메트릭 이름 생성"""
            return f"custom.googleapis.com/rfs/{self.name}"

    class LogEntry(BaseModel):
        """로그 엔트리 (Pydantic v2)"""

        model_config = ConfigDict(
            str_strip_whitespace=True, validate_default=True, frozen=True
        )
        message: str = Field(..., max_length=10000, description="로그 메시지")
        level: LogLevel = Field(default=LogLevel.INFO, description="로그 레벨")
        timestamp: datetime = Field(
            default_factory=datetime.now, description="로그 발생 시간"
        )
        service_name: str = Field(default="rfs-service", description="서비스 이름")
        version: str = Field(default="1.0.0", description="서비스 버전")
        trace_id: str | None = Field(default=None, description="트레이스 ID")
        span_id: str | None = Field(default=None, description="스팬 ID")
        labels: Dict[str, Any] = field(default_factory=dict)
        extra_data: Dict[str, Any] = field(default_factory=dict)

        def to_cloud_logging_entry(self) -> Dict[str, Any]:
            """Cloud Logging 형식으로 변환"""
            entry = {
                "severity": self.level.value,
                "timestamp": self.timestamp.isoformat(),
                "textPayload": self.message,
                "resource": {
                    "type": "cloud_run_revision",
                    "labels": {
                        "service_name": self.service_name,
                        "revision_name": f"{self.service_name}-{self.version}",
                        "configuration_name": self.service_name,
                        "location": os.environ.get(
                            "GOOGLE_CLOUD_REGION", "us-central1"
                        ),
                    },
                },
                "labels": {**self.labels, "version": self.version},
            }
            if self.trace_id:
                entry = {
                    **entry,
                    "trace": {
                        "trace": f"projects/{os.environ.get('GOOGLE_CLOUD_PROJECT', '')}/traces/{self.trace_id}"
                    },
                }
            if self.span_id:
                entry["spanId"] = {"spanId": self.span_id}
            if self.extra_data:
                entry["jsonPayload"] = {"jsonPayload": self.extra_data}
            return entry

else:
    from dataclasses import dataclass, field

    @dataclass(frozen=True)
    class MetricDefinition:
        """메트릭 정의 (Fallback)"""

        name: str
        type: MetricType
        description: str
        unit = "1"
        labels: Dict[str, Any] = field(default_factory=dict)

        def get_full_name(self, project_id: str) -> str:
            return f"custom.googleapis.com/rfs/{self.name}"

    @dataclass(frozen=True)
    class LogEntry:
        """로그 엔트리 (Fallback)"""

        message: str
        level: LogLevel = LogLevel.INFO
        timestamp: datetime = field(default_factory=datetime.now)
        service_name = "rfs-service"
        version = "1.0.0"
        trace_id = None
        span_id = None
        labels: Dict[str, Any] = field(default_factory=dict)
        extra_data: Dict[str, Any] = field(default_factory=dict)

        def to_cloud_logging_entry(self) -> Dict[str, Any]:
            """Cloud Logging 형식으로 변환"""
            entry = {
                "jsonPayload": {
                    "message": self.message,
                    "level": self.level.value,
                    "service_name": self.service_name,
                    "version": self.version,
                    **self.extra_data,
                },
                "resource": {
                    "type": "cloud_run_revision",
                    "labels": {
                        "service_name": self.service_name,
                        "revision_name": f"{self.service_name}-{self.version}",
                        "configuration_name": self.service_name,
                        "location": "us-central1",
                    },
                },
                "severity": self.level.name,
                "timestamp": self.timestamp.isoformat() + "Z",
                "labels": self.labels,
            }

            if self.trace_id:
                entry["trace"] = (
                    f"projects/{os.environ.get('GOOGLE_CLOUD_PROJECT', 'test-project')}/traces/{self.trace_id}"
                )

            if self.span_id:
                entry["spanId"] = self.span_id

            return entry


class CloudMonitoringClient:
    """Cloud Monitoring 클라이언트"""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.project_path = f"projects/{project_id}"
        self.monitoring_client = None
        self.logging_client = None
        if GOOGLE_CLOUD_AVAILABLE:
            try:
                self.monitoring_client = monitoring_v3.MetricServiceClient()
                self.logging_client = cloud_logging.Client(project=project_id)
            except Exception as e:
                logger.warning(f"Google Cloud 클라이언트 초기화 실패: {e}")
        self.registered_metrics = {}
        self.metrics_buffer: List[Dict[str, Any]] = []
        self.logs_buffer = []
        self.buffer_size = 100
        self.flush_interval = 30
        self.flush_task = None
        self._running = False

    async def initialize(self):
        """모니터링 클라이언트 초기화"""
        await self._register_default_metrics()
        self._running = True
        self.flush_task = asyncio.create_task(self._flush_scheduler())
        logger.info("Cloud Monitoring 클라이언트가 초기화되었습니다")

    async def _register_default_metrics(self):
        """기본 메트릭들 등록"""
        default_metrics = [
            MetricDefinition(
                name="request_count",
                type=MetricType.COUNTER,
                description="HTTP 요청 수",
                unit="1",
                labels={"method": "", "status_code": ""},
            ),
            MetricDefinition(
                name="request_duration",
                type=MetricType.HISTOGRAM,
                description="HTTP 요청 처리 시간",
                unit="ms",
            ),
            MetricDefinition(
                name="memory_usage",
                type=MetricType.GAUGE,
                description="메모리 사용률",
                unit="%",
            ),
            MetricDefinition(
                name="cpu_usage",
                type=MetricType.GAUGE,
                description="CPU 사용률",
                unit="%",
            ),
            MetricDefinition(
                name="active_connections",
                type=MetricType.GAUGE,
                description="활성 연결 수",
                unit="1",
            ),
            MetricDefinition(
                name="task_queue_size",
                type=MetricType.GAUGE,
                description="작업 큐 크기",
                unit="1",
                labels={"queue_name": ""},
            ),
            MetricDefinition(
                name="error_rate",
                type=MetricType.GAUGE,
                description="에러 발생률",
                unit="%",
            ),
        ]
        for metric in default_metrics:
            await self.register_metric(metric)

    async def register_metric(self, metric: MetricDefinition) -> Result[None, str]:
        """메트릭 등록"""
        try:
            if GOOGLE_CLOUD_AVAILABLE and self.monitoring_client:
                descriptor = {
                    "type": metric.get_full_name(self.project_id),
                    "metric_kind": self._get_metric_kind(metric.type),
                    "value_type": monitoring_v3.MetricDescriptor.ValueType.DOUBLE,
                    "description": metric.description,
                    "display_name": metric.name.replace("_", " ").title(),
                    "unit": metric.unit,
                }
                if metric.labels:
                    descriptor = {
                        **descriptor,
                        "labels": {
                            "labels": [
                                {
                                    "key": key,
                                    "value_type": monitoring_v3.LabelDescriptor.ValueType.STRING,
                                    "description": f"Label for {key}",
                                }
                                for key in metric.labels.keys()
                            ]
                        },
                    }
                try:
                    self.monitoring_client.create_metric_descriptor(
                        name=self.project_path, metric_descriptor=descriptor
                    )
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"메트릭 디스크립터 생성 실패: {e}")
            self.registered_metrics = {**self.registered_metrics, metric.name: metric}
            logger.info(f"메트릭 등록 완료: {metric.name}")
            return Success(None)
        except Exception as e:
            error_msg = f"메트릭 등록 실패: {metric.name} - {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    def _get_metric_kind(
        self, metric_type: MetricType
    ) -> Any:  # monitoring_v3.MetricDescriptor.MetricKind when available
        """메트릭 유형을 Cloud Monitoring 형식으로 변환"""
        if not monitoring_v3:
            return None
        match metric_type:
            case MetricType.COUNTER:
                return monitoring_v3.MetricDescriptor.MetricKind.CUMULATIVE
            case MetricType.GAUGE:
                return monitoring_v3.MetricDescriptor.MetricKind.GAUGE
            case MetricType.HISTOGRAM | MetricType.SUMMARY:
                return monitoring_v3.MetricDescriptor.MetricKind.CUMULATIVE
            case _:
                return monitoring_v3.MetricDescriptor.MetricKind.GAUGE

    async def record_metric(
        self,
        metric_name: str,
        value: float,
        labels=None,
        timestamp=None,
    ) -> Result[None, str]:
        """메트릭 값 기록"""
        try:
            if metric_name not in self.registered_metrics:
                return Failure(f"등록되지 않은 메트릭: {metric_name}")

            metric_def = self.registered_metrics[metric_name]
            metric_data = {
                "name": metric_name,
                "value": value,
                "labels": labels or {},
                "timestamp": timestamp or datetime.now(),
                "definition": metric_def,
            }
            self.metrics_buffer = self.metrics_buffer + [metric_data]
            if len(self.metrics_buffer) >= self.buffer_size:
                await self._flush_metrics()
            return Success(None)
        except Exception as e:
            error_msg = f"메트릭 기록 실패: {metric_name} - {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def _flush_metrics(self):
        """메트릭 배치 전송"""
        if not self.metrics_buffer:
            return
        if not GOOGLE_CLOUD_AVAILABLE or not self.monitoring_client:
            logger.debug(f"메트릭 {len(self.metrics_buffer)}개 기록 (로컬)")
            metrics_buffer = {}
            return
        try:
            time_series_list = []
            for metric_data in self.metrics_buffer:
                metric_def = metric_data["definition"]
                time_series = TimeSeries()
                time_series.metric.type = metric_def.get_full_name(self.project_id)
                for key, value in metric_data.get("labels").items():
                    time_series.metric.labels = {
                        **time_series.metric.labels,
                        key: str(value),
                    }
                time_series.resource.type = "cloud_run_revision"
                time_series.resource.labels = {
                    **time_series.resource.labels,
                    "service_name": os.environ.get("K_SERVICE", "rfs-service"),
                }
                time_series.resource.labels = {
                    **time_series.resource.labels,
                    "revision_name": os.environ.get("K_REVISION", "unknown"),
                }
                time_series.resource.labels = {
                    **time_series.resource.labels,
                    "location": os.environ.get("GOOGLE_CLOUD_REGION", "us-central1"),
                }
                point = Point()
                point.value.double_value = metric_data["value"]
                timestamp = Timestamp()
                timestamp.FromDatetime(metric_data.get("timestamp"))
                point.interval.end_time = timestamp
                time_series.points = time_series.points + [point]
                time_series_list = time_series_list + [time_series]
            self.monitoring_client.create_time_series(
                name=self.project_path, time_series=time_series_list
            )
            logger.debug(f"메트릭 {len(time_series_list)}개 전송 완료")
        except Exception as e:
            logger.error(f"메트릭 전송 실패: {e}")
        finally:
            self.metrics_buffer = {}

    async def log_structured(self, entry: LogEntry) -> Result[None, str]:
        """구조화된 로그 기록"""
        try:
            self.logs_buffer = self.logs_buffer + [entry]
            if len(self.logs_buffer) >= self.buffer_size:
                await self._flush_logs()
            if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                await self._flush_logs()
            return Success(None)
        except Exception as e:
            error_msg = f"로그 기록 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def _flush_logs(self):
        """로그 배치 전송"""
        if not self.logs_buffer:
            return
        if not GOOGLE_CLOUD_AVAILABLE or not self.logging_client:
            for log_entry in self.logs_buffer:
                logger.log(
                    getattr(logging, log_entry.level.value),
                    log_entry.message,
                    extra=log_entry.extra_data,
                )
            self.logs_buffer = []
            return
        try:
            cloud_logger = self.logging_client.logger("rfs-application")
            for log_entry in self.logs_buffer:
                cloud_entry = log_entry.to_cloud_logging_entry()
                match log_entry.level:
                    case LogLevel.DEBUG:
                        cloud_logger.log_text(log_entry.message, severity="DEBUG")
                    case LogLevel.INFO:
                        cloud_logger.log_text(log_entry.message, severity="INFO")
                    case LogLevel.WARNING:
                        cloud_logger.log_text(log_entry.message, severity="WARNING")
                    case LogLevel.ERROR:
                        cloud_logger.log_text(log_entry.message, severity="ERROR")
                    case LogLevel.CRITICAL:
                        cloud_logger.log_text(log_entry.message, severity="CRITICAL")
            logger.debug(f"로그 {len(self.logs_buffer)}개 전송 완료")
        except Exception as e:
            logger.error(f"로그 전송 실패: {e}")
        finally:
            self.logs_buffer = []

    async def _flush_scheduler(self):
        """정기적 배치 전송"""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush_metrics()
                await self._flush_logs()
            except Exception as e:
                logger.error(f"배치 전송 스케줄러 오류: {e}")

    async def shutdown(self):
        """모니터링 클라이언트 종료"""
        self._running = False
        if self.flush_task:
            self.flush_task.cancel()
            try:
                await self.flush_task
            except asyncio.CancelledError:
                pass
        await self._flush_metrics()
        await self._flush_logs()
        logger.info("Cloud Monitoring 클라이언트가 종료되었습니다")


class PerformanceMonitor:
    """성능 모니터링 도우미"""

    def __init__(self, monitoring_client: CloudMonitoringClient):
        self.client = monitoring_client
        self.active_requests = {}

    def start_request_monitoring(self, request_id: str, method: str, path: str) -> None:
        """요청 모니터링 시작"""
        self.active_requests = {**self.active_requests, request_id: time.time()}
        asyncio.create_task(
            self.client.record_metric(
                "request_count",
                1.0,
                {"method": method, "path": path, "status": "started"},
            )
        )

    def end_request_monitoring(
        self, request_id: str, status_code: int, method: str, path: str
    ) -> None:
        """요청 모니터링 종료"""
        if request_id not in self.active_requests:
            return
        start_time = self.active_requests[request_id]
        self.active_requests = {
            k: v for k, v in self.active_requests.items() if k != request_id
        }
        duration_ms = (time.time() - start_time) * 1000
        labels = {"method": method, "path": path, "status_code": str(status_code)}
        asyncio.create_task(
            self.client.record_metric("request_duration", duration_ms, labels)
        )
        asyncio.create_task(
            self.client.record_metric(
                "request_count", 1.0, {**labels, "status": "completed"}
            )
        )
        if status_code >= 400:
            asyncio.create_task(self.client.record_metric("error_rate", 1.0, labels))

    def request_monitor(self, method: str, path: str):
        """요청 모니터링 데코레이터"""

        def decorator(func: Callable):

            async def wrapper(*args, **kwargs):
                import uuid

                request_id = str(uuid.uuid4())
                self.start_request_monitoring(request_id, method, path)
                try:
                    result = await func(*args, **kwargs)
                    self.end_request_monitoring(request_id, 200, method, path)
                    return result
                except Exception as e:
                    self.end_request_monitoring(request_id, 500, method, path)
                    raise

            return wrapper

        return decorator


_monitoring_client = None


async def get_monitoring_client(project_id: str = None) -> CloudMonitoringClient:
    """모니터링 클라이언트 인스턴스 획득"""
    global _monitoring_client
    if _monitoring_client is None:
        if project_id is None:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            raise ValueError("프로젝트 ID가 필요합니다")
        _monitoring_client = CloudMonitoringClient(project_id)
        await _monitoring_client.initialize()
    return _monitoring_client


async def record_metric(
    metric_name: str, value: float, labels=None
) -> Result[None, str]:
    """메트릭 기록"""
    client = await get_monitoring_client()
    return await client.record_metric(metric_name, value, labels)


async def log_info(message: str, **extra_data):
    """정보 로그 기록"""
    client = await get_monitoring_client()
    entry = LogEntry(message=message, level=LogLevel.INFO, extra_data=extra_data)
    return await client.log_structured(entry)


async def log_warning(message: str, **extra_data):
    """경고 로그 기록"""
    client = await get_monitoring_client()
    entry = LogEntry(message=message, level=LogLevel.WARNING, extra_data=extra_data)
    return await client.log_structured(entry)


async def log_error(message: str, **extra_data):
    """에러 로그 기록"""
    client = await get_monitoring_client()
    entry = LogEntry(message=message, level=LogLevel.ERROR, extra_data=extra_data)
    return await client.log_structured(entry)


def monitor_performance(method="GET", path="/"):
    """성능 모니터링 데코레이터"""

    def decorator(func: Callable):

        async def wrapper(*args, **kwargs):
            client = await get_monitoring_client()
            monitor = PerformanceMonitor(client)
            decorated_func = monitor.request_monitor(method, path)(func)
            return await decorated_func(*args, **kwargs)

        return wrapper

    return decorator
