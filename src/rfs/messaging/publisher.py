"""
RFS Message Publisher (RFS v4.1)

메시지 발행자 구현
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta

from ..core.result import Result, Success, Failure
from ..core.enhanced_logging import get_logger
from .base import Message, MessageBroker, MessagePriority, get_message_broker

logger = get_logger(__name__)


class Publisher:
    """메시지 발행자"""
    
    def __init__(self, broker_name: str = None, topic: str = None):
        self.broker_name = broker_name
        self.default_topic = topic
        self._stats = {
            "messages_published": 0,
            "bytes_published": 0,
            "publish_errors": 0,
            "last_publish_time": None
        }
    
    @property
    def broker(self) -> Optional[MessageBroker]:
        """메시지 브로커"""
        return get_message_broker(self.broker_name)
    
    async def publish(
        self,
        data: Any,
        topic: str = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        ttl: Optional[int] = None,
        headers: Dict[str, Any] = None,
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> Result[str, str]:
        """메시지 발행"""
        try:
            broker = self.broker
            if not broker:
                return Failure("메시지 브로커를 찾을 수 없습니다")
            
            # 토픽 결정
            publish_topic = topic or self.default_topic
            if not publish_topic:
                return Failure("토픽이 지정되지 않았습니다")
            
            # 메시지 생성
            message = Message(
                topic=publish_topic,
                data=data,
                priority=priority,
                ttl=ttl,
                headers=headers or {},
                correlation_id=correlation_id,
                reply_to=reply_to
            )
            
            # 발행
            result = await broker.publish(publish_topic, message)
            
            if result.is_success():
                # 통계 업데이트
                self._stats["messages_published"] += 1
                self._stats["bytes_published"] += len(message.serialize())
                self._stats["last_publish_time"] = datetime.now()
                
                logger.debug(f"메시지 발행: {publish_topic} - {message.id}")
                return Success(message.id)
            else:
                self._stats["publish_errors"] += 1
                return Failure(result.unwrap_err())
            
        except Exception as e:
            self._stats["publish_errors"] += 1
            error_msg = f"메시지 발행 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def publish_delayed(
        self,
        data: Any,
        delay: Union[int, timedelta],
        topic: str = None,
        **kwargs
    ) -> Result[str, str]:
        """지연 메시지 발행"""
        try:
            if isinstance(delay, int):
                delay_seconds = delay
            else:
                delay_seconds = int(delay.total_seconds())
            
            # 지연 후 발행
            await asyncio.sleep(delay_seconds)
            return await self.publish(data, topic, **kwargs)
            
        except Exception as e:
            error_msg = f"지연 메시지 발행 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def publish_at(
        self,
        data: Any,
        scheduled_time: datetime,
        topic: str = None,
        **kwargs
    ) -> Result[str, str]:
        """예약 메시지 발행"""
        try:
            now = datetime.now()
            if scheduled_time <= now:
                # 즉시 발행
                return await self.publish(data, topic, **kwargs)
            
            # 예약 시간까지 대기
            delay_seconds = (scheduled_time - now).total_seconds()
            await asyncio.sleep(delay_seconds)
            
            return await self.publish(data, topic, **kwargs)
            
        except Exception as e:
            error_msg = f"예약 메시지 발행 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    def get_stats(self) -> Dict[str, Any]:
        """발행자 통계"""
        return self._stats.copy()
    
    def reset_stats(self):
        """통계 초기화"""
        self._stats = {
            "messages_published": 0,
            "bytes_published": 0,
            "publish_errors": 0,
            "last_publish_time": None
        }


class BatchPublisher(Publisher):
    """배치 메시지 발행자"""
    
    def __init__(self, broker_name: str = None, topic: str = None, 
                 batch_size: int = 100, flush_interval: float = 1.0):
        super().__init__(broker_name, topic)
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        self._message_batch: List[Message] = []
        self._batch_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._start_flush_timer()
    
    async def publish(
        self,
        data: Any,
        topic: str = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        ttl: Optional[int] = None,
        headers: Dict[str, Any] = None,
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> Result[str, str]:
        """배치에 메시지 추가"""
        try:
            # 토픽 결정
            publish_topic = topic or self.default_topic
            if not publish_topic:
                return Failure("토픽이 지정되지 않았습니다")
            
            # 메시지 생성
            message = Message(
                topic=publish_topic,
                data=data,
                priority=priority,
                ttl=ttl,
                headers=headers or {},
                correlation_id=correlation_id,
                reply_to=reply_to
            )
            
            async with self._batch_lock:
                self._message_batch.append(message)
                
                # 배치 크기 도달시 즉시 플러시
                if len(self._message_batch) >= self.batch_size:
                    await self._flush_batch()
            
            return Success(message.id)
            
        except Exception as e:
            error_msg = f"배치 메시지 추가 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def flush(self) -> Result[int, str]:
        """배치 수동 플러시"""
        async with self._batch_lock:
            return await self._flush_batch()
    
    async def _flush_batch(self) -> Result[int, str]:
        """배치 플러시 (락 필요)"""
        try:
            if not self._message_batch:
                return Success(0)
            
            broker = self.broker
            if not broker:
                return Failure("메시지 브로커를 찾을 수 없습니다")
            
            # 토픽별로 그룹화
            topic_groups: Dict[str, List[Message]] = {}
            for message in self._message_batch:
                if message.topic not in topic_groups:
                    topic_groups[message.topic] = []
                topic_groups[message.topic].append(message)
            
            # 토픽별 배치 발행
            total_published = 0
            
            for topic, messages in topic_groups.items():
                result = await broker.publish_batch(topic, messages)
                if result.is_success():
                    total_published += len(messages)
                    
                    # 통계 업데이트
                    self._stats["messages_published"] += len(messages)
                    for message in messages:
                        self._stats["bytes_published"] += len(message.serialize())
                else:
                    self._stats["publish_errors"] += len(messages)
                    logger.error(f"배치 발행 실패 ({topic}): {result.unwrap_err()}")
            
            # 배치 클리어
            self._message_batch.clear()
            self._stats["last_publish_time"] = datetime.now()
            
            if total_published > 0:
                logger.debug(f"배치 플러시 완료: {total_published}개 메시지")
            
            return Success(total_published)
            
        except Exception as e:
            error_msg = f"배치 플러시 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    def _start_flush_timer(self):
        """플러시 타이머 시작"""
        async def flush_timer():
            while True:
                try:
                    await asyncio.sleep(self.flush_interval)
                    async with self._batch_lock:
                        await self._flush_batch()
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"플러시 타이머 오류: {e}")
        
        self._flush_task = asyncio.create_task(flush_timer())
    
    async def close(self):
        """배치 발행자 종료"""
        try:
            # 플러시 타이머 중지
            if self._flush_task and not self._flush_task.done():
                self._flush_task.cancel()
                try:
                    await self._flush_task
                except asyncio.CancelledError:
                    pass
            
            # 남은 메시지 플러시
            await self.flush()
            
        except Exception as e:
            logger.error(f"배치 발행자 종료 실패: {e}")
    
    def __del__(self):
        """소멸자"""
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()


# 편의 함수들
async def publish_message(
    topic: str,
    data: Any,
    broker_name: str = None,
    priority: MessagePriority = MessagePriority.NORMAL,
    ttl: Optional[int] = None,
    headers: Dict[str, Any] = None,
    correlation_id: Optional[str] = None,
    reply_to: Optional[str] = None
) -> Result[str, str]:
    """간편 메시지 발행"""
    publisher = Publisher(broker_name)
    return await publisher.publish(
        data=data,
        topic=topic,
        priority=priority,
        ttl=ttl,
        headers=headers,
        correlation_id=correlation_id,
        reply_to=reply_to
    )


async def publish_batch(
    topic: str,
    messages: List[Dict[str, Any]],
    broker_name: str = None
) -> Result[List[str], str]:
    """간편 배치 발행"""
    try:
        broker = get_message_broker(broker_name)
        if not broker:
            return Failure("메시지 브로커를 찾을 수 없습니다")
        
        message_objects = []
        for msg_data in messages:
            message = Message(
                topic=topic,
                data=msg_data.get("data"),
                priority=MessagePriority(msg_data.get("priority", MessagePriority.NORMAL.value)),
                ttl=msg_data.get("ttl"),
                headers=msg_data.get("headers", {}),
                correlation_id=msg_data.get("correlation_id"),
                reply_to=msg_data.get("reply_to")
            )
            message_objects.append(message)
        
        result = await broker.publish_batch(topic, message_objects)
        if result.is_success():
            return Success([msg.id for msg in message_objects])
        else:
            return Failure(result.unwrap_err())
            
    except Exception as e:
        error_msg = f"배치 발행 실패: {str(e)}"
        logger.error(error_msg)
        return Failure(error_msg)


# 스케줄링 발행자
class ScheduledPublisher(Publisher):
    """스케줄링 발행자"""
    
    def __init__(self, broker_name: str = None, topic: str = None):
        super().__init__(broker_name, topic)
        self._scheduled_tasks: Dict[str, asyncio.Task] = {}
    
    async def schedule_message(
        self,
        data: Any,
        scheduled_time: datetime,
        topic: str = None,
        message_id: str = None,
        **kwargs
    ) -> Result[str, str]:
        """메시지 스케줄링"""
        try:
            import uuid
            
            if not message_id:
                message_id = str(uuid.uuid4())
            
            # 기존 스케줄 취소
            if message_id in self._scheduled_tasks:
                await self.cancel_scheduled_message(message_id)
            
            # 새 스케줄 생성
            async def scheduled_task():
                try:
                    now = datetime.now()
                    if scheduled_time > now:
                        delay_seconds = (scheduled_time - now).total_seconds()
                        await asyncio.sleep(delay_seconds)
                    
                    result = await self.publish(data, topic, **kwargs)
                    if result.is_success():
                        logger.debug(f"스케줄 메시지 발행: {message_id}")
                    else:
                        logger.error(f"스케줄 메시지 발행 실패: {result.unwrap_err()}")
                
                except asyncio.CancelledError:
                    logger.debug(f"스케줄 메시지 취소: {message_id}")
                except Exception as e:
                    logger.error(f"스케줄 메시지 오류: {e}")
                finally:
                    self._scheduled_tasks.pop(message_id, None)
            
            task = asyncio.create_task(scheduled_task())
            self._scheduled_tasks[message_id] = task
            
            return Success(message_id)
            
        except Exception as e:
            error_msg = f"메시지 스케줄링 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def cancel_scheduled_message(self, message_id: str) -> Result[None, str]:
        """스케줄된 메시지 취소"""
        try:
            if message_id in self._scheduled_tasks:
                task = self._scheduled_tasks.pop(message_id)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            return Success(None)
            
        except Exception as e:
            error_msg = f"스케줄 취소 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    def get_scheduled_messages(self) -> List[str]:
        """스케줄된 메시지 ID 목록"""
        return list(self._scheduled_tasks.keys())
    
    async def cancel_all_scheduled(self) -> Result[None, str]:
        """모든 스케줄 취소"""
        try:
            for message_id in list(self._scheduled_tasks.keys()):
                await self.cancel_scheduled_message(message_id)
            
            return Success(None)
            
        except Exception as e:
            error_msg = f"전체 스케줄 취소 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)


# Priority Queue Publisher
class PriorityPublisher(Publisher):
    """우선순위 큐 발행자"""
    
    def __init__(self, broker_name: str = None, topic: str = None):
        super().__init__(broker_name, topic)
        self._priority_queues = {
            MessagePriority.CRITICAL: asyncio.Queue(),
            MessagePriority.HIGH: asyncio.Queue(),
            MessagePriority.NORMAL: asyncio.Queue(),
            MessagePriority.LOW: asyncio.Queue()
        }
        self._processing = False
        self._process_task: Optional[asyncio.Task] = None
    
    async def start_processing(self):
        """우선순위 처리 시작"""
        if self._processing:
            return
        
        self._processing = True
        self._process_task = asyncio.create_task(self._process_priority_queue())
    
    async def stop_processing(self):
        """우선순위 처리 중지"""
        self._processing = False
        if self._process_task and not self._process_task.done():
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
    
    async def publish_priority(
        self,
        data: Any,
        priority: MessagePriority,
        topic: str = None,
        **kwargs
    ) -> Result[str, str]:
        """우선순위 큐에 메시지 추가"""
        try:
            # 메시지 생성
            message = Message(
                topic=topic or self.default_topic,
                data=data,
                priority=priority,
                **kwargs
            )
            
            # 우선순위 큐에 추가
            await self._priority_queues[priority].put(message)
            
            return Success(message.id)
            
        except Exception as e:
            error_msg = f"우선순위 메시지 추가 실패: {str(e)}"
            logger.error(error_msg)
            return Failure(error_msg)
    
    async def _process_priority_queue(self):
        """우선순위 큐 처리"""
        while self._processing:
            try:
                # 우선순위 순서로 큐 확인
                message = None
                
                for priority in [MessagePriority.CRITICAL, MessagePriority.HIGH, 
                               MessagePriority.NORMAL, MessagePriority.LOW]:
                    try:
                        message = self._priority_queues[priority].get_nowait()
                        break
                    except asyncio.QueueEmpty:
                        continue
                
                if message:
                    # 메시지 발행
                    broker = self.broker
                    if broker:
                        result = await broker.publish(message.topic, message)
                        if result.is_success():
                            self._stats["messages_published"] += 1
                        else:
                            self._stats["publish_errors"] += 1
                else:
                    # 모든 큐가 비어있으면 잠시 대기
                    await asyncio.sleep(0.1)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"우선순위 큐 처리 오류: {e}")
                await asyncio.sleep(0.1)