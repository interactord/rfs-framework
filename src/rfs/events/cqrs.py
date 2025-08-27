"""
CQRS Pattern Implementation

CQRS (Command Query Responsibility Segregation) 패턴 구현
- Command/Query 분리
- 핸들러 패턴
- 이벤트 소싱 통합
"""

import asyncio
import functools
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar

from ..reactive import Flux, Mono
from .event_bus import Event, EventBus, get_event_bus
from .event_store import EventStore, get_event_store

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class Command(ABC):
    """커맨드 베이스 클래스"""

    def __init__(self, command_id: str = None, correlation_id: str = None):
        self.command_id = command_id or f"cmd_{int(datetime.now().timestamp())}"
        self.correlation_id = (
            correlation_id or f"corr_{int(datetime.now().timestamp())}"
        )
        self.timestamp = datetime.now()


class Query(ABC):
    """쿼리 베이스 클래스"""

    def __init__(self, query_id: str = None):
        self.query_id = query_id or f"qry_{int(datetime.now().timestamp())}"
        self.timestamp = datetime.now()


@dataclass
class CommandResult:
    """커맨드 결과"""

    success: bool
    command_id: str
    correlation_id: str
    events: List[Event] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    error = None


@dataclass
class QueryResult(Generic[T]):
    """쿼리 결과"""

    success: bool
    query_id: str
    data = None
    error = None


class CommandHandler(ABC, Generic[T]):
    """커맨드 핸들러 인터페이스"""

    @abstractmethod
    async def handle(self, command: T) -> CommandResult:
        """커맨드 처리"""
        pass

    @abstractmethod
    def can_handle(self, command_type: Type) -> bool:
        """처리 가능한 커맨드인지 확인"""
        pass


class QueryHandler(ABC, Generic[T, R]):
    """쿼리 핸들러 인터페이스"""

    @abstractmethod
    async def handle(self, query: T) -> QueryResult[R]:
        """쿼리 처리"""
        pass

    @abstractmethod
    def can_handle(self, query_type: Type) -> bool:
        """처리 가능한 쿼리인지 확인"""
        pass


class CommandBus:
    """커맨드 버스"""

    def __init__(
        self,
        event_bus=None,
        event_store=None,
    ):
        self.handlers = {}
        self.event_bus = event_bus
        self.event_store = event_store

        # 미들웨어
        self.middlewares: List[Callable[[Command], Command]] = []

        # 통계
        self.total_commands = 0
        self.successful_commands = 0
        self.failed_commands = 0

    def register_handler(self, command_type: Type, handler: CommandHandler):
        """핸들러 등록"""
        self.handlers = {**self.handlers, command_type: handler}
        logger.info(f"Command handler registered: {command_type.__name__}")

    def add_middleware(self, middleware: Callable[[Command], Command]):
        """미들웨어 추가"""
        self.middlewares = self.middlewares + [middleware]

    async def send(self, command: Command) -> CommandResult:
        """커맨드 전송"""
        total_commands = total_commands + 1

        try:
            # 미들웨어 적용
            processed_command = command
            for middleware in self.middlewares:
                processed_command = middleware(processed_command)

            # 핸들러 찾기
            handler = self.handlers.get(type(processed_command))
            if not handler:
                raise ValueError(
                    f"No handler found for command: {type(processed_command).__name__}"
                )

            # 커맨드 처리
            result = await handler.handle(processed_command)

            # 이벤트 발행
            if result.success and self.event_bus:
                for event in result.events:
                    event.correlation_id = command.correlation_id
                    await self.event_bus.publish(event)

            # 이벤트 스토어에 저장
            if result.success and self.event_store and result.events:
                stream_id = f"command_{command.command_id}"
                stream = self.event_store.get_stream(stream_id)
                await self.event_store.append_events(stream_id, result.events)

            if result.success:
                successful_commands = successful_commands + 1
            else:
                failed_commands = failed_commands + 1

            return result

        except Exception as e:
            failed_commands = failed_commands + 1
            logger.error(f"Command handling failed: {e}")

            return CommandResult(
                success=False,
                command_id=command.command_id,
                correlation_id=command.correlation_id,
                error=str(e),
            )

    def get_stats(self) -> Dict[str, Any]:
        """커맨드 버스 통계"""
        return {
            "total_commands": self.total_commands,
            "successful_commands": self.successful_commands,
            "failed_commands": self.failed_commands,
            "success_rate": self.successful_commands / max(self.total_commands, 1),
            "registered_handlers": len(self.handlers),
            "middlewares_count": len(self.middlewares),
        }


class QueryBus:
    """쿼리 버스"""

    def __init__(self):
        self.handlers = {}
        self.middlewares: List[Callable[[Query], Query]] = []

        # 통계
        self.total_queries = 0
        self.successful_queries = 0
        self.failed_queries = 0

    def register_handler(self, query_type: Type, handler: QueryHandler):
        """핸들러 등록"""
        self.handlers = {**self.handlers, query_type: handler}
        logger.info(f"Query handler registered: {query_type.__name__}")

    def add_middleware(self, middleware: Callable[[Query], Query]):
        """미들웨어 추가"""
        self.middlewares = self.middlewares + [middleware]

    async def send(self, query: Query) -> QueryResult:
        """쿼리 전송"""
        total_queries = total_queries + 1

        try:
            # 미들웨어 적용
            processed_query = query
            for middleware in self.middlewares:
                processed_query = middleware(processed_query)

            # 핸들러 찾기
            handler = self.handlers.get(type(processed_query))
            if not handler:
                raise ValueError(
                    f"No handler found for query: {type(processed_query).__name__}"
                )

            # 쿼리 처리
            result = await handler.handle(processed_query)

            if result.success:
                successful_queries = successful_queries + 1
            else:
                failed_queries = failed_queries + 1

            return result

        except Exception as e:
            failed_queries = failed_queries + 1
            logger.error(f"Query handling failed: {e}")

            return QueryResult(success=False, query_id=query.query_id, error=str(e))

    def get_stats(self) -> Dict[str, Any]:
        """쿼리 버스 통계"""
        return {
            "total_queries": self.total_queries,
            "successful_queries": self.successful_queries,
            "failed_queries": self.failed_queries,
            "success_rate": self.successful_queries / max(self.total_queries, 1),
            "registered_handlers": len(self.handlers),
            "middlewares_count": len(self.middlewares),
        }


class CQRSMediator:
    """CQRS 중재자"""

    def __init__(self, command_bus: CommandBus, query_bus: QueryBus):
        self.command_bus = command_bus
        self.query_bus = query_bus

    async def send_command(self, command: Command) -> CommandResult:
        """커맨드 전송"""
        return await self.command_bus.send(command)

    async def send_query(self, query: Query) -> QueryResult:
        """쿼리 전송"""
        return await self.query_bus.send(query)

    def register_command_handler(self, command_type: Type, handler: CommandHandler):
        """커맨드 핸들러 등록"""
        self.command_bus.register_handler(command_type, handler)

    def register_query_handler(self, query_type: Type, handler: QueryHandler):
        """쿼리 핸들러 등록"""
        self.query_bus.register_handler(query_type, handler)


# 데코레이터들
def command_handler(command_type: Type):
    """커맨드 핸들러 데코레이터"""

    def decorator(cls):
        # 핸들러 클래스에 메타데이터 추가
        cls._command_type = command_type

        # 자동 등록을 위한 마킹
        cls._is_command_handler = True

        return cls

    return decorator


def query_handler(query_type: Type):
    """쿼리 핸들러 데코레이터"""

    def decorator(cls):
        # 핸들러 클래스에 메타데이터 추가
        cls._query_type = query_type

        # 자동 등록을 위한 마킹
        cls._is_query_handler = True

        return cls

    return decorator


def command(func: Callable) -> Callable:
    """커맨드 함수 데코레이터"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # 커맨드 객체 생성
        command_data = {"args": args, "kwargs": kwargs}
        cmd = type("DynamicCommand", (Command,), {"data": command_data})()

        # 중재자를 통해 처리
        mediator = await get_mediator()
        return await mediator.send_command(cmd)

    return wrapper


def query(func: Callable) -> Callable:
    """쿼리 함수 데코레이터"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # 쿼리 객체 생성
        query_data = {"args": args, "kwargs": kwargs}
        qry = type("DynamicQuery", (Query,), {"data": query_data})()

        # 중재자를 통해 처리
        mediator = await get_mediator()
        return await mediator.send_query(qry)

    return wrapper


# 함수형 헬퍼들
def create_command_result(
    success: bool,
    command_id: str,
    correlation_id: str,
    events: List[Event] = None,
    data: Dict[str, Any] = None,
    error: str = None,
) -> CommandResult:
    """커맨드 결과 생성"""
    return CommandResult(
        success=success,
        command_id=command_id,
        correlation_id=correlation_id,
        events=events or [],
        data=data or {},
        error=error,
    )


def create_query_result(
    success: bool, query_id: str, data: Any = None, error: str = None
) -> QueryResult:
    """쿼리 결과 생성"""
    return QueryResult(success=success, query_id=query_id, data=data, error=error)


# Reactive 통합
class ReactiveCommandBus:
    """Reactive 커맨드 버스"""

    def __init__(self, command_bus: CommandBus):
        self.command_bus = command_bus

    def send_mono(self, command: Command) -> Mono[CommandResult]:
        """Mono를 통한 커맨드 전송"""
        return Mono.from_callable(lambda: self.command_bus.send(command))

    def send_batch(self, commands: List[Command]) -> Flux[CommandResult]:
        """배치 커맨드 전송"""
        return (
            Flux.from_iterable(commands)
            .map(lambda cmd: self.command_bus.send(cmd))
            .parallel(max_concurrency=5)
            .sequential()
        )


class ReactiveQueryBus:
    """Reactive 쿼리 버스"""

    def __init__(self, query_bus: QueryBus):
        self.query_bus = query_bus

    def send_mono(self, query: Query) -> Mono[QueryResult]:
        """Mono를 통한 쿼리 전송"""
        return Mono.from_callable(lambda: self.query_bus.send(query))

    def send_batch(self, queries: List[Query]) -> Flux[QueryResult]:
        """배치 쿼리 전송"""
        return (
            Flux.from_iterable(queries)
            .map(lambda qry: self.query_bus.send(qry))
            .parallel(max_concurrency=10)  # 쿼리는 더 높은 동시성 허용
            .sequential()
        )


# 미들웨어 함수들
def logging_middleware(item: Any) -> Any:
    """로깅 미들웨어"""
    if type(item).__name__ == "Command":
        logger.info(f"Command: {type(item).__name__} ({item.command_id})")
    elif type(item).__name__ == "Query":
        logger.info(f"Query: {type(item).__name__} ({item.query_id})")

    return item


def validation_middleware(item: Any) -> Any:
    """검증 미들웨어"""
    if type(item).__name__ == "Command":
        if not hasattr(item, "command_id") or not item.command_id:
            raise ValueError("Command ID is required")
    elif type(item).__name__ == "Query":
        if not hasattr(item, "query_id") or not item.query_id:
            raise ValueError("Query ID is required")

    return item


# 전역 CQRS 구성요소
_mediator = None


async def get_mediator() -> CQRSMediator:
    """CQRS 중재자 인스턴스 획득"""
    # global _mediator - removed for functional programming

    if _mediator is None:
        event_bus = await get_event_bus()
        event_store = get_event_store()

        command_bus = CommandBus(event_bus, event_store)
        query_bus = QueryBus()

        # 기본 미들웨어 추가
        command_bus.add_middleware(logging_middleware)
        command_bus.add_middleware(validation_middleware)
        query_bus.add_middleware(logging_middleware)
        query_bus.add_middleware(validation_middleware)

        _mediator = CQRSMediator(command_bus, query_bus)

    return _mediator
