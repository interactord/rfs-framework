"""
RFS Framework - 배포 및 운영 예제

이 예제는 RFS Framework의 프로덕션 배포, 롤백 관리, 서킷 브레이커,
로드 밸런싱 기능을 통합적으로 보여줍니다:
- Blue-Green, Canary, Rolling 배포 전략
- 체크포인트 기반 롤백 관리
- 서킷 브레이커를 통한 장애 격리
- 다양한 로드 밸런싱 알고리즘
- 서비스 디스커버리 및 헬스체크
- 운영 메트릭 및 모니터링
"""

import asyncio
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

# RFS 프레임워크 운영 컴포넌트
from rfs.core.result import Result, Success, Failure
from rfs.production.strategies import (
    DeploymentStrategy, DeploymentStrategyFactory, DeploymentConfig, DeploymentType
)
from rfs.production.rollback import RollbackManager, DeploymentCheckpoint
from rfs.service_discovery.circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, CircuitState
)
from rfs.service_discovery.load_balancer import (
    LoadBalancer, LoadBalancingAlgorithm, ServiceInstance
)
from rfs.core.logging_decorators import AuditLogged, LoggedOperation


# ================================================
# 서비스 및 인프라 모델
# ================================================

class ServiceStatus(str, Enum):
    """서비스 상태"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class ServiceMetrics:
    """서비스 메트릭"""
    service_name: str
    cpu_usage: float
    memory_usage: float
    request_count: int
    error_count: int
    response_time_avg: float
    timestamp: datetime


@dataclass
class DeploymentResult:
    """배포 결과"""
    deployment_id: str
    service_name: str
    version: str
    strategy: str
    status: str
    start_time: datetime
    end_time=None
    success_rate: float = 0.0
    error_message=None


# ================================================
# 마이크로서비스 시뮬레이터
# ================================================

class MicroserviceSimulator:
    """마이크로서비스 시뮬레이터"""
    
    def __init__(self, name: str, version: str, port: int):
        self.name = name
        self.version = version
        self.port = port
        self.status = ServiceStatus.HEALTHY
        self.is_running = False
        self.metrics = ServiceMetrics(
            service_name=name,
            cpu_usage=random.uniform(10, 50),
            memory_usage=random.uniform(30, 70),
            request_count=0,
            error_count=0,
            response_time_avg=random.uniform(50, 200),
            timestamp=datetime.now()
        )
    
    async def start(self) -> Result[bool, str]:
        """서비스 시작"""
        try:
            print(f"🚀 서비스 시작: {self.name} v{self.version} (포트: {self.port})")
            await asyncio.sleep(random.uniform(1, 3))  # 시작 시간 시뮬레이션
            
            self.is_running = True
            self.status = ServiceStatus.HEALTHY
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"서비스 시작 실패: {str(e)}")
    
    async def stop(self) -> Result[bool, str]:
        """서비스 정지"""
        try:
            print(f"🛑 서비스 정지: {self.name} v{self.version}")
            self.is_running = False
            self.status = ServiceStatus.UNHEALTHY
            
            return Success(True)
            
        except Exception as e:
            return Failure(f"서비스 정지 실패: {str(e)}")
    
    async def health_check(self) -> Result[dict, str]:
        """헬스체크"""
        if not self.is_running:
            return Failure("서비스가 실행되지 않음")
        
        # 5% 확률로 헬스체크 실패
        if random.random() < 0.05:
            self.status = ServiceStatus.DEGRADED
            return Failure("서비스 성능 저하")
        
        # 메트릭 업데이트
        self.metrics.cpu_usage = random.uniform(10, 80)
        self.metrics.memory_usage = random.uniform(30, 90)
        self.metrics.response_time_avg = random.uniform(50, 300)
        self.metrics.timestamp = datetime.now()
        
        return Success({
            "status": self.status.value,
            "version": self.version,
            "metrics": {
                "cpu_usage": self.metrics.cpu_usage,
                "memory_usage": self.metrics.memory_usage,
                "response_time": self.metrics.response_time_avg
            }
        })
    
    async def handle_request(self) -> Result[dict, str]:
        """요청 처리"""
        if not self.is_running:
            return Failure("서비스가 실행되지 않음")
        
        self.metrics.request_count += 1
        
        # 응답 시간 시뮬레이션
        response_time = random.uniform(50, 500)
        await asyncio.sleep(response_time / 1000)  # ms -> s
        
        # 5% 확률로 에러 발생
        if random.random() < 0.05:
            self.metrics.error_count += 1
            return Failure("내부 서버 오류")
        
        return Success({
            "service": self.name,
            "version": self.version,
            "response_time": response_time,
            "timestamp": datetime.now().isoformat()
        })


# ================================================
# 고급 배포 관리자
# ================================================

class AdvancedDeploymentManager:
    """고급 배포 관리자"""
    
    def __init__(self):
        self.rollback_manager = RollbackManager()
        self.services = {}
        self.deployment_history = []
        self.active_deployments = {}
    
    async def deploy_service(
        self,
        service_name: str,
        new_version: str,
        strategy: DeploymentType,
        instances=3
    ) -> Result[DeploymentResult, str]:
        """서비스 배포"""
        deployment_id = f"deploy_{int(time.time())}"
        
        print(f"📦 배포 시작: {service_name} v{new_version} ({strategy.value})")
        
        try:
            # 1. 체크포인트 생성
            checkpoint_result = await self._create_checkpoint(
                deployment_id,
                service_name,
                new_version
            )
            
            if checkpoint_result.is_failure():
                return Failure(f"체크포인트 생성 실패: {checkpoint_result.error}")
            
            # 2. 배포 전략 설정
            config = DeploymentConfig(
                deployment_type=strategy,
                health_check_interval=10,
                auto_rollback=True,
                rollback_on_error_rate=0.1,  # 10% 에러율 시 롤백
                validation_duration=60
            )
            
            deployment_strategy = DeploymentStrategyFactory.create(strategy, config)
            
            # 3. 배포 실행
            start_time = datetime.now()
            
            deployment_result = DeploymentResult(
                deployment_id=deployment_id,
                service_name=service_name,
                version=new_version,
                strategy=strategy.value,
                status="in_progress",
                start_time=start_time
            )
            
            self.active_deployments[deployment_id] = deployment_result
            
            # 실제 배포 실행 (전략에 따라 다름)
            deploy_result = await self._execute_deployment(
                deployment_strategy,
                service_name,
                new_version,
                instances
            )
            
            # 4. 결과 처리
            end_time = datetime.now()
            deployment_result.end_time = end_time
            
            if deploy_result.is_success():
                deployment_result.status = "completed"
                deployment_result.success_rate = deploy_result.value.get("success_rate", 1.0)
                print(f"✅ 배포 성공: {service_name} v{new_version}")
            else:
                deployment_result.status = "failed"
                deployment_result.error_message = deploy_result.error
                
                # 자동 롤백
                print(f"🔄 자동 롤백 시작...")
                rollback_result = await self.rollback_manager.rollback_to_checkpoint(
                    checkpoint_result.value,
                    reason="deployment_failure"
                )
                
                if rollback_result.is_success():
                    print("✅ 롤백 완료")
                    deployment_result.status = "rolled_back"
                else:
                    print(f"❌ 롤백 실패: {rollback_result.error}")
            
            # 배포 기록 저장
            self.deployment_history.append(deployment_result)
            del self.active_deployments[deployment_id]
            
            return Success(deployment_result)
            
        except Exception as e:
            return Failure(f"배포 실행 실패: {str(e)}")
    
    async def _create_checkpoint(
        self,
        deployment_id: str,
        service_name: str,
        version: str
    ) -> Result[str, str]:
        """체크포인트 생성"""
        metadata = {
            "deployment_id": deployment_id,
            "service_name": service_name,
            "target_version": version,
            "timestamp": datetime.now().isoformat(),
            "current_services": {
                name: service.version for name, service in self.services.items()
                if isinstance(service, MicroserviceSimulator)
            }
        }
        
        return await self.rollback_manager.create_checkpoint(
            deployment_id,
            metadata
        )
    
    async def _execute_deployment(
        self,
        strategy,
        service_name: str,
        new_version: str,
        instances: int
    ) -> Result[dict, str]:
        """배포 전략에 따른 실제 배포"""
        
        if isinstance(strategy.config.deployment_type, DeploymentType):
            deployment_type = strategy.config.deployment_type
        else:
            deployment_type = strategy.config.deployment_type
        
        if deployment_type == DeploymentType.BLUE_GREEN:
            return await self._blue_green_deployment(service_name, new_version, instances)
        elif deployment_type == DeploymentType.CANARY:
            return await self._canary_deployment(service_name, new_version, instances)
        elif deployment_type == DeploymentType.ROLLING:
            return await self._rolling_deployment(service_name, new_version, instances)
        else:
            return Failure(f"지원하지 않는 배포 전략: {deployment_type}")
    
    async def _blue_green_deployment(
        self,
        service_name: str,
        new_version: str,
        instances: int
    ) -> Result[dict, str]:
        """Blue-Green 배포"""
        print(f"🔵 Blue-Green 배포 실행: {service_name}")
        
        # Green 환경 생성
        green_services = []
        for i in range(instances):
            service = MicroserviceSimulator(
                name=f"{service_name}-green-{i}",
                version=new_version,
                port=8000 + i
            )
            green_services.append(service)
        
        # Green 서비스 시작
        for service in green_services:
            start_result = await service.start()
            if start_result.is_failure():
                return Failure(f"Green 서비스 시작 실패: {start_result.error}")
        
        # 헬스체크
        await asyncio.sleep(5)  # 워밍업 대기
        
        healthy_count = 0
        for service in green_services:
            health_result = await service.health_check()
            if health_result.is_success():
                healthy_count += 1
        
        if healthy_count < instances * 0.8:  # 80% 이상 건강해야 함
            return Failure(f"Green 환경 헬스체크 실패: {healthy_count}/{instances}")
        
        # 트래픽 전환 (시뮬레이션)
        print("🔄 트래픽 전환 중...")
        await asyncio.sleep(2)
        
        # Blue 환경 정리 (기존 서비스)
        if service_name in self.services:
            old_service = self.services[service_name]
            if hasattr(old_service, 'stop'):
                await old_service.stop()
        
        # Green -> Blue로 변경
        for i, service in enumerate(green_services):
            service.name = f"{service_name}-{i}"
            self.services[f"{service_name}-{i}"] = service
        
        return Success({
            "deployed_instances": instances,
            "healthy_instances": healthy_count,
            "success_rate": healthy_count / instances
        })
    
    async def _canary_deployment(
        self,
        service_name: str,
        new_version: str,
        instances: int
    ) -> Result[dict, str]:
        """Canary 배포"""
        print(f"🐤 Canary 배포 실행: {service_name}")
        
        # 10% -> 50% -> 100% 단계적 배포
        percentages = [10, 50, 100]
        
        for percentage in percentages:
            canary_count = max(1, int(instances * percentage / 100))
            print(f"📈 {percentage}% 트래픽으로 확장 ({canary_count}개 인스턴스)")
            
            # Canary 인스턴스 배포
            canary_services = []
            for i in range(canary_count):
                service = MicroserviceSimulator(
                    name=f"{service_name}-canary-{i}",
                    version=new_version,
                    port=9000 + i
                )
                await service.start()
                canary_services.append(service)
            
            # 모니터링 기간
            await asyncio.sleep(10)
            
            # 메트릭 확인
            error_rate = await self._calculate_error_rate(canary_services)
            
            if error_rate > 0.1:  # 10% 이상 에러율
                print(f"❌ Canary 메트릭 실패 (에러율: {error_rate:.1%})")
                
                # Canary 인스턴스 정리
                for service in canary_services:
                    await service.stop()
                
                return Failure(f"Canary 배포 실패: 높은 에러율 ({error_rate:.1%})")
            
            print(f"✅ {percentage}% 단계 성공 (에러율: {error_rate:.1%})")
        
        # 최종 Canary -> Production 전환
        for i, service in enumerate(canary_services):
            service.name = f"{service_name}-{i}"
            self.services[f"{service_name}-{i}"] = service
        
        return Success({
            "deployed_instances": canary_count,
            "healthy_instances": canary_count,
            "success_rate": 1.0 - error_rate
        })
    
    async def _rolling_deployment(
        self,
        service_name: str,
        new_version: str,
        instances: int
    ) -> Result[dict, str]:
        """Rolling 배포"""
        print(f"🔄 Rolling 배포 실행: {service_name}")
        
        batch_size = 2  # 한 번에 2개씩 교체
        deployed_count = 0
        
        for batch_start in range(0, instances, batch_size):
            batch_end = min(batch_start + batch_size, instances)
            batch_services = []
            
            print(f"📦 배치 배포: 인스턴스 {batch_start}-{batch_end-1}")
            
            # 배치 내 서비스 교체
            for i in range(batch_start, batch_end):
                # 기존 서비스 정지
                old_service_name = f"{service_name}-{i}"
                if old_service_name in self.services:
                    await self.services[old_service_name].stop()
                
                # 새 서비스 시작
                new_service = MicroserviceSimulator(
                    name=f"{service_name}-{i}",
                    version=new_version,
                    port=8000 + i
                )
                
                start_result = await new_service.start()
                if start_result.is_failure():
                    return Failure(f"새 서비스 시작 실패: {start_result.error}")
                
                self.services[f"{service_name}-{i}"] = new_service
                batch_services.append(new_service)
                deployed_count += 1
            
            # 배치 헬스체크
            await asyncio.sleep(3)
            
            healthy_in_batch = 0
            for service in batch_services:
                health_result = await service.health_check()
                if health_result.is_success():
                    healthy_in_batch += 1
            
            if healthy_in_batch < len(batch_services):
                return Failure(f"배치 {batch_start}-{batch_end-1} 헬스체크 실패")
            
            print(f"✅ 배치 {batch_start}-{batch_end-1} 성공")
        
        return Success({
            "deployed_instances": deployed_count,
            "healthy_instances": deployed_count,
            "success_rate": 1.0
        })
    
    async def _calculate_error_rate(self, services: List[MicroserviceSimulator]) -> float:
        """에러율 계산"""
        total_requests = 0
        total_errors = 0
        
        # 각 서비스에서 몇 번의 요청 시뮬레이션
        for service in services:
            for _ in range(10):  # 서비스당 10개 요청
                result = await service.handle_request()
                total_requests += 1
                if result.is_failure():
                    total_errors += 1
        
        return total_errors / total_requests if total_requests > 0 else 0.0


# ================================================
# 고급 로드 밸런서 (서킷 브레이커 통합)
# ================================================

class EnhancedLoadBalancer:
    """서킷 브레이커가 통합된 로드 밸런서"""
    
    def __init__(self):
        self.load_balancer = LoadBalancer(
            algorithm=LoadBalancingAlgorithm.ROUND_ROBIN,
            health_check_enabled=True,
            health_check_interval=30
        )
        
        # 각 서비스별 서킷 브레이커
        self.circuit_breakers = {}
    
    def add_service_with_circuit_breaker(
        self,
        service_name: str,
        url: str,
        weight: float = 1.0
    ):
        """서킷 브레이커와 함께 서비스 추가"""
        
        # 로드 밸런서에 서비스 추가
        self.load_balancer.add_service(service_name, url, weight)
        
        # 서킷 브레이커 설정
        circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=5,  # 5회 실패 시 OPEN
                recovery_timeout=30,   # 30초 후 복구 시도
                expected_exception=Exception
            )
        )
        
        self.circuit_breakers[url] = circuit_breaker
        print(f"🔌 서비스 등록: {service_name} ({url}) with Circuit Breaker")
    
    async def route_request(
        self,
        service_name: str,
        request_data: dict
    ) -> Result[dict, str]:
        """서킷 브레이커를 통한 안전한 요청 라우팅"""
        
        # 로드 밸런서에서 인스턴스 선택
        instance_result = await self.load_balancer.select_instance(service_name)
        
        if instance_result.is_failure():
            return Failure(f"사용 가능한 인스턴스 없음: {instance_result.error}")
        
        selected_url = instance_result.value
        circuit_breaker = self.circuit_breakers.get(selected_url)
        
        if not circuit_breaker:
            return Failure(f"서킷 브레이커를 찾을 수 없음: {selected_url}")
        
        # 서킷 브레이커를 통한 요청 실행
        async def make_request():
            return await self._simulate_service_call(selected_url, request_data)
        
        result = await circuit_breaker.execute(make_request)
        
        # 서킷 브레이커 상태 로깅
        if circuit_breaker.state != CircuitState.CLOSED:
            print(f"⚠️ 서킷 브레이커 상태 변경: {selected_url} -> {circuit_breaker.state.value}")
        
        return result
    
    async def _simulate_service_call(
        self,
        service_url: str,
        request_data: dict
    ) -> Result[dict, str]:
        """서비스 호출 시뮬레이션"""
        
        # 응답 시간 시뮬레이션
        response_time = random.uniform(100, 1000)
        await asyncio.sleep(response_time / 1000)
        
        # 10% 확률로 실패
        if random.random() < 0.1:
            return Failure("Service temporarily unavailable")
        
        return Success({
            "service_url": service_url,
            "response_time": response_time,
            "data": {"processed": request_data},
            "timestamp": datetime.now().isoformat()
        })
    
    async def get_service_health(self, service_name: str) -> dict:
        """서비스 헬스 상태 조회"""
        instances = self.load_balancer.get_healthy_instances(service_name)
        
        health_status = {}
        for instance in instances:
            circuit_breaker = self.circuit_breakers.get(instance)
            if circuit_breaker:
                health_status[instance] = {
                    "circuit_state": circuit_breaker.state.value,
                    "failure_count": circuit_breaker.failure_count,
                    "last_failure_time": circuit_breaker.last_failure_time.isoformat() if circuit_breaker.last_failure_time else None
                }
        
        return health_status


# ================================================
# 운영 대시보드
# ================================================

class OperationsDashboard:
    """운영 대시보드"""
    
    def __init__(self, deployment_manager: AdvancedDeploymentManager, load_balancer: EnhancedLoadBalancer):
        self.deployment_manager = deployment_manager
        self.load_balancer = load_balancer
    
    async def display_system_status(self):
        """시스템 상태 표시"""
        print("\n" + "="*60)
        print("📊 RFS 운영 대시보드")
        print("="*60)
        
        # 1. 서비스 상태
        print("\n🔧 서비스 상태:")
        for service_name, service in self.deployment_manager.services.items():
            if isinstance(service, MicroserviceSimulator):
                health = await service.health_check()
                status_icon = "✅" if health.is_success() else "❌"
                
                print(f"{status_icon} {service_name}: v{service.version} ({service.status.value})")
                if health.is_success():
                    metrics = health.value.get("metrics", {})
                    print(f"    CPU: {metrics.get('cpu_usage', 0):.1f}% | "
                          f"메모리: {metrics.get('memory_usage', 0):.1f}% | "
                          f"응답시간: {metrics.get('response_time', 0):.1f}ms")
        
        # 2. 배포 이력
        print("\n📦 최근 배포 이력:")
        for deployment in self.deployment_manager.deployment_history[-5:]:
            status_icon = {
                "completed": "✅",
                "failed": "❌",
                "rolled_back": "🔄",
                "in_progress": "⏳"
            }.get(deployment.status, "❓")
            
            print(f"{status_icon} {deployment.service_name} v{deployment.version} "
                  f"({deployment.strategy}) - {deployment.status}")
            
            if deployment.success_rate:
                print(f"    성공률: {deployment.success_rate:.1%}")
        
        # 3. 서킷 브레이커 상태
        print("\n⚡ 서킷 브레이커 상태:")
        for service_name in ["user-service", "order-service", "payment-service"]:
            health_status = await self.load_balancer.get_service_health(service_name)
            
            for instance, status in health_status.items():
                circuit_state = status["circuit_state"]
                state_icon = {
                    "CLOSED": "🟢",
                    "OPEN": "🔴", 
                    "HALF_OPEN": "🟡"
                }.get(circuit_state, "❓")
                
                print(f"{state_icon} {instance}: {circuit_state} "
                      f"(실패: {status['failure_count']}회)")
        
        print("="*60)
    
    async def run_load_test(self, service_name: str, request_count=50):
        """로드 테스트 실행"""
        print(f"\n🚀 로드 테스트 시작: {service_name} ({request_count}회 요청)")
        
        start_time = time.time()
        successful_requests = 0
        failed_requests = 0
        total_response_time = 0
        
        tasks = []
        for i in range(request_count):
            task = asyncio.create_task(
                self.load_balancer.route_request(service_name, {"request_id": i})
            )
            tasks.append(task)
        
        # 모든 요청 완료 대기
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 분석
        for result in results:
            if isinstance(result, Exception):
                failed_requests += 1
            elif isinstance(result, Result):
                if result.is_success():
                    successful_requests += 1
                    response_time = result.value.get("response_time", 0)
                    total_response_time += response_time
                else:
                    failed_requests += 1
        
        end_time = time.time()
        
        # 결과 출력
        duration = end_time - start_time
        avg_response_time = total_response_time / successful_requests if successful_requests > 0 else 0
        
        print(f"\n📈 로드 테스트 결과:")
        print(f"   총 요청: {request_count}")
        print(f"   성공: {successful_requests} ({successful_requests/request_count:.1%})")
        print(f"   실패: {failed_requests} ({failed_requests/request_count:.1%})")
        print(f"   평균 응답시간: {avg_response_time:.1f}ms")
        print(f"   총 소요시간: {duration:.2f}초")
        print(f"   TPS: {request_count/duration:.1f}")


# ================================================
# 메인 운영 애플리케이션
# ================================================

class ProductionOpsApplication:
    """프로덕션 운영 애플리케이션"""
    
    def __init__(self):
        self.deployment_manager = AdvancedDeploymentManager()
        self.load_balancer = EnhancedLoadBalancer()
        self.dashboard = OperationsDashboard(
            self.deployment_manager,
            self.load_balancer
        )
    
    async def setup_initial_infrastructure(self):
        """초기 인프라 설정"""
        print("🏗️ 초기 인프라 설정 중...")
        
        # 1. 기존 서비스 배포 (v1.0.0)
        services = [
            ("user-service", "1.0.0", 3),
            ("order-service", "1.0.0", 2),
            ("payment-service", "1.0.0", 2)
        ]
        
        for service_name, version, instances in services:
            for i in range(instances):
                service = MicroserviceSimulator(
                    name=f"{service_name}-{i}",
                    version=version,
                    port=8000 + len(self.deployment_manager.services)
                )
                
                await service.start()
                self.deployment_manager.services[f"{service_name}-{i}"] = service
            
            print(f"✅ {service_name} v{version} 배포 완료 ({instances}개 인스턴스)")
        
        # 2. 로드 밸런서 설정
        for service_name, _, instances in services:
            for i in range(instances):
                self.load_balancer.add_service_with_circuit_breaker(
                    service_name,
                    f"http://{service_name}-{i}:800{i}",
                    weight=1.0
                )
        
        print("✅ 초기 인프라 설정 완료")
    
    async def demonstrate_deployment_strategies(self):
        """배포 전략 데모"""
        print("\n🚀 배포 전략 데모")
        print("=" * 40)
        
        # 1. Blue-Green 배포
        print("\n1. Blue-Green 배포 데모")
        
        blue_green_result = await self.deployment_manager.deploy_service(
            service_name="user-service",
            new_version="2.0.0",
            strategy=DeploymentType.BLUE_GREEN,
            instances=3
        )
        
        if blue_green_result.is_success():
            deployment = blue_green_result.value
            print(f"✅ Blue-Green 배포 성공: {deployment.service_name} v{deployment.version}")
            print(f"   성공률: {deployment.success_rate:.1%}")
        else:
            print(f"❌ Blue-Green 배포 실패: {blue_green_result.error}")
        
        await asyncio.sleep(3)  # 잠시 대기
        
        # 2. Canary 배포
        print("\n2. Canary 배포 데모")
        
        canary_result = await self.deployment_manager.deploy_service(
            service_name="order-service",
            new_version="2.1.0",
            strategy=DeploymentType.CANARY,
            instances=2
        )
        
        if canary_result.is_success():
            deployment = canary_result.value
            print(f"✅ Canary 배포 성공: {deployment.service_name} v{deployment.version}")
        else:
            print(f"❌ Canary 배포 실패: {canary_result.error}")
        
        await asyncio.sleep(3)
        
        # 3. Rolling 배포
        print("\n3. Rolling 배포 데모")
        
        rolling_result = await self.deployment_manager.deploy_service(
            service_name="payment-service",
            new_version="1.5.0",
            strategy=DeploymentType.ROLLING,
            instances=2
        )
        
        if rolling_result.is_success():
            deployment = rolling_result.value
            print(f"✅ Rolling 배포 성공: {deployment.service_name} v{deployment.version}")
        else:
            print(f"❌ Rolling 배포 실패: {rolling_result.error}")
    
    async def demonstrate_circuit_breaker(self):
        """서킷 브레이커 데모"""
        print("\n⚡ 서킷 브레이커 데모")
        print("=" * 30)
        
        # 일부 서비스를 의도적으로 불안정하게 만들기
        payment_service = self.deployment_manager.services.get("payment-service-0")
        if payment_service:
            print("💥 payment-service-0을 불안정하게 설정")
            payment_service.status = ServiceStatus.DEGRADED
        
        # 연속적인 요청으로 서킷 브레이커 테스트
        print("🔄 연속 요청 테스트 (서킷 브레이커 트리거 예상)")
        
        for attempt in range(10):
            result = await self.load_balancer.route_request(
                "payment-service",
                {"test_request": attempt}
            )
            
            if result.is_success():
                print(f"✅ 요청 {attempt + 1}: 성공")
            else:
                print(f"❌ 요청 {attempt + 1}: {result.error}")
            
            await asyncio.sleep(0.5)
        
        # 서킷 브레이커 상태 확인
        print("\n🔍 서킷 브레이커 상태 확인:")
        health_status = await self.load_balancer.get_service_health("payment-service")
        for instance, status in health_status.items():
            print(f"   {instance}: {status['circuit_state']} (실패 {status['failure_count']}회)")
    
    async def run_comprehensive_demo(self):
        """종합 데모 실행"""
        print("🎯 RFS Framework 배포 & 운영 종합 데모 시작")
        
        # 1. 초기 인프라 설정
        await self.setup_initial_infrastructure()
        
        # 2. 초기 상태 표시
        await self.dashboard.display_system_status()
        
        # 3. 배포 전략 데모
        await self.demonstrate_deployment_strategies()
        
        # 4. 서킷 브레이커 데모
        await self.demonstrate_circuit_breaker()
        
        # 5. 로드 테스트
        await self.dashboard.run_load_test("user-service", 30)
        
        # 6. 최종 상태 표시
        await self.dashboard.display_system_status()
        
        print("\n✅ 종합 데모 완료!")


async def main():
    """메인 실행"""
    app = ProductionOpsApplication()
    await app.run_comprehensive_demo()


if __name__ == "__main__":
    print("🏭 RFS Framework - 배포 및 운영 통합 예제")
    print("=" * 60)
    print("이 예제는 다음 운영 기능들을 보여줍니다:")
    print("• Blue-Green, Canary, Rolling 배포 전략")
    print("• 체크포인트 기반 자동 롤백")
    print("• 서킷 브레이커를 통한 장애 격리")
    print("• 로드 밸런싱 및 트래픽 분산")
    print("• 서비스 헬스체크 및 모니터링")
    print("• 실시간 운영 대시보드")
    print("• 로드 테스트 및 성능 측정")
    print("=" * 60)
    
    asyncio.run(main())