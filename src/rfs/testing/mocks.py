"""
RFS Testing Framework - Mocks Module
Mock 객체 및 테스트 더블
"""

from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock as BaseAsyncMock
from unittest.mock import MagicMock as BaseMagicMock
from unittest.mock import Mock as BaseMock
from unittest.mock import patch as base_patch

from ..core.result import Failure, Result, Success


class Mock(BaseMock):
    """RFS Mock 객체"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.call_history: List[Tuple[tuple, dict]] = []

    def __call__(self, *args, **kwargs):
        self.call_history.append((args, kwargs))
        return super().__call__(*args, **kwargs)


class AsyncMock(BaseAsyncMock):
    """비동기 Mock 객체"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.call_history: List[Tuple[tuple, dict]] = []

    async def __call__(self, *args, **kwargs):
        self.call_history.append((args, kwargs))
        return await super().__call__(*args, **kwargs)


class MagicMock(BaseMagicMock):
    """Magic Mock 객체"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.call_history: List[Tuple[tuple, dict]] = []

    def __call__(self, *args, **kwargs):
        self.call_history.append((args, kwargs))
        return super().__call__(*args, **kwargs)


class Stub:
    """Stub 객체"""

    def __init__(self, return_value: Any = None, side_effect=None) -> None:
        """초기화"""
        self.return_value = return_value
        self.side_effect = side_effect
        self.called = False
        self.call_count = 0
        self.call_args = None
        self.call_args_list = []

    def __call__(self, *args, **kwargs):
        """호출"""
        self.called = True
        self.call_count += 1
        self.call_args = (args, kwargs)
        self.call_args_list.append((args, kwargs))

        if self.side_effect:
            if callable(self.side_effect):
                return self.side_effect(*args, **kwargs)
            elif isinstance(self.side_effect, Exception):
                raise self.side_effect

        return self.return_value

    def reset(self):
        """상태 리셋"""
        self.called = False
        self.call_count = 0
        self.call_args = None
        self.call_args_list = []


def create_stub(return_value: Any = None, **attributes) -> Stub:
    """Stub 생성"""
    stub = Stub(return_value=return_value)
    for key, value in attributes.items():
        setattr(stub, key, value)
    return stub


# Patch 헬퍼
def patch(target: str, new: Any = None, **kwargs):
    """패치 데코레이터/컨텍스트 매니저"""
    if new is None:
        new = Mock()
    return base_patch(target, new, **kwargs)


def patch_object(target: Any, attribute: str, new: Any = None, **kwargs):
    """객체 패치"""
    if new is None:
        new = Mock()
    return base_patch.object(target, attribute, new, **kwargs)


def patch_method(cls: type, method_name: str, new=None):
    """메서드 패치"""
    if new is None:
        new = Mock()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with patch_object(cls, method_name, new):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# Assertion 헬퍼
def assert_called(mock: Mock) -> Result[None, str]:
    """호출 확인"""
    if not mock.called:
        return Failure(f"Mock was not called")
    return Success(None)


def assert_called_with(mock: Mock, *args, **kwargs) -> Result[None, str]:
    """호출 인자 확인"""
    if not mock.called:
        return Failure("Mock was not called")

    if mock.call_args != (args, kwargs):
        return Failure(
            f"Mock was called with {mock.call_args}, " f"expected ({args}, {kwargs})"
        )

    return Success(None)


def assert_called_once(mock: Mock) -> Result[None, str]:
    """단일 호출 확인"""
    if mock.call_count != 1:
        return Failure(f"Mock was called {mock.call_count} times, expected 1")
    return Success(None)


def assert_not_called(mock: Mock) -> Result[None, str]:
    """미호출 확인"""
    if mock.called:
        return Failure(f"Mock was called {mock.call_count} times")
    return Success(None)


# Fake 객체들
class FakeDatabase:
    """Fake Database"""

    def __init__(self):
        self.data: Dict[str, List[Dict[str, Any]]] = {}
        self.connected = False
        self.transaction_active = False

    def connect(self) -> Result[None, str]:
        """연결"""
        if self.connected:
            return Failure("Already connected")
        self.connected = True
        return Success(None)

    def disconnect(self) -> Result[None, str]:
        """연결 해제"""
        if not self.connected:
            return Failure("Not connected")
        self.connected = False
        return Success(None)

    def insert(self, table: str, data: Dict[str, Any]) -> Result[int, str]:
        """삽입"""
        if not self.connected:
            return Failure("Not connected")

        if table not in self.data:
            self.data[table] = []

        record = data.copy()
        record["id"] = len(self.data[table]) + 1
        self.data[table].append(record)

        return Success(record["id"])

    def select(self, table: str, **filters) -> Result[List[Dict[str, Any]], str]:
        """조회"""
        if not self.connected:
            return Failure("Not connected")

        if table not in self.data:
            return Success([])

        results = self.data[table]

        # 필터 적용
        for key, value in filters.items():
            results = [r for r in results if r.get(key) == value]

        return Success(results)

    def begin_transaction(self) -> Result[None, str]:
        """트랜잭션 시작"""
        if not self.connected:
            return Failure("Not connected")
        if self.transaction_active:
            return Failure("Transaction already active")

        self.transaction_active = True
        return Success(None)

    def commit(self) -> Result[None, str]:
        """커밋"""
        if not self.transaction_active:
            return Failure("No active transaction")

        self.transaction_active = False
        return Success(None)

    def rollback(self) -> Result[None, str]:
        """롤백"""
        if not self.transaction_active:
            return Failure("No active transaction")

        self.transaction_active = False
        return Success(None)


class FakeRedis:
    """Fake Redis"""

    def __init__(self):
        self.data = {}
        self.expiry = {}

    def get(self, key: str) -> Optional[Any]:
        """값 조회"""
        return self.data.get(key)

    def set(self, key: str, value: Any, ex=None) -> bool:
        """값 설정"""
        self.data[key] = value
        if ex:
            import time

            self.expiry[key] = time.time() + ex
        return True

    def delete(self, key: str) -> bool:
        """삭제"""
        if key in self.data:
            del self.data[key]
            if key in self.expiry:
                del self.expiry[key]
            return True
        return False

    def exists(self, key: str) -> bool:
        """존재 확인"""
        return key in self.data

    def flushall(self) -> bool:
        """전체 삭제"""
        self.data.clear()
        self.expiry.clear()
        return True


class FakeMessageBroker:
    """Fake Message Broker"""

    def __init__(self):
        self.queues: Dict[str, List[Any]] = {}
        self.subscribers: Dict[str, List[Callable]] = {}

    def publish(self, channel: str, message: Any) -> Result[None, str]:
        """메시지 발행"""
        if channel not in self.queues:
            self.queues[channel] = []

        self.queues[channel].append(message)

        # 구독자에게 전달
        if channel in self.subscribers:
            for subscriber in self.subscribers[channel]:
                try:
                    subscriber(message)
                except Exception as e:
                    return Failure(f"Subscriber error: {str(e)}")

        return Success(None)

    def subscribe(self, channel: str, callback: Callable) -> Result[None, str]:
        """구독"""
        if channel not in self.subscribers:
            self.subscribers[channel] = []

        self.subscribers[channel].append(callback)
        return Success(None)

    def get_messages(self, channel: str) -> List[Any]:
        """메시지 조회"""
        return self.queues.get(channel, [])

    def clear(self, channel=None) -> None:
        """클리어"""
        if channel:
            if channel in self.queues:
                self.queues[channel] = []
        else:
            self.queues.clear()


__all__ = [
    "Mock",
    "AsyncMock",
    "MagicMock",
    "Stub",
    "create_stub",
    "patch",
    "patch_object",
    "patch_method",
    "assert_called",
    "assert_called_with",
    "assert_called_once",
    "assert_not_called",
    "FakeDatabase",
    "FakeRedis",
    "FakeMessageBroker",
]
