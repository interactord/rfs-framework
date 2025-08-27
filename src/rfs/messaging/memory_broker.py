"""
RFS Memory Message Broker (RFS v4.1)

메모리 기반 메시지 브로커 구현 (테스트 및 개발용)
"""

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from .base import BrokerType, Message, MessageBroker, MessageConfig, MessagePriority

logger = get_logger(__name__)


@dataclass
class MemoryMessageConfig(MessageConfig):
    """메모리 메시지 설정"""

    # 메모리 브로커 전용 설정
    max_queue_size: int = 10000  # 큐 최대 크기
    max_topics: int = 1000  # 최대 토픽 수
    enable_persistence: bool = False  # 메시지 지속성 (메모리에서만)
    message_history_size: int = 1000  # 메시지 히스토리 크기

    def __post_init__(self):
        # MessageConfig가 dataclass이고 __post_init__이 없을 수 있음
        if hasattr(super(), "__post_init__"):
            super().__post_init__()
        if hasattr(self, "broker_type"):
            self.broker_type = BrokerType.MEMORY


class MemoryTopic:
    """메모리 토픽"""

    def __init__(self, name: str, max_size=10000):
        self.name = name
        self.max_size = max_size
        self.messages: deque = deque(maxlen=max_size)
        self.subscribers: Set[Callable] = set()
        self.message_history: deque = deque(maxlen=1000)
        self.created_at = asyncio.get_event_loop().time()

        # 통계
        self.stats = {
            "messages_published": 0,
            "messages_consumed": 0,
            "subscriber_count": 0,
            "total_size": 0,
        }

    async def publish(self, message: Message) -> Result[None, str]:
        """메시지 발행"""
        try:
            # 우선순위에 따른 삽입 위치 결정
            match message.priority:
                case MessagePriority.CRITICAL:
                    self.messages.appendleft(message)
                case MessagePriority.HIGH:
                    # HIGH는 CRITICAL 다음에 삽입
                    insert_pos = 0
                    for i, msg in enumerate(self.messages):
                        if msg.priority != MessagePriority.CRITICAL:
                            insert_pos = i
                            break
                    else:
                        insert_pos = len(self.messages)

                    if insert_pos == 0:
                        self.messages.appendleft(message)
                    else:
                        # deque는 중간 삽입이 비효율적이므로 리스트로 변환
                        temp_list = list(self.messages)
                        temp_list.insert(insert_pos, message)
                        self.messages = deque(temp_list)
                case _:
                    # NORMAL, LOW는 뒤에 추가
                    self.messages.append(message)

            # 히스토리에 추가
            self.message_history.append(
                {
                    "message_id": message.id,
                    "timestamp": message.timestamp,
                    "topic": message.topic,
                    "data_size": len(str(message.data)),
                    "priority": message.priority.value,
                }
            )

            # 통계 업데이트
            self.stats = {
                **self.stats,
                "messages_published": self.stats["messages_published"] + 1,
            }
            self.stats = {**self.stats, "total_size": len(self.messages)}

            # 구독자들에게 알림
            await self._notify_subscribers(message)

            return Success(None)

        except Exception as e:
            return Failure(f"메시지 발행 실패: {str(e)}")

    async def consume(self) -> Optional[Message]:
        """메시지 소비"""
        try:
            if self.messages:
                message = self.messages.popleft()
                self.stats = {
                    **self.stats,
                    "messages_consumed": self.stats["messages_consumed"] + 1,
                }
                self.stats = {**self.stats, "total_size": len(self.messages)}
                return message
            return None

        except Exception as e:
            logger.error(f"메시지 소비 실패: {e}")
            return None

    def add_subscriber(self, handler: Callable):
        """구독자 추가"""
        self.subscribers.add(handler)
        self.stats = {**self.stats, "subscriber_count": len(self.subscribers)}

    def remove_subscriber(self, handler: Callable):
        """구독자 제거"""
        self.subscribers.discard(handler)
        self.stats = {**self.stats, "subscriber_count": len(self.subscribers)}

    async def _notify_subscribers(self, message: Message):
        """구독자들에게 메시지 알림"""
        if not self.subscribers:
            return

        # 각 구독자에게 비동기적으로 알림
        tasks = []
        for handler in list(self.subscribers):  # 복사본으로 순회
            try:
                if asyncio.iscoroutinefunction(handler):
                    task = asyncio.create_task(handler(message))
                else:
                    # 동기 함수는 스레드에서 실행
                    task = asyncio.create_task(
                        asyncio.get_event_loop().run_in_executor(None, handler, message)
                    )
                tasks = [*tasks, task]
            except Exception as e:
                logger.error(f"구독자 알림 생성 실패: {e}")

        # 모든 구독자 알림을 병렬로 처리 (예외 무시)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_stats(self) -> Dict[str, Any]:
        """토픽 통계"""
        return {
            **self.stats,
            "queue_size": len(self.messages),
            "history_size": len(self.message_history),
            "created_at": self.created_at,
        }


class MemoryMessageBroker(MessageBroker):
    """메모리 메시지 브로커"""

    def __init__(self, config: MemoryMessageConfig):
        super().__init__(config)
        self.config: MemoryMessageConfig = config

        # 토픽 저장소
        self.topics = {}

        # Work Queue 구현을 위한 데이터
        self.work_queues = {}
        self.work_queue_consumers: Dict[str, List[asyncio.Task]] = defaultdict(list)

        # 메시지 지속성 (메모리에서만)
        self.persistent_messages: deque = deque(maxlen=config.message_history_size)

    async def connect(self) -> Result[None, str]:
        """브로커 초기화"""
        try:
            if self._connected:
                return Success(None)

            self._connected = True
            logger.info("메모리 메시지 브로커 초기화 완료")
            return Success(None)

        except Exception as e:
            error_msg = f"메모리 브로커 초기화 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def disconnect(self) -> Result[None, str]:
        """브로커 정리"""
        try:
            if not self._connected:
                return Success(None)

            # Work Queue 컨슈머 정리
            for topic, consumers in self.work_queue_consumers.items():
                for consumer in consumers:
                    consumer.cancel()

                # 완료 대기
                if consumers:
                    await asyncio.gather(*consumers, return_exceptions=True)

            work_queue_consumers = {}
            work_queues = {}

            # 토픽 정리
            topics = {}

            self._connected = False
            logger.info("메모리 메시지 브로커 정리 완료")
            return Success(None)

        except Exception as e:
            error_msg = f"메모리 브로커 정리 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def publish(self, topic: str, message: Message) -> Result[None, str]:
        """메시지 발행"""
        try:
            if not self._connected:
                return Failure("브로커가 연결되지 않았습니다")

            # 메시지 유효성 검증
            validation_result = self._validate_message(message)
            if not validation_result.is_success():
                return validation_result

            # 토픽 생성 또는 가져오기
            memory_topic = await self._get_or_create_topic(topic)

            # 메시지 발행
            result = await memory_topic.publish(message)

            if result.is_success():
                # 지속성 처리
                if self.config.enable_persistence:
                    self.persistent_messages.append(
                        {
                            "topic": topic,
                            "message": message,
                            "timestamp": asyncio.get_event_loop().time(),
                        }
                    )

                self._stats = {
                    **self._stats,
                    "messages_sent": self._stats["messages_sent"] + 1,
                }
                logger.debug(f"메모리 메시지 발행: {topic} - {message.id}")
            else:
                self._stats = {**self._stats, "errors": self._stats["errors"] + 1}

            return result

        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"메모리 메시지 발행 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def subscribe(self, topic: str, handler: Callable) -> Result[None, str]:
        """토픽 구독"""
        try:
            if not self._connected:
                return Failure("브로커가 연결되지 않았습니다")

            # 토픽 생성 또는 가져오기
            memory_topic = await self._get_or_create_topic(topic)

            # 구독자 추가
            memory_topic.add_subscriber(handler)

            logger.info(f"메모리 토픽 구독: {topic}")
            return Success(None)

        except Exception as e:
            error_msg = f"메모리 구독 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def unsubscribe(self, topic: str) -> Result[None, str]:
        """구독 해제 (모든 구독자)"""
        try:
            if topic in self.topics:
                memory_topic = self.topics[topic]
                subscribers = {}
                memory_topic.stats = {**memory_topic.stats, "subscriber_count": 0}

            logger.info(f"메모리 구독 해제: {topic}")
            return Success(None)

        except Exception as e:
            error_msg = f"메모리 구독 해제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def unsubscribe_handler(
        self, topic: str, handler: Callable
    ) -> Result[None, str]:
        """특정 핸들러 구독 해제"""
        try:
            if topic in self.topics:
                memory_topic = self.topics[topic]
                memory_topic.remove_subscriber(handler)

            return Success(None)

        except Exception as e:
            error_msg = f"핸들러 구독 해제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def create_topic(self, topic: str, **kwargs) -> Result[None, str]:
        """토픽 생성"""
        try:
            if len(self.topics) >= self.config.max_topics:
                return Failure(f"최대 토픽 수 초과: {self.config.max_topics}")

            if topic not in self.topics:
                self.topics = {
                    **self.topics,
                    topic: MemoryTopic(
                        topic, kwargs.get("max_size", self.config.max_queue_size)
                    ),
                }
                logger.info(f"메모리 토픽 생성: {topic}")

            return Success(None)

        except Exception as e:
            error_msg = f"토픽 생성 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def delete_topic(self, topic: str) -> Result[None, str]:
        """토픽 삭제"""
        try:
            if topic in self.topics:
                # Work Queue 컨슈머 정리
                if topic in self.work_queue_consumers:
                    for consumer in self.work_queue_consumers[topic]:
                        consumer.cancel()

                    if self.work_queue_consumers[topic]:
                        await asyncio.gather(
                            *self.work_queue_consumers[topic], return_exceptions=True
                        )

                    del self.work_queue_consumers[topic]

                # Work Queue 정리
                work_queues = {
                    k: v for k, v in work_queues.items() if k != "topic, None"
                }

                # 토픽 삭제
                del self.topics[topic]

                logger.info(f"메모리 토픽 삭제: {topic}")

            return Success(None)

        except Exception as e:
            error_msg = f"토픽 삭제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def list_topics(self) -> Result[List[str], str]:
        """토픽 목록"""
        try:
            return Success(list(self.topics.keys()))

        except Exception as e:
            error_msg = f"토픽 목록 조회 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def _get_or_create_topic(self, topic: str) -> MemoryTopic:
        """토픽 가져오기 또는 생성"""
        if topic not in self.topics:
            await self.create_topic(topic)

        return self.topics[topic]

    # Work Queue 구현
    async def create_work_queue(self, topic: str, worker_count=1) -> Result[None, str]:
        """Work Queue 생성"""
        try:
            if topic in self.work_queues:
                return Success(None)  # 이미 존재

            # 큐 생성
            queue = asyncio.Queue(maxsize=self.config.max_queue_size)
            self.work_queues = {**self.work_queues, topic: queue}

            # 워커 생성
            consumers = []
            for i in range(worker_count):
                consumer = asyncio.create_task(
                    self._work_queue_consumer(topic, queue, f"worker-{i}")
                )
                consumers = [*consumers, consumer]

            self.work_queue_consumers = {**self.work_queue_consumers, topic: consumers}

            logger.info(f"Work Queue 생성: {topic} ({worker_count}개 워커)")
            return Success(None)

        except Exception as e:
            error_msg = f"Work Queue 생성 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def publish_to_work_queue(
        self, topic: str, message: Message
    ) -> Result[None, str]:
        """Work Queue에 메시지 발행"""
        try:
            if topic not in self.work_queues:
                return Failure(f"Work Queue가 없습니다: {topic}")

            queue = self.work_queues[topic]
            await queue.put(message)

            self._stats = {
                **self._stats,
                "messages_sent": self._stats["messages_sent"] + 1,
            }
            return Success(None)

        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"Work Queue 발행 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def _work_queue_consumer(
        self, topic: str, queue: asyncio.Queue, worker_id: str
    ):
        """Work Queue 컨슈머"""
        try:
            while True:
                try:
                    # 메시지 대기
                    message = await queue.get()

                    # 토픽의 구독자들에게 메시지 전달
                    if topic in self.topics:
                        memory_topic = self.topics[topic]
                        await memory_topic._notify_subscribers(message)

                    # 작업 완료 표시
                    queue.task_done()

                    self._stats = {
                        **self._stats,
                        "messages_received": self._stats["messages_received"] + 1,
                    }

                except Exception as e:
                    logger.error(f"Work Queue 컨슈머 오류 ({worker_id}): {e}")
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Work Queue 컨슈머 종료 오류 ({worker_id}): {e}")

    # 메시지 소비 (Pull 방식)
    async def consume_message(self, topic: str) -> Result[Optional[Message], str]:
        """메시지 소비 (Pull 방식)"""
        try:
            if not self._connected:
                return Failure("브로커가 연결되지 않았습니다")

            if topic not in self.topics:
                return Success(None)

            memory_topic = self.topics[topic]
            message = await memory_topic.consume()

            if message:
                self._stats = {
                    **self._stats,
                    "messages_received": self._stats["messages_received"] + 1,
                }

            return Success(message)

        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"메시지 소비 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    # 통계 및 모니터링
    def get_memory_stats(self) -> Dict[str, Any]:
        """메모리 브로커 전용 통계"""
        base_stats = self.get_stats()

        topic_stats = {}
        total_messages = 0
        total_subscribers = 0

        for topic_name, topic in self.topics.items():
            topic_stat = topic.get_stats()
            topic_stats[topic_name] = topic_stat
            total_messages = total_messages + topic_stat["queue_size"]
            total_subscribers = total_subscribers + topic_stat["subscriber_count"]

        memory_stats = {
            "topic_count": len(self.topics),
            "total_queued_messages": total_messages,
            "total_subscribers": total_subscribers,
            "work_queue_count": len(self.work_queues),
            "persistent_message_count": len(self.persistent_messages),
            "topic_stats": topic_stats,
        }

    async def get_topic_history(
        self, topic: str, limit=10
    ) -> Result[List[Dict[str, Any]], str]:
        """토픽의 메시지 히스토리 조회"""
        try:
            if topic not in self.topics:
                return Failure(f"토픽을 찾을 수 없습니다: {topic}")

            memory_topic = self.topics[topic]
            history = list(memory_topic.message_history)[-limit:]

            return Success(history)

        except Exception as e:
            error_msg = f"토픽 메시지 조회 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def clear_topic(self, topic: str) -> Result[None, str]:
        """토픽 메시지 모두 삭제"""
        try:
            if topic in self.topics:
                memory_topic = self.topics[topic]
                messages = {}
                memory_topic.stats = {**memory_topic.stats, "total_size": 0}

                logger.info(f"토픽 메시지 삭제: {topic}")

            return Success(None)

        except Exception as e:
            error_msg = f"토픽 삭제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
