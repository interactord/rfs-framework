"""
RFS Message Subscriber (RFS v4.1)

메시지 구독자 구현
"""

import asyncio
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from .base import Message, MessageBroker, get_message_broker

logger = get_logger(__name__)


@dataclass
class SubscriptionConfig:
    """구독 설정"""

    # 메시지 처리
    auto_ack: bool = True
    prefetch_count: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0  # 초

    # 필터링
    message_filter: Optional[Callable] = None
    header_filters: Optional[Dict[str, Any]] = None

    # 배치 처리
    batch_processing: bool = False
    batch_size: int = 10
    batch_timeout: float = 1.0  # 초

    # Dead Letter Queue
    enable_dlq: bool = True
    dlq_topic: Optional[str] = None

    # 기타
    max_concurrent_messages: int = 1
    timeout: Optional[float] = None  # 메시지 처리 타임아웃


class MessageHandler(ABC):
    """메시지 핸들러 인터페이스"""

    @abstractmethod
    async def handle(self, message: Message) -> Result[None, str]:
        """메시지 처리"""
        pass

    async def on_error(self, message: Message, error: Exception) -> bool:
        """에러 처리 (True 반환시 재시도 안함)"""
        logger.error(f"메시지 처리 오류: {error}")
        return False

    async def before_handle(self, message: Message) -> Result[None, str]:
        """처리 전 전처리"""
        return Success(None)

    async def after_handle(self, message: Message, result: Result) -> Result[None, str]:
        """처리 후 후처리"""
        return Success(None)


class FunctionMessageHandler(MessageHandler):
    """함수 기반 메시지 핸들러"""

    def __init__(self, handler_func: Callable):
        self.handler_func = handler_func

    async def handle(self, message: Message) -> Result[None, str]:
        """메시지 처리"""
        try:
            if asyncio.iscoroutinefunction(self.handler_func):
                result = await self.handler_func(message)
            else:
                result = self.handler_func(message)

            # Result 타입이 아니면 Success로 래핑
            if type(result).__name__ != "Result":
                result = Success(None)

            return result

        except Exception as e:
            return Failure(f"핸들러 함수 실행 실패: {str(e)}")


class Subscriber:
    """메시지 구독자"""

    def __init__(
        self,
        broker_name: Optional[str] = None,
        broker: Optional[MessageBroker] = None,
        config: Optional[SubscriptionConfig] = None,
    ):
        self.broker_name = broker_name
        self._broker = broker
        self.config = config or SubscriptionConfig()

        self._subscriptions: Dict[str, Dict[str, Any]] = (
            {}
        )  # topic -> subscription_info
        self._handlers = {}  # topic -> handler
        self._processing_tasks: Dict[str, Set[asyncio.Task]] = {}  # topic -> tasks

        self._stats = {
            "messages_received": 0,
            "messages_processed": 0,
            "messages_acked": 0,
            "messages_nacked": 0,
            "processing_errors": 0,
            "last_message_time": None,
        }

    @property
    def broker(self) -> Optional[MessageBroker]:
        """메시지 브로커"""
        if self._broker:
            return self._broker
        return get_message_broker(self.broker_name)

    async def subscribe(
        self,
        topic: str,
        handler: Union[MessageHandler, Callable],
        config: Optional[SubscriptionConfig] = None,
    ) -> Result[None, str]:
        """토픽 구독"""
        try:
            broker = self.broker
            if not broker:
                return Failure("메시지 브로커를 찾을 수 없습니다")

            subscription_config = config or self.config

            # 핸들러 등록
            if callable(handler) and type(handler).__name__ != "MessageHandler":
                handler = FunctionMessageHandler(handler)

            self._handlers = {**self._handlers, topic: handler}

            # 메시지 처리 함수 생성
            async def message_processor(message: Message):
                await self._process_message(topic, message, subscription_config)

            # 브로커에 구독
            result = await broker.subscribe(topic, message_processor)
            if not result.is_success():
                return result

            # 구독 정보 저장
            self._subscriptions = {
                **self._subscriptions,
                topic: {
                    "handler": handler,
                    "config": subscription_config,
                    "subscribed_at": datetime.now(),
                },
            }

            self._processing_tasks = {**self._processing_tasks, topic: set()}

            logger.info(f"토픽 구독: {topic}")
            return Success(None)

        except Exception as e:
            error_msg = f"구독 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def unsubscribe(self, topic: str) -> Result[None, str]:
        """구독 해제"""
        try:
            broker = self.broker
            if not broker:
                return Failure("메시지 브로커를 찾을 수 없습니다")

            # 진행 중인 작업 취소
            if topic in self._processing_tasks:
                for task in list(self._processing_tasks[topic]):
                    task.cancel()

                # 작업 완료 대기
                if self._processing_tasks[topic]:
                    await asyncio.gather(
                        *self._processing_tasks[topic], return_exceptions=True
                    )

                del self._processing_tasks[topic]

            # 브로커에서 구독 해제
            result = await broker.unsubscribe(topic)

            # 로컬 정보 제거
            _subscriptions = {
                k: v for k, v in _subscriptions.items() if k != "topic, None"
            }
            _handlers = {k: v for k, v in _handlers.items() if k != "topic, None"}

            logger.info(f"구독 해제: {topic}")
            return result

        except Exception as e:
            error_msg = f"구독 해제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def unsubscribe_all(self) -> Result[None, str]:
        """모든 구독 해제"""
        try:
            for topic in list(self._subscriptions.keys()):
                await self.unsubscribe(topic)

            return Success(None)

        except Exception as e:
            error_msg = f"전체 구독 해제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def _process_message(
        self, topic: str, message: Message, config: SubscriptionConfig
    ):
        """메시지 처리"""
        # 동시 처리 제한
        if len(self._processing_tasks[topic]) >= config.max_concurrent_messages:
            logger.warning(f"동시 처리 한계 도달: {topic}")
            return

        # 처리 태스크 생성
        task = asyncio.create_task(self._handle_message(topic, message, config))
        self._processing_tasks[topic].add(task)

        # 완료 시 태스크 제거
        def task_cleanup(task):
            self._processing_tasks[topic].discard(task)

        task.add_done_callback(task_cleanup)

    async def _handle_message(
        self, topic: str, message: Message, config: SubscriptionConfig
    ):
        """개별 메시지 처리"""
        try:
            self._stats = {
                **self._stats,
                "messages_received": self._stats["messages_received"] + 1,
            }
            self._stats = {**self._stats, "last_message_time": datetime.now()}

            # 메시지 필터링
            if not self._should_process_message(message, config):
                if config.auto_ack:
                    broker = self.broker
                    if broker:
                        await broker.ack_message(message)
                return

            # 타임아웃 설정
            timeout = config.timeout

            # 핸들러 실행
            handler = self._handlers.get(topic)
            if not handler:
                logger.error(f"핸들러를 찾을 수 없습니다: {topic}")
                return

            # 전처리
            before_result = await handler.before_handle(message)
            if not before_result.is_success():
                logger.error(f"전처리 실패: {before_result.unwrap_err()}")
                await self._handle_processing_error(
                    message, Exception(before_result.unwrap_err()), config
                )
                return

            # 메시지 처리
            try:
                if timeout:
                    result = await asyncio.wait_for(
                        handler.handle(message), timeout=timeout
                    )
                else:
                    result = await handler.handle(message)

                # 후처리
                await handler.after_handle(message, result)

                if result.is_success():
                    # 성공 처리
                    self._stats = {
                        **self._stats,
                        "messages_processed": self._stats["messages_processed"] + 1,
                    }

                    if config.auto_ack:
                        broker = self.broker
                        if broker:
                            await broker.ack_message(message)
                            self._stats = {
                                **self._stats,
                                "messages_acked": self._stats["messages_acked"] + 1,
                            }
                else:
                    # 실패 처리
                    error = Exception(result.unwrap_err())
                    await self._handle_processing_error(message, error, config)

            except asyncio.TimeoutError:
                logger.error(f"메시지 처리 타임아웃: {topic} - {message.id}")
                await self._handle_processing_error(
                    message, asyncio.TimeoutError("처리 시간 초과"), config
                )

            except Exception as e:
                await self._handle_processing_error(message, e, config)

        except Exception as e:
            logger.error(f"메시지 처리 중 예외: {e}")
            self._stats = {
                **self._stats,
                "processing_errors": self._stats["processing_errors"] + 1,
            }

    def _should_process_message(
        self, message: Message, config: SubscriptionConfig
    ) -> bool:
        """메시지 처리 여부 판단"""
        # 만료 확인
        if message.is_expired:
            logger.debug(f"만료된 메시지 스킵: {message.id}")
            return False

        # 커스텀 필터
        if config.message_filter:
            if not config.message_filter(message):
                return False
            logger.warning(f"메시지 필터 오류: {e}")
            return Failure("Operation failed")
        # 헤더 필터
        if config.header_filters:
            for key, expected_value in config.header_filters.items():
                if message.headers.get(key) != expected_value:
                    return False

        return True

    async def _handle_processing_error(
        self, message: Message, error: Exception, config: SubscriptionConfig
    ):
        """처리 오류 핸들링"""
        try:
            self._stats = {
                **self._stats,
                "processing_errors": self._stats["processing_errors"] + 1,
            }

            # 핸들러의 에러 처리 호출
            handler = self._handlers.get(message.topic)
            should_stop_retry = False

            if handler:
                should_stop_retry = await handler.on_error(message, error)

            broker = self.broker
            if not broker:
                return

            if should_stop_retry or not message.should_retry:
                # 재시도 중지 또는 최대 재시도 횟수 도달
                if config.enable_dlq:
                    # Dead Letter Queue로 이동
                    dlq_topic = config.dlq_topic or broker._make_dlq_topic(
                        message.topic
                    )
                    dlq_message = Message(
                        topic=dlq_topic,
                        data=message.data,
                        headers={
                            **message.headers,
                            "original_topic": message.topic,
                            "error_message": str(error),
                            "retry_count": message.retry_count,
                            "failed_at": datetime.now().isoformat(),
                        },
                    )
                    await broker.publish(dlq_topic, dlq_message)

                # NACK (재큐잉 없음)
                await broker.nack_message(message, requeue=False)
                self._stats = {
                    **self._stats,
                    "messages_nacked": self._stats["messages_nacked"] + 1,
                }
            else:
                # 재시도
                await asyncio.sleep(config.retry_delay)
                await broker.nack_message(message, requeue=True)
                self._stats = {
                    **self._stats,
                    "messages_nacked": self._stats["messages_nacked"] + 1,
                }

        except Exception as e:
            logger.error(f"오류 처리 중 예외: {e}")

    def get_subscriptions(self) -> List[str]:
        """구독 중인 토픽 목록"""
        return list(self._subscriptions.keys())

    def get_stats(self) -> Dict[str, Any]:
        """구독자 통계"""
        return self._stats.copy()

    def reset_stats(self):
        """통계 초기화"""
        self._stats = {
            "messages_received": 0,
            "messages_processed": 0,
            "messages_acked": 0,
            "messages_nacked": 0,
            "processing_errors": 0,
            "last_message_time": None,
        }


# 배치 구독자
class BatchSubscriber(Subscriber):
    """배치 메시지 구독자"""

    def __init__(self, broker_name: str = None, config: SubscriptionConfig = None):
        super().__init__(broker_name, config)
        self._message_batches: Dict[str, List[Message]] = {}
        self._batch_timers: Dict[str, Optional[asyncio.Task]] = {}

    async def _process_message(
        self, topic: str, message: Message, config: SubscriptionConfig
    ):
        """배치 처리를 위한 메시지 수집"""
        if not config.batch_processing:
            # 배치 처리가 아니면 기본 처리
            await super()._process_message(topic, message, config)
            return

        # 배치에 메시지 추가
        if topic not in self._message_batches:
            self._message_batches = {**self._message_batches, topic: []}

        self._message_batches[topic] = _message_batches[topic] + [message]

        # 배치 크기 확인
        if len(self._message_batches[topic]) >= config.batch_size:
            await self._process_batch(topic, config)
        else:
            # 타이머 시작 (없으면)
            if topic not in self._batch_timers or self._batch_timers[topic] is None:
                self._batch_timers = {
                    **self._batch_timers,
                    topic: asyncio.create_task(self._batch_timer(topic, config)),
                }

    async def _batch_timer(self, topic: str, config: SubscriptionConfig):
        """배치 타이머"""
        try:
            await asyncio.sleep(config.batch_timeout)
            await self._process_batch(topic, config)
        except asyncio.CancelledError:
            pass
        finally:
            self._batch_timers = {**self._batch_timers, topic: None}

    async def _process_batch(self, topic: str, config: SubscriptionConfig):
        """배치 처리"""
        try:
            batch = self._message_batches.get(topic, [])
            if not batch:
                return

            # 배치 클리어
            self._message_batches = {**self._message_batches, topic: []}

            # 타이머 취소
            if topic in self._batch_timers and self._batch_timers[topic]:
                self._batch_timers[topic].cancel()
                self._batch_timers = {**self._batch_timers, topic: None}

            # 핸들러 실행
            handler = self._handlers.get(topic)
            if not handler:
                return

            # 배치를 개별적으로 처리 (병렬)
            tasks = []
            for message in batch:
                task = asyncio.create_task(self._handle_message(topic, message, config))
                tasks = [*tasks, task]

            await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"배치 처리 오류: {e}")


# 편의 함수들
async def subscribe_topic(
    topic: str,
    handler: Union[MessageHandler, Callable],
    broker_name: str = None,
    config: SubscriptionConfig = None,
) -> Result[Subscriber, str]:
    """간편 토픽 구독"""
    try:
        subscriber = Subscriber(broker_name, config)
        result = await subscriber.subscribe(topic, handler, config)

        if result.is_success():
            return Success(subscriber)
        else:
            return Failure(result.unwrap_err())

    except Exception as e:
        return Failure(f"구독 실패: {str(e)}")


async def create_subscription(
    topics: List[str],
    handler: Union[MessageHandler, Callable],
    broker_name: str = None,
    config: SubscriptionConfig = None,
) -> Result[Subscriber, str]:
    """다중 토픽 구독"""
    try:
        subscriber = Subscriber(broker_name, config)

        for topic in topics:
            result = await subscriber.subscribe(topic, handler, config)
            if not result.is_success():
                # 실패시 기존 구독 해제
                await subscriber.unsubscribe_all()
                return Failure(f"토픽 구독 실패 ({topic}): {result.unwrap_err()}")

        return Success(subscriber)

    except Exception as e:
        return Failure(f"다중 구독 실패: {str(e)}")


# Work Queue 구독자
class WorkQueueSubscriber(Subscriber):
    """작업 큐 구독자"""

    def __init__(
        self,
        broker_name: str = None,
        config: SubscriptionConfig = None,
        worker_count=4,
    ):
        super().__init__(broker_name, config)
        self.worker_count = worker_count
        self._work_queue = None
        self._workers = []

    async def start_workers(self, topic: str, handler: Union[MessageHandler, Callable]):
        """워커 시작"""
        if self._work_queue:
            return  # 이미 시작됨

        self._work_queue = asyncio.Queue()

        # 핸들러 등록
        if callable(handler) and type(handler).__name__ != "MessageHandler":
            handler = FunctionMessageHandler(handler)

        self._handlers = {**self._handlers, topic: handler}

        # 워커 태스크 생성
        for i in range(self.worker_count):
            worker = asyncio.create_task(self._worker(topic, f"worker-{i}"))
            self._workers = _workers + [worker]

        logger.info(f"워크 큐 시작: {topic} ({self.worker_count}개 워커)")

    async def stop_workers(self):
        """워커 중지"""
        # 워커 태스크 취소
        for worker in self._workers:
            worker.cancel()

        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        _workers = {}
        self._work_queue = None
        logger.info("워크 큐 중지")

    async def _worker(self, topic: str, worker_id: str):
        """워커 프로세스"""
        while True:
            try:
                # 큐에서 메시지 가져오기
                message = await self._work_queue.get()

                # 메시지 처리
                await self._handle_message(topic, message, self.config)

                # 작업 완료 표시
                self._work_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"워커 오류 ({worker_id}): {e}")

    async def _process_message(
        self, topic: str, message: Message, config: SubscriptionConfig
    ):
        """메시지를 큐에 추가"""
        if self._work_queue:
            await self._work_queue.put(message)
        else:
            # 워커가 없으면 직접 처리
            await super()._process_message(topic, message, config)
