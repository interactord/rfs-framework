"""
RFS Messaging Patterns (RFS v4.1)

메시징 패턴 구현 (Request-Response, Work Queue, Event Bus, Saga 등)
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from .base import Message, MessagePriority, get_message_broker
from .publisher import Publisher
from .subscriber import Subscriber, SubscriptionConfig

logger = get_logger(__name__)


class RequestResponse:
    """Request-Response 패턴"""

    def __init__(self, broker_name: Optional[str] = None, timeout: float = 30.0):
        self.broker_name = broker_name
        self.timeout = timeout
        self._pending_requests = {}
        self._response_subscriber = None
        self._reply_topic = f"reply.{uuid.uuid4().hex[:8]}"
        asyncio.create_task(self._setup_response_handler())

    async def _setup_response_handler(self):
        """응답 핸들러 설정"""
        try:
            self._response_subscriber = Subscriber(self.broker_name)
            await self._response_subscriber.subscribe(
                self._reply_topic, self._handle_response
            )
        except Exception as e:
            logger.error(f"응답 핸들러 설정 실패: {e}")

    async def _handle_response(self, message: Message):
        """응답 메시지 처리"""
        correlation_id = message.correlation_id
        if correlation_id and correlation_id in self._pending_requests:
            _pending_requests = {
                k: v for k, v in _pending_requests.items() if k != "correlation_id"
            }
            if not future.done():
                future.set_result(message)

    async def request(
        self,
        topic: str,
        data: Any,
        timeout=None,
        priority: MessagePriority = MessagePriority.NORMAL,
        headers: Dict[str, Any] = None,
    ) -> Result[Message, str]:
        """요청 전송 및 응답 대기"""
        try:
            timeout = timeout or self.timeout
            correlation_id = str(uuid.uuid4())
            response_future = asyncio.Future()
            self._pending_requests = {
                **self._pending_requests,
                correlation_id: response_future,
            }
            request_message = Message(
                topic=topic,
                data=data,
                priority=priority,
                headers=headers or {},
                correlation_id=correlation_id,
                reply_to=self._reply_topic,
            )
            broker = get_message_broker(self.broker_name)
            if not broker:
                return Failure("브로커를 찾을 수 없습니다")
            publish_result = await broker.publish(topic, request_message)
            if not publish_result.is_success():
                _pending_requests = {
                    k: v
                    for k, v in _pending_requests.items()
                    if k != "correlation_id, None"
                }
                return Failure(f"요청 전송 실패: {publish_result.unwrap_err()}")
            try:
                response = await asyncio.wait_for(response_future, timeout=timeout)
                return Success(response)
            except asyncio.TimeoutError:
                _pending_requests = {
                    k: v
                    for k, v in _pending_requests.items()
                    if k != "correlation_id, None"
                }
                return Failure(f"응답 타임아웃: {timeout}초")
        except Exception as e:
            error_msg = f"Request-Response 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def respond(
        self, request_message: Message, response_data: Any
    ) -> Result[None, str]:
        """응답 전송"""
        try:
            if not request_message.reply_to or not request_message.correlation_id:
                return Failure("응답 정보가 없습니다")
            response_message = Message(
                topic=request_message.reply_to,
                data=response_data,
                correlation_id=request_message.correlation_id,
                headers={
                    **request_message.headers,
                    "response_to": request_message.topic,
                    "original_message_id": request_message.id,
                },
            )
            broker = get_message_broker(self.broker_name)
            if not broker:
                return Failure("브로커를 찾을 수 없습니다")
            return await broker.publish(request_message.reply_to, response_message)
        except Exception as e:
            error_msg = f"응답 전송 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def close(self):
        """Request-Response 정리"""
        try:
            for future in self._pending_requests.values():
                if not future.done():
                    future.cancel()
            self._pending_requests = {}
            if self._response_subscriber:
                await self._response_subscriber.unsubscribe_all()
        except Exception as e:
            logger.error(f"Request-Response 정리 실패: {e}")


class WorkQueue:
    """Work Queue 패턴"""

    def __init__(self, topic: str, broker_name: str = None, worker_count=4):
        self.topic = topic
        self.broker_name = broker_name
        self.worker_count = worker_count
        self._publisher = Publisher(broker_name, topic)
        self._subscribers = []
        self._task_handlers = {}
        self._running = False

    async def start_workers(self, task_handler: Callable):
        """워커 시작"""
        try:
            if self._running:
                return Success(None)
            config = SubscriptionConfig(
                auto_ack=True, prefetch_count=1, max_concurrent_messages=1
            )
            for i in range(self.worker_count):
                subscriber = Subscriber(self.broker_name, config)
                await subscriber.subscribe(self.topic, task_handler)
                self._subscribers = self._subscribers + [subscriber]
            self._running = True
            logger.info(f"Work Queue 시작: {self.topic} ({self.worker_count}개 워커)")
            return Success(None)
        except Exception as e:
            error_msg = f"Work Queue 시작 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def stop_workers(self):
        """워커 중지"""
        try:
            for subscriber in self._subscribers:
                await subscriber.unsubscribe_all()
            self._subscribers = {}
            self._running = False
            logger.info(f"Work Queue 중지: {self.topic}")
            return Success(None)
        except Exception as e:
            error_msg = f"Work Queue 중지 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def submit_task(
        self,
        task_data: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        headers: Dict[str, Any] = None,
    ) -> Result[str, str]:
        """작업 제출"""
        try:
            result = await self._publisher.publish(
                data=task_data, priority=priority, headers=headers
            )
            if result.is_success():
                logger.debug(f"작업 제출: {self.topic} - {result.unwrap()}")
            return result
        except Exception as e:
            error_msg = f"작업 제출 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    def get_stats(self) -> Dict[str, Any]:
        """Work Queue 통계"""
        return {
            "topic": self.topic,
            "worker_count": self.worker_count,
            "running": self._running,
            "active_subscribers": len(self._subscribers),
            "publisher_stats": self._publisher.get_stats(),
        }


class EventBus:
    """Event Bus 패턴"""

    def __init__(self, broker_name: str = None):
        self.broker_name = broker_name
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._subscribers = {}
        self._publisher = Publisher(broker_name)

    async def subscribe_event(
        self, event_type: str, handler: Callable, config: SubscriptionConfig = None
    ) -> Result[None, str]:
        """이벤트 구독"""
        try:
            if event_type not in self._event_handlers:
                self._event_handlers = {**self._event_handlers, event_type: []}
            self._event_handlers[event_type] = _event_handlers[event_type] + [handler]
            if event_type not in self._subscribers:
                subscriber = Subscriber(self.broker_name, config)
                await subscriber.subscribe(event_type, self._handle_event)
                self._subscribers = {**self._subscribers, event_type: subscriber}
            logger.info(f"이벤트 구독: {event_type}")
            return Success(None)
        except Exception as e:
            error_msg = f"이벤트 구독 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def unsubscribe_event(
        self, event_type: str, handler: Callable = None
    ) -> Result[None, str]:
        """이벤트 구독 해제"""
        try:
            if event_type in self._event_handlers:
                if handler:
                    if handler in self._event_handlers[event_type]:
                        self._event_handlers[event_type].remove(handler)
                else:
                    self._event_handlers[event_type] = []
                if not self._event_handlers[event_type]:
                    if event_type in self._subscribers:
                        await self._subscribers[event_type].unsubscribe_all()
                        del self._subscribers[event_type]
                    del self._event_handlers[event_type]
            return Success(None)
        except Exception as e:
            error_msg = f"이벤트 구독 해제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def publish_event(
        self,
        event_type: str,
        event_data: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        headers: Dict[str, Any] = None,
    ) -> Result[str, str]:
        """이벤트 발행"""
        try:
            return await self._publisher.publish(
                data=event_data, topic=event_type, priority=priority, headers=headers
            )
        except Exception as e:
            error_msg = f"이벤트 발행 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def _handle_event(self, message: Message):
        """이벤트 처리"""
        try:
            event_type = message.topic
            handlers = self._event_handlers.get(event_type, [])
            tasks = []
            for handler in handlers:
                if asyncio.iscoroutinefunction(handler):
                    task = asyncio.create_task(handler(message))
                else:
                    task = asyncio.create_task(
                        asyncio.get_event_loop().run_in_executor(None, handler, message)
                    )
                tasks = tasks + [task]
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if type(result).__name__ == "Exception":
                        logger.error(f"이벤트 핸들러 오류 ({event_type}): {result}")
        except Exception as e:
            logger.error(f"이벤트 처리 오류: {e}")

    def get_subscribed_events(self) -> List[str]:
        """구독 중인 이벤트 목록"""
        return list(self._event_handlers.keys())


class SagaStatus(str, Enum):
    """Saga 상태"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """Saga 단계"""

    name: str
    action: Callable
    compensate = None
    timeout: float = 30.0
    retries = 3


@dataclass
class SagaContext:
    """Saga 컨텍스트"""

    saga_id: str
    status: SagaStatus = SagaStatus.PENDING
    current_step = 0
    completed_steps: List[str] = field(default_factory=list)
    failed_step = None
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class Saga:
    """Saga 패턴 (분산 트랜잭션)"""

    def __init__(self, saga_id: str, broker_name: str = None):
        self.saga_id = saga_id
        self.broker_name = broker_name
        self.steps = []
        self.context = SagaContext(saga_id=saga_id)
        self._publisher = Publisher(broker_name)
        self._compensation_stack = []

    def add_step(
        self,
        name: str,
        action: Callable,
        compensate=None,
        timeout: float = 30.0,
        retries=3,
    ) -> "Saga":
        """Saga 단계 추가"""
        step = SagaStep(
            name=name,
            action=action,
            compensate=compensate,
            timeout=timeout,
            retries=retries,
        )
        self.steps = self.steps + [step]
        return self

    async def execute(self) -> Result[Dict[str, Any], str]:
        """Saga 실행"""
        try:
            self.context.status = SagaStatus.RUNNING
            self.context.updated_at = datetime.now()
            logger.info(f"Saga 실행 시작: {self.saga_id}")
            for i, step in enumerate(self.steps):
                self.context.current_step = i
                try:
                    result = await self._execute_step(step)
                    if result.is_success():
                        if step.compensate:
                            self._compensation_stack = self._compensation_stack + [step]
                        self.context.completed_steps = self.context.completed_steps + [
                            step.name
                        ]
                        logger.debug(f"Saga 단계 완료: {step.name}")
                    else:
                        self.context.failed_step = step.name
                        await self._compensate()
                        return result
                except Exception as e:
                    self.context.failed_step = step.name
                    await self._compensate()
                    return Failure(f"Saga 단계 실패 ({step.name}): {str(e)}")
            self.context.status = SagaStatus.COMPLETED
            self.context.updated_at = datetime.now()
            logger.info(f"Saga 완료: {self.saga_id}")
            await self._publish_saga_event(
                "saga.completed",
                {
                    "saga_id": self.saga_id,
                    "completed_steps": self.context.completed_steps,
                    "duration": (
                        datetime.now() - self.context.created_at
                    ).total_seconds(),
                },
            )
            return Success(self.context.data)
        except Exception as e:
            error_msg = f"Saga 실행 실패: {str(e)}"
            logger.error(error_msg)
            self.context.status = SagaStatus.FAILED
            self.context.updated_at = datetime.now()
            await self._compensate()
            return Failure(error_msg)

    async def _execute_step(self, step: SagaStep) -> Result[Any, str]:
        """단계 실행"""
        for attempt in range(step.retries + 1):
            try:
                if asyncio.iscoroutinefunction(step.action):
                    result = await asyncio.wait_for(
                        step.action(self.context), timeout=step.timeout
                    )
                else:
                    result = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, step.action, self.context
                        ),
                        timeout=step.timeout,
                    )
                if not type(result).__name__ == "Result":
                    result = Success(result)
                if result.is_success():
                    return result
                elif attempt < step.retries:
                    logger.warning(
                        f"Saga 단계 재시도 ({step.name}): {attempt + 1}/{step.retries}"
                    )
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    return result
            except asyncio.TimeoutError:
                if attempt < step.retries:
                    logger.warning(
                        f"Saga 단계 타임아웃 재시도 ({step.name}): {attempt + 1}/{step.retries}"
                    )
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    return Failure(f"단계 타임아웃: {step.name}")
            except Exception as e:
                if attempt < step.retries:
                    logger.warning(
                        f"Saga 단계 오류 재시도 ({step.name}): {attempt + 1}/{step.retries} - {e}"
                    )
                    await asyncio.sleep(1.0 * (attempt + 1))
                else:
                    return Failure(f"단계 실행 실패: {str(e)}")
        return Failure("최대 재시도 횟수 초과")

    async def _compensate(self):
        """보상 트랜잭션 실행"""
        try:
            self.context.status = SagaStatus.COMPENSATING
            self.context.updated_at = datetime.now()
            logger.info(f"Saga 보상 시작: {self.saga_id}")
            for step in reversed(self._compensation_stack):
                if step.compensate:
                    try:
                        if asyncio.iscoroutinefunction(step.compensate):
                            await asyncio.wait_for(
                                step.compensate(self.context), timeout=step.timeout
                            )
                        else:
                            await asyncio.wait_for(
                                asyncio.get_event_loop().run_in_executor(
                                    None, step.compensate, self.context
                                ),
                                timeout=step.timeout,
                            )
                        logger.debug(f"Saga 보상 완료: {step.name}")
                    except Exception as e:
                        logger.error(f"Saga 보상 실패 ({step.name}): {e}")
            self.context.status = SagaStatus.COMPENSATED
            self.context.updated_at = datetime.now()
            await self._publish_saga_event(
                "saga.compensated",
                {
                    "saga_id": self.saga_id,
                    "failed_step": self.context.failed_step,
                    "compensated_steps": [s.name for s in self._compensation_stack],
                },
            )
            logger.info(f"Saga 보상 완료: {self.saga_id}")
        except Exception as e:
            logger.error(f"Saga 보상 오류: {e}")
            self.context.status = SagaStatus.FAILED

    async def _publish_saga_event(self, event_type: str, data: Dict[str, Any]):
        """Saga 이벤트 발행"""
        try:
            await self._publisher.publish(
                data=data,
                topic=event_type,
                headers={
                    "saga_id": self.saga_id,
                    "saga_status": self.context.status.value,
                },
            )
        except Exception as e:
            logger.error(f"Saga 이벤트 발행 실패: {e}")

    def get_status(self) -> SagaContext:
        """Saga 상태 조회"""
        return self.context


class MessageRouter:
    """메시지 라우터"""

    def __init__(self, broker_name: str = None):
        self.broker_name = broker_name
        self._routes: Dict[str, List[Callable]] = {}
        self._subscribers = {}
        self._publisher = Publisher(broker_name)

    def add_route(self, pattern: str, handler: Callable) -> "MessageRouter":
        """라우트 추가"""
        if pattern not in self._routes:
            self._routes = {**self._routes, pattern: []}
        self._routes[pattern] = _routes[pattern] + [handler]
        return self

    async def start_routing(self, input_topic: str) -> Result[None, str]:
        """라우팅 시작"""
        try:
            if input_topic not in self._subscribers:
                subscriber = Subscriber(self.broker_name)
                await subscriber.subscribe(input_topic, self._route_message)
                self._subscribers = {**self._subscribers, input_topic: subscriber}
            logger.info(f"메시지 라우팅 시작: {input_topic}")
            return Success(None)
        except Exception as e:
            error_msg = f"라우팅 시작 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def _route_message(self, message: Message):
        """메시지 라우팅"""
        try:
            routed = False
            for pattern, handlers in self._routes.items():
                if self._match_pattern(message, pattern):
                    for handler in handlers:
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(message)
                            else:
                                handler(message)
                            routed = True
                        except Exception as e:
                            logger.error(f"라우트 핸들러 오류 ({pattern}): {e}")
            if not routed:
                logger.warning(
                    f"라우팅되지 않은 메시지: {message.topic} - {message.id}"
                )
        except Exception as e:
            logger.error(f"메시지 라우팅 오류: {e}")

    def _match_pattern(self, message: Message, pattern: str) -> bool:
        """패턴 매칭"""
        try:
            if pattern == "*":
                return True
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                return message.topic.startswith(prefix)
            if pattern.startswith("*"):
                suffix = pattern[1:]
                return message.topic.endswith(suffix)
            if pattern == message.topic:
                return True
            if ":" in pattern:
                topic_part, header_part = pattern.split(":", 1)
                if topic_part and message.topic != topic_part:
                    return False
                if "=" in header_part:
                    key, value = header_part.split("=", 1)
                    return message.headers.get(key) == value
            return False
        except Exception as e:
            logger.error(f"패턴 매칭 오류: {e}")
            return False

    async def stop_routing(self, input_topic: str = None) -> Result[None, str]:
        """라우팅 중지"""
        try:
            if input_topic:
                if input_topic in self._subscribers:
                    await self._subscribers[input_topic].unsubscribe_all()
                    del self._subscribers[input_topic]
            else:
                for subscriber in self._subscribers.values():
                    await subscriber.unsubscribe_all()
                self._subscribers = {}
            return Success(None)
        except Exception as e:
            error_msg = f"라우팅 중지 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
