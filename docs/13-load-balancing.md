# 로드 밸런싱 (Load Balancing)

## 📌 개요

RFS Framework의 로드 밸런싱 시스템은 클라이언트 사이드 로드 밸런싱을 통해 트래픽을 효율적으로 분산하고 고가용성을 보장합니다. 다양한 알고리즘, 헬스체크, 서킷 브레이커 통합을 제공합니다.

## 🎯 핵심 개념

### 로드 밸런싱 전략
- **Round Robin**: 순차적으로 요청 분산
- **Random**: 임의로 서버 선택
- **Least Connections**: 가장 적은 연결 수를 가진 서버 선택
- **Weighted Round Robin**: 가중치 기반 순차 분산
- **Consistent Hash**: 일관된 해싱으로 세션 고정
- **Least Response Time**: 가장 빠른 응답 시간을 가진 서버 선택

### 헬스체크
- **Active Health Check**: 주기적으로 서버 상태 확인
- **Passive Health Check**: 실제 요청 결과로 상태 판단
- **Circuit Breaker Integration**: 장애 서버 자동 제외

### 서비스 인스턴스 상태
- **HEALTHY**: 정상 동작
- **UNHEALTHY**: 비정상 동작 (제외)
- **DEGRADED**: 성능 저하 (제한적 사용)
- **UNKNOWN**: 상태 불명

## 📚 API 레퍼런스

### LoadBalancerConfig 설정

```python
from rfs.service_discovery.load_balancer import (
    LoadBalancer,
    LoadBalancerConfig,
    LoadBalancingStrategy,
    ServiceInstance
)

config = LoadBalancerConfig(
    strategy=LoadBalancingStrategy.ROUND_ROBIN,
    health_check_enabled=True,
    health_check_interval=30.0,       # 30초마다 헬스체크
    health_check_timeout=5.0,         # 5초 타임아웃
    max_consecutive_failures=3,       # 3회 실패 시 제외
    retry_enabled=True,
    max_retries=2,
    circuit_breaker_enabled=True,
    sticky_sessions=False
)
```

### ServiceInstance 정의

```python
instance = ServiceInstance(
    id="service-1",
    host="192.168.1.100",
    port=8080,
    weight=1,                    # 가중치 (기본 1)
    metadata={"zone": "us-west"} # 메타데이터
)
```

## 💡 사용 예제

### 기본 로드 밸런서 사용

```python
from rfs.service_discovery.load_balancer import (
    LoadBalancer,
    LoadBalancerConfig,
    LoadBalancingStrategy,
    ServiceInstance,
    HealthStatus
)
import asyncio
import random

async def basic_load_balancer_example():
    """기본 로드 밸런서 사용 예제"""
    
    # 로드 밸런서 생성
    lb = LoadBalancer(
        service_name="user_service",
        config=LoadBalancerConfig(
            strategy=LoadBalancingStrategy.ROUND_ROBIN,
            health_check_enabled=True,
            health_check_interval=10.0
        )
    )
    
    # 서비스 인스턴스 추가
    instances = [
        ServiceInstance(id="user-1", host="10.0.1.10", port=8080, weight=1),
        ServiceInstance(id="user-2", host="10.0.1.11", port=8080, weight=2),  # 높은 가중치
        ServiceInstance(id="user-3", host="10.0.1.12", port=8080, weight=1),
    ]
    
    for instance in instances:
        lb.add_instance(instance)
    
    # 헬스체크 시작
    await lb.start_health_checks()
    
    # 실제 서비스 호출 함수
    async def call_user_service(instance: ServiceInstance, user_id: str) -> dict:
        """사용자 서비스 호출"""
        # 실제 HTTP 호출 대신 시뮬레이션
        await asyncio.sleep(0.1)
        
        # 10% 확률로 실패 시뮬레이션
        if random.random() < 0.1:
            raise Exception(f"서비스 {instance.id} 호출 실패")
        
        return {
            "user_id": user_id,
            "name": f"User {user_id}",
            "served_by": instance.id,
            "host": f"{instance.host}:{instance.port}"
        }
    
    # 로드 밸런싱된 요청 실행
    print("로드 밸런싱 테스트 시작...")
    
    for i in range(10):
        try:
            result = await lb.call(
                call_user_service,
                user_id=f"user{i+1}"
            )
            
            print(f"요청 {i+1}: {result['served_by']}에서 처리 - {result['name']}")
            
        except Exception as e:
            print(f"요청 {i+1}: 실패 - {e}")
        
        await asyncio.sleep(0.5)
    
    # 통계 출력
    stats = lb.get_statistics()
    print(f"\n=== 로드 밸런서 통계 ===")
    print(f"총 요청: {stats['total_requests']}")
    print(f"실패 요청: {stats['failed_requests']}")
    print(f"실패율: {stats['failure_rate']:.2%}")
    print(f"사용 가능한 인스턴스: {stats['available_instances']}/{stats['total_instances']}")
    
    # 인스턴스별 상세 통계
    print(f"\n=== 인스턴스별 통계 ===")
    for instance_id, instance_stats in stats['instances'].items():
        print(f"{instance_id}: {instance_stats['status']} - "
              f"요청 {instance_stats['total_requests']}개, "
              f"평균 응답시간 {instance_stats['average_response_time']:.3f}초")
    
    # 헬스체크 중지
    await lb.stop_health_checks()

# 실행
asyncio.run(basic_load_balancer_example())
```

### 다양한 로드 밸런싱 전략

```python
async def test_load_balancing_strategies():
    """다양한 로드 밸런싱 전략 테스트"""
    
    # 서비스 인스턴스 생성
    instances = [
        ServiceInstance(id="server-1", host="10.0.1.10", port=8080, weight=1),
        ServiceInstance(id="server-2", host="10.0.1.11", port=8080, weight=3),  # 높은 가중치
        ServiceInstance(id="server-3", host="10.0.1.12", port=8080, weight=2),
    ]
    
    # 테스트할 전략들
    strategies = [
        LoadBalancingStrategy.ROUND_ROBIN,
        LoadBalancingStrategy.RANDOM,
        LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN,
        LoadBalancingStrategy.LEAST_CONNECTIONS,
        LoadBalancingStrategy.LEAST_RESPONSE_TIME
    ]
    
    for strategy in strategies:
        print(f"\n=== {strategy.value.upper()} 전략 테스트 ===")
        
        # 로드 밸런서 생성
        lb = LoadBalancer(
            service_name="test_service",
            config=LoadBalancerConfig(
                strategy=strategy,
                health_check_enabled=False  # 테스트를 위해 비활성화
            )
        )
        
        # 인스턴스 추가
        for instance in instances:
            instance.active_connections = 0  # 초기화
            instance.total_requests = 0
            instance.total_response_time = 0.0
            lb.add_instance(instance)
        
        # 요청 분산 테스트
        distribution = {}
        
        for i in range(20):
            selected = lb.select_instance()
            if selected:
                # 연결 수와 응답 시간 시뮬레이션
                selected.active_connections += 1
                selected.total_requests += 1
                # 서버별로 다른 응답 시간 시뮬레이션
                response_time = 0.1 + (int(selected.id.split('-')[1]) * 0.05)
                selected.total_response_time += response_time
                selected.last_response_time = response_time
                
                # 분산 통계
                if selected.id not in distribution:
                    distribution[selected.id] = 0
                distribution[selected.id] += 1
                
                # 연결 종료 시뮬레이션
                selected.active_connections = max(0, selected.active_connections - 1)
        
        # 분산 결과 출력
        for server_id, count in distribution.items():
            percentage = (count / 20) * 100
            print(f"{server_id}: {count}회 ({percentage:.1f}%)")

# 실행
asyncio.run(test_load_balancing_strategies())
```

### 일관된 해싱 (Consistent Hashing)

```python
from rfs.service_discovery.load_balancer import ConsistentHashAlgorithm

async def consistent_hashing_example():
    """일관된 해싱을 사용한 세션 고정"""
    
    # 일관된 해싱 로드 밸런서
    lb = LoadBalancer(
        service_name="session_service",
        config=LoadBalancerConfig(
            strategy=LoadBalancingStrategy.CONSISTENT_HASH,
            sticky_sessions=True,
            session_cookie_name="SESSION_ID"
        )
    )
    
    # 서버 인스턴스 추가
    servers = [
        ServiceInstance(id="cache-1", host="10.0.1.20", port=6379),
        ServiceInstance(id="cache-2", host="10.0.1.21", port=6379),
        ServiceInstance(id="cache-3", host="10.0.1.22", port=6379),
    ]
    
    for server in servers:
        lb.add_instance(server)
    
    # 사용자별 세션 테스트
    users = ["user1", "user2", "user3", "user4", "user5"]
    user_to_server = {}
    
    print("=== 일관된 해싱 테스트 ===")
    
    # 초기 배치 확인
    for user in users:
        context = {"user_id": user, "session_id": f"session_{user}"}
        selected = lb.select_instance(context)
        
        if selected:
            user_to_server[user] = selected.id
            print(f"{user} -> {selected.id}")
    
    # 서버 하나 제거 후 재배치 확인
    print(f"\n서버 {servers[1].id} 제거 후:")
    lb.remove_instance(servers[1].id)
    
    moved_users = 0
    for user in users:
        context = {"user_id": user, "session_id": f"session_{user}"}
        selected = lb.select_instance(context)
        
        if selected:
            old_server = user_to_server[user]
            new_server = selected.id
            
            if old_server != new_server:
                print(f"{user}: {old_server} -> {new_server} (이동)")
                moved_users += 1
            else:
                print(f"{user}: {new_server} (유지)")
    
    print(f"\n이동된 사용자: {moved_users}/{len(users)} ({(moved_users/len(users)*100):.1f}%)")
    
    # 서버 추가 후 재배치 확인
    print(f"\n새 서버 cache-4 추가 후:")
    new_server = ServiceInstance(id="cache-4", host="10.0.1.23", port=6379)
    lb.add_instance(new_server)
    
    moved_users = 0
    for user in users:
        context = {"user_id": user, "session_id": f"session_{user}"}
        selected = lb.select_instance(context)
        
        if selected:
            # 현재 서버와 이전 서버 비교 (서버 제거 후 상태 기준)
            prev_selected = lb.select_instance(context)  # 이전 선택 결과 시뮬레이션
            
            print(f"{user} -> {selected.id}")

# 실행
asyncio.run(consistent_hashing_example())
```

### 마이크로서비스 아키텍처에서의 활용

```python
import httpx
from typing import Dict, List, Optional

class MicroserviceLoadBalancer:
    """마이크로서비스용 로드 밸런서"""
    
    def __init__(self):
        self.load_balancers: Dict[str, LoadBalancer] = {}
        self.service_configs = {
            "user-service": LoadBalancerConfig(
                strategy=LoadBalancingStrategy.LEAST_RESPONSE_TIME,
                health_check_enabled=True,
                health_check_interval=15.0,
                circuit_breaker_enabled=True
            ),
            "order-service": LoadBalancerConfig(
                strategy=LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN,
                health_check_enabled=True,
                health_check_interval=20.0,
                max_retries=3
            ),
            "payment-service": LoadBalancerConfig(
                strategy=LoadBalancingStrategy.ROUND_ROBIN,
                health_check_enabled=True,
                health_check_interval=10.0,  # 중요한 서비스라 자주 체크
                circuit_breaker_enabled=True,
                max_consecutive_failures=2  # 엄격한 기준
            )
        }
    
    def register_service(self, service_name: str, instances: List[ServiceInstance]):
        """서비스 등록"""
        config = self.service_configs.get(service_name, LoadBalancerConfig())
        
        lb = LoadBalancer(service_name, config)
        
        for instance in instances:
            lb.add_instance(instance)
        
        self.load_balancers[service_name] = lb
    
    async def start_all_health_checks(self):
        """모든 서비스의 헬스체크 시작"""
        for lb in self.load_balancers.values():
            await lb.start_health_checks()
    
    async def stop_all_health_checks(self):
        """모든 서비스의 헬스체크 중지"""
        for lb in self.load_balancers.values():
            await lb.stop_health_checks()
    
    async def call_service(
        self, 
        service_name: str, 
        endpoint: str, 
        method: str = "GET",
        **kwargs
    ) -> Result[dict, str]:
        """서비스 호출"""
        
        if service_name not in self.load_balancers:
            return Failure(f"서비스 '{service_name}'을 찾을 수 없습니다")
        
        lb = self.load_balancers[service_name]
        
        try:
            result = await lb.call(
                self._http_request,
                method=method,
                endpoint=endpoint,
                **kwargs
            )
            
            return Success(result)
            
        except Exception as e:
            return Failure(f"{service_name} 호출 실패: {str(e)}")
    
    async def _http_request(
        self, 
        instance: ServiceInstance,
        method: str,
        endpoint: str,
        **kwargs
    ) -> dict:
        """실제 HTTP 요청"""
        url = f"http://{instance.host}:{instance.port}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
    
    def get_system_overview(self) -> dict:
        """전체 시스템 개요"""
        overview = {
            "services": {},
            "total_instances": 0,
            "healthy_instances": 0,
            "total_requests": 0,
            "total_failures": 0
        }
        
        for service_name, lb in self.load_balancers.items():
            stats = lb.get_statistics()
            
            overview["services"][service_name] = {
                "strategy": stats["strategy"],
                "total_instances": stats["total_instances"],
                "available_instances": stats["available_instances"],
                "total_requests": stats["total_requests"],
                "failure_rate": stats["failure_rate"]
            }
            
            overview["total_instances"] += stats["total_instances"]
            overview["healthy_instances"] += stats["available_instances"]
            overview["total_requests"] += stats["total_requests"]
            overview["total_failures"] += stats["failed_requests"]
        
        overview["overall_health"] = (
            overview["healthy_instances"] / max(overview["total_instances"], 1)
        )
        
        return overview

# 사용 예제
async def microservice_example():
    """마이크로서비스 로드 밸런싱 예제"""
    
    # 마이크로서비스 로드 밸런서 생성
    ms_lb = MicroserviceLoadBalancer()
    
    # 각 서비스의 인스턴스 등록
    ms_lb.register_service("user-service", [
        ServiceInstance(id="user-1", host="10.0.1.10", port=8001),
        ServiceInstance(id="user-2", host="10.0.1.11", port=8001),
        ServiceInstance(id="user-3", host="10.0.1.12", port=8001, weight=2)  # 고성능 서버
    ])
    
    ms_lb.register_service("order-service", [
        ServiceInstance(id="order-1", host="10.0.2.10", port=8002, weight=1),
        ServiceInstance(id="order-2", host="10.0.2.11", port=8002, weight=3),  # 높은 가중치
    ])
    
    ms_lb.register_service("payment-service", [
        ServiceInstance(id="payment-1", host="10.0.3.10", port=8003),
        ServiceInstance(id="payment-2", host="10.0.3.11", port=8003),
    ])
    
    # 헬스체크 시작
    await ms_lb.start_all_health_checks()
    
    try:
        # 비즈니스 로직 시뮬레이션
        await simulate_e_commerce_workflow(ms_lb)
        
        # 시스템 개요 출력
        overview = ms_lb.get_system_overview()
        print(f"\n=== 시스템 개요 ===")
        print(f"전체 건강도: {overview['overall_health']:.2%}")
        print(f"총 인스턴스: {overview['total_instances']}")
        print(f"건강한 인스턴스: {overview['healthy_instances']}")
        print(f"총 요청: {overview['total_requests']}")
        
        for service_name, service_stats in overview["services"].items():
            print(f"\n{service_name}:")
            print(f"  전략: {service_stats['strategy']}")
            print(f"  가용 인스턴스: {service_stats['available_instances']}/{service_stats['total_instances']}")
            print(f"  총 요청: {service_stats['total_requests']}")
            print(f"  실패율: {service_stats['failure_rate']:.2%}")
    
    finally:
        # 헬스체크 정리
        await ms_lb.stop_all_health_checks()

async def simulate_e_commerce_workflow(ms_lb: MicroserviceLoadBalancer):
    """전자상거래 워크플로우 시뮬레이션"""
    
    for order_id in range(1, 11):
        print(f"\n=== 주문 {order_id} 처리 ===")
        
        try:
            # 1. 사용자 정보 조회
            user_result = await ms_lb.call_service(
                "user-service", 
                f"/users/{order_id}",
                timeout=5.0
            )
            
            if user_result.is_success():
                print(f"사용자 조회 성공: {user_result.unwrap()}")
            else:
                print(f"사용자 조회 실패: {user_result.unwrap_err()}")
                continue
            
            # 2. 주문 생성
            order_result = await ms_lb.call_service(
                "order-service",
                "/orders",
                method="POST",
                json={"user_id": order_id, "items": [{"product": "item1", "qty": 1}]},
                timeout=10.0
            )
            
            if order_result.is_success():
                print(f"주문 생성 성공: {order_result.unwrap()}")
            else:
                print(f"주문 생성 실패: {order_result.unwrap_err()}")
                continue
            
            # 3. 결제 처리
            payment_result = await ms_lb.call_service(
                "payment-service",
                "/payments",
                method="POST",
                json={"order_id": order_id, "amount": 100.0},
                timeout=15.0
            )
            
            if payment_result.is_success():
                print(f"결제 처리 성공: {payment_result.unwrap()}")
            else:
                print(f"결제 처리 실패: {payment_result.unwrap_err()}")
                
                # 결제 실패 시 주문 취소 (보상 트랜잭션)
                await ms_lb.call_service(
                    "order-service",
                    f"/orders/{order_id}/cancel",
                    method="POST"
                )
                print("주문 취소 완료")
        
        except Exception as e:
            print(f"워크플로우 실행 중 오류: {e}")
        
        await asyncio.sleep(1)

# 실행
asyncio.run(microservice_example())
```

### 동적 서비스 디스커버리 통합

```python
import consul
import etcd3

class DynamicServiceRegistry:
    """동적 서비스 레지스트리"""
    
    def __init__(self, ms_lb: MicroserviceLoadBalancer):
        self.ms_lb = ms_lb
        self.consul_client = consul.Consul()  # Consul 클라이언트
        self.running = False
    
    async def start_service_discovery(self):
        """서비스 디스커버리 시작"""
        self.running = True
        
        # 주기적으로 서비스 인스턴스 갱신
        asyncio.create_task(self._update_services_periodically())
    
    def stop_service_discovery(self):
        """서비스 디스커버리 중지"""
        self.running = False
    
    async def _update_services_periodically(self):
        """주기적 서비스 업데이트"""
        while self.running:
            try:
                await self._discover_and_update_services()
                await asyncio.sleep(30)  # 30초마다 갱신
                
            except Exception as e:
                print(f"서비스 디스커버리 오류: {e}")
                await asyncio.sleep(10)  # 오류 시 10초 후 재시도
    
    async def _discover_and_update_services(self):
        """Consul에서 서비스 발견 및 업데이트"""
        
        # Consul에서 서비스 목록 조회
        services = self.consul_client.agent.services()
        
        service_groups = {}
        
        # 서비스별로 인스턴스 그룹화
        for service_id, service_info in services.items():
            service_name = service_info['Service']
            
            if service_name not in service_groups:
                service_groups[service_name] = []
            
            # 헬스체크 결과 조회
            health_info = self.consul_client.health.service(service_name)[1]
            is_healthy = all(
                check['Status'] == 'passing' 
                for instance in health_info 
                for check in instance.get('Checks', [])
                if instance['Service']['ID'] == service_id
            )
            
            instance = ServiceInstance(
                id=service_id,
                host=service_info['Address'],
                port=service_info['Port'],
                weight=service_info.get('Meta', {}).get('weight', 1),
                health_status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
                metadata=service_info.get('Meta', {})
            )
            
            service_groups[service_name].append(instance)
        
        # 로드 밸런서 업데이트
        for service_name, instances in service_groups.items():
            if service_name in self.ms_lb.load_balancers:
                # 기존 서비스 업데이트
                self._update_service_instances(service_name, instances)
            else:
                # 새 서비스 등록
                self.ms_lb.register_service(service_name, instances)
                print(f"새 서비스 등록: {service_name}")
    
    def _update_service_instances(self, service_name: str, new_instances: List[ServiceInstance]):
        """서비스 인스턴스 업데이트"""
        lb = self.ms_lb.load_balancers[service_name]
        
        # 현재 인스턴스 ID 집합
        current_instance_ids = set(lb.instances.keys())
        new_instance_ids = {instance.id for instance in new_instances}
        
        # 제거된 인스턴스
        removed_ids = current_instance_ids - new_instance_ids
        for instance_id in removed_ids:
            lb.remove_instance(instance_id)
            print(f"인스턴스 제거: {service_name}/{instance_id}")
        
        # 추가된 인스턴스
        added_ids = new_instance_ids - current_instance_ids
        for instance in new_instances:
            if instance.id in added_ids:
                lb.add_instance(instance)
                print(f"인스턴스 추가: {service_name}/{instance.id}")
        
        # 기존 인스턴스 상태 업데이트
        for instance in new_instances:
            if instance.id in current_instance_ids:
                existing_instance = lb.instances[instance.id]
                existing_instance.health_status = instance.health_status
                existing_instance.weight = instance.weight
                existing_instance.metadata = instance.metadata

# 사용
async def dynamic_discovery_example():
    """동적 서비스 디스커버리 예제"""
    
    # 마이크로서비스 로드 밸런서
    ms_lb = MicroserviceLoadBalancer()
    
    # 동적 서비스 레지스트리
    registry = DynamicServiceRegistry(ms_lb)
    
    try:
        # 서비스 디스커버리 시작
        await registry.start_service_discovery()
        await ms_lb.start_all_health_checks()
        
        print("동적 서비스 디스커버리 실행 중...")
        
        # 10분간 실행
        await asyncio.sleep(600)
        
    finally:
        # 정리
        registry.stop_service_discovery()
        await ms_lb.stop_all_health_checks()

# 실행 (실제 환경에서만)
# asyncio.run(dynamic_discovery_example())
```

## 🎨 베스트 프랙티스

### 1. 전략 선택 가이드

```python
# ✅ 좋은 예 - 상황별 적절한 전략 선택
def choose_load_balancing_strategy(service_type: str, requirements: dict) -> LoadBalancingStrategy:
    """서비스 유형과 요구사항에 따른 전략 선택"""
    
    if requirements.get("session_affinity", False):
        # 세션 고정이 필요한 경우
        return LoadBalancingStrategy.CONSISTENT_HASH
    
    elif service_type == "database":
        # 데이터베이스: 연결 수 기반
        return LoadBalancingStrategy.LEAST_CONNECTIONS
    
    elif service_type == "api_gateway":
        # API 게이트웨이: 응답 시간 기반
        return LoadBalancingStrategy.LEAST_RESPONSE_TIME
    
    elif service_type == "compute_intensive":
        # 계산 집약적: 가중치 기반
        return LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN
    
    elif requirements.get("high_throughput", False):
        # 높은 처리량: 랜덤 (오버헤드 최소)
        return LoadBalancingStrategy.RANDOM
    
    else:
        # 기본: 라운드 로빈
        return LoadBalancingStrategy.ROUND_ROBIN
```

### 2. 헬스체크 설정

```python
# ✅ 좋은 예 - 서비스별 맞춤 헬스체크
def configure_health_check(service_name: str) -> LoadBalancerConfig:
    """서비스별 헬스체크 설정"""
    
    base_config = LoadBalancerConfig(health_check_enabled=True)
    
    if service_name == "database":
        # 데이터베이스: 자주, 빠르게
        base_config.health_check_interval = 15.0
        base_config.health_check_timeout = 2.0
        base_config.max_consecutive_failures = 2
        
    elif service_name == "external_api":
        # 외부 API: 덜 자주, 관대하게
        base_config.health_check_interval = 60.0
        base_config.health_check_timeout = 10.0
        base_config.max_consecutive_failures = 5
        
    elif "critical" in service_name:
        # 중요한 서비스: 엄격하게
        base_config.health_check_interval = 10.0
        base_config.health_check_timeout = 3.0
        base_config.max_consecutive_failures = 1
    
    return base_config
```

### 3. 모니터링 및 알림

```python
# ✅ 좋은 예 - 포괄적인 로드 밸런서 모니터링
class LoadBalancerMonitor:
    def __init__(self, ms_lb: MicroserviceLoadBalancer):
        self.ms_lb = ms_lb
        self.alert_thresholds = {
            "availability": 0.95,  # 95% 가용성
            "failure_rate": 0.05,  # 5% 실패율
            "response_time": 1.0   # 1초 응답시간
        }
    
    async def monitor_and_alert(self):
        """모니터링 및 알림"""
        overview = self.ms_lb.get_system_overview()
        alerts = []
        
        # 전체 시스템 가용성
        if overview["overall_health"] < self.alert_thresholds["availability"]:
            alerts.append({
                "severity": "critical",
                "message": f"시스템 가용성 {overview['overall_health']:.2%} (임계값: {self.alert_thresholds['availability']:.2%})",
                "metric": "availability"
            })
        
        # 서비스별 세부 모니터링
        for service_name, service_stats in overview["services"].items():
            if service_stats["failure_rate"] > self.alert_thresholds["failure_rate"]:
                alerts.append({
                    "severity": "warning",
                    "message": f"{service_name} 실패율 {service_stats['failure_rate']:.2%}",
                    "metric": "failure_rate",
                    "service": service_name
                })
        
        return alerts
```

### 4. 가중치 동적 조정

```python
# ✅ 좋은 예 - 성능 기반 가중치 자동 조정
class AdaptiveWeightManager:
    def __init__(self, lb: LoadBalancer):
        self.lb = lb
        self.adjustment_history = {}
    
    async def adjust_weights_based_on_performance(self):
        """성능 기반 가중치 자동 조정"""
        
        # 인스턴스별 성능 메트릭 수집
        performance_scores = {}
        
        for instance_id, instance in self.lb.instances.items():
            if instance.total_requests > 10:  # 충분한 데이터가 있는 경우만
                # 성능 점수 계산 (응답시간 기반)
                avg_response_time = instance.average_response_time
                error_rate = 1 - (instance.total_requests - instance.consecutive_failures) / instance.total_requests
                
                # 점수 계산 (낮은 응답시간, 낮은 에러율이 높은 점수)
                performance_score = 1.0 / (1.0 + avg_response_time + error_rate)
                performance_scores[instance_id] = performance_score
        
        if not performance_scores:
            return
        
        # 평균 성능 대비 상대적 가중치 계산
        avg_score = sum(performance_scores.values()) / len(performance_scores)
        
        for instance_id, score in performance_scores.items():
            relative_performance = score / avg_score
            
            # 현재 가중치에서 점진적 조정
            instance = self.lb.instances[instance_id]
            current_weight = instance.weight
            
            # 10% 씩 점진적 조정
            if relative_performance > 1.2:  # 20% 이상 우수
                new_weight = min(10, int(current_weight * 1.1))
            elif relative_performance < 0.8:  # 20% 이상 저조
                new_weight = max(1, int(current_weight * 0.9))
            else:
                new_weight = current_weight
            
            if new_weight != current_weight:
                instance.weight = new_weight
                print(f"가중치 조정: {instance_id} {current_weight} -> {new_weight} (성능: {relative_performance:.2f})")
```

## ⚠️ 주의사항

### 1. 세션 고정 (Sticky Sessions)
- 서버 장애 시 세션 손실 가능성
- 로드 분산의 불균형 야기 가능
- 세션 데이터는 별도 저장소 사용 권장

### 2. 헬스체크 오버헤드
- 너무 빈번한 헬스체크는 서버 부하 증가
- 네트워크 대역폭 사용량 고려
- 헬스체크 실패가 실제 장애인지 구분 필요

### 3. 서킷 브레이커와의 상호작용
- 서킷 브레이커가 열리면 해당 인스턴스 자동 제외
- 복구 시점에서 트래픽 급증 가능성
- 점진적 복구 전략 고려

### 4. 일관된 해싱의 한계
- 서버 추가/제거 시 일부 세션 재분배
- 가상 노드 수에 따른 메모리 사용량 증가
- 서버 성능 차이 고려 어려움

## 🔗 관련 문서
- [서킷 브레이커](./12-circuit-breaker.md) - 장애 격리와 로드 밸런싱 통합
- [모니터링](./08-monitoring.md) - 로드 밸런서 메트릭 수집
- [배포](./05-deployment.md) - 무중단 배포와 로드 밸런싱
- [보안](./11-security.md) - 로드 밸런서 보안 고려사항