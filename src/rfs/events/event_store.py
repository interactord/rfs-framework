"""
Event Store Implementation

이벤트 스토어 구현
- 이벤트 영속화
- 이벤트 스트리밍
- 스냅샷 관리
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Protocol

from ..reactive import Flux
from .event_bus import Event

logger = logging.getLogger(__name__)


class StorageType(Enum):
    """저장소 타입"""

    MEMORY = "memory"
    FILE = "file"
    REDIS = "redis"
    POSTGRES = "postgres"
    FIRESTORE = "firestore"


@dataclass
class EventStreamMetadata:
    """이벤트 스트림 메타데이터"""

    stream_id: str
    version = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    event_count = 0


class EventStoreProtocol(Protocol):
    """이벤트 스토어 인터페이스"""

    async def append_events(
        self, stream_id: str, events: List[Event], expected_version: int = -1
    ) -> int:
        """이벤트 추가"""
        ...

    async def read_events(
        self, stream_id: str, from_version=0, max_count: int = None
    ) -> List[Event]:
        """이벤트 읽기"""
        ...

    async def read_all_events(
        self, from_position=0, max_count: int = None
    ) -> List[Event]:
        """모든 이벤트 읽기"""
        ...

    async def get_stream_metadata(
        self, stream_id: str
    ) -> Optional[EventStreamMetadata]:
        """스트림 메타데이터 조회"""
        ...


class MemoryEventStore:
    """메모리 기반 이벤트 스토어"""

    def __init__(self):
        self.streams: Dict[str, List[Event]] = {}
        self.metadata = {}
        self.all_events = []

    async def append_events(
        self, stream_id: str, events: List[Event], expected_version: int = -1
    ) -> int:
        """이벤트 추가"""
        if stream_id not in self.streams:
            self.streams = {**self.streams, stream_id: []}
            self.metadata = {
                **self.metadata,
                stream_id: EventStreamMetadata(stream_id=stream_id),
            }
        stream = self.streams[stream_id]
        metadata = self.metadata[stream_id]
        current_version = len(stream) - 1
        if expected_version != -1 and current_version != expected_version:
            raise ValueError(
                f"Expected version {expected_version}, but current version is {current_version}"
            )
        new_stream = stream + events
        self.streams = {**self.streams, stream_id: new_stream}
        self.all_events = self.all_events + events

        updated_metadata = EventStreamMetadata(
            stream_id=stream_id,
            version=len(new_stream) - 1,
            created_at=metadata.created_at,
            updated_at=datetime.now(),
            event_count=len(new_stream),
        )
        self.metadata = {**self.metadata, stream_id: updated_metadata}
        logger.info(f"Appended {len(events)} events to stream {stream_id}")
        return updated_metadata.version

    async def read_events(
        self, stream_id: str, from_version=0, max_count: int = None
    ) -> List[Event]:
        """이벤트 읽기"""
        if stream_id not in self.streams:
            return []
        stream = self.streams[stream_id]
        end_index = len(stream)
        if max_count is not None:
            end_index = min(from_version + max_count, len(stream))
        return stream[from_version:end_index]

    async def read_all_events(
        self, from_position=0, max_count: int = None
    ) -> List[Event]:
        """모든 이벤트 읽기"""
        end_index = len(self.all_events)
        if max_count is not None:
            end_index = min(from_position + max_count, len(self.all_events))
        return self.all_events[from_position:end_index]

    async def get_stream_metadata(
        self, stream_id: str
    ) -> Optional[EventStreamMetadata]:
        """스트림 메타데이터 조회"""
        return self.metadata.get(stream_id)

    def get_stats(self) -> Dict[str, Any]:
        """통계 정보"""
        return {
            "total_streams": len(self.streams),
            "total_events": len(self.all_events),
            "streams": {
                stream_id: {
                    "event_count": len(events),
                    "last_updated": self.metadata[stream_id].updated_at.isoformat(),
                }
                for stream_id, events in self.streams.items()
            },
        }


class FileEventStore:
    """파일 기반 이벤트 스토어"""

    def __init__(self, base_path="./event_store"):
        import os

        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
        self._cache = MemoryEventStore()

    def _get_stream_file(self, stream_id: str) -> str:
        """스트림 파일 경로"""
        return f"{self.base_path}/{stream_id}.jsonl"

    def _get_metadata_file(self, stream_id: str) -> str:
        """메타데이터 파일 경로"""
        return f"{self.base_path}/{stream_id}.metadata.json"

    async def _load_stream(self, stream_id: str):
        """스트림 로드"""
        if stream_id in self._cache.streams:
            return
        import aiofiles

        stream_file = self._get_stream_file(stream_id)
        events = []
        try:
            async with aiofiles.open(stream_file, "r", encoding="utf-8") as f:
                async for line in f:
                    event_data = json.loads(line.strip())
                    event = Event(**event_data)
                    events = events + [event]
        except FileNotFoundError:
            pass
        metadata = None
        try:
            async with aiofiles.open(
                self._get_metadata_file(stream_id), "r", encoding="utf-8"
            ) as f:
                content = await f.read()
                metadata_data = json.loads(content)
                metadata_data["created_at"] = {
                    "created_at": datetime.fromisoformat(metadata_data["created_at"])
                }
                metadata_data["updated_at"] = {
                    "updated_at": datetime.fromisoformat(metadata_data["updated_at"])
                }
                metadata = EventStreamMetadata(**metadata_data)
        except FileNotFoundError:
            metadata = EventStreamMetadata(stream_id=stream_id)
        self._cache.streams = {**self._cache.streams, stream_id: events}
        self._cache.metadata = {**self._cache.metadata, stream_id: metadata}
        self._cache.all_events = self._cache.all_events + events

    async def append_events(
        self, stream_id: str, events: List[Event], expected_version: int = -1
    ) -> int:
        """이벤트 추가"""
        await self._load_stream(stream_id)
        version = await self._cache.append_events(stream_id, events, expected_version)
        import aiofiles

        stream_file = self._get_stream_file(stream_id)
        async with aiofiles.open(stream_file, "a", encoding="utf-8") as f:
            for event in events:
                event_dict = asdict(event)
                event_dict["timestamp"] = {"timestamp": event.timestamp.isoformat()}
                await f.write(json.dumps(event_dict) + "\n")
        metadata = self._cache.metadata[stream_id]
        metadata_dict = asdict(metadata)
        metadata_dict["created_at"] = {"created_at": metadata.created_at.isoformat()}
        metadata_dict["updated_at"] = {"updated_at": metadata.updated_at.isoformat()}
        async with aiofiles.open(
            self._get_metadata_file(stream_id), "w", encoding="utf-8"
        ) as f:
            await f.write(json.dumps(metadata_dict, indent=2))
        return version

    async def read_events(
        self, stream_id: str, from_version=0, max_count: int = None
    ) -> List[Event]:
        """이벤트 읽기"""
        await self._load_stream(stream_id)
        return await self._cache.read_events(stream_id, from_version, max_count)

    async def read_all_events(
        self, from_position=0, max_count: int = None
    ) -> List[Event]:
        """모든 이벤트 읽기"""
        import os

        for filename in os.listdir(self.base_path):
            if filename.endswith(".jsonl"):
                stream_id = filename[:-6]
                await self._load_stream(stream_id)
        return await self._cache.read_all_events(from_position, max_count)

    async def get_stream_metadata(
        self, stream_id: str
    ) -> Optional[EventStreamMetadata]:
        """스트림 메타데이터 조회"""
        await self._load_stream(stream_id)
        return await self._cache.get_stream_metadata(stream_id)


class EventStream:
    """이벤트 스트림"""

    def __init__(self, store: EventStoreProtocol, stream_id: str):
        self.store = store
        self.stream_id = stream_id
        self._version = -1

    async def append(self, *events: Event) -> int:
        """이벤트 추가"""
        version = await self.store.append_events(
            self.stream_id, list(events), self._version
        )
        return version

    async def read(self, from_version=0, max_count: int = None) -> List[Event]:
        """이벤트 읽기"""
        return await self.store.read_events(self.stream_id, from_version, max_count)

    async def read_all(self) -> List[Event]:
        """모든 이벤트 읽기"""
        return await self.read()

    async def stream_events(
        self, from_version=0, batch_size=10
    ) -> AsyncGenerator[Event, None]:
        """이벤트 스트리밍"""
        current_version = from_version
        while True:
            events = await self.read(current_version, batch_size)
            if not events:
                break
            for event in events:
                yield event
            current_version = current_version + len(events)
            if len(events) < batch_size:
                break

    async def get_version(self) -> int:
        """현재 버전"""
        metadata = await self.store.get_stream_metadata(self.stream_id)
        return metadata.version if metadata else -1

    def to_flux(self, from_version=0) -> Flux[Event]:
        """Flux로 변환"""

        async def event_generator():
            async for event in self.stream_events(from_version):
                yield event

        return Flux.from_async_iterable(event_generator())


class EventStore:
    """이벤트 스토어 파사드"""

    def __init__(self, storage_type: StorageType = StorageType.MEMORY, **config):
        self.storage_type = storage_type
        self.config = config
        self._store = self._create_store()

    def _create_store(self) -> EventStoreProtocol:
        """스토어 구현체 생성"""
        match self.storage_type:
            case StorageType.MEMORY:
                return MemoryEventStore()
            case StorageType.FILE:
                return FileEventStore(**self.config)
            case _:
                raise ValueError(f"Unsupported storage type: {self.storage_type}")

    def get_stream(self, stream_id: str) -> EventStream:
        """이벤트 스트림 획득"""
        return EventStream(self._store, stream_id)

    async def create_snapshot(
        self, stream_id: str, snapshot_data: Dict[str, Any], version: int
    ):
        """스냅샷 생성"""
        snapshot_event = Event(
            event_type="__snapshot__",
            data=snapshot_data,
            metadata={"snapshot_version": version, "stream_id": stream_id},
        )
        stream = self.get_stream(f"{stream_id}__snapshots__")
        await stream.append(snapshot_event)

    async def get_latest_snapshot(self, stream_id: str) -> Optional[Event]:
        """최신 스냅샷 조회"""
        snapshot_stream = self.get_stream(f"{stream_id}__snapshots__")
        snapshots = await snapshot_stream.read_all()
        if not snapshots:
            return None
        return snapshots[-1]


def create_event_stream(stream_id: str, store: EventStore) -> EventStream:
    """이벤트 스트림 생성"""
    return store.get_stream(stream_id)


async def append_to_stream(stream: EventStream, *events: Event) -> int:
    """스트림에 이벤트 추가"""
    return await stream.append(*events)


async def read_from_stream(stream: EventStream, from_version=0) -> List[Event]:
    """스트림에서 이벤트 읽기"""
    return await stream.read(from_version)


_event_store = None


def get_event_store(
    storage_type: StorageType = StorageType.MEMORY, **config
) -> EventStore:
    """이벤트 스토어 인스턴스 획득"""
    # global _event_store - removed for functional programming
    if _event_store is None:
        _event_store = EventStore(storage_type, **config)
    return _event_store
