"""
Base Components for Service Discovery

서비스 디스커버리 기본 컴포넌트
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ..core.result import Failure, Result, Success


class ServiceStatus(Enum):
    """서비스 상태"""

    STARTING = "starting"  # 시작 중
    RUNNING = "running"  # 실행 중
    STOPPING = "stopping"  # 중지 중
    STOPPED = "stopped"  # 중지됨
    UNHEALTHY = "unhealthy"  # 비정상
    MAINTENANCE = "maintenance"  # 유지보수


class HealthStatus(Enum):
    """헬스 상태"""

    HEALTHY = "healthy"  # 정상
    UNHEALTHY = "unhealthy"  # 비정상
    CRITICAL = "critical"  # 심각
    UNKNOWN = "unknown"  # 알 수 없음


class LoadBalancerType(Enum):
    """로드 밸런서 타입"""

    ROUND_ROBIN = "round_robin"  # 라운드 로빈
    RANDOM = "random"  # 랜덤
    WEIGHTED = "weighted"  # 가중치
    LEAST_CONNECTIONS = "least_connections"  # 최소 연결
    IP_HASH = "ip_hash"  # IP 해시
    CONSISTENT_HASH = "consistent_hash"  # 일관된 해시


@dataclass
class ServiceEndpoint:
    """서비스 엔드포인트"""

    host: str
    port: int
    protocol = "http"  # http, https, grpc, tcp
    path = "/"

    @property
    def url(self) -> str:
        """URL 생성"""
        if self.protocol in ["http", "https"]:
            return f"{self.protocol}://{self.host}:{self.port}{self.path}"
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def address(self) -> str:
        """주소 생성"""
        return f"{self.host}:{self.port}"

    def __str__(self) -> str:
        return self.url

    def __hash__(self) -> int:
        return hash((self.host, self.port, self.protocol))

    def __eq__(self, other) -> bool:
        if not (type(other).__name__ == "ServiceEndpoint"):
            return False
        return (
            self.host == other.host
            and self.port == other.port
            and self.protocol == other.protocol
        )


@dataclass
class ServiceHealth:
    """서비스 헬스 정보"""

    status: HealthStatus = HealthStatus.UNKNOWN
    last_check = None
    response_time = None
    error_count = 0
    success_count = 0
    consecutive_failures = 0
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """헬스 여부"""
        return self.status == HealthStatus.HEALTHY

    @property
    def success_rate(self) -> float:
        """성공률"""
        total = self.success_count + self.error_count
        if total == 0:
            return 0.0
        return self.success_count / total

    def update_health(self, success: bool, response_time=None):
        """헬스 업데이트"""
        self.last_check = datetime.now()
        self.response_time = response_time

        if success:
            success_count = success_count + 1
            self.consecutive_failures = 0
            self.status = HealthStatus.HEALTHY
        else:
            error_count = error_count + 1
            consecutive_failures = consecutive_failures + 1

            if self.consecutive_failures >= 3:
                self.status = HealthStatus.CRITICAL
            else:
                self.status = HealthStatus.UNHEALTHY


@dataclass
class ServiceMetadata:
    """서비스 메타데이터"""

    version = "1.0.0"
    environment = "production"
    region = "default"
    zone = "default"
    tags: List[str] = field(default_factory=list)
    labels: Dict[str, Any] = field(default_factory=dict)
    annotations: Dict[str, Any] = field(default_factory=dict)
    weight = 100  # 로드 밸런싱 가중치
    priority = 0  # 우선순위

    def matches_tags(self, required_tags: List[str]) -> bool:
        """태그 매칭"""
        return all(tag in self.tags for tag in required_tags)

    def matches_labels(self, required_labels: Dict[str, str]) -> bool:
        """레이블 매칭"""
        for key, value in required_labels.items():
            if key not in self.labels or self.labels[key] != value:
                return False
        return True


@dataclass
class ServiceInfo:
    """서비스 정보"""

    service_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name = ""
    endpoint: ServiceEndpoint = field(
        default_factory=lambda: ServiceEndpoint("localhost", 8080)
    )
    status: ServiceStatus = ServiceStatus.STARTING
    health: ServiceHealth = field(default_factory=ServiceHealth)
    metadata: ServiceMetadata = field(default_factory=ServiceMetadata)

    # 등록 정보
    registered_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    ttl = None

    # 의존성
    dependencies: List[str] = field(default_factory=list)

    @property
    def is_available(self) -> bool:
        """사용 가능 여부"""
        return self.status == ServiceStatus.RUNNING and self.health.is_healthy

    @property
    def is_expired(self) -> bool:
        """만료 여부"""
        if not self.ttl:
            return False
        return datetime.now() - self.updated_at > self.ttl

    def refresh(self):
        """갱신"""
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "service_id": self.service_id,
            "name": self.name,
            "endpoint": {
                "host": self.endpoint.host,
                "port": self.endpoint.port,
                "protocol": self.endpoint.protocol,
                "path": self.endpoint.path,
            },
            "status": self.status.value,
            "health": {
                "status": self.health.status.value,
                "last_check": (
                    self.health.last_check.isoformat()
                    if self.health.last_check
                    else None
                ),
                "success_rate": self.health.success_rate,
            },
            "metadata": {
                "version": self.metadata.version,
                "environment": self.metadata.environment,
                "region": self.metadata.region,
                "zone": self.metadata.zone,
                "tags": self.metadata.tags,
                "labels": self.metadata.labels,
                "weight": self.metadata.weight,
                "priority": self.metadata.priority,
            },
            "registered_at": self.registered_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "ttl": self.ttl.total_seconds() if self.ttl else None,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceInfo":
        """딕셔너리에서 생성"""
        endpoint = ServiceEndpoint(
            host=data["endpoint"]["host"],
            port=data["endpoint"]["port"],
            protocol=data["endpoint"].get("protocol", "http"),
            path=data["endpoint"].get("path", "/"),
        )

        health = ServiceHealth(
            status=HealthStatus(data["health"]["status"]),
            last_check=(
                datetime.fromisoformat(data["health"]["last_check"])
                if data["health"].get("last_check")
                else None
            ),
        )

        metadata = ServiceMetadata(
            version=data["metadata"].get("version", "1.0.0"),
            environment=data["metadata"].get("environment", "production"),
            region=data["metadata"].get("region", "default"),
            zone=data["metadata"].get("zone", "default"),
            tags=data["metadata"].get("tags", []),
            labels=data["metadata"].get("labels", {}),
            weight=data["metadata"].get("weight", 100),
            priority=data["metadata"].get("priority", 0),
        )

        return cls(
            service_id=data["service_id"],
            name=data["name"],
            endpoint=endpoint,
            status=ServiceStatus(data["status"]),
            health=health,
            metadata=metadata,
            registered_at=datetime.fromisoformat(data["registered_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            ttl=timedelta(seconds=data["ttl"]) if data.get("ttl") else None,
            dependencies=data.get("dependencies", []),
        )


@dataclass
class HealthCheck:
    """헬스 체크 설정"""

    enabled = True
    interval: timedelta = timedelta(seconds=10)
    timeout: timedelta = timedelta(seconds=5)
    healthy_threshold = 2  # 정상 판정 임계값
    unhealthy_threshold = 3  # 비정상 판정 임계값

    # 체크 방법
    check_type = "http"  # http, tcp, grpc, exec
    check_path = "/health"
    check_method = "GET"
    check_headers: Dict[str, Any] = field(default_factory=dict)
    check_body = None
    expected_status: List[str] = field(default_factory=list)

    def should_check(self, last_check: Optional[datetime]) -> bool:
        """체크 필요 여부"""
        if not self.enabled:
            return False

        if not last_check:
            return True

        return datetime.now() - last_check >= self.interval


class ServiceDiscoveryError(Exception):
    """서비스 디스커버리 에러"""

    pass


class ServiceNotFoundError(ServiceDiscoveryError):
    """서비스를 찾을 수 없음"""

    pass


class RegistrationError(ServiceDiscoveryError):
    """등록 에러"""

    pass


class HealthCheckError(ServiceDiscoveryError):
    """헬스 체크 에러"""

    pass
