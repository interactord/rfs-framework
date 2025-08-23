# 롤백 관리 (Rollback Management)

## 📌 개요

RFS Framework는 체크포인트 기반의 포괄적인 롤백 시스템을 제공합니다. 배포 실패, 설정 오류, 데이터 손상 등의 상황에서 안전하게 이전 상태로 복원할 수 있습니다.

## 🎯 핵심 개념

### 롤백 전략
- **체크포인트 기반**: 특정 시점의 상태 저장 및 복원
- **증분 롤백**: 변경사항만 되돌리기
- **전체 롤백**: 완전한 이전 버전으로 복원
- **선택적 롤백**: 특정 컴포넌트만 롤백

### 체크포인트 타입
- **자동 체크포인트**: 배포 전 자동 생성
- **수동 체크포인트**: 관리자가 명시적으로 생성
- **예약 체크포인트**: 주기적으로 자동 생성
- **조건부 체크포인트**: 특정 조건 충족 시 생성

## 📚 API 레퍼런스

### RollbackManager 클래스

```python
from rfs.production.rollback import (
    RollbackManager,
    DeploymentCheckpoint,
    RollbackRecord,
    CheckpointType,
    RollbackStrategy
)
```

### 주요 롤백 전략

| 전략 | 설명 | 사용 시기 |
|------|------|-----------|
| `IMMEDIATE` | 즉시 롤백 | 긴급 상황 |
| `GRADUAL` | 점진적 롤백 | 부분 문제 |
| `SCHEDULED` | 예약 롤백 | 계획된 복원 |
| `CONDITIONAL` | 조건부 롤백 | 메트릭 기반 |

## 💡 사용 예제

### 기본 롤백 관리

```python
from rfs.production.rollback import RollbackManager
from rfs.core.result import Result, Success, Failure
from datetime import datetime
import json

class DeploymentRollbackManager:
    """배포 롤백 관리자"""
    
    def __init__(self):
        self.rollback_manager = RollbackManager()
        self.checkpoints = []
        self.rollback_history = []
    
    async def create_checkpoint(
        self,
        deployment_id: str,
        metadata: dict
    ) -> Result[str, str]:
        """체크포인트 생성"""
        
        try:
            # 현재 상태 수집
            current_state = await self.collect_system_state()
            
            # 체크포인트 생성
            checkpoint = DeploymentCheckpoint(
                checkpoint_id=self.generate_checkpoint_id(),
                deployment_id=deployment_id,
                created_at=datetime.now(),
                state=current_state,
                metadata=metadata
            )
            
            # 저장
            await self.save_checkpoint(checkpoint)
            self.checkpoints.append(checkpoint)
            
            print(f"체크포인트 생성: {checkpoint.checkpoint_id}")
            
            return Success(checkpoint.checkpoint_id)
            
        except Exception as e:
            return Failure(f"체크포인트 생성 실패: {str(e)}")
    
    async def rollback_to_checkpoint(
        self,
        checkpoint_id: str,
        reason: str
    ) -> Result[dict, str]:
        """특정 체크포인트로 롤백"""
        
        # 체크포인트 조회
        checkpoint = self.find_checkpoint(checkpoint_id)
        if not checkpoint:
            return Failure(f"체크포인트를 찾을 수 없습니다: {checkpoint_id}")
        
        print(f"롤백 시작: {checkpoint_id}")
        
        try:
            # 현재 상태 백업 (롤백의 롤백을 위해)
            backup = await self.create_backup()
            
            # 롤백 실행
            result = await self.execute_rollback(checkpoint)
            
            if result.is_success():
                # 롤백 기록
                record = RollbackRecord(
                    rollback_id=self.generate_rollback_id(),
                    checkpoint_id=checkpoint_id,
                    reason=reason,
                    executed_at=datetime.now(),
                    status="completed",
                    backup_id=backup
                )
                
                self.rollback_history.append(record)
                
                return Success({
                    "rollback_id": record.rollback_id,
                    "status": "completed",
                    "rolled_back_to": checkpoint_id
                })
            else:
                # 롤백 실패 - 백업에서 복원
                await self.restore_from_backup(backup)
                return Failure(f"롤백 실패: {result.error}")
                
        except Exception as e:
            return Failure(f"롤백 중 오류: {str(e)}")
    
    async def collect_system_state(self) -> dict:
        """시스템 상태 수집"""
        return {
            "configuration": await self.get_configuration(),
            "database_schema": await self.get_database_schema(),
            "deployed_services": await self.get_deployed_services(),
            "environment_variables": await self.get_environment_variables(),
            "file_checksums": await self.calculate_file_checksums()
        }
    
    async def execute_rollback(
        self,
        checkpoint: DeploymentCheckpoint
    ) -> Result:
        """롤백 실행"""
        
        # 1. 서비스 중지
        await self.stop_services()
        
        # 2. 상태 복원
        await self.restore_configuration(checkpoint.state["configuration"])
        await self.restore_database(checkpoint.state["database_schema"])
        await self.restore_files(checkpoint.state["file_checksums"])
        
        # 3. 서비스 재시작
        await self.start_services()
        
        # 4. 헬스체크
        health = await self.health_check()
        if not health:
            return Failure("헬스체크 실패")
        
        return Success(None)
```

### 조건부 자동 롤백

```python
from rfs.production.rollback import ConditionalRollback
from typing import Callable

class AutoRollbackManager:
    """자동 롤백 관리자"""
    
    def __init__(self):
        self.rollback_manager = RollbackManager()
        self.conditions = []
        self.monitoring_active = False
    
    def add_rollback_condition(
        self,
        name: str,
        condition: Callable,
        threshold: float,
        action: str = "rollback"
    ):
        """롤백 조건 추가"""
        self.conditions.append({
            "name": name,
            "condition": condition,
            "threshold": threshold,
            "action": action
        })
    
    async def start_monitoring(self):
        """모니터링 시작"""
        self.monitoring_active = True
        
        while self.monitoring_active:
            for condition in self.conditions:
                # 조건 평가
                metric_value = await condition["condition"]()
                
                if self.should_rollback(metric_value, condition["threshold"]):
                    print(f"롤백 조건 충족: {condition['name']}")
                    
                    if condition["action"] == "rollback":
                        # 자동 롤백 실행
                        await self.execute_auto_rollback(condition["name"])
                    elif condition["action"] == "alert":
                        # 알림만 발송
                        await self.send_alert(condition["name"], metric_value)
            
            await asyncio.sleep(30)  # 30초마다 체크
    
    def should_rollback(self, value: float, threshold: float) -> bool:
        """롤백 여부 결정"""
        return value > threshold
    
    async def execute_auto_rollback(self, reason: str):
        """자동 롤백 실행"""
        # 가장 최근 체크포인트로 롤백
        latest_checkpoint = await self.get_latest_checkpoint()
        
        if latest_checkpoint:
            result = await self.rollback_manager.rollback_to_checkpoint(
                latest_checkpoint.checkpoint_id,
                reason=f"자동 롤백: {reason}"
            )
            
            if result.is_success():
                print(f"자동 롤백 성공: {result.value}")
            else:
                print(f"자동 롤백 실패: {result.error}")
                # 수동 개입 필요 알림

# 사용 예제
auto_rollback = AutoRollbackManager()

# 에러율 기반 롤백
auto_rollback.add_rollback_condition(
    name="high_error_rate",
    condition=lambda: get_error_rate(),
    threshold=0.05,  # 5% 이상
    action="rollback"
)

# 응답 시간 기반 롤백
auto_rollback.add_rollback_condition(
    name="slow_response",
    condition=lambda: get_p99_latency(),
    threshold=2000,  # 2초 이상
    action="rollback"
)

# 메모리 사용량 알림
auto_rollback.add_rollback_condition(
    name="high_memory",
    condition=lambda: get_memory_usage(),
    threshold=90,  # 90% 이상
    action="alert"
)

# 모니터링 시작
await auto_rollback.start_monitoring()
```

### 증분 롤백

```python
class IncrementalRollback:
    """증분 롤백 시스템"""
    
    def __init__(self):
        self.change_log = []
        self.rollback_stack = []
    
    async def track_change(
        self,
        component: str,
        change_type: str,
        old_value: any,
        new_value: any
    ):
        """변경사항 추적"""
        change = {
            "timestamp": datetime.now(),
            "component": component,
            "type": change_type,
            "old_value": old_value,
            "new_value": new_value
        }
        
        self.change_log.append(change)
        
        # 롤백 액션 생성
        rollback_action = self.create_rollback_action(change)
        self.rollback_stack.append(rollback_action)
    
    def create_rollback_action(self, change: dict) -> Callable:
        """롤백 액션 생성"""
        component = change["component"]
        old_value = change["old_value"]
        
        async def rollback():
            if component == "configuration":
                await self.restore_config(old_value)
            elif component == "database":
                await self.restore_database_record(old_value)
            elif component == "file":
                await self.restore_file(old_value)
        
        return rollback
    
    async def rollback_last_n_changes(self, n: int) -> Result:
        """최근 N개 변경사항 롤백"""
        
        if n > len(self.rollback_stack):
            return Failure(f"롤백 가능한 변경사항이 {len(self.rollback_stack)}개뿐입니다")
        
        rolled_back = []
        
        for _ in range(n):
            if self.rollback_stack:
                rollback_action = self.rollback_stack.pop()
                try:
                    await rollback_action()
                    change = self.change_log.pop()
                    rolled_back.append(change)
                except Exception as e:
                    return Failure(f"롤백 실패: {str(e)}")
        
        return Success({
            "rolled_back_count": n,
            "changes": rolled_back
        })
    
    async def rollback_component(
        self,
        component: str
    ) -> Result:
        """특정 컴포넌트만 롤백"""
        
        component_changes = [
            (i, change) for i, change in enumerate(self.change_log)
            if change["component"] == component
        ]
        
        if not component_changes:
            return Failure(f"컴포넌트 {component}의 변경사항이 없습니다")
        
        # 역순으로 롤백
        for index, change in reversed(component_changes):
            rollback_action = self.create_rollback_action(change)
            await rollback_action()
            
            # 로그에서 제거
            del self.change_log[index]
            del self.rollback_stack[index]
        
        return Success({
            "component": component,
            "rolled_back_count": len(component_changes)
        })
```

### 데이터베이스 롤백

```python
class DatabaseRollbackManager:
    """데이터베이스 롤백 관리"""
    
    def __init__(self, connection):
        self.conn = connection
        self.migration_history = []
    
    async def create_database_checkpoint(
        self,
        checkpoint_name: str
    ) -> Result[str, str]:
        """데이터베이스 체크포인트 생성"""
        
        try:
            # 1. 스키마 덤프
            schema = await self.dump_schema()
            
            # 2. 데이터 스냅샷 (중요 테이블만)
            snapshot = await self.create_data_snapshot()
            
            # 3. 저장
            checkpoint_id = await self.conn.fetchval(
                """INSERT INTO db_checkpoints 
                   (name, schema_dump, data_snapshot, created_at)
                   VALUES ($1, $2, $3, $4) RETURNING id""",
                checkpoint_name,
                schema,
                json.dumps(snapshot),
                datetime.now()
            )
            
            return Success(checkpoint_id)
            
        except Exception as e:
            return Failure(f"DB 체크포인트 생성 실패: {str(e)}")
    
    async def rollback_database(
        self,
        checkpoint_id: str
    ) -> Result[dict, str]:
        """데이터베이스 롤백"""
        
        # 체크포인트 조회
        checkpoint = await self.conn.fetchrow(
            "SELECT * FROM db_checkpoints WHERE id = $1",
            checkpoint_id
        )
        
        if not checkpoint:
            return Failure(f"체크포인트를 찾을 수 없습니다: {checkpoint_id}")
        
        try:
            # 1. 현재 데이터 백업
            backup = await self.backup_current_state()
            
            # 2. 스키마 복원
            await self.restore_schema(checkpoint['schema_dump'])
            
            # 3. 데이터 복원
            snapshot = json.loads(checkpoint['data_snapshot'])
            await self.restore_data(snapshot)
            
            # 4. 검증
            if await self.validate_database():
                return Success({
                    "checkpoint_id": checkpoint_id,
                    "backup_id": backup,
                    "status": "completed"
                })
            else:
                # 검증 실패 - 백업에서 복원
                await self.restore_from_backup(backup)
                return Failure("데이터베이스 검증 실패")
                
        except Exception as e:
            return Failure(f"DB 롤백 실패: {str(e)}")
    
    async def rollback_migration(
        self,
        migration_version: str
    ) -> Result:
        """마이그레이션 롤백"""
        
        # 롤백할 마이그레이션 찾기
        migrations = await self.get_migrations_after(migration_version)
        
        for migration in reversed(migrations):
            print(f"마이그레이션 롤백: {migration['version']}")
            
            # down 스크립트 실행
            if migration.get('down_script'):
                await self.conn.execute(migration['down_script'])
            
            # 기록 업데이트
            await self.conn.execute(
                "DELETE FROM migration_history WHERE version = $1",
                migration['version']
            )
        
        return Success(f"{len(migrations)}개 마이그레이션 롤백 완료")
```

### 설정 롤백

```python
class ConfigurationRollback:
    """설정 롤백 관리"""
    
    def __init__(self):
        self.config_history = []
        self.current_config = None
    
    async def save_config_version(
        self,
        config: dict,
        version: str,
        description: str = ""
    ):
        """설정 버전 저장"""
        config_version = {
            "version": version,
            "config": config.copy(),
            "description": description,
            "created_at": datetime.now(),
            "hash": self.calculate_hash(config)
        }
        
        self.config_history.append(config_version)
        
        # 파일로도 저장
        await self.persist_config_version(config_version)
    
    async def rollback_config(
        self,
        target_version: str
    ) -> Result[dict, str]:
        """특정 버전으로 설정 롤백"""
        
        # 대상 버전 찾기
        target_config = None
        for config in self.config_history:
            if config["version"] == target_version:
                target_config = config
                break
        
        if not target_config:
            return Failure(f"설정 버전을 찾을 수 없습니다: {target_version}")
        
        # 현재 설정 백업
        await self.save_config_version(
            self.current_config,
            f"backup_{datetime.now().isoformat()}",
            "롤백 전 자동 백업"
        )
        
        # 설정 적용
        self.current_config = target_config["config"].copy()
        
        # 설정 재로드 트리거
        await self.reload_configuration()
        
        return Success({
            "rolled_back_to": target_version,
            "previous_version": self.config_history[-2]["version"]
        })
    
    def calculate_hash(self, config: dict) -> str:
        """설정 해시 계산"""
        import hashlib
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()
```

## 🎨 베스트 프랙티스

### 1. 체크포인트 전략

```python
# 배포 전 항상 체크포인트 생성
checkpoint = await create_checkpoint(
    deployment_id="deploy_123",
    metadata={
        "type": "pre_deployment",
        "version": "v2.0.0",
        "auto_rollback": True
    }
)

# 주기적 체크포인트
schedule_checkpoint(interval=timedelta(hours=6))
```

### 2. 롤백 테스트

```python
# 롤백 시뮬레이션
async def test_rollback():
    # 테스트 환경에서 롤백 검증
    checkpoint = await create_test_checkpoint()
    make_changes()
    result = await rollback_to_checkpoint(checkpoint)
    assert result.is_success()
```

### 3. 롤백 정책

```python
rollback_policy = {
    "auto_rollback": True,
    "max_rollback_time": 300,  # 5분
    "health_check_required": True,
    "approval_required": False  # 긴급 상황
}
```

## ⚠️ 주의사항

### 1. 데이터 일관성
- 트랜잭션 중간에 롤백 금지
- 외부 시스템과의 동기화 고려
- 롤백 불가능한 작업 식별

### 2. 성능 영향
- 체크포인트 생성 오버헤드
- 대용량 데이터 롤백 시간
- 서비스 중단 최소화

### 3. 롤백 한계
- 외부 API 호출은 롤백 불가
- 사용자 데이터 손실 방지
- 롤백 이력 관리

## 🔗 관련 문서
- [배포 전략](./05-deployment.md)
- [트랜잭션](./04-transactions.md)
- [모니터링](./08-monitoring.md)