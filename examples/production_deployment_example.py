"""
Production Deployment Examples (RFS v4.0.3)

프로덕션 배포 시스템 사용 예제:
- Blue-Green 배포
- Canary 배포  
- Rolling 배포
- 자동 롤백
- 배포 모니터링
"""

import asyncio
from datetime import datetime
from rfs import (
    ProductionDeployer, DeploymentStrategy, DeploymentConfig, DeploymentResult,
    RollbackManager, get_production_deployer, get_rollback_manager,
    deploy_to_production, rollback_deployment
)


async def blue_green_deployment_example():
    """Blue-Green 배포 예제"""
    print("🔵🟢 Blue-Green 배포 예제")
    
    # 배포 설정
    config = DeploymentConfig(
        strategy=DeploymentStrategy.BLUE_GREEN,
        health_check_url="/health",
        health_check_timeout=30,
        rollback_on_failure=True,
        validation_duration=60
    )
    
    deployer = ProductionDeployer(config)
    
    # Blue-Green 배포 실행
    result = await deployer.deploy(
        version="v2.1.0",
        environment="production",
        strategy=DeploymentStrategy.BLUE_GREEN
    )
    
    if result.is_success():
        deployment = result.value
        print(f"   ✅ 배포 성공: {deployment.deployment_id}")
        print(f"   📊 배포 전략: {deployment.strategy.value}")
        print(f"   ⏱️ 배포 시간: {deployment.end_time - deployment.start_time}")
        print(f"   📈 배포 메트릭: {deployment.metrics}")
    else:
        print(f"   ❌ 배포 실패: {result.error}")
    
    print()


async def canary_deployment_example():
    """Canary 배포 예제"""
    print("🐤 Canary 배포 예제")
    
    # 헬퍼 함수 사용
    result = await deploy_to_production(
        version="v2.2.0",
        strategy=DeploymentStrategy.CANARY,
        environment="production"
    )
    
    if result.is_success():
        deployment = result.value
        print(f"   ✅ Canary 배포 성공: {deployment.deployment_id}")
        print(f"   📊 배포 상태: {deployment.status.value}")
        print(f"   🎯 Canary 트래픽: {deployment.metrics.get('canary_percentage', 10)}%")
        
        # 배포 상태 모니터링 시뮬레이션
        deployer = get_production_deployer()
        status = deployer.get_deployment_status(deployment.deployment_id)
        
        if status:
            print(f"   📋 현재 상태: {status.status.value}")
            if status.errors:
                print(f"   ⚠️ 오류: {status.errors}")
        
    else:
        print(f"   ❌ Canary 배포 실패: {result.error}")
    
    print()


async def rolling_deployment_example():
    """Rolling 배포 예제"""
    print("🔄 Rolling 배포 예제")
    
    # 커스텀 설정으로 Rolling 배포
    config = DeploymentConfig(
        strategy=DeploymentStrategy.ROLLING,
        deployment_timeout=1800,  # 30분 타임아웃
        pre_deployment_hooks=[
            lambda result: print(f"   🔍 사전 검증 실행 중...")
        ],
        post_deployment_hooks=[
            lambda result: print(f"   🎉 배포 완료 후 정리 작업 실행")
        ]
    )
    
    deployer = ProductionDeployer(config)
    
    result = await deployer.deploy(
        version="v2.3.0",
        environment="production"
    )
    
    if result.is_success():
        deployment = result.value
        print(f"   ✅ Rolling 배포 성공")
        print(f"   🆔 배포 ID: {deployment.deployment_id}")
        print(f"   📦 버전: {deployment.version}")
        print(f"   🌍 환경: {deployment.environment}")
        
        # 인스턴스별 업데이트 정보
        for i in range(5):
            if f"instance_{i}_updated" in deployment.metrics:
                print(f"   📟 Instance {i}: ✅ 업데이트 완료")
        
    else:
        print(f"   ❌ Rolling 배포 실패: {result.error}")
    
    print()


async def automatic_rollback_example():
    """자동 롤백 예제"""
    print("↩️ 자동 롤백 예제")
    
    # 실패하는 배포 시뮬레이션 (높은 금액으로 실패 유도)
    config = DeploymentConfig(
        rollback_on_failure=True,
        max_rollback_attempts=3,
        rollback_hooks=[
            lambda result: print(f"   🔄 롤백 훅 실행: {result.deployment_id}")
        ]
    )
    
    deployer = ProductionDeployer(config)
    
    # 롤백 관리자 준비
    rollback_manager = get_rollback_manager()
    
    try:
        # 의도적으로 실패할 배포 (실제로는 검증 실패 등으로)
        result = await deployer.deploy(
            version="v2.4.0-unstable",
            environment="staging"  # 스테이징에서 테스트
        )
        
        if result.is_success():
            deployment = result.value
            print(f"   📦 배포 시도: {deployment.deployment_id}")
            
            # 스냅샷 생성
            snapshot_result = await rollback_manager.create_snapshot(deployment.deployment_id)
            if snapshot_result.is_success():
                print(f"   📸 스냅샷 생성: {snapshot_result.value}")
            
            # 문제 발생 시뮬레이션 - 수동 롤백
            print("   ⚠️ 배포 후 문제 발견, 롤백 실행...")
            rollback_result = await rollback_manager.rollback(
                deployment_id=deployment.deployment_id,
                strategy=DeploymentStrategy.BLUE_GREEN
            )
            
            if rollback_result.is_success():
                rollback_info = rollback_result.value
                print(f"   ✅ 롤백 성공: {rollback_info['id']}")
                print(f"   🔧 롤백 방법: {rollback_info['method']}")
            else:
                print(f"   ❌ 롤백 실패: {rollback_result.error}")
                
        else:
            print(f"   ❌ 배포 실패 (자동 롤백됨): {result.error}")
    
    except Exception as e:
        print(f"   💥 예외 발생: {e}")
    
    print()


async def deployment_monitoring_example():
    """배포 모니터링 예제"""
    print("📊 배포 모니터링 예제")
    
    deployer = get_production_deployer()
    
    # 간단한 A/B 테스트 배포
    result = await deployer.deploy(
        version="v2.5.0-ab-test",
        strategy=DeploymentStrategy.A_B_TESTING
    )
    
    if result.is_success():
        deployment = result.value
        print(f"   🧪 A/B 테스트 배포: {deployment.deployment_id}")
        
        # 배포 이력 조회
        history = deployer.get_deployment_history()
        print(f"   📚 총 배포 이력: {len(history)}개")
        
        # 최근 3개 배포 정보
        print("   📋 최근 배포들:")
        for i, dep in enumerate(history[:3]):
            print(f"     {i+1}. {dep.deployment_id}: {dep.status.value} ({dep.version})")
        
        # 현재 배포 상세 정보
        current = deployer.get_current_deployment()
        if current:
            print(f"   🚀 현재 활성 배포: {current.deployment_id}")
            print(f"   📈 성공률 예상: 95%")  # 실제로는 메트릭에서 계산
    
    print()


async def deployment_strategies_comparison():
    """배포 전략 비교 예제"""
    print("⚖️ 배포 전략 비교")
    
    strategies = [
        (DeploymentStrategy.RECREATE, "빠름, 다운타임 있음"),
        (DeploymentStrategy.ROLLING, "점진적, 안전함"),
        (DeploymentStrategy.BLUE_GREEN, "무중단, 리소스 2배"),
        (DeploymentStrategy.CANARY, "위험 최소화, 점진적 검증"),
        (DeploymentStrategy.A_B_TESTING, "사용자 테스트, 데이터 기반 결정")
    ]
    
    print("   📋 배포 전략별 특징:")
    for strategy, description in strategies:
        print(f"     • {strategy.value}: {description}")
    
    # 각 전략별 시뮬레이션 배포 시간 예측
    print("\n   ⏱️ 예상 배포 시간 (시뮬레이션):")
    deployment_times = {
        DeploymentStrategy.RECREATE: "2-3분",
        DeploymentStrategy.ROLLING: "5-10분", 
        DeploymentStrategy.BLUE_GREEN: "3-5분",
        DeploymentStrategy.CANARY: "15-30분",
        DeploymentStrategy.A_B_TESTING: "30분-수시간"
    }
    
    for strategy, time_estimate in deployment_times.items():
        print(f"     • {strategy.value}: {time_estimate}")
    
    print()


async def main():
    """모든 배포 예제 실행"""
    print("🚀 RFS Framework - Production Deployment 예제")
    print("=" * 65)
    
    await blue_green_deployment_example()
    await canary_deployment_example()
    await rolling_deployment_example()
    await automatic_rollback_example()
    await deployment_monitoring_example()
    await deployment_strategies_comparison()
    
    print("✅ 모든 Production Deployment 예제 완료!")


if __name__ == "__main__":
    asyncio.run(main())