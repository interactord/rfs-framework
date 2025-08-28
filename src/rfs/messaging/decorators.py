"""
RFS Messaging Decorators (RFS v4.1)

메시징 데코레이터 시스템
"""

import asyncio
import functools
import inspect
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success
from .base import Message, MessagePriority, get_message_broker
from .publisher import Publisher
from .subscriber import MessageHandler, Subscriber, SubscriptionConfig

logger = get_logger(__name__)


def message_handler(
    topic: Optional[str] = None,
    broker_name: Optional[str] = None,
    auto_ack: bool = True,
    max_retries: int = 3,
    retry_delay: float = 1.0,
):
    """메시지 핸들러 데코레이터"""

    def decorator(func: Callable) -> Callable:
        func.__message_handler__ = True
        func.__handler_topic__ = topic
        func.__handler_broker__ = broker_name
        func.__handler_config__ = {
            "auto_ack": auto_ack,
            "max_retries": max_retries,
            "retry_delay": retry_delay,
        }

        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(message, *args, **kwargs)
                else:
                    result = func(message, *args, **kwargs)
                if not type(result).__name__ == "Result":
                    result = Success(result)
                return result
            except Exception as e:
                logger.error(f"메시지 핸들러 오류: {e}")
                return Failure(f"핸들러 실행 실패: {str(e)}")

        return wrapper

    return decorator


def topic_subscriber(
    topic: str,
    broker_name: Optional[str] = None,
    config: Optional[SubscriptionConfig] = None,
    auto_start: bool = True,
):
    """토픽 구독 데코레이터"""

    def decorator(cls_or_func):
        if inspect.isclass(cls_or_func):
            original_init = cls_or_func.__init__

            def new_init(self, *args, **kwargs):
                original_init(self, *args, **kwargs)
                self._subscriber = Subscriber(broker_name, config)
                if auto_start:
                    asyncio.create_task(self._start_subscription())

            async def _start_subscription(self):
                """구독 시작"""
                try:
                    await self._subscriber.subscribe(topic, self.handle_message)
                    logger.info(f"자동 구독 시작: {topic}")
                except Exception as e:
                    logger.error(f"자동 구독 실패: {e}")

            cls_or_func.__init__ = new_init
            cls_or_func._start_subscription = _start_subscription
            if not hasattr(cls_or_func, "handle_message"):
                raise ValueError("handle_message 메서드가 필요합니다")
            return cls_or_func
        else:

            @functools.wraps(cls_or_func)
            def wrapper(*args, **kwargs):

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
    exceptions: tuple = (Exception,),
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
                    return result
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(f"재시도 {attempt + 1}/{max_retries}: {e}")
                        await asyncio.sleep(current_delay)
                        current_delay = min(current_delay * backoff_factor, max_delay)
                    else:
                        logger.error(f"최대 재시도 횟수 도달: {e}")
                        raise last_exception
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def dead_letter_queue(dlq_topic: Optional[str] = None, max_failures: int = 5, broker_name: Optional[str] = None):
    """Dead Letter Queue 데코레이터"""

    def decorator(func: Callable) -> Callable:
        failure_count = {}

        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            message_key = f"{message.topic}:{message.id}"
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(message, *args, **kwargs)
                else:
                    result = func(message, *args, **kwargs)
                failure_count = failure_count[:-1]
                return result
            except Exception as e:
                failure_count = {
                    **failure_count,
                    message_key: {message_key: failure_count.get(message_key, 0) + 1},
                }
                if failure_count[message_key] >= max_failures:
                    await send_to_dlq(message, str(e), dlq_topic, broker_name)
                    failure_count = failure_count[:-1]
                    logger.error(f"메시지를 DLQ로 전송: {message.id}")
                    return Failure(f"DLQ로 전송됨: {e}")
                else:
                    logger.warning(
                        f"메시지 처리 실패 ({failure_count[message_key]}/{max_failures}): {e}"
                    )
                    raise e

        return wrapper

    return decorator


async def send_to_dlq(
    message: Message, error_message: str, dlq_topic: Optional[str] = None, broker_name: Optional[str] = None
):
    """메시지를 Dead Letter Queue로 전송"""
    try:
        broker = get_message_broker(broker_name)
        if not broker:
            logger.error("브로커를 찾을 수 없어 DLQ 전송 실패")
            return
        if not dlq_topic:
            dlq_topic = broker._make_dlq_topic(message.topic)
        dlq_message = Message(
            topic=dlq_topic,
            data=message.data,
            headers={
                **message.headers,
                "original_topic": message.topic,
                "original_message_id": message.id,
                "error_message": error_message,
                "dlq_timestamp": datetime.now().isoformat(),
                "retry_count": message.retry_count,
            },
            priority=message.priority,
            correlation_id=message.correlation_id,
        )
        await broker.publish(dlq_topic, dlq_message)
    except Exception as e:
        logger.error(f"DLQ 전송 실패: {e}")


def message_filter(filter_func: Callable[[Message], bool]):
    """메시지 필터 데코레이터"""

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            try:
                if not filter_func(message):
                    logger.debug(f"메시지 필터링됨: {message.id}")
                    return Success(None)
            except Exception as e:
                logger.warning(f"메시지 필터 오류: {e}")
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
            try:
                transformed_message = transform_func(message)
            except Exception as e:
                logger.error(f"메시지 변환 실패: {e}")
                return Failure(f"메시지 변환 실패: {str(e)}")
            if asyncio.iscoroutinefunction(func):
                return await func(transformed_message, *args, **kwargs)
            else:
                return func(transformed_message, *args, **kwargs)

        return wrapper

    return decorator


def rate_limit(
    max_calls: int,
    time_window: float = 60.0,
    key_func: Optional[Callable[[Message], str]] = None,
):
    """속도 제한 데코레이터"""
    call_history = {}

    def get_key(message: Message) -> str:
        if key_func:
            return key_func(message)
        return message.topic

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            key = get_key(message)
            current_time = asyncio.get_event_loop().time()
            if key not in call_history:
                call_history[key] = {key: []}
            call_history = {
                **call_history,
                key: {
                    key: [
                        call_time
                        for call_time in call_history[key]
                        if current_time - call_time < time_window
                    ]
                },
            }
            if len(call_history[key]) >= max_calls:
                logger.warning(
                    f"속도 제한 도달: {key} ({len(call_history[key])}/{max_calls})"
                )
                return Failure(f"속도 제한 초과: {key}")
            call_history[key] = call_history[key] + [current_time]
            if asyncio.iscoroutinefunction(func):
                return await func(message, *args, **kwargs)
            else:
                return func(message, *args, **kwargs)

        return wrapper

    return decorator


def message_metrics(
    metric_name: Optional[str] = None,
    include_data_size: bool = True,
    include_processing_time: bool = True,
):
    """메시지 메트릭스 수집 데코레이터"""

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            start_time = asyncio.get_event_loop().time()
            metric_key = metric_name or f"{func.__module__}.{func.__name__}"
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(message, *args, **kwargs)
                else:
                    result = func(message, *args, **kwargs)
                processing_time = asyncio.get_event_loop().time() - start_time
                metrics = {
                    "topic": message.topic,
                    "message_id": message.id,
                    "status": "success",
                    "processing_time": (
                        processing_time if include_processing_time else None
                    ),
                    "data_size": len(str(message.data)) if include_data_size else None,
                    "priority": message.priority.value,
                    "timestamp": datetime.now().isoformat(),
                }
                logger.debug(f"메시지 메트릭스 ({metric_key}): {metrics}")
                return result
            except Exception as e:
                processing_time = asyncio.get_event_loop().time() - start_time
                metrics = {
                    "topic": message.topic,
                    "message_id": message.id,
                    "status": "error",
                    "error": str(e),
                    "processing_time": (
                        processing_time if include_processing_time else None
                    ),
                    "data_size": len(str(message.data)) if include_data_size else None,
                    "priority": message.priority.value,
                    "timestamp": datetime.now().isoformat(),
                }
                logger.error(f"메시지 처리 오류 메트릭스 ({metric_key}): {metrics}")
                raise e

        return wrapper

    return decorator


def batch_handler(batch_size: int = 10, batch_timeout: float = 1.0, max_batch_size: int = 100):
    """배치 메시지 처리 데코레이터"""
    message_batches = {}
    batch_timers = {}

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            topic = message.topic
            if topic not in message_batches:
                message_batches[topic] = []
            message_batches = {
                **message_batches,
                topic: message_batches[topic] + [message],
            }
            if len(message_batches[topic]) >= batch_size:
                await process_batch(topic)
            elif topic not in batch_timers:
                batch_timers = {
                    **batch_timers,
                    topic: asyncio.create_task(batch_timer(topic)),
                }

        async def batch_timer(topic: str):
            """배치 타이머"""
            try:
                await asyncio.sleep(batch_timeout)
                await process_batch(topic)
            except asyncio.CancelledError:
                pass
            finally:
                batch_timers = batch_timers[:-1]

        async def process_batch(topic: str):
            """배치 처리"""
            try:
                batch = message_batches.get(topic, [])
                if not batch:
                    return
                if len(batch) > max_batch_size:
                    batch = batch[:max_batch_size]
                    message_batches = {
                        **message_batches,
                        topic: {topic: message_batches[topic][max_batch_size:]},
                    }
                else:
                    message_batches[topic] = {topic: []}
                if topic in batch_timers:
                    batch_timers[topic].cancel()
                    batch_timers = batch_timers[:-1]
                if asyncio.iscoroutinefunction(func):
                    await func(batch, *args, **kwargs)
                else:
                    func(batch, *args, **kwargs)
                logger.debug(f"배치 처리 완료: {topic} ({len(batch)}개 메시지)")
            except Exception as e:
                logger.error(f"배치 처리 오류: {e}")

        return wrapper

    return decorator


def create_message_handler_class(
    topic: str,
    handler_func: Callable,
    broker_name: Optional[str] = None,
    config: Optional[SubscriptionConfig] = None,
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
                if not type(result).__name__ == "Result":
                    result = Success(result)
                return result
            except Exception as e:
                return Failure(f"핸들러 실행 실패: {str(e)}")

    DynamicMessageHandler.__handler_topic__ = topic
    DynamicMessageHandler.__handler_broker__ = broker_name
    DynamicMessageHandler.__handler_config__ = config
    return DynamicMessageHandler
