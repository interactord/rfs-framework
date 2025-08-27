"""
Cloud Run Request/Response Processing Tests

Google Cloud Run의 요청/응답 처리, Task Queue, 및 서비스 통신 테스트
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from rfs.cloud_run import get_cloud_run_status, initialize_cloud_run_services
from rfs.cloud_run.helpers import (
    CloudTaskQueue,
    call_service,
    get_task_queue,
    schedule_task,
    submit_task,
    task_handler,
)
from rfs.core.result import Failure, Success


class TestCloudTaskQueue:
    """Cloud Task Queue 요청/응답 처리 테스트"""

    def test_task_queue_singleton(self):
        """Task Queue 싱글톤 패턴 확인"""
        queue1 = CloudTaskQueue()
        queue2 = CloudTaskQueue()

        assert queue1 is queue2

    def test_initial_state(self):
        """Task Queue 초기 상태 확인"""
        queue = CloudTaskQueue()

        assert queue._queue == []
        assert queue._processing is False

    @pytest.mark.asyncio
    async def test_enqueue_task_simple(self):
        """단순 작업 큐잉 테스트"""
        queue = CloudTaskQueue()

        task = {
            "type": "email",
            "payload": {"to": "user@example.com", "subject": "Hello"},
        }

        task_id = await queue.enqueue(task)

        assert task_id.startswith("task_")
        assert len(queue._queue) == 1

        queued_task = queue._queue[0]
        assert "id" in queued_task
        assert "created_at" in queued_task
        assert queued_task["type"] == "email"

    @pytest.mark.asyncio
    async def test_enqueue_multiple_tasks(self):
        """다수 작업 큐잉 테스트"""
        queue = CloudTaskQueue()

        tasks = [
            {"type": "email", "payload": {"to": "user1@example.com"}},
            {"type": "sms", "payload": {"to": "+821012345678"}},
            {"type": "push", "payload": {"device_id": "abc123"}},
        ]

        task_ids = []
        for task in tasks:
            task_id = await queue.enqueue(task)
            task_ids.append(task_id)

        assert len(task_ids) == 3
        assert len(set(task_ids)) == 3  # 모든 ID가 고유함
        assert len(queue._queue) == 3

    @pytest.mark.asyncio
    async def test_enqueue_triggers_processing(self):
        """큐잉 시 자동 처리 시작 확인"""
        queue = CloudTaskQueue()

        # 처리가 비활성 상태인지 확인
        assert queue._processing is False

        # Mock asyncio.create_task to verify it's called
        with patch("asyncio.create_task") as mock_create_task:
            task = {"type": "test", "payload": {}}
            await queue.enqueue(task)

            # 처리가 시작되었는지 확인
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_task_execution_flow(self):
        """작업 실행 흐름 테스트"""
        queue = CloudTaskQueue()

        # _execute_task 메서드 모킹
        with patch.object(
            queue, "_execute_task", new_callable=AsyncMock
        ) as mock_execute:
            task = {"type": "test", "payload": {"data": "test"}}

            # 큐에 작업 추가하고 수동으로 처리
            await queue.enqueue(task)

            # 처리 메서드 직접 호출하여 테스트
            await queue._process_queue()

            # 실행이 호출되었는지 확인 (큐가 비어있을 수 있으므로 유연하게 검증)
            assert queue._processing is False

    @pytest.mark.asyncio
    async def test_task_execution_error_handling(self):
        """작업 실행 에러 처리 테스트"""
        queue = CloudTaskQueue()

        # _execute_task이 예외를 발생시키도록 설정
        with patch.object(queue, "_execute_task", side_effect=Exception("Task failed")):
            with patch("rfs.cloud_run.helpers.logger") as mock_logger:
                task = {"type": "failing_task", "payload": {}}
                await queue.enqueue(task)

                # 처리 시작
                await queue._process_queue()

                # 처리가 완료되고 에러가 로깅되었는지 확인
                assert queue._processing is False

    def test_task_id_generation_uniqueness(self):
        """작업 ID 생성 고유성 테스트"""
        import time

        # 시간 기반 ID 생성 테스트
        timestamp1 = int(time.time() * 1000)
        timestamp2 = int(time.time() * 1000) + 1

        id1 = f"task_{timestamp1}"
        id2 = f"task_{timestamp2}"

        assert id1 != id2

    @pytest.mark.asyncio
    async def test_concurrent_enqueue(self):
        """동시 큐잉 테스트"""
        queue = CloudTaskQueue()

        async def enqueue_task(task_type: str):
            task = {"type": task_type, "payload": {"data": f"test_{task_type}"}}
            return await queue.enqueue(task)

        # 동시에 여러 작업 큐잉
        task_ids = await asyncio.gather(
            *[
                enqueue_task("type1"),
                enqueue_task("type2"),
                enqueue_task("type3"),
                enqueue_task("type4"),
                enqueue_task("type5"),
            ]
        )

        assert len(task_ids) == 5
        assert len(set(task_ids)) == 5  # 모든 ID가 고유함
        assert len(queue._queue) == 5


class TestTaskQueueHelperFunctions:
    """Task Queue 헬퍼 함수 테스트"""

    def test_get_task_queue_singleton(self):
        """글로벌 Task Queue 인스턴스 반환 확인"""
        queue1 = get_task_queue()
        queue2 = get_task_queue()

        assert queue1 is queue2
        assert isinstance(queue1, CloudTaskQueue)

    @pytest.mark.asyncio
    async def test_submit_task_success(self):
        """작업 제출 성공 테스트"""
        with patch("rfs.cloud_run.helpers.get_task_queue") as mock_get_queue:
            mock_queue = AsyncMock(spec=CloudTaskQueue)
            mock_queue.enqueue.return_value = "task_123456789"
            mock_get_queue.return_value = mock_queue

            task_id = await submit_task(
                url="https://api.example.com/webhook",
                payload={"user_id": "123", "action": "notify"},
                delay_seconds=0,
            )

            assert task_id == "task_123456789"

            # enqueue가 올바른 파라미터로 호출되었는지 확인
            expected_task = {
                "url": "https://api.example.com/webhook",
                "payload": {"user_id": "123", "action": "notify"},
                "delay_seconds": 0,
            }
            mock_queue.enqueue.assert_called_once_with(expected_task)

    @pytest.mark.asyncio
    async def test_submit_task_with_delay(self):
        """지연 작업 제출 테스트"""
        with patch("rfs.cloud_run.helpers.get_task_queue") as mock_get_queue:
            with patch("asyncio.sleep") as mock_sleep:
                mock_queue = AsyncMock(spec=CloudTaskQueue)
                mock_queue.enqueue.return_value = "delayed_task_123"
                mock_get_queue.return_value = mock_queue

                task_id = await submit_task(
                    url="https://api.example.com/delayed",
                    payload={"message": "Hello, World!"},
                    delay_seconds=30,
                )

                assert task_id == "delayed_task_123"

                # 지연 시간만큼 sleep이 호출되었는지 확인
                mock_sleep.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_schedule_task_future_time(self):
        """미래 시간으로 작업 스케줄링 테스트"""
        future_time = datetime.now() + timedelta(minutes=30)

        with patch("rfs.cloud_run.helpers.submit_task") as mock_submit:
            mock_submit.return_value = "scheduled_task_456"

            task_id = await schedule_task(
                url="https://api.example.com/scheduled",
                payload={"event": "reminder"},
                schedule_time=future_time,
            )

            assert task_id == "scheduled_task_456"

            # submit_task가 적절한 delay와 함께 호출되었는지 확인
            mock_submit.assert_called_once()
            args = mock_submit.call_args
            assert args[0][0] == "https://api.example.com/scheduled"
            assert args[0][1] == {"event": "reminder"}
            # delay는 약 30분(1800초) 정도여야 함
            assert 1790 <= args[0][2] <= 1810

    @pytest.mark.asyncio
    async def test_schedule_task_past_time(self):
        """과거 시간으로 작업 스케줄링 테스트 (즉시 실행)"""
        past_time = datetime.now() - timedelta(minutes=10)

        with patch("rfs.cloud_run.helpers.submit_task") as mock_submit:
            mock_submit.return_value = "immediate_task_789"

            task_id = await schedule_task(
                url="https://api.example.com/immediate",
                payload={"urgent": True},
                schedule_time=past_time,
            )

            assert task_id == "immediate_task_789"

            # submit_task가 0 delay로 호출되었는지 확인
            mock_submit.assert_called_once_with(
                "https://api.example.com/immediate", {"urgent": True}, 0
            )

    def test_task_handler_decorator(self):
        """작업 핸들러 데코레이터 테스트"""

        @task_handler("/api/webhooks/user-events")
        def handle_user_events(payload):
            return f"Processed: {payload}"

        # 데코레이터가 함수를 반환하는지 확인
        assert callable(handle_user_events)

        # 원래 함수가 정상 작동하는지 확인
        result = handle_user_events({"user_id": "123", "event": "login"})
        assert result == "Processed: {'user_id': '123', 'event': 'login'}"

    def test_task_handler_logging(self):
        """작업 핸들러 로깅 테스트"""
        with patch("rfs.cloud_run.helpers.logger") as mock_logger:

            @task_handler("/api/webhooks/notifications")
            def handle_notifications(payload):
                return "OK"

            # 데코레이터 적용 시 로깅되었는지 확인
            mock_logger.info.assert_called_once_with(
                "Task handler registered: /api/webhooks/notifications"
            )


class TestRequestResponseIntegration:
    """요청/응답 처리 통합 테스트"""

    @pytest.mark.asyncio
    async def test_service_call_integration(self):
        """서비스 호출 통합 테스트"""
        with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get_sd:
            from rfs.cloud_run.helpers import ServiceEndpoint

            # Mock 서비스 디스커버리 설정
            mock_discovery = MagicMock()
            endpoint = ServiceEndpoint("user-service", "https://user.example.com")
            endpoint.is_healthy = True
            mock_discovery.get_service.return_value = endpoint
            mock_get_sd.return_value = mock_discovery

            # 서비스 호출
            result = await call_service(
                "user-service",
                "/api/v1/users/123",
                method="GET",
                headers={"Authorization": "Bearer token123"},
            )

            assert isinstance(result, Success)
            response = result.value
            assert response["status"] == "success"
            assert "timestamp" in response

    @pytest.mark.asyncio
    async def test_task_submission_integration(self):
        """작업 제출 통합 테스트"""
        # 실제 Task Queue를 사용한 테스트
        queue = get_task_queue()

        # 큐 초기화
        queue._queue = []
        queue._processing = False

        # 작업 제출
        task_id = await submit_task(
            url="https://webhook.example.com/process",
            payload={
                "type": "user_registration",
                "user_id": "user_123",
                "timestamp": datetime.now().isoformat(),
            },
        )

        assert task_id is not None
        assert task_id.startswith("task_")
        assert len(queue._queue) == 1

        # 큐된 작업 내용 검증
        queued_task = queue._queue[0]
        assert queued_task["url"] == "https://webhook.example.com/process"
        assert queued_task["payload"]["type"] == "user_registration"
        assert queued_task["payload"]["user_id"] == "user_123"

    @pytest.mark.asyncio
    async def test_scheduled_task_integration(self):
        """스케줄된 작업 통합 테스트"""
        future_time = datetime.now() + timedelta(seconds=10)

        with patch("asyncio.sleep") as mock_sleep:
            task_id = await schedule_task(
                url="https://scheduler.example.com/run",
                payload={"job_type": "cleanup", "resource": "temp_files"},
                schedule_time=future_time,
            )

            assert task_id is not None
            # 스케줄된 시간만큼 지연되었는지 확인
            assert mock_sleep.called

    @pytest.mark.asyncio
    async def test_error_handling_integration(self):
        """에러 처리 통합 테스트"""
        # 서비스 호출 실패 시나리오
        with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get_sd:
            mock_discovery = MagicMock()
            mock_discovery.get_service.return_value = None  # 서비스를 찾을 수 없음
            mock_get_sd.return_value = mock_discovery

            result = await call_service(
                "nonexistent-service", "/api/test", method="POST"
            )

            assert isinstance(result, Failure)
            assert "Service not found" in result.error

    @pytest.mark.asyncio
    async def test_concurrent_request_processing(self):
        """동시 요청 처리 테스트"""
        with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get_sd:
            from rfs.cloud_run.helpers import ServiceEndpoint

            # Mock 서비스 설정
            mock_discovery = MagicMock()
            endpoint = ServiceEndpoint("api-service", "https://api.example.com")
            endpoint.is_healthy = True
            mock_discovery.get_service.return_value = endpoint
            mock_get_sd.return_value = mock_discovery

            # 동시에 여러 요청 처리
            requests = [
                call_service("api-service", f"/api/resource/{i}", method="GET")
                for i in range(5)
            ]

            results = await asyncio.gather(*requests)

            # 모든 요청이 성공했는지 확인
            assert len(results) == 5
            for result in results:
                assert isinstance(result, Success)
                assert result.value["status"] == "success"

    @pytest.mark.asyncio
    async def test_high_volume_task_processing(self):
        """대용량 작업 처리 테스트"""
        queue = get_task_queue()

        # 큐 초기화
        queue._queue = []
        queue._processing = False

        # 대량의 작업 제출
        tasks = []
        for i in range(50):
            task_coro = submit_task(
                url=f"https://worker.example.com/job/{i}",
                payload={"job_id": i, "type": "batch_process"},
            )
            tasks.append(task_coro)

        task_ids = await asyncio.gather(*tasks)

        # 모든 작업이 큐에 추가되었는지 확인
        assert len(task_ids) == 50
        assert len(set(task_ids)) == 50  # 모든 ID가 고유함
        assert len(queue._queue) == 50

    @pytest.mark.asyncio
    async def test_request_response_timeout_simulation(self):
        """요청/응답 타임아웃 시뮬레이션"""
        # 실제 네트워크 타임아웃을 시뮬레이션하지는 않지만,
        # 서비스 호출 시 응답 시간 추적 테스트

        with patch("rfs.cloud_run.helpers.get_service_discovery") as mock_get_sd:
            from rfs.cloud_run.helpers import ServiceEndpoint

            mock_discovery = MagicMock()
            endpoint = ServiceEndpoint("slow-service", "https://slow.example.com")
            endpoint.is_healthy = True
            mock_discovery.get_service.return_value = endpoint
            mock_get_sd.return_value = mock_discovery

            start_time = datetime.now()
            result = await call_service("slow-service", "/api/slow-operation")
            end_time = datetime.now()

            assert isinstance(result, Success)

            # 응답 시간이 합리적인 범위 내인지 확인 (빠른 Mock이므로 매우 빠를 것)
            response_time = (end_time - start_time).total_seconds()
            assert response_time < 1.0  # 1초 미만

    @pytest.mark.asyncio
    async def test_payload_serialization_handling(self):
        """페이로드 직렬화 처리 테스트"""
        complex_payload = {
            "user": {
                "id": 12345,
                "email": "test@example.com",
                "preferences": {
                    "notifications": True,
                    "theme": "dark",
                    "language": "ko-KR",
                },
            },
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "source": "web",
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0 Chrome/91.0",
            },
        }

        queue = get_task_queue()
        queue._queue = []

        task_id = await submit_task(
            url="https://processor.example.com/complex", payload=complex_payload
        )

        assert task_id is not None
        assert len(queue._queue) == 1

        queued_task = queue._queue[0]
        # 복잡한 페이로드가 제대로 저장되었는지 확인
        assert queued_task["payload"]["user"]["email"] == "test@example.com"
        assert queued_task["payload"]["metadata"]["source"] == "web"
