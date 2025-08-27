"""
Production Deployment Tools

프로덕션 배포 자동화 및 관리 도구
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..core.result import Failure, Result, Success
from ..core.singleton import SingletonMeta
from .rollback import (
    DeploymentCheckpoint,
    RollbackManager,
    RollbackTrigger,
)

# Alias for internal use
RollbackManagerImpl = RollbackManager
from .strategies import DeploymentConfig as StrategyConfig
from .strategies import (
    DeploymentMetrics,
)
from .strategies import DeploymentStrategy as StrategyImpl
from .strategies import (
    DeploymentStrategyFactory,
    DeploymentType,
)

logger = logging.getLogger(__name__)


class DeploymentStrategy(Enum):
    """배포 전략"""

    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    ROLLING = "rolling"
    RECREATE = "recreate"
    A_B_TESTING = "a_b_testing"


class DeploymentStatus(Enum):
    """배포 상태"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeploymentConfig:
    """배포 설정"""

    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    target_environment = "production"
    health_check_url = "/health"
    health_check_timeout = 30
    rollback_on_failure = True
    canary_percentage = 10
    validation_duration = 300  # seconds
    max_rollback_attempts = 3
    deployment_timeout = 1800  # seconds
    pre_deployment_hooks: List[str] = field(default_factory=list)
    post_deployment_hooks: List[str] = field(default_factory=list)
    rollback_hooks: List[str] = field(default_factory=list)


@dataclass
class DeploymentResult:
    """배포 결과"""

    deployment_id: str
    status: DeploymentStatus
    strategy: DeploymentStrategy
    start_time: datetime
    end_time = None
    version = None
    environment = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    rollback_performed = False


class ProductionDeployer:
    """
    프로덕션 배포 관리자

    다양한 배포 전략을 지원하며 자동 롤백 기능 제공
    """

    def __init__(self, config=None):
        self.config = config or DeploymentConfig()
        self._deployments = {}
        self._current_deployment = None
        self._rollback_manager = RollbackManagerImpl()
        self._strategy_factory = DeploymentStrategyFactory()

    async def deploy(
        self, version: str, environment=None, strategy=None
    ) -> Result[DeploymentResult, str]:
        """
        프로덕션 배포 실행

        Args:
            version: 배포할 버전
            environment: 대상 환경
            strategy: 배포 전략

        Returns:
            Result[배포 결과, 에러 메시지]
        """
        deployment_id = f"deploy_{int(datetime.now().timestamp())}"
        environment = environment or self.config.target_environment
        strategy = strategy or self.config.strategy

        result = DeploymentResult(
            deployment_id=deployment_id,
            status=DeploymentStatus.PENDING,
            strategy=strategy,
            start_time=datetime.now(),
            version=version,
            environment=environment,
        )

        self._deployments = {**self._deployments, deployment_id: result}
        self._current_deployment = deployment_id

        try:
            # Create checkpoint before deployment
            checkpoint_result = await self._rollback_manager.create_checkpoint(
                service_name=f"service_{environment}",
                version=version,
                configuration={"environment": environment, "strategy": strategy.value},
                metadata={"deployment_id": deployment_id},
            )

            # Pre-deployment hooks
            await self._run_hooks(self.config.pre_deployment_hooks, result)

            # Execute deployment based on strategy
            result.status = DeploymentStatus.IN_PROGRESS

            # Map DeploymentStrategy enum to DeploymentType
            strategy_mapping = {
                DeploymentStrategy.BLUE_GREEN: DeploymentType.BLUE_GREEN,
                DeploymentStrategy.CANARY: DeploymentType.CANARY,
                DeploymentStrategy.ROLLING: DeploymentType.ROLLING,
                DeploymentStrategy.RECREATE: DeploymentType.INSTANT,
                DeploymentStrategy.A_B_TESTING: DeploymentType.AB_TESTING,
            }

            deployment_type = strategy_mapping.get(strategy, DeploymentType.ROLLING)

            # Create strategy configuration
            strategy_config = StrategyConfig(
                deployment_type=deployment_type,
                health_check_interval=self.config.health_check_timeout,
                max_deployment_time=self.config.deployment_timeout,
                canary_percentage=self.config.canary_percentage,
                auto_rollback=self.config.rollback_on_failure,
            )

            # Get strategy implementation
            strategy_impl = self._strategy_factory.create(
                deployment_type, strategy_config
            )

            # Execute deployment using strategy
            deployment_result = await strategy_impl.deploy(
                service_name=f"service_{environment}",
                new_version=version,
                instance_count=5,  # Can be configured
            )

            if type(deployment_result).__name__ == "Failure":
                raise Exception(deployment_result.error)

            # Update result with strategy metrics
            deployment_metrics = deployment_result.value
            result.metrics = {
                **metrics,
                **{
                    "success_rate": deployment_metrics.success_rate,
                    "error_rate": deployment_metrics.error_rate,
                    "deployment_duration": str(deployment_metrics.deployment_duration),
                    "rollback_triggered": deployment_metrics.rollback_triggered,
                },
            }

            if deployment_metrics.rollback_triggered:
                result.status = DeploymentStatus.ROLLED_BACK
                result.rollback_performed = True
                return Failure(
                    f"Deployment rolled back: {deployment_metrics.rollback_reason}"
                )

            # Validation
            result.status = DeploymentStatus.VALIDATING
            validation_success = await self._validate_deployment(result)

            if not validation_success:
                if self.config.rollback_on_failure:
                    await self._rollback_deployment(result)
                    result.status = DeploymentStatus.ROLLED_BACK
                else:
                    result.status = DeploymentStatus.FAILED
                return Failure(f"Deployment validation failed: {deployment_id}")

            # Post-deployment hooks
            await self._run_hooks(self.config.post_deployment_hooks, result)

            result.status = DeploymentStatus.COMPLETED
            result.end_time = datetime.now()

            logger.info(f"Deployment completed successfully: {deployment_id}")
            return Success(result)

        except Exception as e:
            result.status = DeploymentStatus.FAILED
            result.errors = result.errors + [str(e)]
            result.end_time = datetime.now()

            if self.config.rollback_on_failure:
                await self._rollback_deployment(result)
                result.status = DeploymentStatus.ROLLED_BACK

            logger.error(f"Deployment failed: {e}")
            return Failure(str(e))

    async def _validate_deployment(self, result: DeploymentResult) -> bool:
        """배포 검증"""
        logger.info(f"Validating deployment: {result.deployment_id}")

        # Health check
        if not await self._health_check(result.environment):
            result.errors = result.errors + ["Health check failed"]
            return False

        # Metrics validation
        await asyncio.sleep(2)  # Simulate metrics collection

        # Smoke tests
        result.metrics = {**result.metrics, "validation_complete": datetime.now()}

        return True

    async def _health_check(self, environment: str) -> bool:
        """헬스 체크"""
        # Simulate health check
        await asyncio.sleep(0.5)
        return True  # Simplified for demo

    async def _rollback_deployment(self, result: DeploymentResult):
        """배포 롤백"""
        logger.warning(f"Rolling back deployment: {result.deployment_id}")

        # Execute rollback hooks
        await self._run_hooks(self.config.rollback_hooks, result)

        # Perform rollback using new RollbackManager
        service_name = f"service_{result.environment}"
        rollback_result = await self._rollback_manager.rollback(
            service_name=service_name,
            trigger=RollbackTrigger.AUTO_ERROR_RATE,
            reason=f"Deployment {result.deployment_id} failed validation",
        )

        if type(rollback_result).__name__ == "Success":
            result.rollback_performed = True
            result.metrics = {**result.metrics, "rollback_time": datetime.now()}
            result.metrics = {
                **result.metrics,
                "rollback_id": rollback_result.value.rollback_id,
            }
        else:
            result.errors = result.errors + [
                f"Rollback failed: {rollback_result.error}"
            ]

    async def _run_hooks(self, hooks: List[Callable], result: DeploymentResult):
        """훅 실행"""
        for hook in hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(result)
                else:
                    hook(result)
            except Exception as e:
                logger.error(f"Hook execution failed: {e}")
                result.errors = result.errors + [f"Hook error: {e}"]

    def get_deployment_status(self, deployment_id: str) -> Optional[DeploymentResult]:
        """배포 상태 조회"""
        return self._deployments.get(deployment_id)

    def get_current_deployment(self) -> Optional[DeploymentResult]:
        """현재 배포 조회"""
        if self._current_deployment:
            return self._deployments.get(self._current_deployment)
        return None

    def get_deployment_history(self) -> List[DeploymentResult]:
        """배포 이력 조회"""
        return sorted(
            self._deployments.values(), key=lambda x: x.start_time, reverse=True
        )


# Export functions for easy access
_production_deployer = None
_rollback_manager = None


def get_production_deployer(config: DeploymentConfig = None) -> ProductionDeployer:
    """
    전역 ProductionDeployer 인스턴스 반환

    Args:
        config: 배포 설정

    Returns:
        ProductionDeployer 인스턴스
    """
    # global _production_deployer - removed for functional programming
    if _production_deployer is None:
        _production_deployer = ProductionDeployer(config)
    return _production_deployer


def get_rollback_manager() -> RollbackManagerImpl:
    """
    전역 RollbackManager 인스턴스 반환

    Returns:
        RollbackManager 인스턴스
    """
    # global _rollback_manager - removed for functional programming
    if _rollback_manager is None:
        _rollback_manager = RollbackManagerImpl()
    return _rollback_manager


async def deploy_to_production(
    version: str,
    strategy=DeploymentStrategy.ROLLING,
    environment="production",
) -> Result[DeploymentResult, str]:
    """
    프로덕션 배포 헬퍼 함수

    Args:
        version: 배포할 버전
        strategy: 배포 전략
        environment: 대상 환경

    Returns:
        Result[배포 결과, 에러 메시지]
    """
    deployer = get_production_deployer()
    return await deployer.deploy(version, environment, strategy)


async def rollback_deployment(
    deployment_id: str, strategy=None
) -> Result[Dict[str, Any], str]:
    """
    배포 롤백 헬퍼 함수

    Args:
        deployment_id: 배포 ID
        strategy: 롤백 전략

    Returns:
        Result[롤백 결과, 에러 메시지]
    """
    manager = get_rollback_manager()
    return await manager.rollback(deployment_id, strategy)


async def rollback_deployment(
    deployment_id: str, reason="Manual rollback"
) -> Result[bool, str]:
    """
    배포 롤백 실행

    Args:
        deployment_id: 배포 ID
        reason: 롤백 사유

    Returns:
        Result[성공 여부, 에러 메시지]
    """
    manager = get_rollback_manager()
    try:
        # Trigger rollback with reason
        result = await manager.trigger_rollback(RollbackTrigger.MANUAL, reason=reason)

        if result:
            logger.info(
                f"Deployment {deployment_id} rolled back successfully: {reason}"
            )
            return Success(True)
        else:
            return Failure(f"Failed to rollback deployment {deployment_id}")
    except Exception as e:
        logger.error(f"Rollback failed for {deployment_id}: {e}")
        return Failure(str(e))


__all__ = [
    "ProductionDeployer",
    "DeploymentStrategy",
    "DeploymentStatus",
    "DeploymentConfig",
    "DeploymentResult",
    "RollbackManager",
    "get_production_deployer",
    "get_rollback_manager",
    "deploy_to_production",
    "rollback_deployment",
]
