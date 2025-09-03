# 데이터 파이프라인 모니터링 예제

Readable HOF를 사용하여 실시간 데이터 파이프라인 모니터링 및 품질 검사를 수행하는 완전한 예제입니다.

## 전체 코드

```python
"""
RFS Readable HOF를 활용한 데이터 파이프라인 모니터링 시스템

이 예제는 다음 기능을 포함합니다:
- 실시간 데이터 스트림 모니터링
- 데이터 품질 검사
- 이상 패턴 탐지
- 자동 알림 시스템
- 성능 메트릭 수집
- 일일 리포트 생성
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, AsyncGenerator, Optional
from dataclasses import dataclass
from enum import Enum

from rfs.hof.readable import (
    apply_rules_to, scan_data_for, extract_from, validate_config,
    required, range_check, custom_check, 
    create_log_entry
)
from rfs.core.result import Result, Success, Failure


class DataQuality(Enum):
    """데이터 품질 레벨"""
    EXCELLENT = "excellent"
    GOOD = "good" 
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    CRITICAL = "critical"


@dataclass
class DataBatch:
    """데이터 배치 모델"""
    id: str
    timestamp: datetime
    source: str
    records: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    
    def __len__(self) -> int:
        return len(self.records)


@dataclass 
class QualityMetrics:
    """품질 메트릭"""
    completeness: float  # 완성도 (0-1)
    consistency: float   # 일관성 (0-1)
    accuracy: float      # 정확도 (0-1)
    timeliness: float    # 적시성 (0-1)
    
    @property
    def overall_score(self) -> float:
        """전체 품질 점수"""
        return (self.completeness + self.consistency + 
                self.accuracy + self.timeliness) / 4
    
    @property
    def quality_level(self) -> DataQuality:
        """품질 레벨 분류"""
        score = self.overall_score
        if score >= 0.9:
            return DataQuality.EXCELLENT
        elif score >= 0.8:
            return DataQuality.GOOD
        elif score >= 0.7:
            return DataQuality.ACCEPTABLE
        elif score >= 0.5:
            return DataQuality.POOR
        else:
            return DataQuality.CRITICAL


class DataPipelineMonitor:
    """데이터 파이프라인 모니터링 시스템"""
    
    def __init__(self):
        self.setup_logging()
        self.quality_rules = self._load_quality_rules()
        self.anomaly_patterns = self._load_anomaly_patterns()
        self.alert_thresholds = self._load_alert_thresholds()
        self.metrics_history = []
        self.alert_count = 0
    
    def setup_logging(self):
        """로깅 설정"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    async def monitor_data_stream(self, data_stream: AsyncGenerator[DataBatch, None]):
        """데이터 스트림 실시간 모니터링"""
        self.logger.info("🚀 데이터 파이프라인 모니터링을 시작합니다...")
        
        batch_count = 0
        async for batch in data_stream:
            batch_count += 1
            self.logger.info(f"📦 배치 #{batch_count} 처리 중... (ID: {batch.id})")
            
            try:
                # 1. 데이터 품질 검사
                quality_issues = await self._check_data_quality(batch)
                
                # 2. 이상 패턴 탐지
                anomalies = await self._detect_anomalies(batch)
                
                # 3. 성능 메트릭 수집
                performance_metrics = await self._collect_performance_metrics(batch)
                
                # 4. 배치 처리 상태 확인
                processing_status = await self._check_processing_status(batch)
                
                # 5. 알림 처리
                if quality_issues or anomalies:
                    await self._send_alerts({
                        "batch_id": batch.id,
                        "timestamp": batch.timestamp,
                        "quality_issues": quality_issues,
                        "anomalies": anomalies,
                        "performance_metrics": performance_metrics,
                        "processing_status": processing_status
                    })
                
                # 6. 메트릭 저장
                await self._store_metrics(batch, {
                    "quality_issues": quality_issues,
                    "anomalies": anomalies,
                    "performance_metrics": performance_metrics,
                    "processing_status": processing_status
                })
                
                self.logger.info(f"✅ 배치 #{batch_count} 처리 완료")
                
            except Exception as e:
                self.logger.error(f"❌ 배치 처리 오류: {e}")
                await self._handle_processing_error(batch, e)
    
    async def _check_data_quality(self, batch: DataBatch) -> List[Dict]:
        """배치 데이터 품질 검사"""
        
        # Readable HOF로 품질 규칙 적용
        quality_violations = (apply_rules_to(batch.records)
                             .using(self.quality_rules)
                             .with_context({
                                 "batch_id": batch.id,
                                 "source": batch.source,
                                 "record_count": len(batch.records),
                                 "timestamp": batch.timestamp
                             })
                             .collect_violations()
                             .filter_by(lambda v: v.severity in ["high", "critical"]))
        
        # 품질 메트릭 계산
        metrics = self._calculate_quality_metrics(batch.records)
        
        # 임계값 검사
        threshold_violations = []
        if metrics.overall_score < self.alert_thresholds["quality_score_min"]:
            threshold_violations.append({
                "type": "quality_threshold",
                "metric": "overall_score",
                "value": metrics.overall_score,
                "threshold": self.alert_thresholds["quality_score_min"],
                "severity": "high" if metrics.overall_score < 0.5 else "medium"
            })
        
        all_issues = quality_violations.collect() + threshold_violations
        
        if all_issues:
            self.logger.warning(f"⚠️ 품질 이슈 {len(all_issues)}개 발견 (배치: {batch.id})")
        
        return all_issues
    
    async def _detect_anomalies(self, batch: DataBatch) -> List[Dict]:
        """이상 패턴 탐지"""
        
        # Readable HOF로 이상 패턴 스캔
        anomalies = (scan_data_for(self.anomaly_patterns)
                    .in_data(batch.records)
                    .extract(lambda record, pattern_name: {
                        "batch_id": batch.id,
                        "record_id": record.get("id", "unknown"),
                        "pattern": pattern_name,
                        "anomaly_score": self._calculate_anomaly_score(record, pattern_name),
                        "timestamp": record.get("timestamp", batch.timestamp),
                        "details": self._get_anomaly_details(record, pattern_name),
                        "severity": self._get_anomaly_severity(pattern_name)
                    })
                    .filter_by(lambda item: item["anomaly_score"] > 0.7)
                    .sort_by(lambda item: item["anomaly_score"], reverse=True))
        
        detected_anomalies = anomalies.collect()
        
        if detected_anomalies:
            self.logger.warning(f"🚨 이상 패턴 {len(detected_anomalies)}개 탐지 (배치: {batch.id})")
        
        return detected_anomalies
    
    async def _collect_performance_metrics(self, batch: DataBatch) -> Dict:
        """성능 메트릭 수집"""
        
        processing_start = datetime.now()
        
        # 배치 처리 성능 측정
        metrics = (extract_from(batch.records)
                  .transform_to(lambda record: {
                      "processing_time": self._measure_record_processing_time(record),
                      "memory_usage": self._measure_memory_usage(),
                      "cpu_usage": self._measure_cpu_usage(),
                      "record_size": len(str(record)) if record else 0
                  })
                  .collect())
        
        processing_end = datetime.now()
        batch_processing_time = (processing_end - processing_start).total_seconds()
        
        # 성능 요약
        performance_summary = {
            "batch_processing_time": batch_processing_time,
            "records_per_second": len(batch.records) / batch_processing_time if batch_processing_time > 0 else 0,
            "average_record_processing_time": sum(m["processing_time"] for m in metrics) / len(metrics) if metrics else 0,
            "total_memory_usage": max(m["memory_usage"] for m in metrics) if metrics else 0,
            "average_cpu_usage": sum(m["cpu_usage"] for m in metrics) / len(metrics) if metrics else 0,
            "total_data_size": sum(m["record_size"] for m in metrics),
            "throughput_mb_per_sec": sum(m["record_size"] for m in metrics) / (1024 * 1024) / batch_processing_time if batch_processing_time > 0 else 0
        }
        
        return performance_summary
    
    async def _check_processing_status(self, batch: DataBatch) -> Dict:
        """배치 처리 상태 확인"""
        
        # 배치 메타데이터 검증
        metadata_validation = validate_config(batch.metadata).against_rules([
            required("source_system", "소스 시스템 정보 필요"),
            required("pipeline_stage", "파이프라인 단계 정보 필요"),
            custom_check("data_freshness", 
                        lambda x: (datetime.now() - datetime.fromisoformat(x)).total_seconds() < 3600,
                        "데이터가 1시간 이상 오래됨"),
            range_check("expected_records", 1, 1000000, "예상 레코드 수 범위 오류")
        ])
        
        status = {
            "batch_id": batch.id,
            "processing_timestamp": datetime.now(),
            "metadata_valid": metadata_validation.is_success(),
            "record_count": len(batch.records),
            "expected_count": batch.metadata.get("expected_records", len(batch.records)),
            "completion_rate": len(batch.records) / batch.metadata.get("expected_records", len(batch.records)) if batch.metadata.get("expected_records") else 1.0,
            "processing_stage": batch.metadata.get("pipeline_stage", "unknown")
        }
        
        if not metadata_validation.is_success():
            status["metadata_errors"] = metadata_validation.unwrap_error()
        
        return status
    
    async def _send_alerts(self, alert_data: Dict):
        """알림 발송"""
        
        self.alert_count += 1
        
        # 알림 심각도 결정
        severity = self._determine_alert_severity(alert_data)
        
        # 알림 메시지 생성
        alert_message = self._generate_alert_message(alert_data, severity)
        
        # 알림 발송 (실제 구현에서는 이메일, 슬랙, SMS 등)
        self.logger.warning(f"🚨 Alert #{self.alert_count} [{severity.upper()}]: {alert_message}")
        
        # 심각한 알림의 경우 즉시 처리
        if severity == "critical":
            await self._handle_critical_alert(alert_data)
    
    async def _store_metrics(self, batch: DataBatch, monitoring_results: Dict):
        """메트릭 저장"""
        
        metric_entry = {
            "timestamp": datetime.now(),
            "batch_id": batch.id,
            "source": batch.source,
            "record_count": len(batch.records),
            "quality_score": self._calculate_quality_metrics(batch.records).overall_score,
            "anomaly_count": len(monitoring_results["anomalies"]),
            "quality_issues_count": len(monitoring_results["quality_issues"]),
            "performance_metrics": monitoring_results["performance_metrics"],
            "processing_status": monitoring_results["processing_status"]
        }
        
        self.metrics_history.append(metric_entry)
        
        # 메트릭 히스토리 크기 제한 (메모리 관리)
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-800:]
    
    async def generate_daily_report(self, date: str) -> Dict:
        """일일 모니터링 리포트 생성"""
        
        self.logger.info(f"📊 {date} 일일 리포트를 생성합니다...")
        
        # 해당 날짜의 메트릭 필터링
        daily_metrics = [
            m for m in self.metrics_history 
            if m["timestamp"].strftime("%Y-%m-%d") == date
        ]
        
        if not daily_metrics:
            return {"error": f"{date}에 대한 데이터가 없습니다."}
        
        # Readable HOF로 리포트 생성
        report = (extract_from(daily_metrics)
                 .group_by(lambda metric: metric["source"])
                 .transform_to(lambda group: {
                     "source": group["key"],
                     "total_batches": len(group["items"]),
                     "total_records": sum(item["record_count"] for item in group["items"]),
                     "average_quality_score": sum(item["quality_score"] for item in group["items"]) / len(group["items"]),
                     "total_anomalies": sum(item["anomaly_count"] for item in group["items"]),
                     "total_quality_issues": sum(item["quality_issues_count"] for item in group["items"]),
                     "average_processing_time": sum(
                         item["performance_metrics"]["batch_processing_time"] 
                         for item in group["items"]
                     ) / len(group["items"]),
                     "peak_records_per_second": max(
                         item["performance_metrics"]["records_per_second"] 
                         for item in group["items"]
                     ),
                     "data_quality_trend": self._calculate_quality_trend(group["items"])
                 })
                 .sort_by(lambda item: item["average_quality_score"], reverse=True))
        
        # 전체 요약 계산
        summary = {
            "date": date,
            "total_batches": len(daily_metrics),
            "total_records": sum(m["record_count"] for m in daily_metrics),
            "average_quality_score": sum(m["quality_score"] for m in daily_metrics) / len(daily_metrics),
            "total_alerts": self.alert_count,
            "sources": report.collect(),
            "recommendations": self._generate_daily_recommendations(daily_metrics)
        }
        
        self.logger.info(f"✅ {date} 일일 리포트 생성 완료")
        return summary
    
    # ========== 헬퍼 메서드들 ==========
    
    def _load_quality_rules(self) -> List:
        """데이터 품질 규칙 로드"""
        return [
            # 필수 필드 검사
            lambda records: self._check_required_fields(records),
            
            # 데이터 타입 일관성 검사
            lambda records: self._check_data_type_consistency(records),
            
            # 값 범위 검사
            lambda records: self._check_value_ranges(records),
            
            # 중복 데이터 검사
            lambda records: self._check_duplicate_records(records),
            
            # 데이터 신선도 검사
            lambda records: self._check_data_freshness(records),
        ]
    
    def _load_anomaly_patterns(self) -> Dict:
        """이상 패턴 로드"""
        return {
            "unexpected_spike": lambda record: self._detect_spike_anomaly(record),
            "missing_data": lambda record: self._detect_missing_data_anomaly(record),
            "format_inconsistency": lambda record: self._detect_format_anomaly(record),
            "unusual_timing": lambda record: self._detect_timing_anomaly(record),
            "data_drift": lambda record: self._detect_data_drift_anomaly(record),
            "outlier_values": lambda record: self._detect_outlier_anomaly(record),
        }
    
    def _load_alert_thresholds(self) -> Dict:
        """알림 임계값 로드"""
        return {
            "quality_score_min": 0.7,
            "anomaly_score_max": 0.8,
            "processing_time_max": 30.0,  # seconds
            "memory_usage_max": 512,      # MB
            "error_rate_max": 0.05,       # 5%
        }
    
    def _calculate_quality_metrics(self, records: List[Dict]) -> QualityMetrics:
        """품질 메트릭 계산"""
        if not records:
            return QualityMetrics(0, 0, 0, 0)
        
        # 완성도 (필수 필드 비율)
        required_fields = ["id", "timestamp", "data"]
        completeness = sum(
            1 for record in records 
            if all(field in record and record[field] is not None for field in required_fields)
        ) / len(records)
        
        # 일관성 (데이터 타입 일관성)
        consistency = self._calculate_consistency_score(records)
        
        # 정확도 (값 유효성)
        accuracy = self._calculate_accuracy_score(records)
        
        # 적시성 (데이터 신선도)
        timeliness = self._calculate_timeliness_score(records)
        
        return QualityMetrics(completeness, consistency, accuracy, timeliness)
    
    def _calculate_anomaly_score(self, record: Dict, pattern_name: str) -> float:
        """이상 점수 계산"""
        base_scores = {
            "unexpected_spike": 0.9,
            "missing_data": 0.8,
            "format_inconsistency": 0.7,
            "unusual_timing": 0.6,
            "data_drift": 0.8,
            "outlier_values": 0.7,
        }
        
        base_score = base_scores.get(pattern_name, 0.5)
        
        # 레코드별 가중치 적용
        if record.get("critical_field"):
            base_score *= 1.2
        
        return min(base_score, 1.0)
    
    def _determine_alert_severity(self, alert_data: Dict) -> str:
        """알림 심각도 결정"""
        quality_issues = alert_data.get("quality_issues", [])
        anomalies = alert_data.get("anomalies", [])
        
        # Critical: 심각한 품질 이슈 또는 높은 이상 점수
        if any(issue.get("severity") == "critical" for issue in quality_issues):
            return "critical"
        
        if any(anomaly.get("anomaly_score", 0) > 0.9 for anomaly in anomalies):
            return "critical"
        
        # High: 다수의 이슈 또는 중요한 이슈
        if len(quality_issues) + len(anomalies) > 10:
            return "high"
        
        if any(issue.get("severity") == "high" for issue in quality_issues):
            return "high"
        
        # Medium: 일반적인 이슈들
        return "medium"
    
    def _generate_alert_message(self, alert_data: Dict, severity: str) -> str:
        """알림 메시지 생성"""
        batch_id = alert_data["batch_id"]
        quality_count = len(alert_data.get("quality_issues", []))
        anomaly_count = len(alert_data.get("anomalies", []))
        
        message = f"배치 {batch_id}에서 "
        
        if quality_count > 0:
            message += f"품질 이슈 {quality_count}개"
        
        if anomaly_count > 0:
            if quality_count > 0:
                message += ", "
            message += f"이상 패턴 {anomaly_count}개"
        
        message += " 발견됨"
        
        return message


# 데이터 스트림 시뮬레이터
async def simulate_data_stream() -> AsyncGenerator[DataBatch, None]:
    """데이터 스트림 시뮬레이션"""
    
    batch_id = 1
    sources = ["user_events", "transaction_logs", "system_metrics", "api_calls"]
    
    while True:
        # 랜덤 배치 생성
        import random
        
        source = random.choice(sources)
        record_count = random.randint(50, 500)
        
        records = []
        for i in range(record_count):
            record = {
                "id": f"{source}_{batch_id}_{i}",
                "timestamp": datetime.now().isoformat(),
                "data": {"value": random.randint(1, 1000), "status": "active"},
                "user_id": f"user_{random.randint(1, 10000)}",
                "session_id": f"session_{random.randint(1, 1000)}"
            }
            
            # 가끔 문제가 있는 데이터 생성
            if random.random() < 0.1:  # 10% 확률로 문제 데이터
                if random.random() < 0.5:
                    del record["timestamp"]  # 필수 필드 누락
                else:
                    record["data"]["value"] = -999  # 이상값
            
            records.append(record)
        
        batch = DataBatch(
            id=f"batch_{batch_id}",
            timestamp=datetime.now(),
            source=source,
            records=records,
            metadata={
                "source_system": source,
                "pipeline_stage": "ingestion",
                "expected_records": record_count,
                "data_freshness": datetime.now().isoformat()
            }
        )
        
        yield batch
        
        batch_id += 1
        await asyncio.sleep(2)  # 2초마다 새 배치


# 사용 예제
async def main():
    """데이터 파이프라인 모니터링 실행 예제"""
    
    # 1. 모니터링 시스템 초기화
    monitor = DataPipelineMonitor()
    
    # 2. 데이터 스트림 생성
    data_stream = simulate_data_stream()
    
    # 3. 모니터링 태스크 시작
    monitor_task = asyncio.create_task(
        monitor.monitor_data_stream(data_stream)
    )
    
    # 4. 일정 시간 후 리포트 생성 (별도 태스크)
    async def generate_periodic_reports():
        await asyncio.sleep(30)  # 30초 후 리포트 생성
        today = datetime.now().strftime("%Y-%m-%d")
        report = await monitor.generate_daily_report(today)
        
        print("\n" + "="*80)
        print("📊 RFS 데이터 파이프라인 일일 리포트")
        print("="*80)
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    
    report_task = asyncio.create_task(generate_periodic_reports())
    
    # 5. 모니터링 실행 (30초간)
    try:
        await asyncio.wait_for(
            asyncio.gather(monitor_task, report_task),
            timeout=60.0
        )
    except asyncio.TimeoutError:
        print("\n✅ 모니터링 세션 완료")
        monitor_task.cancel()
        report_task.cancel()
        
        # 최종 리포트
        today = datetime.now().strftime("%Y-%m-%d")
        final_report = await monitor.generate_daily_report(today)
        print("\n📈 최종 요약:")
        print(f"  • 처리된 배치: {final_report['total_batches']}개")
        print(f"  • 총 레코드: {final_report['total_records']:,}개")
        print(f"  • 평균 품질 점수: {final_report['average_quality_score']:.3f}")
        print(f"  • 총 알림: {final_report['total_alerts']}개")


if __name__ == "__main__":
    # 비동기 실행
    asyncio.run(main())
```

## 실행 결과 예시

```
🚀 데이터 파이프라인 모니터링을 시작합니다...
📦 배치 #1 처리 중... (ID: batch_1)
✅ 배치 #1 처리 완료
📦 배치 #2 처리 중... (ID: batch_2)
⚠️ 품질 이슈 2개 발견 (배치: batch_2)
🚨 Alert #1 [MEDIUM]: 배치 batch_2에서 품질 이슈 2개 발견됨
✅ 배치 #2 처리 완료
📦 배치 #3 처리 중... (ID: batch_3)
🚨 이상 패턴 1개 탐지 (배치: batch_3)
🚨 Alert #2 [HIGH]: 배치 batch_3에서 이상 패턴 1개 발견됨
✅ 배치 #3 처리 완료

================================================================================
📊 RFS 데이터 파이프라인 일일 리포트
================================================================================
{
  "date": "2024-01-15",
  "total_batches": 15,
  "total_records": 3420,
  "average_quality_score": 0.847,
  "total_alerts": 5,
  "sources": [
    {
      "source": "user_events",
      "total_batches": 4,
      "total_records": 950,
      "average_quality_score": 0.892,
      "total_anomalies": 1,
      "total_quality_issues": 2,
      "average_processing_time": 0.125,
      "peak_records_per_second": 1200.5,
      "data_quality_trend": "improving"
    },
    {
      "source": "transaction_logs", 
      "total_batches": 5,
      "total_records": 1150,
      "average_quality_score": 0.834,
      "total_anomalies": 3,
      "total_quality_issues": 4,
      "average_processing_time": 0.180,
      "peak_records_per_second": 980.2,
      "data_quality_trend": "stable"
    }
  ],
  "recommendations": [
    "💡 user_events 소스의 품질이 우수합니다. 이 패턴을 다른 소스에도 적용하세요.",
    "⚠️ transaction_logs에서 이상 패턴이 자주 발견됩니다. 데이터 소스를 점검하세요.",
    "🚀 전체적인 처리 성능이 양호합니다. 현재 설정을 유지하세요."
  ]
}

📈 최종 요약:
  • 처리된 배치: 15개
  • 총 레코드: 3,420개  
  • 평균 품질 점수: 0.847
  • 총 알림: 5개

✅ 모니터링 세션 완료
```

## 핵심 기능

### 1. Readable HOF 패턴 활용

- **apply_rules_to()**: 데이터 품질 규칙 적용
- **scan_data_for()**: 이상 패턴 탐지
- **extract_from()**: 메트릭 처리 및 그룹화
- **validate_config()**: 메타데이터 검증

### 2. 실시간 모니터링

```python
quality_violations = (apply_rules_to(batch.records)
                     .using(self.quality_rules)
                     .with_context({"batch_id": batch.id})
                     .collect_violations()
                     .filter_by(lambda v: v.severity in ["high", "critical"]))
```

### 3. 종합적 데이터 품질 관리

- 완성도, 일관성, 정확도, 적시성 평가
- 자동 이상 탐지 및 알림
- 성능 메트릭 수집
- 일일 리포트 자동 생성

이 예제는 Readable HOF가 복잡한 실시간 데이터 처리 시나리오에서 어떻게 활용될 수 있는지 보여주며, 선언적이고 읽기 쉬운 코드로 강력한 모니터링 시스템을 구축하는 방법을 제시합니다.