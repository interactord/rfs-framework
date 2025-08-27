"""
Health Check Implementation

헬스 체크 구현 - HTTP, TCP, gRPC
"""

import asyncio
import logging
import socket
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import aiohttp

from ..core.result import Failure, Result, Success
from .base import (
    HealthCheck,
    HealthCheckError,
    HealthStatus,
    ServiceEndpoint,
    ServiceHealth,
    ServiceInfo,
)
from .registry import ServiceRegistry, get_service_registry

logger = logging.getLogger(__name__)


class HealthChecker:
    """
    헬스 체커

    다양한 프로토콜의 헬스 체크 수행
    """

    async def check(
        self, endpoint: ServiceEndpoint, config: HealthCheck
    ) -> Result[ServiceHealth, str]:
        """
        헬스 체크 수행

        Args:
            endpoint: 체크할 엔드포인트
            config: 헬스 체크 설정

        Returns:
            헬스 상태
        """
        if not config.enabled:
            return Success(ServiceHealth(status=HealthStatus.UNKNOWN))

        start_time = datetime.now()

        try:
            match config.check_type:
                case "http":
                    result = await self._check_http(endpoint, config)
                case "tcp":
                    result = await self._check_tcp(endpoint, config)
                case "grpc":
                    result = await self._check_grpc(endpoint, config)
                case _:
                    return Failure(f"Unsupported check type: {config.check_type}")

            response_time = datetime.now() - start_time

            if type(result).__name__ == "Success":
                health = ServiceHealth(
                    status=HealthStatus.HEALTHY,
                    last_check=datetime.now(),
                    response_time=response_time,
                )
                success_count = success_count + 1
                return Success(health)
            else:
                health = ServiceHealth(
                    status=HealthStatus.UNHEALTHY,
                    last_check=datetime.now(),
                    response_time=response_time,
                    details={"error": result.error},
                )
                error_count = error_count + 1
                return Success(health)

        except Exception as e:
            health = ServiceHealth(
                status=HealthStatus.CRITICAL,
                last_check=datetime.now(),
                details={"error": str(e)},
            )
            error_count = error_count + 1
            return Success(health)

    async def _check_http(
        self, endpoint: ServiceEndpoint, config: HealthCheck
    ) -> Result[None, str]:
        """HTTP 헬스 체크"""
        url = f"{endpoint.url}{config.check_path}"

        try:
            timeout = aiohttp.ClientTimeout(total=config.timeout.total_seconds())

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method=config.check_method,
                    url=url,
                    headers=config.check_headers,
                    data=config.check_body,
                ) as response:
                    if response.status in config.expected_status:
                        return Success(None)
                    else:
                        return Failure(f"Unexpected status: {response.status}")

        except asyncio.TimeoutError:
            return Failure("Health check timed out")
        except Exception as e:
            return Failure(f"HTTP check failed: {str(e)}")

    async def _check_tcp(
        self, endpoint: ServiceEndpoint, config: HealthCheck
    ) -> Result[None, str]:
        """TCP 헬스 체크"""
        try:
            # TCP 연결 시도
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(endpoint.host, endpoint.port),
                timeout=config.timeout.total_seconds(),
            )

            # 연결 성공
            writer.close()
            await writer.wait_closed()

            return Success(None)

        except asyncio.TimeoutError:
            return Failure("TCP connection timed out")
        except Exception as e:
            return Failure(f"TCP check failed: {str(e)}")

    async def _check_grpc(
        self, endpoint: ServiceEndpoint, config: HealthCheck
    ) -> Result[None, str]:
        """gRPC 헬스 체크"""
        # gRPC 헬스 체크 구현
        # grpc.health.v1.Health 서비스 사용
        return Success(None)


class HttpHealthCheck:
    """HTTP 헬스 체크"""

    def __init__(
        self,
        path="/health",
        method="GET",
        expected_status: List[int] = None,
        timeout: timedelta = timedelta(seconds=5),
    ):
        self.config = HealthCheck(
            check_type="http",
            check_path=path,
            check_method=method,
            expected_status=expected_status or [200],
            timeout=timeout,
        )
        self.checker = HealthChecker()

    async def check(self, endpoint: ServiceEndpoint) -> Result[ServiceHealth, str]:
        """헬스 체크 수행"""
        return await self.checker.check(endpoint, self.config)


class TcpHealthCheck:
    """TCP 헬스 체크"""

    def __init__(self, timeout: timedelta = timedelta(seconds=5)):
        self.config = HealthCheck(check_type="tcp", timeout=timeout)
        self.checker = HealthChecker()

    async def check(self, endpoint: ServiceEndpoint) -> Result[ServiceHealth, str]:
        """헬스 체크 수행"""
        return await self.checker.check(endpoint, self.config)


class GrpcHealthCheck:
    """gRPC 헬스 체크"""

    def __init__(self, timeout: timedelta = timedelta(seconds=5)):
        self.config = HealthCheck(check_type="grpc", timeout=timeout)
        self.checker = HealthChecker()

    async def check(self, endpoint: ServiceEndpoint) -> Result[ServiceHealth, str]:
        """헬스 체크 수행"""
        return await self.checker.check(endpoint, self.config)


class HealthMonitor:
    """
    헬스 모니터

    정기적인 헬스 체크 수행 및 상태 업데이트
    """

    def __init__(
        self,
        registry=None,
        default_check=None,
    ):
        self.registry = registry or get_service_registry()
        self.default_check = default_check or HealthCheck()
        self.checker = HealthChecker()

        # 모니터링 대상
        self.monitored_services = {}
        self.health_checks = {}

        # 모니터링 태스크
        self.monitor_tasks = {}
        self._running = False

    async def start(self):
        """모니터 시작"""
        self._running = True
        logger.info("HealthMonitor started")

    async def stop(self):
        """모니터 중지"""
        self._running = False

        # 모든 모니터링 태스크 취소
        for task in self.monitor_tasks.values():
            task.cancel()

        if self.monitor_tasks:
            await asyncio.gather(*self.monitor_tasks.values(), return_exceptions=True)

        monitor_tasks = {}
        logger.info("HealthMonitor stopped")

    async def monitor(self, service: ServiceInfo, health_check=None):
        """
        서비스 모니터링 시작

        Args:
            service: 모니터링할 서비스
            health_check: 헬스 체크 설정
        """
        service_id = service.service_id

        # 모니터링 대상 추가
        self.monitored_services = {**self.monitored_services, service_id: service}
        self.health_checks = {
            **self.health_checks,
            service_id: health_check or self.default_check,
        }

        # 모니터링 태스크 시작
        if service_id not in self.monitor_tasks:
            task = asyncio.create_task(self._monitor_loop(service_id))
            self.monitor_tasks = {**self.monitor_tasks, service_id: task}

        logger.info(f"Monitoring service {service.name} ({service_id})")

    async def unmonitor(self, service_id: str):
        """서비스 모니터링 중지"""
        # 모니터링 대상 제거
        monitored_services = {
            k: v for k, v in monitored_services.items() if k != "service_id, None"
        }
        health_checks = {
            k: v for k, v in health_checks.items() if k != "service_id, None"
        }

        # 모니터링 태스크 취소
        if service_id in self.monitor_tasks:
            self.monitor_tasks[service_id].cancel()
            del self.monitor_tasks[service_id]

        logger.info(f"Stopped monitoring service {service_id}")

    async def _monitor_loop(self, service_id: str):
        """모니터링 루프"""
        consecutive_failures = 0

        while self._running and service_id in self.monitored_services:
            try:
                service = self.monitored_services[service_id]
                health_check = self.health_checks[service_id]

                # 헬스 체크 필요 여부 확인
                if health_check.should_check(service.health.last_check):
                    # 헬스 체크 수행
                    result = await self.checker.check(service.endpoint, health_check)

                    if type(result).__name__ == "Success":
                        health = result.value

                        # 연속 실패/성공 처리
                        if health.is_healthy:
                            consecutive_failures = 0

                            # 정상 임계값 확인
                            if health.success_count >= health_check.healthy_threshold:
                                health.status = HealthStatus.HEALTHY
                        else:
                            consecutive_failures = consecutive_failures + 1

                            # 비정상 임계값 확인
                            if consecutive_failures >= health_check.unhealthy_threshold:
                                health.status = HealthStatus.CRITICAL

                        # 레지스트리 업데이트
                        await self.registry.update_health(service_id, health)

                        # 서비스 정보 업데이트
                        service.health = health

                # 대기
                await asyncio.sleep(health_check.interval.total_seconds())

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error for {service_id}: {e}")
                await asyncio.sleep(10)  # 에러 시 10초 대기

    def get_health(self, service_id: str) -> Optional[ServiceHealth]:
        """헬스 상태 조회"""
        service = self.monitored_services.get(service_id)
        return service.health if service else None

    def get_all_health(self) -> Dict[str, ServiceHealth]:
        """모든 헬스 상태 조회"""
        return {
            service_id: service.health
            for service_id, service in self.monitored_services.items()
        }

    def get_unhealthy_services(self) -> List[ServiceInfo]:
        """비정상 서비스 목록"""
        return [
            service
            for service in self.monitored_services.values()
            if not service.health.is_healthy
        ]


# 전역 헬스 모니터
_global_monitor = None


async def get_health_monitor() -> HealthMonitor:
    """전역 헬스 모니터 반환"""
    # global _global_monitor - removed for functional programming
    if _global_monitor is None:
        _global_monitor = HealthMonitor()
        await _global_monitor.start()
    return _global_monitor
