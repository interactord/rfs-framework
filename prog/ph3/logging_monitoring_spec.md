# 로깅 및 모니터링 시스템 상세 사양서

**문서 버전**: 1.0  
**작성일**: 2025-09-03  
**상태**: 설계 완료

---

## 📋 개요

Phase 1의 MonoResult/FluxResult와 Phase 2의 FastAPI 통합을 기반으로, 프로덕션 환경에서 Result 패턴을 완전하게 관측하고 모니터링할 수 있는 시스템의 상세 사양입니다.

---

## 🎯 1. Result 로깅 확장 (`result_logging.py`)

### 1.1 MonoResult 로깅 메서드 확장

**목적**: MonoResult에 로깅 기능을 추가하여 각 단계별 실행 과정을 추적

#### 구현 사양
```python
# MonoResult 클래스에 추가할 메서드들
class MonoResult(Generic[T, E]):
    
    def log_step(self, step_name: str, log_level: str = "INFO") -> "MonoResult[T, E]":
        """
        파이프라인의 특정 단계를 로깅
        
        Args:
            step_name: 단계 이름 (예: "user_validation", "data_transform")
            log_level: 로그 레벨 ("DEBUG", "INFO", "WARNING", "ERROR")
            
        Returns:
            MonoResult: 로깅이 추가된 MonoResult (체이닝 가능)
            
        Example:
            result = await (
                MonoResult.from_async_result(fetch_user)
                .log_step("user_fetch", "INFO")
                .bind_result(validate_user)
                .log_step("user_validation", "DEBUG")  
                .to_result()
            )
        """
        async def logged_step():
            start_time = time.time()
            correlation_id = get_correlation_id()
            
            logger.log(
                getattr(logging, log_level),
                f"[{correlation_id}] 단계 시작: {step_name}"
            )
            
            try:
                result = await self._async_func()
                processing_time = (time.time() - start_time) * 1000
                
                if result.is_success():
                    logger.log(
                        getattr(logging, log_level),
                        f"[{correlation_id}] 단계 성공: {step_name} "
                        f"({processing_time:.2f}ms)"
                    )
                    
                    # 구조화된 로그 엔트리 생성
                    log_entry = ResultLogEntry(
                        timestamp=datetime.now(),
                        correlation_id=correlation_id,
                        operation_name=get_current_operation_name(),
                        step_name=step_name,
                        result_type="success",
                        processing_time_ms=processing_time,
                        success_type=type(result.unwrap()).__name__
                    )
                    structured_logger.log_result_entry(log_entry)
                    
                else:
                    error = result.unwrap_error()
                    logger.log(
                        logging.WARNING,
                        f"[{correlation_id}] 단계 실패: {step_name} "
                        f"({processing_time:.2f}ms) - {error}"
                    )
                    
                    # 구조화된 에러 로그
                    log_entry = ResultLogEntry(
                        timestamp=datetime.now(),
                        correlation_id=correlation_id,
                        operation_name=get_current_operation_name(),
                        step_name=step_name,
                        result_type="error",
                        processing_time_ms=processing_time,
                        error_type=type(error).__name__,
                        error_code=getattr(error, 'code', None),
                        error_message=str(error)
                    )
                    structured_logger.log_result_entry(log_entry)
                
                return result
                
            except Exception as e:
                processing_time = (time.time() - start_time) * 1000
                logger.error(
                    f"[{correlation_id}] 단계 예외: {step_name} "
                    f"({processing_time:.2f}ms) - {e}"
                )
                
                # 예외 로그
                log_entry = ResultLogEntry(
                    timestamp=datetime.now(),
                    correlation_id=correlation_id,
                    operation_name=get_current_operation_name(),
                    step_name=step_name,
                    result_type="error",
                    processing_time_ms=processing_time,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                structured_logger.log_result_entry(log_entry)
                
                return Failure(e)
        
        return MonoResult(logged_step)
    
    def log_error(self, error_context: str) -> "MonoResult[T, E]":
        """
        에러 발생 시에만 로깅 (성공 시에는 로깅하지 않음)
        
        Args:
            error_context: 에러 컨텍스트 설명
            
        Example:
            result = await (
                MonoResult.from_async_result(risky_operation)
                .log_error("critical_operation_failure")
                .to_result()
            )
        """
        async def error_logged():
            result = await self._async_func()
            
            if result.is_failure():
                correlation_id = get_correlation_id()
                error = result.unwrap_error()
                
                logger.error(
                    f"[{correlation_id}] 에러 발생 - {error_context}: {error}"
                )
                
                # 에러 전용 구조화된 로깅
                log_entry = ResultLogEntry(
                    timestamp=datetime.now(),
                    correlation_id=correlation_id,
                    operation_name=get_current_operation_name(),
                    step_name=error_context,
                    result_type="error",
                    processing_time_ms=0.0,  # 이미 처리 완료된 상태
                    error_type=type(error).__name__,
                    error_code=getattr(error, 'code', None),
                    error_message=str(error)
                )
                structured_logger.log_result_entry(log_entry)
            
            return result
        
        return MonoResult(error_logged)
    
    def log_performance(self, performance_threshold_ms: float = 1000.0) -> "MonoResult[T, E]":
        """
        성능 임계값을 초과하는 경우에만 로깅
        
        Args:
            performance_threshold_ms: 성능 임계값 (밀리초)
            
        Example:
            result = await (
                MonoResult.from_async_result(slow_operation)
                .log_performance(500.0)  # 500ms 초과 시 로깅
                .to_result()
            )
        """
        async def performance_logged():
            start_time = time.time()
            result = await self._async_func()
            processing_time = (time.time() - start_time) * 1000
            
            if processing_time > performance_threshold_ms:
                correlation_id = get_correlation_id()
                logger.warning(
                    f"[{correlation_id}] 성능 임계값 초과: "
                    f"{processing_time:.2f}ms (임계값: {performance_threshold_ms}ms)"
                )
                
                # 성능 로그
                log_entry = ResultLogEntry(
                    timestamp=datetime.now(),
                    correlation_id=correlation_id,
                    operation_name=get_current_operation_name(),
                    step_name="performance_check",
                    result_type="success" if result.is_success() else "error",
                    processing_time_ms=processing_time,
                    metadata={
                        "performance_threshold_ms": performance_threshold_ms,
                        "threshold_exceeded": True
                    }
                )
                structured_logger.log_result_entry(log_entry)
            
            return result
        
        return MonoResult(performance_logged)
```

### 1.2 @log_result_operation 데코레이터

**목적**: 전체 작업(operation)을 자동으로 로깅하는 데코레이터

#### 구현 사양
```python
from functools import wraps
from typing import Callable, Optional
import uuid

def log_result_operation(
    operation_name: str,
    log_level: str = "INFO",
    include_args: bool = False,
    mask_sensitive: bool = True,
    performance_threshold_ms: Optional[float] = None
) -> Callable:
    """
    Result를 반환하는 함수의 전체 실행을 자동 로깅
    
    Args:
        operation_name: 작업 이름 (메트릭 수집에도 사용됨)
        log_level: 로그 레벨
        include_args: 함수 인자를 로그에 포함할지 여부
        mask_sensitive: 민감 정보 마스킹 여부
        performance_threshold_ms: 성능 임계값 (초과 시 WARNING 로그)
        
    Example:
        @log_result_operation("user_retrieval", include_args=True)
        async def get_user(user_id: str) -> Result[User, APIError]:
            return await user_service.get_user(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Correlation ID 생성 및 설정
            correlation_id = str(uuid.uuid4())
            set_correlation_id(correlation_id)
            set_current_operation_name(operation_name)
            
            start_time = time.time()
            
            # 함수 인자 로깅 (옵션)
            args_info = ""
            if include_args:
                masked_args = mask_sensitive_data(args, kwargs) if mask_sensitive else (args, kwargs)
                args_info = f" - 인자: {masked_args}"
            
            logger.log(
                getattr(logging, log_level),
                f"[{correlation_id}] 작업 시작: {operation_name}{args_info}"
            )
            
            try:
                result = await func(*args, **kwargs)
                processing_time = (time.time() - start_time) * 1000
                
                # 성능 임계값 체크
                log_level_final = log_level
                if performance_threshold_ms and processing_time > performance_threshold_ms:
                    log_level_final = "WARNING"
                
                if result.is_success():
                    logger.log(
                        getattr(logging, log_level_final),
                        f"[{correlation_id}] 작업 완료: {operation_name} "
                        f"({processing_time:.2f}ms) - 성공"
                    )
                else:
                    error = result.unwrap_error()
                    logger.log(
                        logging.WARNING,
                        f"[{correlation_id}] 작업 완료: {operation_name} "
                        f"({processing_time:.2f}ms) - 실패: {error}"
                    )
                
                # 메트릭 수집
                metrics_collector = ResultMetricsCollector.instance()
                metrics_collector.record_operation(
                    operation_name=operation_name,
                    success=result.is_success(),
                    processing_time_ms=processing_time,
                    error_type=type(result.unwrap_error()).__name__ if result.is_failure() else None
                )
                
                # 구조화된 작업 로그
                log_entry = ResultLogEntry(
                    timestamp=datetime.now(),
                    correlation_id=correlation_id,
                    operation_name=operation_name,
                    step_name="operation_complete",
                    result_type="success" if result.is_success() else "error",
                    processing_time_ms=processing_time,
                    success_type=type(result.unwrap()).__name__ if result.is_success() else None,
                    error_type=type(result.unwrap_error()).__name__ if result.is_failure() else None,
                    error_code=getattr(result.unwrap_error(), 'code', None) if result.is_failure() else None,
                    error_message=str(result.unwrap_error()) if result.is_failure() else None,
                    metadata={
                        "function_name": func.__name__,
                        "module_name": func.__module__
                    }
                )
                structured_logger.log_result_entry(log_entry)
                
                return result
                
            except Exception as e:
                processing_time = (time.time() - start_time) * 1000
                logger.error(
                    f"[{correlation_id}] 작업 예외: {operation_name} "
                    f"({processing_time:.2f}ms) - {type(e).__name__}: {e}"
                )
                
                # 예외 메트릭 기록
                metrics_collector = ResultMetricsCollector.instance()
                metrics_collector.record_operation(
                    operation_name=operation_name,
                    success=False,
                    processing_time_ms=processing_time,
                    error_type=type(e).__name__
                )
                
                # 예외를 Result로 변환하여 반환
                api_error = APIError.from_exception(e)
                return Failure(api_error)
                
            finally:
                # Correlation ID 정리
                clear_correlation_id()
                clear_current_operation_name()
        
        return wrapper
    
    return decorator
```

---

## 📊 2. 메트릭 수집 시스템 (`metrics.py`)

### 2.1 ResultMetricsCollector 클래스

**목적**: Result 패턴 기반 작업의 성능 메트릭을 실시간으로 수집

#### 구현 사양
```python
from collections import defaultdict, deque
from threading import Lock
import threading
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import statistics

class ResultMetricsCollector:
    """Result 패턴 메트릭 수집기 (Singleton)"""
    
    _instance = None
    _instance_lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self._metrics_lock = Lock()
            self._operation_metrics: Dict[str, deque] = defaultdict(
                lambda: deque(maxlen=10000)  # 최대 10,000개 기록 유지
            )
            self._error_counts: Dict[str, Dict[str, int]] = defaultdict(
                lambda: defaultdict(int)
            )
            self._hourly_stats: Dict[str, Dict[int, int]] = defaultdict(
                lambda: defaultdict(int)
            )
    
    def record_operation(
        self,
        operation_name: str,
        success: bool,
        processing_time_ms: float,
        error_type: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """
        작업 실행 결과를 메트릭으로 기록
        
        Args:
            operation_name: 작업 이름
            success: 성공 여부
            processing_time_ms: 처리 시간 (밀리초)
            error_type: 에러 타입 (실패 시)
            user_id: 사용자 ID (옵션)
            metadata: 추가 메타데이터
        """
        with self._metrics_lock:
            timestamp = datetime.now()
            
            # 기본 메트릭 기록
            metric_entry = {
                'timestamp': timestamp,
                'success': success,
                'processing_time_ms': processing_time_ms,
                'error_type': error_type,
                'user_id': user_id,
                'metadata': metadata or {}
            }
            
            self._operation_metrics[operation_name].append(metric_entry)
            
            # 에러 카운트 업데이트
            if not success and error_type:
                self._error_counts[operation_name][error_type] += 1
            
            # 시간대별 통계 업데이트
            hour = timestamp.hour
            self._hourly_stats[operation_name][hour] += 1
    
    def get_operation_metrics(
        self,
        operation_name: str,
        time_range: str = "1h"
    ) -> OperationMetrics:
        """
        특정 작업의 메트릭을 조회
        
        Args:
            operation_name: 작업 이름
            time_range: 시간 범위 ("1h", "1d", "1w")
            
        Returns:
            OperationMetrics: 집계된 메트릭 데이터
        """
        with self._metrics_lock:
            # 시간 범위 필터링
            cutoff_time = self._get_cutoff_time(time_range)
            filtered_metrics = [
                m for m in self._operation_metrics[operation_name]
                if m['timestamp'] >= cutoff_time
            ]
            
            if not filtered_metrics:
                return OperationMetrics(
                    operation_name=operation_name,
                    time_window=time_range,
                    total_requests=0,
                    successful_requests=0,
                    failed_requests=0,
                    success_rate=0.0,
                    avg_response_time_ms=0.0,
                    p50_response_time_ms=0.0,
                    p90_response_time_ms=0.0,
                    p99_response_time_ms=0.0,
                    max_response_time_ms=0.0,
                    error_breakdown={},
                    top_errors=[],
                    avg_memory_usage_mb=0.0,
                    avg_cpu_usage_percent=0.0,
                    hourly_distribution={}
                )
            
            # 기본 통계
            total_requests = len(filtered_metrics)
            successful_requests = sum(1 for m in filtered_metrics if m['success'])
            failed_requests = total_requests - successful_requests
            success_rate = successful_requests / total_requests if total_requests > 0 else 0.0
            
            # 응답 시간 통계
            response_times = [m['processing_time_ms'] for m in filtered_metrics]
            avg_response_time = statistics.mean(response_times)
            
            # 백분위수 계산
            sorted_times = sorted(response_times)
            p50_response_time = self._percentile(sorted_times, 0.5)
            p90_response_time = self._percentile(sorted_times, 0.9)
            p99_response_time = self._percentile(sorted_times, 0.99)
            max_response_time = max(response_times)
            
            # 에러 통계
            error_breakdown = defaultdict(int)
            for m in filtered_metrics:
                if not m['success'] and m['error_type']:
                    error_breakdown[m['error_type']] += 1
            
            top_errors = sorted(
                error_breakdown.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            # 시간대별 분포
            hourly_distribution = defaultdict(int)
            for m in filtered_metrics:
                hour = m['timestamp'].hour
                hourly_distribution[hour] += 1
            
            return OperationMetrics(
                operation_name=operation_name,
                time_window=time_range,
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                success_rate=success_rate,
                avg_response_time_ms=avg_response_time,
                p50_response_time_ms=p50_response_time,
                p90_response_time_ms=p90_response_time,
                p99_response_time_ms=p99_response_time,
                max_response_time_ms=max_response_time,
                error_breakdown=dict(error_breakdown),
                top_errors=top_errors,
                avg_memory_usage_mb=0.0,  # TODO: 메모리 사용량 수집
                avg_cpu_usage_percent=0.0,  # TODO: CPU 사용량 수집
                hourly_distribution=dict(hourly_distribution)
            )
    
    def _get_cutoff_time(self, time_range: str) -> datetime:
        """시간 범위에 따른 cut-off 시간 계산"""
        now = datetime.now()
        if time_range == "1h":
            return now - timedelta(hours=1)
        elif time_range == "1d":
            return now - timedelta(days=1)
        elif time_range == "1w":
            return now - timedelta(weeks=1)
        else:
            return now - timedelta(hours=1)
    
    def _percentile(self, sorted_data: List[float], percentile: float) -> float:
        """백분위수 계산"""
        if not sorted_data:
            return 0.0
        
        index = percentile * (len(sorted_data) - 1)
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    @classmethod
    def instance(cls) -> "ResultMetricsCollector":
        """싱글톤 인스턴스 접근"""
        return cls()
```

---

## 🚨 3. 알림 시스템 (`alerts.py`)

### 3.1 임계값 기반 알림

#### 구현 사양
```python
from enum import Enum
from dataclasses import dataclass
from typing import Callable, Dict, Any, List
import asyncio
from abc import ABC, abstractmethod

class AlertSeverity(str, Enum):
    """알림 심각도"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AlertCondition(str, Enum):
    """알림 조건"""
    ERROR_RATE_THRESHOLD = "error_rate_threshold"
    RESPONSE_TIME_THRESHOLD = "response_time_threshold"
    FAILURE_COUNT_THRESHOLD = "failure_count_threshold"
    CONSECUTIVE_FAILURES = "consecutive_failures"

@dataclass
class AlertRule:
    """알림 규칙"""
    name: str
    operation_name: str
    condition: AlertCondition
    threshold_value: float
    time_window: str  # "5m", "1h", "1d"
    severity: AlertSeverity
    enabled: bool = True
    
    # 알림 설정
    cooldown_minutes: int = 15  # 동일 알림 재발송 방지 시간
    
    def __post_init__(self):
        self.last_triggered = None

@dataclass
class AlertEvent:
    """알림 이벤트"""
    rule_name: str
    operation_name: str
    severity: AlertSeverity
    message: str
    current_value: float
    threshold_value: float
    timestamp: datetime
    metadata: Dict[str, Any]

class AlertNotifier(ABC):
    """알림 전송 인터페이스"""
    
    @abstractmethod
    async def send_alert(self, alert_event: AlertEvent) -> bool:
        """알림 전송"""
        pass

class LogAlertNotifier(AlertNotifier):
    """로그 기반 알림 전송기"""
    
    async def send_alert(self, alert_event: AlertEvent) -> bool:
        logger = logging.getLogger("rfs.alerts")
        logger.log(
            self._severity_to_log_level(alert_event.severity),
            f"🚨 알림: {alert_event.rule_name} - {alert_event.message}"
        )
        return True
    
    def _severity_to_log_level(self, severity: AlertSeverity) -> int:
        mapping = {
            AlertSeverity.LOW: logging.INFO,
            AlertSeverity.MEDIUM: logging.WARNING,
            AlertSeverity.HIGH: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL
        }
        return mapping.get(severity, logging.WARNING)

class ResultAlertManager:
    """Result 패턴 기반 알림 관리자"""
    
    def __init__(self):
        self._alert_rules: Dict[str, AlertRule] = {}
        self._notifiers: List[AlertNotifier] = []
        self._metrics_collector = ResultMetricsCollector.instance()
        self._check_interval = 60  # 1분마다 체크
        self._running = False
        self._check_task = None
    
    def add_alert_rule(self, rule: AlertRule):
        """알림 규칙 추가"""
        self._alert_rules[rule.name] = rule
    
    def remove_alert_rule(self, rule_name: str):
        """알림 규칙 제거"""
        self._alert_rules.pop(rule_name, None)
    
    def add_notifier(self, notifier: AlertNotifier):
        """알림 전송기 추가"""
        self._notifiers.append(notifier)
    
    async def start_monitoring(self):
        """알림 모니터링 시작"""
        if self._running:
            return
        
        self._running = True
        self._check_task = asyncio.create_task(self._monitoring_loop())
    
    async def stop_monitoring(self):
        """알림 모니터링 중지"""
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
    
    async def _monitoring_loop(self):
        """알림 모니터링 루프"""
        while self._running:
            try:
                await self._check_all_rules()
                await asyncio.sleep(self._check_interval)
            except Exception as e:
                logger.exception(f"Alert monitoring error: {e}")
                await asyncio.sleep(self._check_interval)
    
    async def _check_all_rules(self):
        """모든 알림 규칙 체크"""
        for rule in self._alert_rules.values():
            if not rule.enabled:
                continue
                
            try:
                alert_event = await self._evaluate_rule(rule)
                if alert_event:
                    await self._send_alert(alert_event)
                    rule.last_triggered = datetime.now()
            except Exception as e:
                logger.exception(f"Error evaluating alert rule {rule.name}: {e}")
    
    async def _evaluate_rule(self, rule: AlertRule) -> Optional[AlertEvent]:
        """알림 규칙 평가"""
        # Cooldown 체크
        if rule.last_triggered:
            cooldown_delta = timedelta(minutes=rule.cooldown_minutes)
            if datetime.now() - rule.last_triggered < cooldown_delta:
                return None
        
        # 메트릭 조회
        metrics = self._metrics_collector.get_operation_metrics(
            rule.operation_name,
            rule.time_window
        )
        
        # 조건별 평가
        current_value = None
        message = ""
        
        if rule.condition == AlertCondition.ERROR_RATE_THRESHOLD:
            current_value = 1.0 - metrics.success_rate  # 에러율
            if current_value > rule.threshold_value:
                message = (
                    f"에러율이 임계값을 초과했습니다: "
                    f"{current_value:.2%} > {rule.threshold_value:.2%}"
                )
        
        elif rule.condition == AlertCondition.RESPONSE_TIME_THRESHOLD:
            current_value = metrics.p90_response_time_ms
            if current_value > rule.threshold_value:
                message = (
                    f"응답시간(P90)이 임계값을 초과했습니다: "
                    f"{current_value:.2f}ms > {rule.threshold_value:.2f}ms"
                )
        
        elif rule.condition == AlertCondition.FAILURE_COUNT_THRESHOLD:
            current_value = metrics.failed_requests
            if current_value > rule.threshold_value:
                message = (
                    f"실패 건수가 임계값을 초과했습니다: "
                    f"{current_value} > {rule.threshold_value}"
                )
        
        # 알림 이벤트 생성
        if current_value is not None and message:
            return AlertEvent(
                rule_name=rule.name,
                operation_name=rule.operation_name,
                severity=rule.severity,
                message=message,
                current_value=current_value,
                threshold_value=rule.threshold_value,
                timestamp=datetime.now(),
                metadata={
                    "time_window": rule.time_window,
                    "total_requests": metrics.total_requests,
                    "success_rate": metrics.success_rate
                }
            )
        
        return None
    
    async def _send_alert(self, alert_event: AlertEvent):
        """알림 전송"""
        for notifier in self._notifiers:
            try:
                success = await notifier.send_alert(alert_event)
                if not success:
                    logger.warning(f"Failed to send alert via {type(notifier).__name__}")
            except Exception as e:
                logger.exception(f"Alert notification error: {e}")
```

---

## 📊 성능 및 품질 요구사항

### 성능 요구사항
- 로깅 오버헤드: <5ms per operation
- 메트릭 수집 지연시간: <50ms
- 메모리 사용량 증가: <100MB (10,000개 메트릭 기준)
- 알림 반응 시간: <60초

### 품질 요구사항
- 로그 데이터 무결성: 99.9%
- 메트릭 정확도: 99.5%
- 알림 정확도: 95% (false positive <5%)
- 시스템 가용성: 99.9%

### 확장성 요구사항
- 동시 작업 처리: 10,000+ operations/second
- 메트릭 보관 기간: 30일 (자동 아카이빙)
- 알림 규칙 개수: 100+ rules per operation
- 다중 인스턴스 지원: 분산 환경에서 메트릭 집계

---

**문서 상태**: 설계 완료, 구현 대기  
**다음 단계**: 테스팅 헬퍼 사양 작성 및 실제 구현