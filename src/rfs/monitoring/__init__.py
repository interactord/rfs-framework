"""
RFS Framework 모니터링 시스템

Result 패턴 기반 로깅, 메트릭 수집, 성능 모니터링을 제공합니다.
Phase 3 구현: 운영 관측가능성(Observability) 완성
"""

from .metrics import (
    AlertCondition,
    MetricType,
    ResultAlertManager,
    ResultMetricsCollector,
    collect_flux_result_metric,
    collect_metric,
    collect_result_metric,
    create_alert_rule,
    get_dashboard_data,
    get_metrics_summary,
    setup_default_alerts,
    start_monitoring,
    stop_monitoring,
)
from .result_logging import (
    CorrelationContext,
    LoggingMonoResult,
    LogLevel,
    ResultLogger,
    configure_result_logging,
    create_logging_mono,
    get_correlation_id,
    log_flux_results,
    log_result_operation,
    with_correlation_id,
)

__all__ = [
    # 로깅 시스템
    "ResultLogger",
    "CorrelationContext",
    "log_result_operation",
    "with_correlation_id",
    "get_correlation_id",
    "LoggingMonoResult",
    "create_logging_mono",
    "log_flux_results",
    "configure_result_logging",
    "LogLevel",
    # 메트릭 시스템
    "ResultMetricsCollector",
    "ResultAlertManager",
    "MetricType",
    "AlertCondition",
    "collect_metric",
    "create_alert_rule",
    "get_metrics_summary",
    "start_monitoring",
    "stop_monitoring",
    "collect_result_metric",
    "collect_flux_result_metric",
    "setup_default_alerts",
    "get_dashboard_data",
]

__version__ = "3.0.0"
__author__ = "RFS Framework Team"
__description__ = "Result 패턴 통합 모니터링 시스템"
