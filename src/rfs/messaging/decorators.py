"""
RFS Messaging Decorators (RFS v4.1)

메시징 데코레이터 시스템
"""

import asyncio
import functools
import inspect
from typing import Any, Callable, Optional, Union, Dict, List
from datetime import datetime, timedelta

from ..core.result import Result, Success, Failure
from ..core.enhanced_logging import get_logger
from .base import Message, MessagePriority, get_message_broker
from .publisher import Publisher
from .subscriber import Subscriber, SubscriptionConfig, MessageHandler

logger = get_logger(__name__)


def message_handler(
    topic: str = None,
    broker_name: str = None,
    auto_ack: bool = True,
    max_retries: int = 3,
    retry_delay: float = 1.0
):
    """메시지 핸들러 데코레이터"""
    def decorator(func: Callable) -> Callable:
        # 메타데이터 추가
        func.__message_handler__ = True
        func.__handler_topic__ = topic
        func.__handler_broker__ = broker_name
        func.__handler_config__ = {
            "auto_ack": auto_ack,
            "max_retries": max_retries,
            "retry_delay": retry_delay
        }
        
        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(message, *args, **kwargs)
                else:
                    result = func(message, *args, **kwargs)
                
                # Result 타입이 아니면 Success로 래핑
                if not isinstance(result, Result):
                    result = Success(result)
                
                return result
                
            except Exception as e:
                logger.error(f"메시지 핸들러 오류: {e}")
                return Failure(f"핸들러 실행 실패: {str(e)}")
        
        return wrapper
    
    return decorator


def topic_subscriber(
    topic: str,
    broker_name: str = None,
    config: SubscriptionConfig = None,
    auto_start: bool = True
):
    """토픽 구독 데코레이터"""
    def decorator(cls_or_func):
        if inspect.isclass(cls_or_func):
            # 클래스 데코레이터
            original_init = cls_or_func.__init__
            
            def new_init(self, *args, **kwargs):
                original_init(self, *args, **kwargs)
                
                # 구독자 초기화
                self._subscriber = Subscriber(broker_name, config)
                
                if auto_start:
                    # 자동 구독 시작
                    asyncio.create_task(self._start_subscription())
            
            async def _start_subscription(self):
                """구독 시작"""
                try:
                    await self._subscriber.subscribe(topic, self.handle_message)
                    logger.info(f"자동 구독 시작: {topic}")
                except Exception as e:
                    logger.error(f"자동 구독 실패: {e}")
            
            # 메서드 추가
            cls_or_func.__init__ = new_init
            cls_or_func._start_subscription = _start_subscription
            
            # handle_message 메서드가 있는지 확인
            if not hasattr(cls_or_func, 'handle_message'):
                raise ValueError("handle_message 메서드가 필요합니다")
            
            return cls_or_func
            
        else:
            # 함수 데코레이터
            @functools.wraps(cls_or_func)
            def wrapper(*args, **kwargs):
                # 구독자 생성 및 시작
                async def start_subscription():
                    subscriber = Subscriber(broker_name, config)
                    await subscriber.subscribe(topic, cls_or_func)
                    return subscriber
                
                return asyncio.run(start_subscription())
            
            return wrapper
    
    return decorator


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
):
    """실패시 재시도 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    
                    # 성공시 결과 반환
                    return result
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(f"재시도 {attempt + 1}/{max_retries}: {e}")
                        await asyncio.sleep(current_delay)
                        
                        # 지수적 백오프
                        current_delay = min(current_delay * backoff_factor, max_delay)
                    else:
                        logger.error(f"최대 재시도 횟수 도달: {e}")
                        raise last_exception
            
            # 여기에 도달하면 안되지만 안전장치
            if last_exception:
                raise last_exception
        
        return wrapper
    
    return decorator


def dead_letter_queue(
    dlq_topic: str = None,
    max_failures: int = 5,
    broker_name: str = None
):
    """Dead Letter Queue 데코레이터"""
    def decorator(func: Callable) -> Callable:
        # 실패 카운터 (메모리에서만 유지)
        failure_count = {}
        
        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            message_key = f"{message.topic}:{message.id}"
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(message, *args, **kwargs)
                else:
                    result = func(message, *args, **kwargs)
                
                # 성공시 실패 카운터 초기화
                failure_count.pop(message_key, None)
                
                return result
                
            except Exception as e:
                # 실패 카운트 증가
                failure_count[message_key] = failure_count.get(message_key, 0) + 1
                
                if failure_count[message_key] >= max_failures:
                    # DLQ로 전송
                    await send_to_dlq(message, str(e), dlq_topic, broker_name)
                    
                    # 실패 카운터에서 제거
                    failure_count.pop(message_key, None)
                    
                    logger.error(f"메시지를 DLQ로 전송: {message.id}")
                    return Failure(f"DLQ로 전송됨: {e}")
                else:
                    logger.warning(f"메시지 처리 실패 ({failure_count[message_key]}/{max_failures}): {e}")
                    raise e
        
        return wrapper
    
    return decorator


async def send_to_dlq(
    message: Message,
    error_message: str,
    dlq_topic: str = None,
    broker_name: str = None
):
    """메시지를 Dead Letter Queue로 전송"""
    try:
        broker = get_message_broker(broker_name)
        if not broker:
            logger.error("브로커를 찾을 수 없어 DLQ 전송 실패")
            return
        
        # DLQ 토픽 결정
        if not dlq_topic:
            dlq_topic = broker._make_dlq_topic(message.topic)
        
        # DLQ 메시지 생성
        dlq_message = Message(
            topic=dlq_topic,
            data=message.data,
            headers={
                **message.headers,
                "original_topic": message.topic,
                "original_message_id": message.id,
                "error_message": error_message,
                "dlq_timestamp": datetime.now().isoformat(),
                "retry_count": message.retry_count
            },
            priority=message.priority,
            correlation_id=message.correlation_id
        )
        
        # DLQ에 발행
        await broker.publish(dlq_topic, dlq_message)
        
    except Exception as e:
        logger.error(f"DLQ 전송 실패: {e}")


def message_filter(filter_func: Callable[[Message], bool]):
    """메시지 필터 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            # 필터 조건 확인
            try:
                if not filter_func(message):
                    logger.debug(f"메시지 필터링됨: {message.id}")
                    return Success(None)  # 필터링된 메시지는 성공으로 처리
            except Exception as e:
                logger.warning(f"메시지 필터 오류: {e}")
                # 필터 오류시에는 메시지를 처리함
            
            # 원본 핸들러 실행
            if asyncio.iscoroutinefunction(func):
                return await func(message, *args, **kwargs)
            else:
                return func(message, *args, **kwargs)
        
        return wrapper
    
    return decorator


def message_transformer(transform_func: Callable[[Message], Message]):
    """메시지 변환 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            # 메시지 변환
            try:
                transformed_message = transform_func(message)
            except Exception as e:
                logger.error(f"메시지 변환 실패: {e}")
                return Failure(f"메시지 변환 실패: {str(e)}")
            
            # 변환된 메시지로 핸들러 실행
            if asyncio.iscoroutinefunction(func):
                return await func(transformed_message, *args, **kwargs)
            else:
                return func(transformed_message, *args, **kwargs)
        
        return wrapper
    
    return decorator


def rate_limit(
    max_calls: int,
    time_window: float = 60.0,  # 초
    key_func: Optional[Callable[[Message], str]] = None
):
    """속도 제한 데코레이터"""
    call_history = {}
    
    def get_key(message: Message) -> str:
        if key_func:
            return key_func(message)
        return message.topic  # 기본적으로 토픽별로 제한
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            key = get_key(message)
            current_time = asyncio.get_event_loop().time()
            
            # 기록 초기화 또는 업데이트
            if key not in call_history:
                call_history[key] = []
            
            # 시간 윈도우 밖의 기록 제거
            call_history[key] = [
                call_time for call_time in call_history[key]
                if current_time - call_time < time_window
            ]
            
            # 속도 제한 확인
            if len(call_history[key]) >= max_calls:
                logger.warning(f"속도 제한 도달: {key} ({len(call_history[key])}/{max_calls})")
                return Failure(f"속도 제한 초과: {key}")
            
            # 현재 호출 기록
            call_history[key].append(current_time)
            
            # 원본 함수 실행
            if asyncio.iscoroutinefunction(func):
                return await func(message, *args, **kwargs)
            else:
                return func(message, *args, **kwargs)
        
        return wrapper
    
    return decorator


def message_metrics(
    metric_name: str = None,
    include_data_size: bool = True,
    include_processing_time: bool = True
):
    """메시지 메트릭스 수집 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            start_time = asyncio.get_event_loop().time()
            metric_key = metric_name or f"{func.__module__}.{func.__name__}"
            
            try:
                # 원본 함수 실행
                if asyncio.iscoroutinefunction(func):
                    result = await func(message, *args, **kwargs)
                else:
                    result = func(message, *args, **kwargs)
                
                # 성공 메트릭스
                processing_time = asyncio.get_event_loop().time() - start_time
                
                metrics = {
                    "topic": message.topic,
                    "message_id": message.id,
                    "status": "success",
                    "processing_time": processing_time if include_processing_time else None,
                    "data_size": len(str(message.data)) if include_data_size else None,
                    "priority": message.priority.value,
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.debug(f"메시지 메트릭스 ({metric_key}): {metrics}")
                
                return result
                
            except Exception as e:
                # 실패 메트릭스
                processing_time = asyncio.get_event_loop().time() - start_time
                
                metrics = {
                    "topic": message.topic,
                    "message_id": message.id,
                    "status": "error",
                    "error": str(e),
                    "processing_time": processing_time if include_processing_time else None,
                    "data_size": len(str(message.data)) if include_data_size else None,
                    "priority": message.priority.value,
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.error(f"메시지 처리 오류 메트릭스 ({metric_key}): {metrics}")
                
                raise e
        
        return wrapper
    
    return decorator


def batch_handler(
    batch_size: int = 10,
    batch_timeout: float = 1.0,
    max_batch_size: int = 100
):
    """배치 메시지 처리 데코레이터"""
    message_batches = {}
    batch_timers = {}
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            topic = message.topic
            
            # 배치 초기화
            if topic not in message_batches:
                message_batches[topic] = []
            
            # 메시지 추가
            message_batches[topic].append(message)
            
            # 배치 크기 확인
            if len(message_batches[topic]) >= batch_size:
                await process_batch(topic)
            else:
                # 타이머 시작 (없으면)
                if topic not in batch_timers:
                    batch_timers[topic] = asyncio.create_task(
                        batch_timer(topic)
                    )
        
        async def batch_timer(topic: str):
            """배치 타이머"""
            try:
                await asyncio.sleep(batch_timeout)
                await process_batch(topic)
            except asyncio.CancelledError:
                pass
            finally:
                batch_timers.pop(topic, None)
        
        async def process_batch(topic: str):
            """배치 처리"""
            try:
                batch = message_batches.get(topic, [])
                if not batch:
                    return
                
                # 배치 크기 제한
                if len(batch) > max_batch_size:
                    batch = batch[:max_batch_size]
                    message_batches[topic] = message_batches[topic][max_batch_size:]
                else:
                    message_batches[topic] = []
                
                # 타이머 취소
                if topic in batch_timers:
                    batch_timers[topic].cancel()
                    batch_timers.pop(topic, None)
                
                # 배치 처리
                if asyncio.iscoroutinefunction(func):
                    await func(batch, *args, **kwargs)
                else:
                    func(batch, *args, **kwargs)
                
                logger.debug(f"배치 처리 완료: {topic} ({len(batch)}개 메시지)")
                
            except Exception as e:
                logger.error(f"배치 처리 오류: {e}")
        
        return wrapper
    
    return decorator


# 편의 함수들
def create_message_handler_class(
    topic: str,
    handler_func: Callable,
    broker_name: str = None,
    config: SubscriptionConfig = None
) -> type:
    """메시지 핸들러 클래스 동적 생성"""
    class DynamicMessageHandler(MessageHandler):
        def __init__(self):
            self.handler_func = handler_func
        
        async def handle(self, message: Message) -> Result[None, str]:
            try:
                if asyncio.iscoroutinefunction(self.handler_func):
                    result = await self.handler_func(message)
                else:
                    result = self.handler_func(message)
                
                if not isinstance(result, Result):
                    result = Success(result)
                
                return result
                
            except Exception as e:
                return Failure(f"핸들러 실행 실패: {str(e)}")
    
    # 클래스에 메타데이터 추가
    DynamicMessageHandler.__handler_topic__ = topic
    DynamicMessageHandler.__handler_broker__ = broker_name
    DynamicMessageHandler.__handler_config__ = config
    
    return DynamicMessageHandler