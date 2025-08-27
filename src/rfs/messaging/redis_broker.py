"""
RFS Redis Message Broker (RFS v4.1)

Redis 기반 메시지 브로커 구현
"""

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Set

try:
    import aioredis

    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None
    REDIS_AVAILABLE = False

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from .base import Message, MessageBroker, MessageConfig

logger = get_logger(__name__)


class RedisMessageConfig(MessageConfig):
    """Redis 메시지 설정"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.broker_type.value != "redis":
            self.broker_type = "redis"


class RedisMessageBroker(MessageBroker):
    """Redis 메시지 브로커"""

    def __init__(self, config: RedisMessageConfig):
        if not REDIS_AVAILABLE:
            raise ImportError("aioredis 패키지가 필요합니다: pip install aioredis")

        super().__init__(config)
        self.config: RedisMessageConfig = config

        self.redis = None
        self.pubsub = None

        self._subscription_tasks = {}
        self._message_handlers = {}

        # Stream 기반 구현을 위한 변수들
        self._stream_consumers = {}
        self._stream_consumer_tasks = {}

    async def connect(self) -> Result[None, str]:
        """Redis 연결"""
        try:
            if self._connected:
                return Success(None)

            # Redis 클라이언트 생성
            if self.config.broker_url.startswith("redis://"):
                self.redis = await aioredis.from_url(
                    self.config.broker_url,
                    decode_responses=True,
                    max_connections=self.config.connection_pool_size,
                )
            else:
                # 개별 설정으로 연결
                url_parts = self.config.broker_url.replace("redis://", "").split(":")
                host = url_parts[0] if len(url_parts) > 0 else "localhost"
                port = int(url_parts[1]) if len(url_parts) > 1 else 6379

                self.redis = aioredis.Redis(
                    host=host,
                    port=port,
                    decode_responses=True,
                    max_connections=self.config.connection_pool_size,
                )

            # 연결 테스트
            await self.redis.ping()

            # Pub/Sub 객체 생성
            self.pubsub = self.redis.pubsub()

            self._connected = True
            logger.info(f"Redis 메시지 브로커 연결 성공")
            return Success(None)

        except Exception as e:
            error_msg = f"Redis 연결 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def disconnect(self) -> Result[None, str]:
        """Redis 연결 해제"""
        try:
            if not self._connected:
                return Success(None)

            # 구독 태스크 정리
            for task in list(self._subscription_tasks.values()):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            _subscription_tasks = {}

            # Stream consumer 태스크 정리
            for task in list(self._stream_consumer_tasks.values()):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            _stream_consumer_tasks = {}

            # Pub/Sub 정리
            if self.pubsub:
                await self.pubsub.close()

            # Redis 연결 해제
            if self.redis:
                await self.redis.close()

            self._connected = False
            logger.info("Redis 메시지 브로커 연결 해제")
            return Success(None)

        except Exception as e:
            error_msg = f"Redis 연결 해제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def publish(self, topic: str, message: Message) -> Result[None, str]:
        """메시지 발행 (Pub/Sub 방식)"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")

            # 메시지 유효성 검증
            validation_result = self._validate_message(message)
            if not validation_result.is_success():
                return validation_result

            # 토픽 이름 생성
            redis_topic = self._make_topic_name(topic)

            # 메시지 직렬화
            serialized_message = message.serialize()

            # Redis Pub/Sub로 발행
            await self.redis.publish(redis_topic, serialized_message)

            self._stats = {
                **self._stats,
                "messages_sent": self._stats["messages_sent"] + 1,
            }
            logger.debug(f"메시지 발행: {redis_topic} - {message.id}")

            return Success(None)

        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"Redis 메시지 발행 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def publish_stream(self, topic: str, message: Message) -> Result[str, str]:
        """메시지 발행 (Stream 방식)"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")

            # 메시지 유효성 검증
            validation_result = self._validate_message(message)
            if not validation_result.is_success():
                return Failure(validation_result.unwrap_err())

            # Stream 이름 생성
            stream_name = f"{self._make_topic_name(topic)}:stream"

            # 메시지 데이터 준비
            message_data = message.to_dict()

            # Redis Stream에 추가
            message_id = await self.redis.xadd(stream_name, message_data)

            self._stats = {
                **self._stats,
                "messages_sent": self._stats["messages_sent"] + 1,
            }
            logger.debug(f"스트림 메시지 발행: {stream_name} - {message_id}")

            return Success(message_id)

        except Exception as e:
            self._stats = {**self._stats, "errors": self._stats["errors"] + 1}
            error_msg = f"Redis 스트림 발행 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def subscribe(self, topic: str, handler: Callable) -> Result[None, str]:
        """토픽 구독 (Pub/Sub 방식)"""
        try:
            if not self._connected or not self.pubsub:
                return Failure("Redis 연결이 없습니다")

            redis_topic = self._make_topic_name(topic)

            # 기존 구독 해제
            if topic in self._subscription_tasks:
                await self.unsubscribe(topic)

            # 핸들러 저장
            self._message_handlers = {**self._message_handlers, topic: handler}

            # Pub/Sub 구독
            await self.pubsub.subscribe(redis_topic)

            # 메시지 리스닝 태스크 시작
            task = asyncio.create_task(self._listen_messages(topic, redis_topic))
            self._subscription_tasks = {**self._subscription_tasks, topic: task}

            logger.info(f"Redis 토픽 구독: {redis_topic}")
            return Success(None)

        except Exception as e:
            error_msg = f"Redis 구독 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def subscribe_stream(
        self,
        topic: str,
        handler: Callable,
        consumer_group="default",
        consumer_name="consumer-1",
    ) -> Result[None, str]:
        """스트림 구독"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")

            stream_name = f"{self._make_topic_name(topic)}:stream"

            # Consumer Group 생성 (이미 있어도 오류 무시)
            try:
                await self.redis.xgroup_create(
                    stream_name, consumer_group, "0", mkstream=True
                )
            except Exception:
                pass  # 이미 존재하는 경우 무시

            # 기존 구독 해제
            if topic in self._stream_consumer_tasks:
                await self.unsubscribe_stream(topic)

            # 핸들러 저장
            self._message_handlers = {**self._message_handlers, topic: handler}
            self._stream_consumers = {**self._stream_consumers, topic: consumer_group}

            # 스트림 소비 태스크 시작
            task = asyncio.create_task(
                self._consume_stream(topic, stream_name, consumer_group, consumer_name)
            )
            self._stream_consumer_tasks = {**self._stream_consumer_tasks, topic: task}

            logger.info(f"Redis 스트림 구독: {stream_name} (그룹: {consumer_group})")
            return Success(None)

        except Exception as e:
            error_msg = f"Redis 스트림 구독 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def unsubscribe(self, topic: str) -> Result[None, str]:
        """구독 해제 (Pub/Sub 방식)"""
        try:
            redis_topic = self._make_topic_name(topic)

            # 리스닝 태스크 중지
            if topic in self._subscription_tasks:
                _subscription_tasks = {
                    k: v for k, v in _subscription_tasks.items() if k != "topic"
                }
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Pub/Sub 구독 해제
            if self.pubsub:
                await self.pubsub.unsubscribe(redis_topic)

            # 핸들러 제거
            _message_handlers = {
                k: v for k, v in _message_handlers.items() if k != "topic, None"
            }

            logger.info(f"Redis 구독 해제: {redis_topic}")
            return Success(None)

        except Exception as e:
            error_msg = f"Redis 구독 해제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def unsubscribe_stream(self, topic: str) -> Result[None, str]:
        """스트림 구독 해제"""
        try:
            # 소비 태스크 중지
            if topic in self._stream_consumer_tasks:
                _stream_consumer_tasks = {
                    k: v for k, v in _stream_consumer_tasks.items() if k != "topic"
                }
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # 정보 제거
            _message_handlers = {
                k: v for k, v in _message_handlers.items() if k != "topic, None"
            }
            _stream_consumers = {
                k: v for k, v in _stream_consumers.items() if k != "topic, None"
            }

            logger.info(f"Redis 스트림 구독 해제: {topic}")
            return Success(None)

        except Exception as e:
            error_msg = f"Redis 스트림 구독 해제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def _listen_messages(self, topic: str, redis_topic: str):
        """메시지 리스닝 (Pub/Sub)"""
        try:
            while topic in self._subscription_tasks and self.pubsub:
                try:
                    # 타임아웃을 두고 메시지 대기
                    raw_message = await asyncio.wait_for(
                        self.pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=1.0,
                    )

                    if raw_message and raw_message.get("type") == "message":
                        # 메시지 역직렬화
                        message = Message.deserialize(raw_message["data"].encode())

                        if message:
                            self._stats = {
                                **self._stats,
                                "messages_received": self._stats["messages_received"]
                                + 1,
                            }

                            # 핸들러 호출
                            handler = self._message_handlers.get(topic)
                            if handler:
                                try:
                                    if asyncio.iscoroutinefunction(handler):
                                        await handler(message)
                                    else:
                                        handler(message)

                                    # 자동 ACK (Pub/Sub에서는 의미없지만 통계용)
                                    await self.ack_message(message)

                                except Exception as e:
                                    logger.error(f"메시지 처리 오류: {e}")
                                    await self.nack_message(message)

                except asyncio.TimeoutError:
                    continue  # 타임아웃은 정상
                except Exception as e:
                    logger.error(f"메시지 리스닝 오류: {e}")
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"메시지 리스닝 종료 오류: {e}")

    async def _consume_stream(
        self, topic: str, stream_name: str, consumer_group: str, consumer_name: str
    ):
        """스트림 메시지 소비"""
        try:
            while topic in self._stream_consumer_tasks:
                try:
                    # Pending 메시지 먼저 처리
                    pending_messages = await self.redis.xreadgroup(
                        consumer_group,
                        consumer_name,
                        {stream_name: "0"},
                        count=self.config.prefetch_count,
                        block=100,
                    )

                    if not pending_messages:
                        # 새 메시지 읽기
                        messages = await self.redis.xreadgroup(
                            consumer_group,
                            consumer_name,
                            {stream_name: ">"},
                            count=self.config.prefetch_count,
                            block=1000,
                        )
                    else:
                        messages = pending_messages

                    if messages:
                        for stream, stream_messages in messages:
                            for message_id, fields in stream_messages:
                                await self._process_stream_message(
                                    topic,
                                    stream_name,
                                    consumer_group,
                                    message_id,
                                    fields,
                                )

                except Exception as e:
                    logger.error(f"스트림 소비 오류: {e}")
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"스트림 소비 종료 오류: {e}")

    async def _process_stream_message(
        self,
        topic: str,
        stream_name: str,
        consumer_group: str,
        message_id: str,
        fields: Dict[str, str],
    ):
        """스트림 메시지 처리"""
        try:
            # Message 객체 재구성
            message = Message.from_dict(fields)

            self._stats = {
                **self._stats,
                "messages_received": self._stats["messages_received"] + 1,
            }

            # 핸들러 호출
            handler = self._message_handlers.get(topic)
            if handler:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)

                    # ACK
                    await self.redis.xack(stream_name, consumer_group, message_id)
                    self._stats = {
                        **self._stats,
                        "messages_acked": self._stats["messages_acked"] + 1,
                    }

                except Exception as e:
                    logger.error(f"스트림 메시지 처리 오류: {e}")
                    self._stats = {
                        **self._stats,
                        "processing_errors": self._stats["processing_errors"] + 1,
                    }

                    # 재시도 또는 DLQ 처리 로직
                    if message.should_retry:
                        message.increment_retry()
                        # 재시도는 자동으로 pending에 남음
                    else:
                        # DLQ로 이동
                        if self.config.enable_dlq:
                            dlq_topic = self._make_dlq_topic(topic)
                            await self.publish(dlq_topic, message)

                        # ACK 처리 (더 이상 처리하지 않음)
                        await self.redis.xack(stream_name, consumer_group, message_id)

        except Exception as e:
            logger.error(f"스트림 메시지 처리 중 예외: {e}")

    async def create_topic(self, topic: str, **kwargs) -> Result[None, str]:
        """토픽 생성 (Redis에서는 자동 생성되므로 성공 반환)"""
        return Success(None)

    async def delete_topic(self, topic: str) -> Result[None, str]:
        """토픽 삭제"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")

            # Stream 삭제
            stream_name = f"{self._make_topic_name(topic)}:stream"
            try:
                await self.redis.delete(stream_name)
            except:
                pass  # 없어도 상관없음

            return Success(None)

        except Exception as e:
            error_msg = f"토픽 삭제 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def list_topics(self) -> Result[List[str], str]:
        """토픽 목록 (현재 구독 중인 토픽들)"""
        try:
            topics = list(self._message_handlers.keys())
            return Success(topics)

        except Exception as e:
            error_msg = f"토픽 목록 조회 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    # Redis 전용 메서드들
    async def get_stream_info(self, topic: str) -> Result[Dict[str, Any], str]:
        """스트림 정보 조회"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")

            stream_name = f"{self._make_topic_name(topic)}:stream"
            info = await self.redis.xinfo_stream(stream_name)

            return Success(info)

        except Exception as e:
            error_msg = f"스트림 정보 조회 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def get_consumer_group_info(
        self, topic: str
    ) -> Result[List[Dict[str, Any]], str]:
        """Consumer Group 정보 조회"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")

            stream_name = f"{self._make_topic_name(topic)}:stream"
            groups = await self.redis.xinfo_groups(stream_name)

            return Success(groups)

        except Exception as e:
            error_msg = f"Consumer Group 정보 조회 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    async def trim_stream(self, topic: str, max_length: int) -> Result[None, str]:
        """스트림 트리밍"""
        try:
            if not self._connected or not self.redis:
                return Failure("Redis 연결이 없습니다")

            stream_name = f"{self._make_topic_name(topic)}:stream"
            await self.redis.xtrim(stream_name, maxlen=max_length, approximate=True)

            return Success(None)

        except Exception as e:
            error_msg = f"스트림 트리밍 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)

    def get_redis_stats(self) -> Dict[str, Any]:
        """Redis 전용 통계"""
        base_stats = self.get_stats()

        redis_stats = {
            "subscription_count": len(self._subscription_tasks),
            "stream_consumer_count": len(self._stream_consumer_tasks),
            "active_handlers": len(self._message_handlers),
        }

        return {**base_stats, **redis_stats}
