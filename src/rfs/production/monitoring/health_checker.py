"""
Health Checker for RFS Framework

종합적인 헬스 체크 및 상태 관리 시스템
- 엔드포인트 헬스 체크
- 데이터베이스 연결 상태 확인
- 외부 서비스 의존성 체크
- 시스템 리소스 상태 모니터링
"""

import asyncio
import json
import logging
import socket
import ssl
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import aiohttp
import psutil

from rfs.core.config import get_config
from rfs.core.result import Failure, Result, Success
from rfs.events.event_bus import Event
from rfs.reactive.mono import Mono


class HealthStatus(Enum):
    """헬스 상태"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(Enum):
    """체크 유형"""

    HTTP = "http"
    TCP = "tcp"
    DATABASE = "database"
    SERVICE = "service"
    CUSTOM = "custom"
    RESOURCE = "resource"


@dataclass
class HealthCheckConfig:
    """헬스 체크 설정"""

    check_interval_seconds: float = 30.0
    timeout_seconds: float = 10.0
    retries = 3
    retry_delay_seconds: float = 1.0
    unhealthy_threshold = 3
    healthy_threshold = 2
    enable_detailed_metrics = True
    max_check_history = 100


@dataclass
class HealthCheckResult:
    """헬스 체크 결과"""

    check_name: str
    status: HealthStatus
    response_time_ms: float
    timestamp: datetime
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class HealthCheck:
    """헬스 체크 정의"""

    name: str
    check_type: CheckType
    config: Dict[str, Any]
    enabled = True
    critical = True
    tags: Dict[str, Any] = field(default_factory=dict)
    description = ""
    expected_response_time_ms: float = 1000.0


class EndpointCheck:
    """HTTP 엔드포인트 체크"""

    def __init__(self, check_config: HealthCheck):
        self.config = check_config
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> None:
        """체크 초기화"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.config.config.get("timeout", 10))
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def execute(self) -> HealthCheckResult:
        """헬스 체크 실행"""
        await self.initialize()
        if self.session is None:
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=0,
                timestamp=datetime.now(),
                message="Failed to initialize session",
                error="Session initialization failed"
            )
        url = self.config.config["url"]
        method = self.config.config.get("method", "GET").upper()
        headers = self.config.config.get("headers", {})
        expected_status = self.config.config.get("expected_status", [200])
        expected_content = self.config.config.get("expected_content")
        start_time = time.time()
        try:
            match method:
                case "GET":
                    async with self.session.get(url, headers=headers) as response:
                        response_time_ms = (time.time() - start_time) * 1000
                        content = await response.text()
                        return await self._evaluate_response(
                            response,
                            content,
                            response_time_ms,
                            expected_status,
                            expected_content,
                        )
                case "POST":
                    data = self.config.config.get("data", {})
                    async with self.session.post(
                        url, json=data, headers=headers
                    ) as response:
                        response_time_ms = (time.time() - start_time) * 1000
                        content = await response.text()
                        return await self._evaluate_response(
                            response,
                            content,
                            response_time_ms,
                            expected_status,
                            expected_content,
                        )
                case _:
                    return HealthCheckResult(
                        check_name=self.config.name,
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=0,
                        timestamp=datetime.now(),
                        message=f"Unsupported method: {method}",
                        error=f"Method {method} not implemented",
                    )
        except asyncio.TimeoutError:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message="Request timeout",
                error="Timeout exceeded",
            )
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"Request failed: {str(e)}",
                error=str(e),
            )

    async def _evaluate_response(
        self,
        response: aiohttp.ClientResponse,
        content: str,
        response_time_ms: float,
        expected_status: List[int],
        expected_content: Optional[str],
    ) -> HealthCheckResult:
        """응답 평가"""
        if response.status not in expected_status:
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"Unexpected status code: {response.status}",
                details={
                    "status_code": response.status,
                    "expected_status": expected_status,
                    "content_length": len(content),
                },
                error=f"Status {response.status} not in expected {expected_status}",
            )
        if expected_content and expected_content not in content:
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.DEGRADED,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message="Expected content not found in response",
                details={
                    "status_code": response.status,
                    "content_length": len(content),
                    "expected_content": expected_content,
                },
                error="Expected content missing",
            )
        if response_time_ms > self.config.expected_response_time_ms * 2:
            status = HealthStatus.DEGRADED
            message = f"Slow response: {response_time_ms:.2f}ms"
        elif response_time_ms > self.config.expected_response_time_ms:
            status = HealthStatus.DEGRADED
            message = f"Slow response: {response_time_ms:.2f}ms"
        else:
            status = HealthStatus.HEALTHY
            message = "OK"
        return HealthCheckResult(
            check_name=self.config.name,
            status=status,
            response_time_ms=response_time_ms,
            timestamp=datetime.now(),
            message=message,
            details={
                "status_code": response.status,
                "content_length": len(content),
                "response_headers": dict(response.headers),
            },
        )

    async def cleanup(self) -> None:
        """리소스 정리"""
        if self.session and (not self.session.closed):
            await self.session.close()
            self.session = None


class DatabaseCheck:
    """데이터베이스 연결 체크"""

    def __init__(self, check_config: HealthCheck):
        self.config = check_config

    async def execute(self) -> HealthCheckResult:
        """데이터베이스 헬스 체크 실행"""
        db_type = self.config.config.get("type", "postgresql")
        connection_string = self.config.config.get("connection_string")
        test_query = self.config.config.get("test_query", "SELECT 1")
        start_time = time.time()
        try:
            match db_type:
                case "postgresql":
                    return await self._check_postgresql(
                        connection_string, test_query, start_time
                    )
                case "mysql":
                    return await self._check_mysql(
                        connection_string, test_query, start_time
                    )
                case "sqlite":
                    return await self._check_sqlite(
                        connection_string, test_query, start_time
                    )
                case "redis":
                    return await self._check_redis(connection_string, start_time)
                case _:
                    return HealthCheckResult(
                        check_name=self.config.name,
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=0,
                        timestamp=datetime.now(),
                        message=f"Unsupported database type: {db_type}",
                        error=f"Database type {db_type} not supported",
                    )
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"Database check failed: {str(e)}",
                error=str(e),
            )

    async def _check_postgresql(
        self, connection_string: str, test_query: str, start_time: float
    ) -> HealthCheckResult:
        """PostgreSQL 체크"""
        try:
            import asyncpg

            conn = await asyncpg.connect(connection_string)
            try:
                result = await conn.fetchrow(test_query)
                response_time_ms = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    check_name=self.config.name,
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time_ms,
                    timestamp=datetime.now(),
                    message="PostgreSQL connection successful",
                    details={
                        "database_type": "postgresql",
                        "query_result": str(result) if result else None,
                    },
                )
            finally:
                await conn.close()
        except ImportError:
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=0,
                timestamp=datetime.now(),
                message="PostgreSQL driver not available",
                error="asyncpg not installed",
            )

    async def _check_mysql(
        self, connection_string: str, test_query: str, start_time: float
    ) -> HealthCheckResult:
        """MySQL 체크"""
        try:
            import aiomysql

            conn = await aiomysql.connect(
                host="localhost", port=3306, user="user", password="pass", db="db"
            )
            try:
                cursor = await conn.cursor()
                await cursor.execute(test_query)
                result = await cursor.fetchone()
                response_time_ms = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    check_name=self.config.name,
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time_ms,
                    timestamp=datetime.now(),
                    message="MySQL connection successful",
                    details={
                        "database_type": "mysql",
                        "query_result": str(result) if result else None,
                    },
                )
            finally:
                conn.close()
        except ImportError:
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=0,
                timestamp=datetime.now(),
                message="MySQL driver not available",
                error="aiomysql not installed",
            )

    async def _check_sqlite(
        self, connection_string: str, test_query: str, start_time: float
    ) -> HealthCheckResult:
        """SQLite 체크"""
        try:
            import aiosqlite

            async with aiosqlite.connect(connection_string) as conn:
                cursor = await conn.execute(test_query)
                result = await cursor.fetchone()
                response_time_ms = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    check_name=self.config.name,
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time_ms,
                    timestamp=datetime.now(),
                    message="SQLite connection successful",
                    details={
                        "database_type": "sqlite",
                        "query_result": str(result) if result else None,
                    },
                )
        except ImportError:
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=0,
                timestamp=datetime.now(),
                message="SQLite driver not available",
                error="aiosqlite not installed",
            )

    async def _check_redis(
        self, connection_string: str, start_time: float
    ) -> HealthCheckResult:
        """Redis 체크"""
        try:
            import aioredis

            redis = aioredis.from_url(connection_string)
            try:
                await redis.ping()
                response_time_ms = (time.time() - start_time) * 1000
                return HealthCheckResult(
                    check_name=self.config.name,
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time_ms,
                    timestamp=datetime.now(),
                    message="Redis connection successful",
                    details={"database_type": "redis", "ping_result": "pong"},
                )
            finally:
                await redis.close()
        except ImportError:
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=0,
                timestamp=datetime.now(),
                message="Redis driver not available",
                error="aioredis not installed",
            )


class ServiceCheck:
    """외부 서비스 체크"""

    def __init__(self, check_config: HealthCheck):
        self.config = check_config

    async def execute(self) -> HealthCheckResult:
        """서비스 헬스 체크 실행"""
        service_type = self.config.config.get("type", "tcp")
        start_time = time.time()
        try:
            match service_type:
                case "tcp":
                    return await self._check_tcp_port(start_time)
                case "udp":
                    return await self._check_udp_port(start_time)
                case "dns":
                    return await self._check_dns(start_time)
                case "ssl":
                    return await self._check_ssl_certificate(start_time)
                case _:
                    return HealthCheckResult(
                        check_name=self.config.name,
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=0,
                        timestamp=datetime.now(),
                        message=f"Unsupported service type: {service_type}",
                        error=f"Service type {service_type} not supported",
                    )
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"Service check failed: {str(e)}",
                error=str(e),
            )

    async def _check_tcp_port(self, start_time: float) -> HealthCheckResult:
        """TCP 포트 체크"""
        host = self.config.config["host"]
        port = self.config.config["port"]
        timeout = self.config.config.get("timeout", 5)
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"TCP connection to {host}:{port} successful",
                details={"host": host, "port": port, "protocol": "tcp"},
            )
        except asyncio.TimeoutError:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"TCP connection to {host}:{port} timed out",
                error="Connection timeout",
            )
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"TCP connection to {host}:{port} failed",
                error=str(e),
            )

    async def _check_udp_port(self, start_time: float) -> HealthCheckResult:
        """UDP 포트 체크"""
        host = self.config.config["host"]
        port = self.config.config["port"]
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            sock.sendto(b"", (host, port))
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"UDP packet sent to {host}:{port}",
                details={"host": host, "port": port, "protocol": "udp"},
            )
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"UDP check to {host}:{port} failed",
                error=str(e),
            )
        finally:
            sock.close()

    async def _check_dns(self, start_time: float) -> HealthCheckResult:
        """DNS 체크"""
        hostname = self.config.config["hostname"]
        try:
            import socket

            result = socket.gethostbyname(hostname)
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"DNS resolution for {hostname} successful",
                details={"hostname": hostname, "resolved_ip": result},
            )
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"DNS resolution for {hostname} failed",
                error=str(e),
            )

    async def _check_ssl_certificate(self, start_time: float) -> HealthCheckResult:
        """SSL 인증서 체크"""
        host = self.config.config["host"]
        port = self.config.config.get("port", 443)
        try:
            context = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
            response_time_ms = (time.time() - start_time) * 1000
            not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
            days_until_expiry = (not_after - datetime.now()).days
            if days_until_expiry < 7:
                status = HealthStatus.UNHEALTHY
                message = f"SSL certificate expires in {days_until_expiry} days"
            elif days_until_expiry < 30:
                status = HealthStatus.DEGRADED
                message = f"SSL certificate expires in {days_until_expiry} days"
            else:
                status = HealthStatus.HEALTHY
                message = "SSL certificate valid"
            return HealthCheckResult(
                check_name=self.config.name,
                status=status,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=message,
                details={
                    "host": host,
                    "port": port,
                    "subject": cert.get("subject"),
                    "issuer": cert.get("issuer"),
                    "not_after": cert.get("notAfter"),
                    "days_until_expiry": days_until_expiry,
                },
            )
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"SSL check for {host}:{port} failed",
                error=str(e),
            )


class ResourceCheck:
    """시스템 리소스 체크"""

    def __init__(self, check_config: HealthCheck):
        self.config = check_config

    async def execute(self) -> HealthCheckResult:
        """리소스 헬스 체크 실행"""
        resource_type = self.config.config.get("type", "cpu")
        start_time = time.time()
        try:
            match resource_type:
                case "cpu":
                    return await self._check_cpu_usage(start_time)
                case "memory":
                    return await self._check_memory_usage(start_time)
                case "disk":
                    return await self._check_disk_usage(start_time)
                case "load":
                    return await self._check_system_load(start_time)
                case _:
                    return HealthCheckResult(
                        check_name=self.config.name,
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=0,
                        timestamp=datetime.now(),
                        message=f"Unsupported resource type: {resource_type}",
                        error=f"Resource type {resource_type} not supported",
                    )
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"Resource check failed: {str(e)}",
                error=str(e),
            )

    async def _check_cpu_usage(self, start_time: float) -> HealthCheckResult:
        """CPU 사용률 체크"""
        warning_threshold = self.config.config.get("warning_threshold", 80.0)
        critical_threshold = self.config.config.get("critical_threshold", 95.0)
        cpu_usage = psutil.cpu_percent(interval=1)
        response_time_ms = (time.time() - start_time) * 1000
        if cpu_usage >= critical_threshold:
            status = HealthStatus.UNHEALTHY
            message = f"Critical CPU usage: {cpu_usage:.1f}%"
        elif cpu_usage >= warning_threshold:
            status = HealthStatus.DEGRADED
            message = f"High CPU usage: {cpu_usage:.1f}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"CPU usage normal: {cpu_usage:.1f}%"
        return HealthCheckResult(
            check_name=self.config.name,
            status=status,
            response_time_ms=response_time_ms,
            timestamp=datetime.now(),
            message=message,
            details={
                "cpu_usage_percent": cpu_usage,
                "warning_threshold": warning_threshold,
                "critical_threshold": critical_threshold,
                "cpu_count": psutil.cpu_count(),
            },
        )

    async def _check_memory_usage(self, start_time: float) -> HealthCheckResult:
        """메모리 사용률 체크"""
        warning_threshold = self.config.config.get("warning_threshold", 80.0)
        critical_threshold = self.config.config.get("critical_threshold", 95.0)
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        response_time_ms = (time.time() - start_time) * 1000
        if memory_usage >= critical_threshold:
            status = HealthStatus.UNHEALTHY
            message = f"Critical memory usage: {memory_usage:.1f}%"
        elif memory_usage >= warning_threshold:
            status = HealthStatus.DEGRADED
            message = f"High memory usage: {memory_usage:.1f}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"Memory usage normal: {memory_usage:.1f}%"
        return HealthCheckResult(
            check_name=self.config.name,
            status=status,
            response_time_ms=response_time_ms,
            timestamp=datetime.now(),
            message=message,
            details={
                "memory_usage_percent": memory_usage,
                "total_gb": memory.total / 1024**3,
                "available_gb": memory.available / 1024**3,
                "warning_threshold": warning_threshold,
                "critical_threshold": critical_threshold,
            },
        )

    async def _check_disk_usage(self, start_time: float) -> HealthCheckResult:
        """디스크 사용률 체크"""
        path = self.config.config.get("path", "/")
        warning_threshold = self.config.config.get("warning_threshold", 85.0)
        critical_threshold = self.config.config.get("critical_threshold", 95.0)
        disk = psutil.disk_usage(path)
        disk_usage = disk.used / disk.total * 100
        response_time_ms = (time.time() - start_time) * 1000
        if disk_usage >= critical_threshold:
            status = HealthStatus.UNHEALTHY
            message = f"Critical disk usage: {disk_usage:.1f}%"
        elif disk_usage >= warning_threshold:
            status = HealthStatus.DEGRADED
            message = f"High disk usage: {disk_usage:.1f}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"Disk usage normal: {disk_usage:.1f}%"
        return HealthCheckResult(
            check_name=self.config.name,
            status=status,
            response_time_ms=response_time_ms,
            timestamp=datetime.now(),
            message=message,
            details={
                "disk_usage_percent": disk_usage,
                "path": path,
                "total_gb": disk.total / 1024**3,
                "free_gb": disk.free / 1024**3,
                "warning_threshold": warning_threshold,
                "critical_threshold": critical_threshold,
            },
        )

    async def _check_system_load(self, start_time: float) -> HealthCheckResult:
        """시스템 로드 체크"""
        warning_threshold = self.config.config.get("warning_threshold", 2.0)
        critical_threshold = self.config.config.get("critical_threshold", 5.0)
        try:
            load_avg = psutil.getloadavg()[0]
        except AttributeError:
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNKNOWN,
                response_time_ms=0,
                timestamp=datetime.now(),
                message="System load not available on this platform",
                error="Load average not supported",
            )
        response_time_ms = (time.time() - start_time) * 1000
        if load_avg >= critical_threshold:
            status = HealthStatus.UNHEALTHY
            message = f"Critical system load: {load_avg:.2f}"
        elif load_avg >= warning_threshold:
            status = HealthStatus.DEGRADED
            message = f"High system load: {load_avg:.2f}"
        else:
            status = HealthStatus.HEALTHY
            message = f"System load normal: {load_avg:.2f}"
        return HealthCheckResult(
            check_name=self.config.name,
            status=status,
            response_time_ms=response_time_ms,
            timestamp=datetime.now(),
            message=message,
            details={
                "load_average_1min": load_avg,
                "warning_threshold": warning_threshold,
                "critical_threshold": critical_threshold,
                "cpu_count": psutil.cpu_count(),
            },
        )


class CustomCheck:
    """커스텀 헬스 체크"""

    def __init__(self, check_config: HealthCheck, check_function: Callable):
        self.config = check_config
        self.check_function = check_function

    async def execute(self) -> HealthCheckResult:
        """커스텀 헬스 체크 실행"""
        start_time = time.time()
        try:
            if asyncio.iscoroutinefunction(self.check_function):
                result = await self.check_function()
            else:
                result = self.check_function()
            response_time_ms = (time.time() - start_time) * 1000
            if type(result).__name__ == "HealthCheckResult":
                return result
            if type(result).__name__ == "bool":
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                message = "Custom check passed" if result else "Custom check failed"
                return HealthCheckResult(
                    check_name=self.config.name,
                    status=status,
                    response_time_ms=response_time_ms,
                    timestamp=datetime.now(),
                    message=message,
                )
            if type(result).__name__ == "dict":
                status_str = result.get("status", "unknown")
                status = (
                    HealthStatus(status_str)
                    if status_str in [s.value for s in HealthStatus]
                    else HealthStatus.UNKNOWN
                )
                return HealthCheckResult(
                    check_name=self.config.name,
                    status=status,
                    response_time_ms=response_time_ms,
                    timestamp=datetime.now(),
                    message=result.get("message", "Custom check completed"),
                    details=result.get("details", {}),
                    error=result.get("error"),
                )
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"Custom check returned: {result}",
            )
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                check_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                message=f"Custom check failed: {str(e)}",
                error=str(e),
            )


class HealthChecker:
    """헬스 체커"""

    def __init__(self, config=None):
        self.config = config or HealthCheckConfig()
        self.checks = {}
        self.check_handlers = {}
        self.custom_functions = {}
        self.check_results = {}
        self.latest_results = {}
        self.consecutive_failures = {}
        self.consecutive_successes = {}
        self.check_states = {}
        self.monitoring_task = None
        self.is_running = False
        self.total_checks_run = 0
        self.total_checks_passed = 0
        self.total_checks_failed = 0

    async def initialize(self) -> Result[bool, str]:
        """헬스 체커 초기화"""
        try:
            logging.info("Health checker initialized successfully")
            return Success(True)
        except Exception as e:
            return Failure(f"Health checker initialization failed: {e}")

    def add_check(self, check: HealthCheck) -> Result[bool, str]:
        """헬스 체크 추가"""
        try:
            self.checks = {**self.checks, check.name: check}
            match check.check_type:
                case CheckType.HTTP:
                    self.check_handlers = {
                        **self.check_handlers,
                        check.name: EndpointCheck(check),
                    }
                case CheckType.DATABASE:
                    self.check_handlers = {
                        **self.check_handlers,
                        check.name: DatabaseCheck(check),
                    }
                case CheckType.SERVICE:
                    self.check_handlers = {
                        **self.check_handlers,
                        check.name: ServiceCheck(check),
                    }
                case CheckType.RESOURCE:
                    self.check_handlers = {
                        **self.check_handlers,
                        check.name: ResourceCheck(check),
                    }
                case CheckType.CUSTOM:
                    if check.name in self.custom_functions:
                        self.check_handlers = {
                            **self.check_handlers,
                            check.name: CustomCheck(
                                check, self.custom_functions[check.name]
                            ),
                        }
                    else:
                        return Failure(
                            f"Custom check function not registered for: {check.name}"
                        )
                case _:
                    return Failure(f"Unsupported check type: {check.check_type}")
            logging.info(f"Health check added: {check.name}")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to add health check: {e}")

    def register_custom_check(self, name: str, check_function: Callable) -> None:
        """커스텀 체크 함수 등록"""
        self.custom_functions = {**self.custom_functions, name: check_function}

    async def run_check(self, check_name: str) -> Result[HealthCheckResult, str]:
        """단일 헬스 체크 실행"""
        if check_name not in self.checks:
            return Failure(f"Health check not found: {check_name}")
        check = self.checks[check_name]
        if not check.enabled:
            return Failure(f"Health check disabled: {check_name}")
        if check_name not in self.check_handlers:
            return Failure(f"Check handler not found for: {check_name}")
        try:
            handler = self.check_handlers[check_name]
            last_error = None
            for attempt in range(self.config.retries + 1):
                try:
                    result = await handler.execute()
                    self._update_check_state(check_name, result)
                    total_checks_run = total_checks_run + 1
                    if result.status == HealthStatus.HEALTHY:
                        total_checks_passed = total_checks_passed + 1
                    else:
                        total_checks_failed = total_checks_failed + 1
                    return Success(result)
                except Exception as e:
                    last_error = str(e)
                    if attempt < self.config.retries:
                        await asyncio.sleep(self.config.retry_delay_seconds)
                    continue
            result = HealthCheckResult(
                check_name=check_name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=0,
                timestamp=datetime.now(),
                message=f"Check failed after {self.config.retries + 1} attempts",
                error=last_error,
            )
            self._update_check_state(check_name, result)
            total_checks_run = total_checks_run + 1
            total_checks_failed = total_checks_failed + 1
            return Success(result)
        except Exception as e:
            return Failure(f"Health check execution failed: {e}")

    def _update_check_state(self, check_name: str, result: HealthCheckResult) -> None:
        """체크 상태 업데이트"""
        self.check_results[check_name] = check_results[check_name] + [result]
        self.latest_results = {**self.latest_results, check_name: result}
        if result.status == HealthStatus.HEALTHY:
            self.consecutive_successes = {
                **self.consecutive_successes,
                check_name: self.consecutive_successes[check_name] + 1,
            }
            self.consecutive_failures = {**self.consecutive_failures, check_name: 0}
        else:
            self.consecutive_failures = {
                **self.consecutive_failures,
                check_name: self.consecutive_failures[check_name] + 1,
            }
            self.consecutive_successes = {**self.consecutive_successes, check_name: 0}
        if self.consecutive_failures[check_name] >= self.config.unhealthy_threshold:
            self.check_states = {
                **self.check_states,
                check_name: HealthStatus.UNHEALTHY,
            }
        elif self.consecutive_successes[check_name] >= self.config.healthy_threshold:
            self.check_states = {**self.check_states, check_name: HealthStatus.HEALTHY}
        else:
            self.check_states = {**self.check_states, check_name: result.status}

    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """모든 헬스 체크 실행"""
        results = {}
        tasks: List[Tuple[str, Any]] = []
        for check_name in self.checks:
            if self.checks[check_name].enabled:
                task = self.run_check(check_name)
                tasks = tasks + [(check_name, task)]
        for check_name, task in tasks:
            try:
                result = await task
                if result.is_success():
                    results[check_name] = {check_name: result.unwrap()}
                else:
                    results = {
                        **results,
                        check_name: {
                            check_name: HealthCheckResult(
                                check_name=check_name,
                                status=HealthStatus.UNHEALTHY,
                                response_time_ms=0,
                                timestamp=datetime.now(),
                                message="Check execution failed",
                                error=result.error,
                            )
                        },
                    }
            except Exception as e:
                results = {
                    **results,
                    check_name: {
                        check_name: HealthCheckResult(
                            check_name=check_name,
                            status=HealthStatus.UNHEALTHY,
                            response_time_ms=0,
                            timestamp=datetime.now(),
                            message=f"Check execution error: {str(e)}",
                            error=str(e),
                        )
                    },
                }
        return results

    async def start_monitoring(self) -> Result[bool, str]:
        """헬스 모니터링 시작"""
        if self.is_running:
            return Success(True)
        try:
            self.is_running = True
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            logging.info("Health monitoring started")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to start health monitoring: {e}")

    async def stop_monitoring(self) -> Result[bool, str]:
        """헬스 모니터링 중지"""
        try:
            self.is_running = False
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
                self.monitoring_task = None
            logging.info("Health monitoring stopped")
            return Success(True)
        except Exception as e:
            return Failure(f"Failed to stop health monitoring: {e}")

    async def _monitoring_loop(self) -> None:
        """헬스 모니터링 루프"""
        while self.is_running:
            try:
                await self.run_all_checks()
                await asyncio.sleep(self.config.check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Health monitoring loop error: {e}")
                await asyncio.sleep(self.config.check_interval_seconds)

    def get_overall_health(self) -> Dict[str, Any]:
        """전체 헬스 상태 조회"""
        if not self.latest_results:
            return {
                "status": HealthStatus.UNKNOWN.value,
                "message": "No health checks available",
                "checks": {},
            }
        critical_failures: List[str] = []
        degraded_services: List[str] = []
        healthy_services: List[str] = []
        for check_name, result in self.latest_results.items():
            check = self.checks[check_name]
            match result.status:
                case HealthStatus.UNHEALTHY:
                    if check.critical:
                        critical_failures = critical_failures + [check_name]
                    else:
                        degraded_services = degraded_services + [check_name]
                case HealthStatus.DEGRADED:
                    degraded_services = degraded_services + [check_name]
                case HealthStatus.HEALTHY:
                    healthy_services = healthy_services + [check_name]
        if critical_failures:
            overall_status = HealthStatus.UNHEALTHY
            message = f"Critical failures: {', '.join(critical_failures)}"
        elif degraded_services:
            overall_status = HealthStatus.DEGRADED
            message = f"Degraded services: {', '.join(degraded_services)}"
        elif healthy_services:
            overall_status = HealthStatus.HEALTHY
            message = "All checks passing"
        else:
            overall_status = HealthStatus.UNKNOWN
            message = "Unknown status"
        return {
            "status": overall_status.value,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "checks": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "response_time_ms": result.response_time_ms,
                    "last_check": result.timestamp.isoformat(),
                }
                for name, result in self.latest_results.items()
            },
            "summary": {
                "total_checks": len(self.latest_results),
                "healthy": len(healthy_services),
                "degraded": len(degraded_services),
                "unhealthy": len(critical_failures),
                "critical_failures": critical_failures,
                "degraded_services": degraded_services,
            },
            "statistics": {
                "total_checks_run": self.total_checks_run,
                "total_checks_passed": self.total_checks_passed,
                "total_checks_failed": self.total_checks_failed,
                "success_rate": self.total_checks_passed
                / max(1, self.total_checks_run),
            },
        }

    def get_check_history(self, check_name: str, limit=50) -> List[HealthCheckResult]:
        """체크 이력 조회"""
        if check_name not in self.check_results:
            return []
        results = list(self.check_results[check_name])
        return results[-limit:] if limit else results

    async def cleanup(self) -> Result[bool, str]:
        """리소스 정리"""
        try:
            await self.stop_monitoring()
            for handler in self.check_handlers.values():
                if hasattr(handler, "cleanup"):
                    await handler.cleanup()
            checks: Dict[str, HealthCheck] = {}
            check_handlers: Dict[str, Any] = {}
            check_results: Dict[str, HealthCheckResult] = {}
            logging.info("Health checker cleanup completed")
            return Success(True)
        except Exception as e:
            return Failure(f"Cleanup failed: {e}")


_health_checker: Optional[HealthChecker] = None


def get_health_checker(config: Optional[HealthCheckConfig] = None) -> HealthChecker:
    """헬스 체커 싱글톤 인스턴스 반환"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker(config)
    return _health_checker


async def run_health_checks(
    checks: List[HealthCheck], config=None
) -> Result[Dict[str, Any], str]:
    """헬스 체크 실행"""
    checker = get_health_checker(config)
    init_result = await checker.initialize()
    if not init_result.is_success():
        return Failure(f"Health checker initialization failed: {init_result.error}")
    for check in checks:
        add_result = checker.add_check(check)
        if not add_result.is_success():
            return Failure(f"Failed to add check {check.name}: {add_result.error}")
    results = await checker.run_all_checks()
    return Success(checker.get_overall_health())
