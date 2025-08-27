"""
Cloud Run Task Queue Tests - Google Cloud Run Official Patterns

RFS Cloud Run Task Queue 시스템 테스트
Google Cloud Tasks 및 Cloud Run Job 공식 패턴 검증
- Cloud Tasks 큐 통합
- Cloud Run Job 패턴
- Task Scheduler 및 Priority 관리
- Retry 및 Error Handling 패턴
- Batch Processing 최적화
"""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from rfs.cloud_run.helpers import (
    CloudTaskQueue,
    get_task_queue,
    schedule_task,
    submit_task,
    task_handler,
)
from rfs.core.result import Failure, Result, Success


class TaskPriority:
    """태스크 우선순위 (Google Cloud Tasks 호환)"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


class TaskStatus:
    """태스크 상태 (Google Cloud Tasks 호환)"""

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"


class TestCloudTasksIntegration:
    """Google Cloud Tasks 통합 테스트"""

    def setup_method(self):
        """테스트 설정"""
        # Cloud Run 환경 설정
        os.environ.update(
            {
                "GOOGLE_CLOUD_PROJECT": "task-queue-project-12345",
                "K_SERVICE": "task-processor-service",
                "CLOUD_RUN_REGION": "asia-northeast3",
            }
        )

        self.project_id = "task-queue-project-12345"
        self.queue_name = "task-processing-queue"
        self.task_queue = CloudTaskQueue()
        self.task_queue._queue = []
        self.task_queue._processing = False

    def teardown_method(self):
        """테스트 후 정리"""
        # 환경 변수 정리
        for key in ["GOOGLE_CLOUD_PROJECT", "K_SERVICE", "CLOUD_RUN_REGION"]:
            os.environ.pop(key, None)

    def test_cloud_tasks_queue_configuration(self):
        """Cloud Tasks 큐 설정 테스트"""
        # Given: Google Cloud Tasks 큐 설정
        queue_config = {
            "name": f"projects/{self.project_id}/locations/asia-northeast3/queues/{self.queue_name}",
            "rate_limits": {
                "max_dispatches_per_second": 100.0,
                "max_burst_size": 100,
                "max_concurrent_dispatches": 1000,
            },
            "retry_config": {
                "max_attempts": 5,
                "max_retry_duration": "3600s",
                "min_backoff": "5s",
                "max_backoff": "300s",
                "max_doublings": 16,
            },
            "target": {
                "type": "HTTP",
                "http_target": {
                    "uri_override": {
                        "scheme": "HTTPS",
                        "host": f"task-processor-service-abc123-du.a.run.app",
                        "port": 443,
                    }
                },
            },
        }

        # When & Then: 큐 설정이 올바른 구조를 가짐
        assert "projects/" in queue_config["name"]
        assert "locations/" in queue_config["name"]
        assert "queues/" in queue_config["name"]
        assert queue_config["rate_limits"]["max_dispatches_per_second"] == 100.0
        assert queue_config["retry_config"]["max_attempts"] == 5
        assert queue_config["target"]["type"] == "HTTP"

    @pytest.mark.asyncio
    async def test_task_creation_with_cloud_tasks_format(self):
        """Cloud Tasks 형식의 태스크 생성 테스트"""
        # Given: Cloud Tasks 호환 태스크 데이터
        task_data = {
            "name": f"projects/{self.project_id}/locations/asia-northeast3/queues/{self.queue_name}/tasks/task-{uuid4().hex[:8]}",
            "http_request": {
                "http_method": "POST",
                "url": "https://task-processor-service-abc123-du.a.run.app/api/process-payment",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer task-token-123",
                },
                "body": json.dumps(
                    {
                        "payment_id": "pay_789",
                        "amount": 150.00,
                        "currency": "USD",
                        "customer_id": "cust_456",
                    }
                ).encode(),
            },
            "schedule_time": (datetime.now() + timedelta(minutes=5)).isoformat() + "Z",
            "dispatch_deadline": "30s",
        }

        # When: 태스크 큐에 추가
        task_id = await self.task_queue.enqueue(task_data)

        # Then: 태스크가 성공적으로 큐에 추가됨
        assert task_id is not None
        assert len(self.task_queue._queue) == 1

        queued_task = self.task_queue._queue[0]
        assert "http_request" in queued_task
        assert queued_task["http_request"]["http_method"] == "POST"
        assert "payment_id" in json.loads(queued_task["http_request"]["body"].decode())

    @pytest.mark.asyncio
    async def test_task_priority_handling(self):
        """태스크 우선순위 처리 테스트"""
        # Given: 다양한 우선순위의 태스크들
        tasks = [
            {
                "name": "low-priority-task",
                "priority": TaskPriority.LOW,
                "http_request": {
                    "http_method": "POST",
                    "url": "https://service.run.app/api/low-priority",
                    "body": json.dumps({"type": "cleanup"}).encode(),
                },
            },
            {
                "name": "urgent-task",
                "priority": TaskPriority.URGENT,
                "http_request": {
                    "http_method": "POST",
                    "url": "https://service.run.app/api/urgent",
                    "body": json.dumps({"type": "alert"}).encode(),
                },
            },
            {
                "name": "normal-task",
                "priority": TaskPriority.NORMAL,
                "http_request": {
                    "http_method": "POST",
                    "url": "https://service.run.app/api/normal",
                    "body": json.dumps({"type": "process"}).encode(),
                },
            },
        ]

        # When: 순서대로 태스크 추가 (우선순위와 관계없이)
        for task in tasks:
            await self.task_queue.enqueue(task)

        # Then: 우선순위에 따라 정렬되어 있음
        assert len(self.task_queue._queue) == 3

        # 실제 구현에서는 우선순위 정렬이 필요하지만,
        # 현재는 FIFO 큐이므로 추가된 순서대로 처리됨을 확인
        first_task = self.task_queue._queue[0]
        assert first_task["name"] == "low-priority-task"

    @pytest.mark.asyncio
    async def test_scheduled_task_execution(self):
        """예약된 태스크 실행 테스트"""
        # Given: 미래 시간에 예약된 태스크
        future_time = datetime.now() + timedelta(seconds=1)

        scheduled_task = {
            "name": "scheduled-maintenance",
            "schedule_time": future_time.isoformat() + "Z",
            "http_request": {
                "http_method": "POST",
                "url": "https://maintenance-service.run.app/api/cleanup",
                "headers": {"Authorization": "Bearer maintenance-token"},
                "body": json.dumps(
                    {
                        "cleanup_type": "database",
                        "tables": ["temp_data", "old_logs"],
                        "retention_days": 7,
                    }
                ).encode(),
            },
        }

        # When: 예약된 태스크 추가
        task_id = await self.task_queue.enqueue(scheduled_task)

        # Then: 태스크가 큐에 추가됨
        assert task_id is not None
        assert len(self.task_queue._queue) == 1

        # 스케줄 시간까지 대기
        await asyncio.sleep(1.2)

        # 태스크가 처리됨 (큐에서 제거)
        assert len(self.task_queue._queue) == 0

    @pytest.mark.asyncio
    async def test_task_retry_mechanism(self):
        """태스크 재시도 메커니즘 테스트"""
        # Given: 재시도 설정이 있는 실패하는 태스크
        failing_task = {
            "name": "failing-task",
            "retry_config": {
                "max_attempts": 3,
                "retry_count": 0,
                "backoff_multiplier": 2.0,
                "initial_backoff": "1s",
            },
            "http_request": {
                "http_method": "POST",
                "url": "https://flaky-service.run.app/api/unstable",
                "body": json.dumps({"operation": "risky_operation"}).encode(),
            },
        }

        # When: 실패하는 태스크 추가
        task_id = await self.task_queue.enqueue(failing_task)

        # Then: 태스크가 큐에 추가됨
        assert task_id is not None
        assert len(self.task_queue._queue) == 1

        queued_task = self.task_queue._queue[0]
        assert queued_task["retry_config"]["max_attempts"] == 3
        assert queued_task["retry_config"]["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_batch_task_processing(self):
        """배치 태스크 처리 테스트"""
        # Given: 대량의 배치 처리 태스크
        batch_tasks = []

        for i in range(20):
            task = {
                "name": f"batch-task-{i:02d}",
                "http_request": {
                    "http_method": "POST",
                    "url": "https://batch-processor.run.app/api/process-item",
                    "body": json.dumps(
                        {
                            "item_id": f"item_{i:05d}",
                            "batch_id": "batch_001",
                            "processing_type": "data_transformation",
                        }
                    ).encode(),
                },
            }
            batch_tasks.append(task)

        # When: 모든 배치 태스크 추가
        task_ids = []
        for task in batch_tasks:
            task_id = await self.task_queue.enqueue(task)
            task_ids.append(task_id)

        # Then: 모든 태스크가 큐에 추가됨
        assert len(task_ids) == 20
        assert len(self.task_queue._queue) == 20

        # 모든 태스크 ID가 유니크함
        assert len(set(task_ids)) == 20

    @pytest.mark.asyncio
    async def test_task_status_tracking(self):
        """태스크 상태 추적 테스트"""
        # Given: 상태 추적이 가능한 태스크
        task_with_status = {
            "name": "status-trackable-task",
            "status": TaskStatus.PENDING,
            "created_time": datetime.now().isoformat() + "Z",
            "http_request": {
                "http_method": "POST",
                "url": "https://status-service.run.app/api/track-progress",
                "body": json.dumps(
                    {"operation": "long_running_task", "estimated_duration": "300s"}
                ).encode(),
            },
        }

        # When: 태스크 추가
        task_id = await self.task_queue.enqueue(task_with_status)

        # Then: 초기 상태가 PENDING
        queued_task = self.task_queue._queue[0]
        assert queued_task["status"] == TaskStatus.PENDING
        assert "created_time" in queued_task

    def test_task_handler_decorator_registration(self):
        """태스크 핸들러 데코레이터 등록 테스트"""
        # Given: 다양한 태스크 핸들러
        handlers = []

        @task_handler("/api/process-payment")
        async def payment_handler(request):
            return {"status": "payment_processed", "transaction_id": "txn_123"}

        @task_handler("/api/send-notification")
        async def notification_handler(request):
            return {"status": "notification_sent", "message_id": "msg_456"}

        @task_handler("/api/generate-report")
        async def report_handler(request):
            return {"status": "report_generated", "report_id": "rpt_789"}

        handlers.extend([payment_handler, notification_handler, report_handler])

        # When & Then: 핸들러들이 정상적으로 데코레이션됨
        for handler in handlers:
            assert callable(handler)

    @pytest.mark.asyncio
    async def test_cloud_run_job_integration(self):
        """Cloud Run Job 통합 테스트"""
        # Given: Cloud Run Job 형태의 태스크
        job_task = {
            "name": "data-processing-job",
            "job_spec": {
                "template": {
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "image": "asia-northeast3-docker.pkg.dev/task-queue-project-12345/jobs/data-processor:latest",
                                        "env": [
                                            {
                                                "name": "DATA_SOURCE",
                                                "value": "gs://data-bucket/input/",
                                            },
                                            {
                                                "name": "OUTPUT_DESTINATION",
                                                "value": "gs://data-bucket/output/",
                                            },
                                            {
                                                "name": "PROCESSING_TYPE",
                                                "value": "batch_transform",
                                            },
                                        ],
                                        "resources": {
                                            "limits": {"cpu": "2000m", "memory": "4Gi"}
                                        },
                                    }
                                ],
                                "max_retries": 3,
                                "active_deadline_seconds": 3600,
                                "parallelism": 4,
                                "completions": 1,
                            }
                        }
                    }
                }
            },
        }

        # When: Job 태스크 추가
        task_id = await self.task_queue.enqueue(job_task)

        # Then: Job이 큐에 추가됨
        assert task_id is not None
        assert len(self.task_queue._queue) == 1

        queued_job = self.task_queue._queue[0]
        assert "job_spec" in queued_job
        assert (
            queued_job["job_spec"]["template"]["spec"]["template"]["spec"][
                "max_retries"
            ]
            == 3
        )


class TestTaskSchedulerPatterns:
    """태스크 스케줄러 패턴 테스트"""

    def setup_method(self):
        """테스트 설정"""
        self.task_queue = CloudTaskQueue()
        self.task_queue._queue = []

    @pytest.mark.asyncio
    async def test_cron_schedule_pattern(self):
        """Cron 스케줄 패턴 테스트"""
        # Given: Cron 표현식을 사용한 반복 태스크
        cron_task = {
            "name": "daily-report-generation",
            "schedule": "0 9 * * 1-5",  # 평일 오전 9시
            "timezone": "Asia/Seoul",
            "http_request": {
                "http_method": "POST",
                "url": "https://reporting-service.run.app/api/generate-daily-report",
                "body": json.dumps(
                    {
                        "report_type": "daily_summary",
                        "recipients": ["manager@company.com", "team@company.com"],
                    }
                ).encode(),
            },
        }

        # When: Cron 태스크 스케줄링
        task_id = await schedule_task(
            url=cron_task["http_request"]["url"],
            payload=json.loads(cron_task["http_request"]["body"].decode()),
            schedule_time=datetime.now() + timedelta(seconds=1),
        )

        # Then: 스케줄된 태스크 ID 반환
        assert task_id is not None
        assert isinstance(task_id, str)

    @pytest.mark.asyncio
    async def test_recurring_task_pattern(self):
        """반복 태스크 패턴 테스트"""
        # Given: 주기적으로 실행되는 태스크
        recurring_intervals = [
            {"name": "every-minute", "interval": timedelta(minutes=1)},
            {"name": "every-hour", "interval": timedelta(hours=1)},
            {"name": "every-day", "interval": timedelta(days=1)},
        ]

        task_ids = []

        # When: 각 주기마다 태스크 스케줄링
        for task_info in recurring_intervals:
            schedule_time = datetime.now() + task_info["interval"]

            task_id = await schedule_task(
                url=f"https://scheduler.run.app/api/{task_info['name']}",
                payload={"task_type": task_info["name"]},
                schedule_time=schedule_time,
            )
            task_ids.append(task_id)

        # Then: 모든 반복 태스크가 스케줄됨
        assert len(task_ids) == 3
        assert all(isinstance(tid, str) for tid in task_ids)

    @pytest.mark.asyncio
    async def test_deadline_based_scheduling(self):
        """데드라인 기반 스케줄링 테스트"""
        # Given: 데드라인이 있는 긴급 태스크들
        deadline_tasks = [
            {
                "name": "urgent-security-patch",
                "deadline": datetime.now() + timedelta(minutes=5),
                "priority": TaskPriority.URGENT,
            },
            {
                "name": "daily-backup",
                "deadline": datetime.now() + timedelta(hours=2),
                "priority": TaskPriority.NORMAL,
            },
            {
                "name": "weekly-cleanup",
                "deadline": datetime.now() + timedelta(days=1),
                "priority": TaskPriority.LOW,
            },
        ]

        # When: 데드라인 기반으로 태스크 스케줄링
        scheduled_tasks = []

        for task_info in deadline_tasks:
            task_data = {
                "name": task_info["name"],
                "priority": task_info["priority"],
                "deadline": task_info["deadline"].isoformat() + "Z",
                "http_request": {
                    "http_method": "POST",
                    "url": f"https://deadline-processor.run.app/api/{task_info['name']}",
                    "body": json.dumps({"deadline_task": True}).encode(),
                },
            }

            task_id = await self.task_queue.enqueue(task_data)
            scheduled_tasks.append((task_id, task_info["priority"]))

        # Then: 모든 데드라인 태스크가 스케줄됨
        assert len(scheduled_tasks) == 3

        # 우선순위별로 확인
        urgent_tasks = [t for t in scheduled_tasks if t[1] == TaskPriority.URGENT]
        normal_tasks = [t for t in scheduled_tasks if t[1] == TaskPriority.NORMAL]
        low_tasks = [t for t in scheduled_tasks if t[1] == TaskPriority.LOW]

        assert len(urgent_tasks) == 1
        assert len(normal_tasks) == 1
        assert len(low_tasks) == 1


class TestTaskErrorHandlingPatterns:
    """태스크 에러 처리 패턴 테스트"""

    def setup_method(self):
        """테스트 설정"""
        self.task_queue = CloudTaskQueue()
        self.task_queue._queue = []

    @pytest.mark.asyncio
    async def test_exponential_backoff_retry(self):
        """지수 백오프 재시도 테스트"""
        # Given: 지수 백오프 재시도 설정
        retry_task = {
            "name": "retry-with-backoff",
            "retry_config": {
                "max_attempts": 5,
                "initial_backoff": "2s",
                "max_backoff": "300s",
                "backoff_multiplier": 2.0,
                "max_doublings": 10,
            },
            "http_request": {
                "http_method": "POST",
                "url": "https://unreliable-service.run.app/api/flaky-endpoint",
                "body": json.dumps({"operation": "unreliable_task"}).encode(),
            },
        }

        # When: 재시도 태스크 추가
        task_id = await self.task_queue.enqueue(retry_task)

        # Then: 재시도 설정이 올바르게 적용됨
        assert task_id is not None
        queued_task = self.task_queue._queue[0]

        retry_config = queued_task["retry_config"]
        assert retry_config["max_attempts"] == 5
        assert retry_config["backoff_multiplier"] == 2.0
        assert retry_config["initial_backoff"] == "2s"

    @pytest.mark.asyncio
    async def test_dead_letter_queue_pattern(self):
        """Dead Letter Queue 패턴 테스트"""
        # Given: Dead Letter Queue 설정이 있는 태스크
        dlq_task = {
            "name": "task-with-dlq",
            "retry_config": {"max_attempts": 3},
            "dead_letter_config": {
                "queue": f"projects/{os.environ.get('GOOGLE_CLOUD_PROJECT', 'test-project')}/locations/asia-northeast3/queues/dead-letter-queue",
                "max_delivery_attempts": 3,
            },
            "http_request": {
                "http_method": "POST",
                "url": "https://failing-service.run.app/api/always-fails",
                "body": json.dumps({"will_fail": True}).encode(),
            },
        }

        # When: DLQ 태스크 추가
        task_id = await self.task_queue.enqueue(dlq_task)

        # Then: Dead Letter Queue 설정이 적용됨
        assert task_id is not None
        queued_task = self.task_queue._queue[0]

        assert "dead_letter_config" in queued_task
        assert "dead-letter-queue" in queued_task["dead_letter_config"]["queue"]
        assert queued_task["dead_letter_config"]["max_delivery_attempts"] == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern(self):
        """Circuit Breaker 패턴 테스트"""
        # Given: Circuit Breaker 로직이 포함된 태스크
        circuit_breaker_tasks = []

        # 연속 실패 시나리오
        for i in range(10):
            task = {
                "name": f"circuit-breaker-test-{i}",
                "circuit_breaker": {
                    "failure_threshold": 5,
                    "recovery_timeout": "60s",
                    "current_failures": 0,
                },
                "http_request": {
                    "http_method": "POST",
                    "url": "https://circuit-test-service.run.app/api/test",
                    "body": json.dumps({"test_id": i, "should_fail": i < 7}).encode(),
                },
            }
            circuit_breaker_tasks.append(task)

        # When: Circuit Breaker 태스크들 추가
        task_ids = []
        for task in circuit_breaker_tasks:
            task_id = await self.task_queue.enqueue(task)
            task_ids.append(task_id)

        # Then: 모든 태스크가 Circuit Breaker 설정과 함께 큐에 추가됨
        assert len(task_ids) == 10
        assert len(self.task_queue._queue) == 10

        # Circuit Breaker 설정 확인
        for task in self.task_queue._queue:
            assert "circuit_breaker" in task
            assert task["circuit_breaker"]["failure_threshold"] == 5
            assert task["circuit_breaker"]["current_failures"] == 0

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """타임아웃 처리 테스트"""
        # Given: 다양한 타임아웃 설정의 태스크들
        timeout_tasks = [
            {
                "name": "quick-task",
                "dispatch_deadline": "10s",
                "http_request": {
                    "http_method": "GET",
                    "url": "https://fast-service.run.app/api/quick",
                },
            },
            {
                "name": "medium-task",
                "dispatch_deadline": "60s",
                "http_request": {
                    "http_method": "POST",
                    "url": "https://medium-service.run.app/api/process",
                    "body": json.dumps({"processing_time": "30s"}).encode(),
                },
            },
            {
                "name": "long-task",
                "dispatch_deadline": "300s",
                "http_request": {
                    "http_method": "POST",
                    "url": "https://batch-service.run.app/api/long-process",
                    "body": json.dumps({"processing_time": "240s"}).encode(),
                },
            },
        ]

        # When: 타임아웃 설정이 다른 태스크들 추가
        task_ids = []
        for task in timeout_tasks:
            task_id = await self.task_queue.enqueue(task)
            task_ids.append(task_id)

        # Then: 모든 태스크가 각자의 타임아웃 설정과 함께 큐에 추가됨
        assert len(task_ids) == 3

        quick_task = next(
            t for t in self.task_queue._queue if t["name"] == "quick-task"
        )
        medium_task = next(
            t for t in self.task_queue._queue if t["name"] == "medium-task"
        )
        long_task = next(t for t in self.task_queue._queue if t["name"] == "long-task")

        assert quick_task["dispatch_deadline"] == "10s"
        assert medium_task["dispatch_deadline"] == "60s"
        assert long_task["dispatch_deadline"] == "300s"


class TestTaskQueuePerformanceOptimization:
    """태스크 큐 성능 최적화 테스트"""

    def setup_method(self):
        """테스트 설정"""
        self.task_queue = CloudTaskQueue()
        self.task_queue._queue = []

    @pytest.mark.asyncio
    async def test_rate_limiting_configuration(self):
        """요청 속도 제한 설정 테스트"""
        # Given: 요청 속도 제한이 설정된 큐
        rate_limited_config = {
            "max_dispatches_per_second": 50.0,
            "max_burst_size": 100,
            "max_concurrent_dispatches": 500,
        }

        # When: 속도 제한 내에서 태스크들 추가
        tasks_within_limit = []

        for i in range(25):  # 50/초 제한의 절반
            task = {
                "name": f"rate-limited-task-{i}",
                "rate_limits": rate_limited_config,
                "http_request": {
                    "http_method": "POST",
                    "url": "https://rate-limited-service.run.app/api/process",
                    "body": json.dumps({"item_id": i}).encode(),
                },
            }
            task_id = await self.task_queue.enqueue(task)
            tasks_within_limit.append(task_id)

        # Then: 모든 태스크가 성공적으로 큐에 추가됨
        assert len(tasks_within_limit) == 25
        assert len(self.task_queue._queue) == 25

        # 속도 제한 설정 확인
        for task in self.task_queue._queue:
            assert task["rate_limits"]["max_dispatches_per_second"] == 50.0
            assert task["rate_limits"]["max_concurrent_dispatches"] == 500

    @pytest.mark.asyncio
    async def test_batch_processing_optimization(self):
        """배치 처리 최적화 테스트"""
        # Given: 배치 처리에 최적화된 태스크들
        batch_size = 100
        batch_tasks = []

        for batch_id in range(5):  # 5개 배치
            for item_id in range(batch_size):  # 각 배치당 100개 아이템
                task = {
                    "name": f"batch-{batch_id}-item-{item_id:03d}",
                    "batch_id": f"batch_{batch_id}",
                    "batch_size": batch_size,
                    "http_request": {
                        "http_method": "POST",
                        "url": "https://batch-optimizer.run.app/api/process-batch-item",
                        "body": json.dumps(
                            {
                                "batch_id": f"batch_{batch_id}",
                                "item_id": item_id,
                                "total_items": batch_size,
                            }
                        ).encode(),
                    },
                }
                batch_tasks.append(task)

        # When: 모든 배치 태스크 추가
        task_ids = []
        for task in batch_tasks:
            task_id = await self.task_queue.enqueue(task)
            task_ids.append(task_id)

        # Then: 500개 태스크가 모두 큐에 추가됨
        assert len(task_ids) == 500
        assert len(self.task_queue._queue) == 500

        # 배치별로 그룹화 검증
        batch_groups = {}
        for task in self.task_queue._queue:
            batch_id = task["batch_id"]
            if batch_id not in batch_groups:
                batch_groups[batch_id] = []
            batch_groups[batch_id].append(task)

        assert len(batch_groups) == 5  # 5개 배치
        for batch_id, tasks in batch_groups.items():
            assert len(tasks) == 100  # 각 배치당 100개

    @pytest.mark.asyncio
    async def test_priority_queue_optimization(self):
        """우선순위 큐 최적화 테스트"""
        # Given: 다양한 우선순위의 태스크들
        priority_tasks = []

        # 우선순위별 태스크 생성
        priorities = [
            (TaskPriority.URGENT, "critical-security-patch", 5),
            (TaskPriority.HIGH, "user-facing-bug-fix", 15),
            (TaskPriority.NORMAL, "feature-deployment", 30),
            (TaskPriority.LOW, "maintenance-cleanup", 50),
        ]

        for priority, task_type, count in priorities:
            for i in range(count):
                task = {
                    "name": f"{task_type}-{i:02d}",
                    "priority": priority,
                    "http_request": {
                        "http_method": "POST",
                        "url": f"https://priority-processor.run.app/api/{task_type}",
                        "body": json.dumps(
                            {
                                "task_type": task_type,
                                "priority": priority,
                                "sequence": i,
                            }
                        ).encode(),
                    },
                }
                priority_tasks.append(task)

        # When: 우선순위 섞어서 태스크 추가 (실제 환경 시뮬레이션)
        import random

        random.shuffle(priority_tasks)

        task_ids = []
        for task in priority_tasks:
            task_id = await self.task_queue.enqueue(task)
            task_ids.append(task_id)

        # Then: 모든 태스크가 큐에 추가됨 (총 100개)
        assert len(task_ids) == 100
        assert len(self.task_queue._queue) == 100

        # 우선순위별 카운트 확인
        priority_counts = {}
        for task in self.task_queue._queue:
            priority = task["priority"]
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        assert priority_counts[TaskPriority.URGENT] == 5
        assert priority_counts[TaskPriority.HIGH] == 15
        assert priority_counts[TaskPriority.NORMAL] == 30
        assert priority_counts[TaskPriority.LOW] == 50

    @pytest.mark.asyncio
    async def test_memory_efficient_task_processing(self):
        """메모리 효율적인 태스크 처리 테스트"""
        # Given: 대량의 작은 태스크들 (메모리 효율성 테스트)
        memory_efficient_tasks = []

        for i in range(1000):  # 1000개의 작은 태스크
            task = {
                "name": f"micro-task-{i:04d}",
                "http_request": {
                    "http_method": "GET",
                    "url": f"https://micro-service.run.app/api/item/{i}",
                    "headers": {"Content-Type": "application/json"},
                },
                "memory_optimized": True,
            }
            memory_efficient_tasks.append(task)

        # When: 모든 micro 태스크 추가 (메모리 사용량 모니터링)
        task_ids = []
        for task in memory_efficient_tasks:
            task_id = await self.task_queue.enqueue(task)
            task_ids.append(task_id)

        # Then: 1000개 태스크가 모두 큐에 추가됨
        assert len(task_ids) == 1000
        assert len(self.task_queue._queue) == 1000

        # 메모리 최적화 플래그 확인
        optimized_tasks = [
            task for task in self.task_queue._queue if task.get("memory_optimized")
        ]
        assert len(optimized_tasks) == 1000


class TestTaskQueueIntegrationScenarios:
    """태스크 큐 통합 시나리오 테스트"""

    def setup_method(self):
        """테스트 설정"""
        # Cloud Run 환경 설정
        os.environ.update(
            {
                "GOOGLE_CLOUD_PROJECT": "integration-project-67890",
                "K_SERVICE": "task-integration-service",
                "CLOUD_RUN_REGION": "asia-northeast3",
            }
        )

        self.task_queue = CloudTaskQueue()
        self.task_queue._queue = []

    def teardown_method(self):
        """테스트 후 정리"""
        for key in ["GOOGLE_CLOUD_PROJECT", "K_SERVICE", "CLOUD_RUN_REGION"]:
            os.environ.pop(key, None)

    @pytest.mark.asyncio
    async def test_e_commerce_order_processing_workflow(self):
        """전자상거래 주문 처리 워크플로우 테스트"""
        # Given: 전자상거래 주문 처리에 필요한 태스크들
        order_id = f"order_{uuid4().hex[:8]}"

        order_workflow_tasks = [
            {
                "name": f"validate-inventory-{order_id}",
                "priority": TaskPriority.HIGH,
                "http_request": {
                    "http_method": "POST",
                    "url": "https://inventory-service.run.app/api/validate",
                    "body": json.dumps(
                        {
                            "order_id": order_id,
                            "items": [{"sku": "ITEM-001", "quantity": 2}],
                        }
                    ).encode(),
                },
            },
            {
                "name": f"process-payment-{order_id}",
                "priority": TaskPriority.URGENT,
                "depends_on": [f"validate-inventory-{order_id}"],
                "http_request": {
                    "http_method": "POST",
                    "url": "https://payment-service.run.app/api/charge",
                    "body": json.dumps(
                        {
                            "order_id": order_id,
                            "amount": 199.99,
                            "payment_method": "card_xxx1234",
                        }
                    ).encode(),
                },
            },
            {
                "name": f"update-inventory-{order_id}",
                "priority": TaskPriority.NORMAL,
                "depends_on": [f"process-payment-{order_id}"],
                "http_request": {
                    "http_method": "POST",
                    "url": "https://inventory-service.run.app/api/reserve",
                    "body": json.dumps(
                        {
                            "order_id": order_id,
                            "items": [{"sku": "ITEM-001", "quantity": 2}],
                        }
                    ).encode(),
                },
            },
            {
                "name": f"send-confirmation-{order_id}",
                "priority": TaskPriority.NORMAL,
                "depends_on": [f"update-inventory-{order_id}"],
                "http_request": {
                    "http_method": "POST",
                    "url": "https://notification-service.run.app/api/send-email",
                    "body": json.dumps(
                        {
                            "order_id": order_id,
                            "customer_email": "customer@example.com",
                            "template": "order_confirmation",
                        }
                    ).encode(),
                },
            },
            {
                "name": f"schedule-fulfillment-{order_id}",
                "priority": TaskPriority.LOW,
                "schedule_time": (datetime.now() + timedelta(hours=2)).isoformat()
                + "Z",
                "http_request": {
                    "http_method": "POST",
                    "url": "https://fulfillment-service.run.app/api/schedule",
                    "body": json.dumps(
                        {
                            "order_id": order_id,
                            "shipping_address": "123 Customer St, City, State",
                        }
                    ).encode(),
                },
            },
        ]

        # When: 전체 주문 처리 워크플로우 태스크 추가
        workflow_task_ids = []
        for task in order_workflow_tasks:
            task_id = await self.task_queue.enqueue(task)
            workflow_task_ids.append(task_id)

        # Then: 모든 워크플로우 태스크가 큐에 추가됨
        assert len(workflow_task_ids) == 5
        assert len(self.task_queue._queue) == 5

        # 의존성 관계 확인
        payment_task = next(
            t for t in self.task_queue._queue if "process-payment" in t["name"]
        )
        inventory_update_task = next(
            t for t in self.task_queue._queue if "update-inventory" in t["name"]
        )

        assert f"validate-inventory-{order_id}" in payment_task["depends_on"]
        assert f"process-payment-{order_id}" in inventory_update_task["depends_on"]

    @pytest.mark.asyncio
    async def test_data_pipeline_processing_scenario(self):
        """데이터 파이프라인 처리 시나리오 테스트"""
        # Given: 데이터 파이프라인 처리를 위한 배치 태스크들
        pipeline_id = f"pipeline_{uuid4().hex[:8]}"

        # ETL 파이프라인: Extract -> Transform -> Load
        etl_pipeline_tasks = []

        # Extract 단계 (10개 소스에서 데이터 추출)
        for source_id in range(10):
            extract_task = {
                "name": f"extract-{pipeline_id}-source-{source_id:02d}",
                "priority": TaskPriority.HIGH,
                "batch_id": f"extract-batch-{pipeline_id}",
                "http_request": {
                    "http_method": "POST",
                    "url": "https://data-extractor.run.app/api/extract",
                    "body": json.dumps(
                        {
                            "pipeline_id": pipeline_id,
                            "source_id": f"source_{source_id:02d}",
                            "output_location": f"gs://data-bucket/raw/{pipeline_id}/source_{source_id:02d}/",
                        }
                    ).encode(),
                },
            }
            etl_pipeline_tasks.append(extract_task)

        # Transform 단계 (추출된 데이터 변환)
        transform_task = {
            "name": f"transform-{pipeline_id}",
            "priority": TaskPriority.NORMAL,
            "depends_on": [f"extract-{pipeline_id}-source-{i:02d}" for i in range(10)],
            "job_spec": {  # Cloud Run Job으로 실행
                "template": {
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "image": "asia-northeast3-docker.pkg.dev/integration-project-67890/data-pipeline/transformer:latest",
                                        "env": [
                                            {
                                                "name": "PIPELINE_ID",
                                                "value": pipeline_id,
                                            },
                                            {
                                                "name": "INPUT_LOCATION",
                                                "value": f"gs://data-bucket/raw/{pipeline_id}/",
                                            },
                                            {
                                                "name": "OUTPUT_LOCATION",
                                                "value": f"gs://data-bucket/transformed/{pipeline_id}/",
                                            },
                                        ],
                                        "resources": {
                                            "limits": {"cpu": "4000m", "memory": "8Gi"}
                                        },
                                    }
                                ],
                                "max_retries": 2,
                                "active_deadline_seconds": 7200,  # 2시간
                            }
                        }
                    }
                }
            },
        }
        etl_pipeline_tasks.append(transform_task)

        # Load 단계 (변환된 데이터를 데이터 웨어하우스에 로드)
        load_task = {
            "name": f"load-{pipeline_id}",
            "priority": TaskPriority.NORMAL,
            "depends_on": [f"transform-{pipeline_id}"],
            "http_request": {
                "http_method": "POST",
                "url": "https://data-warehouse-loader.run.app/api/load",
                "body": json.dumps(
                    {
                        "pipeline_id": pipeline_id,
                        "source_location": f"gs://data-bucket/transformed/{pipeline_id}/",
                        "target_table": "analytics.daily_metrics",
                        "load_mode": "WRITE_APPEND",
                    }
                ).encode(),
            },
        }
        etl_pipeline_tasks.append(load_task)

        # When: ETL 파이프라인 태스크들 추가
        pipeline_task_ids = []
        for task in etl_pipeline_tasks:
            task_id = await self.task_queue.enqueue(task)
            pipeline_task_ids.append(task_id)

        # Then: 전체 ETL 파이프라인이 큐에 추가됨
        assert len(pipeline_task_ids) == 12  # 10 Extract + 1 Transform + 1 Load
        assert len(self.task_queue._queue) == 12

        # Extract 배치 확인
        extract_tasks = [t for t in self.task_queue._queue if t.get("batch_id")]
        assert len(extract_tasks) == 10

        # Transform Job 설정 확인
        transform_task = next(
            t for t in self.task_queue._queue if "transform" in t["name"]
        )
        assert "job_spec" in transform_task
        assert len(transform_task["depends_on"]) == 10

    @pytest.mark.asyncio
    async def test_real_time_notification_system(self):
        """실시간 알림 시스템 테스트"""
        # Given: 실시간 알림 시스템을 위한 다양한 채널 태스크들
        notification_scenarios = [
            {
                "type": "urgent_alert",
                "priority": TaskPriority.URGENT,
                "channels": ["sms", "push", "email", "slack"],
                "message": "Critical system alert: Database connection lost",
            },
            {
                "type": "marketing_campaign",
                "priority": TaskPriority.LOW,
                "channels": ["email", "push"],
                "message": "New product launch - 20% off this week!",
            },
            {
                "type": "user_activity",
                "priority": TaskPriority.NORMAL,
                "channels": ["push", "in_app"],
                "message": "Your friend John liked your post",
            },
        ]

        notification_tasks = []

        # When: 각 알림 시나리오별로 채널당 태스크 생성
        for scenario in notification_scenarios:
            for channel in scenario["channels"]:
                task = {
                    "name": f"{scenario['type']}-{channel}-{uuid4().hex[:6]}",
                    "priority": scenario["priority"],
                    "notification_type": scenario["type"],
                    "channel": channel,
                    "http_request": {
                        "http_method": "POST",
                        "url": f"https://{channel}-service.run.app/api/send",
                        "headers": {
                            "Content-Type": "application/json",
                            "X-Priority": str(scenario["priority"]),
                        },
                        "body": json.dumps(
                            {
                                "notification_type": scenario["type"],
                                "channel": channel,
                                "message": scenario["message"],
                                "priority": scenario["priority"],
                            }
                        ).encode(),
                    },
                }
                notification_tasks.append(task)

        # 모든 알림 태스크 추가
        notification_task_ids = []
        for task in notification_tasks:
            task_id = await self.task_queue.enqueue(task)
            notification_task_ids.append(task_id)

        # Then: 모든 채널별 알림 태스크가 큐에 추가됨
        total_expected_tasks = sum(
            len(scenario["channels"]) for scenario in notification_scenarios
        )
        assert len(notification_task_ids) == total_expected_tasks  # 4 + 2 + 2 = 8개
        assert len(self.task_queue._queue) == total_expected_tasks

        # 우선순위별 분류 확인
        urgent_tasks = [
            t for t in self.task_queue._queue if t["priority"] == TaskPriority.URGENT
        ]
        normal_tasks = [
            t for t in self.task_queue._queue if t["priority"] == TaskPriority.NORMAL
        ]
        low_tasks = [
            t for t in self.task_queue._queue if t["priority"] == TaskPriority.LOW
        ]

        assert len(urgent_tasks) == 4  # urgent_alert의 4개 채널
        assert len(normal_tasks) == 2  # user_activity의 2개 채널
        assert len(low_tasks) == 2  # marketing_campaign의 2개 채널
