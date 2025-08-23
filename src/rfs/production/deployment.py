"""
Production Deployment Tools

프로덕션 배포 자동화 및 관리 도구
"""

from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from datetime import datetime
import asyncio
import logging
from dataclasses import dataclass, field

from ..core.result import Result, Success, Failure
from ..core.singleton import SingletonMeta

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
    target_environment: str = "production"
    health_check_url: str = "/health"
    health_check_timeout: int = 30
    rollback_on_failure: bool = True
    canary_percentage: int = 10
    validation_duration: int = 300  # seconds
    max_rollback_attempts: int = 3
    deployment_timeout: int = 1800  # seconds
    pre_deployment_hooks: List[Callable] = field(default_factory=list)
    post_deployment_hooks: List[Callable] = field(default_factory=list)
    rollback_hooks: List[Callable] = field(default_factory=list)


@dataclass
class DeploymentResult:
    """배포 결과"""
    deployment_id: str
    status: DeploymentStatus
    strategy: DeploymentStrategy
    start_time: datetime
    end_time: Optional[datetime] = None
    version: Optional[str] = None
    environment: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    rollback_performed: bool = False


class ProductionDeployer:
    """
    프로덕션 배포 관리자
    
    다양한 배포 전략을 지원하며 자동 롤백 기능 제공
    """
    
    def __init__(self, config: DeploymentConfig = None):
        self.config = config or DeploymentConfig()
        self._deployments: Dict[str, DeploymentResult] = {}
        self._current_deployment: Optional[str] = None
        self._rollback_manager = RollbackManager()
    
    async def deploy(
        self,
        version: str,
        environment: str = None,
        strategy: DeploymentStrategy = None
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
            environment=environment
        )
        
        self._deployments[deployment_id] = result
        self._current_deployment = deployment_id
        
        try:
            # Pre-deployment hooks
            await self._run_hooks(self.config.pre_deployment_hooks, result)
            
            # Execute deployment based on strategy
            result.status = DeploymentStatus.IN_PROGRESS
            
            if strategy == DeploymentStrategy.BLUE_GREEN:
                await self._deploy_blue_green(version, environment, result)
            elif strategy == DeploymentStrategy.CANARY:
                await self._deploy_canary(version, environment, result)
            elif strategy == DeploymentStrategy.ROLLING:
                await self._deploy_rolling(version, environment, result)
            elif strategy == DeploymentStrategy.RECREATE:
                await self._deploy_recreate(version, environment, result)
            elif strategy == DeploymentStrategy.A_B_TESTING:
                await self._deploy_ab_testing(version, environment, result)
            
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
            result.errors.append(str(e))
            result.end_time = datetime.now()
            
            if self.config.rollback_on_failure:
                await self._rollback_deployment(result)
                result.status = DeploymentStatus.ROLLED_BACK
            
            logger.error(f"Deployment failed: {e}")
            return Failure(str(e))
    
    async def _deploy_blue_green(
        self,
        version: str,
        environment: str,
        result: DeploymentResult
    ):
        """Blue-Green 배포 전략"""
        logger.info(f"Starting Blue-Green deployment: {version}")
        
        # 1. Deploy to green environment
        result.metrics["green_deployment_start"] = datetime.now()
        await asyncio.sleep(2)  # Simulate deployment
        
        # 2. Run health checks on green
        health_check_passed = await self._health_check(f"{environment}-green")
        if not health_check_passed:
            raise Exception("Green environment health check failed")
        
        # 3. Switch traffic to green
        result.metrics["traffic_switch_time"] = datetime.now()
        await asyncio.sleep(1)  # Simulate traffic switch
        
        # 4. Keep blue as backup for rollback
        result.metrics["blue_backup_retained"] = True
        
    async def _deploy_canary(
        self,
        version: str,
        environment: str,
        result: DeploymentResult
    ):
        """Canary 배포 전략"""
        logger.info(f"Starting Canary deployment: {version}")
        
        # 1. Deploy to canary instances
        canary_percentage = self.config.canary_percentage
        result.metrics["canary_percentage"] = canary_percentage
        await asyncio.sleep(2)  # Simulate canary deployment
        
        # 2. Route percentage of traffic to canary
        result.metrics["canary_traffic_start"] = datetime.now()
        
        # 3. Monitor canary metrics
        await asyncio.sleep(self.config.validation_duration)
        
        # 4. Gradually increase traffic if successful
        for percentage in [25, 50, 75, 100]:
            await asyncio.sleep(1)
            result.metrics[f"traffic_{percentage}%"] = datetime.now()
    
    async def _deploy_rolling(
        self,
        version: str,
        environment: str,
        result: DeploymentResult
    ):
        """Rolling 배포 전략"""
        logger.info(f"Starting Rolling deployment: {version}")
        
        # Simulate rolling update across instances
        instance_count = 5
        for i in range(instance_count):
            result.metrics[f"instance_{i}_updated"] = datetime.now()
            await asyncio.sleep(1)
            
            # Health check after each instance
            if not await self._health_check(f"{environment}-{i}"):
                raise Exception(f"Instance {i} health check failed")
    
    async def _deploy_recreate(
        self,
        version: str,
        environment: str,
        result: DeploymentResult
    ):
        """Recreate 배포 전략"""
        logger.info(f"Starting Recreate deployment: {version}")
        
        # 1. Stop all existing instances
        result.metrics["shutdown_start"] = datetime.now()
        await asyncio.sleep(2)
        
        # 2. Deploy new version
        result.metrics["deployment_start"] = datetime.now()
        await asyncio.sleep(3)
        
        # 3. Start new instances
        result.metrics["startup_complete"] = datetime.now()
    
    async def _deploy_ab_testing(
        self,
        version: str,
        environment: str,
        result: DeploymentResult
    ):
        """A/B Testing 배포 전략"""
        logger.info(f"Starting A/B Testing deployment: {version}")
        
        # Deploy both versions
        result.metrics["version_a"] = "current"
        result.metrics["version_b"] = version
        result.metrics["traffic_split"] = "50/50"
        
        await asyncio.sleep(2)  # Simulate deployment
        
        # Configure traffic routing for A/B testing
        result.metrics["ab_test_configured"] = datetime.now()
    
    async def _validate_deployment(self, result: DeploymentResult) -> bool:
        """배포 검증"""
        logger.info(f"Validating deployment: {result.deployment_id}")
        
        # Health check
        if not await self._health_check(result.environment):
            result.errors.append("Health check failed")
            return False
        
        # Metrics validation
        await asyncio.sleep(2)  # Simulate metrics collection
        
        # Smoke tests
        result.metrics["validation_complete"] = datetime.now()
        
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
        
        # Perform rollback
        rollback_result = await self._rollback_manager.rollback(
            deployment_id=result.deployment_id,
            strategy=result.strategy
        )
        
        if rollback_result.is_success():
            result.rollback_performed = True
            result.metrics["rollback_time"] = datetime.now()
        else:
            result.errors.append("Rollback failed")
    
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
                result.errors.append(f"Hook error: {e}")
    
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
            self._deployments.values(),
            key=lambda x: x.start_time,
            reverse=True
        )


class RollbackManager:
    """
    롤백 관리자
    
    배포 실패 시 자동 롤백 및 복구 기능 제공
    """
    
    def __init__(self):
        self._rollback_history: List[Dict[str, Any]] = []
        self._snapshots: Dict[str, Any] = {}
    
    async def create_snapshot(self, deployment_id: str) -> Result[str, str]:
        """
        배포 전 스냅샷 생성
        
        Args:
            deployment_id: 배포 ID
            
        Returns:
            Result[스냅샷 ID, 에러 메시지]
        """
        snapshot_id = f"snapshot_{deployment_id}"
        
        try:
            # Create snapshot of current state
            snapshot = {
                "id": snapshot_id,
                "deployment_id": deployment_id,
                "timestamp": datetime.now(),
                "state": await self._capture_current_state()
            }
            
            self._snapshots[snapshot_id] = snapshot
            
            logger.info(f"Snapshot created: {snapshot_id}")
            return Success(snapshot_id)
            
        except Exception as e:
            logger.error(f"Snapshot creation failed: {e}")
            return Failure(str(e))
    
    async def rollback(
        self,
        deployment_id: str,
        strategy: DeploymentStrategy = None
    ) -> Result[Dict[str, Any], str]:
        """
        배포 롤백 실행
        
        Args:
            deployment_id: 배포 ID
            strategy: 롤백 전략
            
        Returns:
            Result[롤백 결과, 에러 메시지]
        """
        try:
            rollback_id = f"rollback_{int(datetime.now().timestamp())}"
            
            rollback_info = {
                "id": rollback_id,
                "deployment_id": deployment_id,
                "strategy": strategy,
                "start_time": datetime.now(),
                "status": "in_progress"
            }
            
            # Find snapshot
            snapshot_id = f"snapshot_{deployment_id}"
            if snapshot_id not in self._snapshots:
                # Try to rollback without snapshot
                logger.warning(f"No snapshot found for {deployment_id}, attempting rollback")
            
            # Execute rollback based on strategy
            if strategy == DeploymentStrategy.BLUE_GREEN:
                await self._rollback_blue_green(rollback_info)
            elif strategy == DeploymentStrategy.CANARY:
                await self._rollback_canary(rollback_info)
            else:
                await self._rollback_standard(rollback_info)
            
            rollback_info["status"] = "completed"
            rollback_info["end_time"] = datetime.now()
            
            self._rollback_history.append(rollback_info)
            
            logger.info(f"Rollback completed: {rollback_id}")
            return Success(rollback_info)
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return Failure(str(e))
    
    async def _rollback_blue_green(self, rollback_info: Dict[str, Any]):
        """Blue-Green 롤백"""
        # Switch traffic back to blue
        await asyncio.sleep(1)
        rollback_info["method"] = "traffic_switch_to_blue"
    
    async def _rollback_canary(self, rollback_info: Dict[str, Any]):
        """Canary 롤백"""
        # Stop canary instances and route all traffic to stable
        await asyncio.sleep(1)
        rollback_info["method"] = "canary_termination"
    
    async def _rollback_standard(self, rollback_info: Dict[str, Any]):
        """표준 롤백"""
        # Restore from snapshot or previous version
        await asyncio.sleep(2)
        rollback_info["method"] = "version_restore"
    
    async def _capture_current_state(self) -> Dict[str, Any]:
        """현재 상태 캡처"""
        return {
            "timestamp": datetime.now().isoformat(),
            "version": "current",
            "configuration": {},
            "metrics": {}
        }
    
    def get_rollback_history(self) -> List[Dict[str, Any]]:
        """롤백 이력 조회"""
        return self._rollback_history
    
    def can_rollback(self, deployment_id: str) -> bool:
        """롤백 가능 여부 확인"""
        snapshot_id = f"snapshot_{deployment_id}"
        return snapshot_id in self._snapshots


# Export functions for easy access
_production_deployer: Optional[ProductionDeployer] = None
_rollback_manager: Optional[RollbackManager] = None


def get_production_deployer(config: DeploymentConfig = None) -> ProductionDeployer:
    """
    전역 ProductionDeployer 인스턴스 반환
    
    Args:
        config: 배포 설정
        
    Returns:
        ProductionDeployer 인스턴스
    """
    global _production_deployer
    if _production_deployer is None:
        _production_deployer = ProductionDeployer(config)
    return _production_deployer


def get_rollback_manager() -> RollbackManager:
    """
    전역 RollbackManager 인스턴스 반환
    
    Returns:
        RollbackManager 인스턴스
    """
    global _rollback_manager
    if _rollback_manager is None:
        _rollback_manager = RollbackManager()
    return _rollback_manager


async def deploy_to_production(
    version: str,
    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING,
    environment: str = "production"
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
    deployment_id: str,
    strategy: DeploymentStrategy = None
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