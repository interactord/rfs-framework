"""
State persistence for State Machine

상태 머신 영속성 관리
"""

import asyncio
import json
import pickle
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

try:
    import aiofiles

    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False


class PersistenceType(Enum):
    """영속성 타입"""

    MEMORY = "memory"
    FILE = "file"
    REDIS = "redis"
    DATABASE = "database"


@dataclass
class StateMachineSnapshot:
    """상태 머신 스냅샷"""

    machine_name: str
    current_state: Optional[str]
    context: Dict[str, Any]
    machine_state: str
    total_transitions: int
    failed_transitions: int
    start_time: Optional[datetime]
    snapshot_time: datetime
    event_history: List[Dict[str, Any]]


class StatePersistence(Protocol):
    """상태 영속성 인터페이스"""

    async def save_snapshot(self, snapshot: StateMachineSnapshot) -> bool:
        """스냅샷 저장"""
        ...

    async def load_snapshot(self, machine_name: str) -> Optional[StateMachineSnapshot]:
        """스냅샷 로드"""
        ...

    async def delete_snapshot(self, machine_name: str) -> bool:
        """스냅샷 삭제"""
        ...

    async def list_snapshots(self) -> List[str]:
        """스냅샷 목록"""
        ...


class MemoryStatePersistence:
    """메모리 기반 상태 영속성"""

    def __init__(self):
        self.snapshots = {}

    async def save_snapshot(self, snapshot: StateMachineSnapshot) -> bool:
        """스냅샷 저장"""
        try:
            self.snapshots = {**self.snapshots, snapshot.machine_name: snapshot}
            return True
        except Exception as e:
            print(f"Failed to save snapshot for {snapshot.machine_name}: {e}")
            return False

    async def load_snapshot(self, machine_name: str) -> Optional[StateMachineSnapshot]:
        """스냅샷 로드"""
        return self.snapshots.get(machine_name)

    async def delete_snapshot(self, machine_name: str) -> bool:
        """스냅샷 삭제"""
        try:
            if machine_name in self.snapshots:
                del self.snapshots[machine_name]
                return True
            return False
        except Exception as e:
            print(f"Failed to delete snapshot for {machine_name}: {e}")
            return False

    async def list_snapshots(self) -> List[str]:
        """스냅샷 목록"""
        return list(self.snapshots.keys())

    def clear_all(self):
        """모든 스냅샷 삭제"""
        snapshots = {}


class FileStatePersistence:
    """파일 기반 상태 영속성"""

    def __init__(self, base_path="./state_snapshots"):
        if not HAS_AIOFILES:
            raise ImportError(
                "aiofiles is required for file persistence. Install with: pip install rfs-framework[eventstore]"
            )
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_snapshot_path(self, machine_name: str) -> Path:
        """스냅샷 파일 경로"""
        return self.base_path / f"{machine_name}.json"

    async def save_snapshot(self, snapshot: StateMachineSnapshot) -> bool:
        """스냅샷 저장"""
        try:
            snapshot_path = self._get_snapshot_path(snapshot.machine_name)
            snapshot_dict = asdict(snapshot)
            if snapshot_dict["start_time"]:
                snapshot_dict = {
                    **snapshot_dict,
                    "start_time": {
                        "start_time": snapshot_dict["start_time"].isoformat()
                    },
                }
            snapshot_dict = {
                **snapshot_dict,
                "snapshot_time": {
                    "snapshot_time": snapshot_dict["snapshot_time"].isoformat()
                },
            }
            async with aiofiles.open(snapshot_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(snapshot_dict, indent=2, ensure_ascii=False))
            return True
        except Exception as e:
            print(f"Failed to save snapshot for {snapshot.machine_name}: {e}")
            return False

    async def load_snapshot(self, machine_name: str) -> Optional[StateMachineSnapshot]:
        """스냅샷 로드"""
        try:
            snapshot_path = self._get_snapshot_path(machine_name)
            if not snapshot_path.exists():
                return None
            async with aiofiles.open(snapshot_path, "r", encoding="utf-8") as f:
                content = await f.read()
                snapshot_dict = json.loads(content)
            if snapshot_dict["start_time"]:
                snapshot_dict = {
                    **snapshot_dict,
                    "start_time": {
                        "start_time": datetime.fromisoformat(
                            snapshot_dict["start_time"]
                        )
                    },
                }
            snapshot_dict = {
                **snapshot_dict,
                "snapshot_time": {
                    "snapshot_time": datetime.fromisoformat(
                        snapshot_dict["snapshot_time"]
                    )
                },
            }
            return StateMachineSnapshot(**snapshot_dict)
        except Exception as e:
            print(f"Failed to load snapshot for {machine_name}: {e}")
            return None

    async def delete_snapshot(self, machine_name: str) -> bool:
        """스냅샷 삭제"""
        try:
            snapshot_path = self._get_snapshot_path(machine_name)
            if snapshot_path.exists():
                snapshot_path.unlink()
                return True
            return False
        except Exception as e:
            print(f"Failed to delete snapshot for {machine_name}: {e}")
            return False

    async def list_snapshots(self) -> List[str]:
        """스냅샷 목록"""
        try:
            snapshots = []
            for path in self.base_path.glob("*.json"):
                snapshots = snapshots + [path.stem]
            return snapshots
        except Exception as e:
            print(f"Failed to list snapshots: {e}")
            return []


class RedisStatePersistence:
    """Redis 기반 상태 영속성"""

    def __init__(
        self,
        redis_url="redis://localhost:6379",
        key_prefix="state_machine:",
    ):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self._redis = None

    async def _get_redis(self):
        """Redis 연결 획득"""
        if self._redis is None:
            try:
                import aioredis

                self._redis = await aioredis.from_url(self.redis_url)
            except ImportError:
                raise ImportError("aioredis package is required for Redis persistence")
        return self._redis

    def _get_key(self, machine_name: str) -> str:
        """Redis 키 생성"""
        return f"{self.key_prefix}{machine_name}"

    async def save_snapshot(self, snapshot: StateMachineSnapshot) -> bool:
        """스냅샷 저장"""
        try:
            redis = await self._get_redis()
            key = self._get_key(snapshot.machine_name)
            snapshot_dict = asdict(snapshot)
            if snapshot_dict["start_time"]:
                snapshot_dict = {
                    **snapshot_dict,
                    "start_time": {
                        "start_time": snapshot_dict["start_time"].isoformat()
                    },
                }
            snapshot_dict = {
                **snapshot_dict,
                "snapshot_time": {
                    "snapshot_time": snapshot_dict["snapshot_time"].isoformat()
                },
            }
            await redis.set(key, json.dumps(snapshot_dict))
            return True
        except Exception as e:
            print(f"Failed to save snapshot for {snapshot.machine_name}: {e}")
            return False

    async def load_snapshot(self, machine_name: str) -> Optional[StateMachineSnapshot]:
        """스냅샷 로드"""
        try:
            redis = await self._get_redis()
            key = self._get_key(machine_name)
            data = await redis.get(key)
            if not data:
                return None
            snapshot_dict = json.loads(data)
            if snapshot_dict["start_time"]:
                snapshot_dict = {
                    **snapshot_dict,
                    "start_time": {
                        "start_time": datetime.fromisoformat(
                            snapshot_dict["start_time"]
                        )
                    },
                }
            snapshot_dict = {
                **snapshot_dict,
                "snapshot_time": {
                    "snapshot_time": datetime.fromisoformat(
                        snapshot_dict["snapshot_time"]
                    )
                },
            }
            return StateMachineSnapshot(**snapshot_dict)
        except Exception as e:
            print(f"Failed to load snapshot for {machine_name}: {e}")
            return None

    async def delete_snapshot(self, machine_name: str) -> bool:
        """스냅샷 삭제"""
        try:
            redis = await self._get_redis()
            key = self._get_key(machine_name)
            result = await redis.delete(key)
            return result > 0
        except Exception as e:
            print(f"Failed to delete snapshot for {machine_name}: {e}")
            return False

    async def list_snapshots(self) -> List[str]:
        """스냅샷 목록"""
        try:
            redis = await self._get_redis()
            pattern = f"{self.key_prefix}*"
            keys = await redis.keys(pattern)
            machine_names = [key.decode().replace(self.key_prefix, "") for key in keys]
            return machine_names
        except Exception as e:
            print(f"Failed to list snapshots: {e}")
            return []

    async def close(self):
        """Redis 연결 종료"""
        if self._redis:
            await self._redis.close()


class PersistenceManager:
    """영속성 관리자"""

    def __init__(
        self, persistence_type: PersistenceType = PersistenceType.MEMORY, **kwargs
    ):
        self.persistence_type = persistence_type
        self.persistence = self._create_persistence(**kwargs)

    def _create_persistence(self, **kwargs) -> StatePersistence:
        """영속성 구현체 생성"""
        match self.persistence_type:
            case PersistenceType.MEMORY:
                return MemoryStatePersistence()
            case PersistenceType.FILE:
                return FileStatePersistence(**kwargs)
            case PersistenceType.REDIS:
                return RedisStatePersistence(**kwargs)
            case _:
                raise ValueError(
                    f"Unsupported persistence type: {self.persistence_type}"
                )

    async def create_snapshot(self, state_machine) -> StateMachineSnapshot:
        """상태 머신에서 스냅샷 생성"""
        event_history = []
        for event in state_machine.event_history:
            event_dict = {
                "name": event.name,
                "data": event.data,
                "timestamp": event.timestamp.isoformat(),
            }
            event_history = event_history + [event_dict]
        return StateMachineSnapshot(
            machine_name=state_machine.name,
            current_state=(
                state_machine.current_state.name
                if state_machine.current_state
                else None
            ),
            context=state_machine.context,
            machine_state=state_machine.machine_state.value,
            total_transitions=state_machine.total_transitions,
            failed_transitions=state_machine.failed_transitions,
            start_time=state_machine.start_time,
            snapshot_time=datetime.now(),
            event_history=event_history,
        )

    async def restore_from_snapshot(
        self, state_machine, snapshot: StateMachineSnapshot
    ):
        """스냅샷에서 상태 머신 복원"""
        if snapshot.current_state:
            current_state = state_machine.get_state(snapshot.current_state)
            if current_state:
                state_machine.current_state = current_state
        state_machine.context = snapshot.context.copy()
        state_machine.total_transitions = snapshot.total_transitions
        state_machine.failed_transitions = snapshot.failed_transitions
        state_machine.start_time = snapshot.start_time
        from .machine import MachineEvent

        state_machine.event_history = []
        for event_dict in snapshot.event_history[-100:]:
            event = MachineEvent(
                name=event_dict["name"],
                data=event_dict["data"],
                timestamp=datetime.fromisoformat(event_dict["timestamp"]),
            )
            state_machine.event_history = state_machine.event_history + [event]

    async def save_state(self, state_machine) -> bool:
        """상태 머신 상태 저장"""
        snapshot = await self.create_snapshot(state_machine)
        return await self.persistence.save_snapshot(snapshot)

    async def load_state(self, state_machine) -> bool:
        """상태 머신 상태 로드"""
        snapshot = await self.persistence.load_snapshot(state_machine.name)
        if snapshot:
            await self.restore_from_snapshot(state_machine, snapshot)
            return True
        return False

    async def delete_state(self, machine_name: str) -> bool:
        """상태 머신 상태 삭제"""
        return await self.persistence.delete_snapshot(machine_name)

    async def list_saved_states(self) -> List[str]:
        """저장된 상태 목록"""
        return await self.persistence.list_snapshots()


def memory_persistence() -> PersistenceManager:
    """메모리 영속성 관리자"""
    return PersistenceManager(PersistenceType.MEMORY)


def file_persistence(base_path="./state_snapshots") -> PersistenceManager:
    """파일 영속성 관리자"""
    return PersistenceManager(PersistenceType.FILE, base_path=base_path)


def redis_persistence(redis_url="redis://localhost:6379") -> PersistenceManager:
    """Redis 영속성 관리자"""
    return PersistenceManager(PersistenceType.REDIS, redis_url=redis_url)
