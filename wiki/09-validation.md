# 입력 유효성 검사 (Input Validation)

## 📌 개요

RFS Framework의 유효성 검사 시스템은 다차원 검증을 통해 시스템 무결성을 보장합니다. 기능, 통합, 성능, 보안, 호환성 검증을 포괄하며 자동화된 품질 관리를 제공합니다.

## 🎯 핵심 개념

### 검증 레벨
- **BASIC**: 기본적인 기능 검증
- **STANDARD**: 표준 품질 검증 (기본값)
- **COMPREHENSIVE**: 종합적인 시스템 검증
- **CRITICAL**: 중요 시스템용 엄격한 검증

### 검증 카테고리
- **FUNCTIONAL**: 기능 검증 (모듈 임포트, 핵심 로직)
- **INTEGRATION**: 통합 검증 (모듈 간 상호작용)
- **PERFORMANCE**: 성능 검증 (응답시간, 메모리 사용량)
- **SECURITY**: 보안 검증 (권한, 취약점)
- **COMPATIBILITY**: 호환성 검증 (플랫폼, 버전)
- **CONFIGURATION**: 설정 검증
- **DEPLOYMENT**: 배포 검증

### 검증 상태
- **PASS**: 검증 성공
- **FAIL**: 검증 실패
- **WARNING**: 경고 (문제 있지만 치명적이지 않음)
- **SKIP**: 검증 생략
- **ERROR**: 검증 실행 오류

## 📚 API 레퍼런스

### SystemValidator 클래스

```python
from rfs.validation.validator import SystemValidator, ValidationSuite, ValidationLevel

# 시스템 검증기 생성
validator = SystemValidator(project_path="/path/to/project")
```

### ValidationSuite 설정

```python
from rfs.validation.validator import ValidationSuite, ValidationLevel, ValidationCategory

# 검증 스위트 생성
suite = ValidationSuite(
    name="프로덕션 배포 검증",
    description="프로덕션 환경 배포 전 종합 검증",
    level=ValidationLevel.COMPREHENSIVE,
    categories=[
        ValidationCategory.FUNCTIONAL,
        ValidationCategory.SECURITY,
        ValidationCategory.PERFORMANCE
    ],
    timeout=300,              # 5분 타임아웃
    parallel=True,            # 병렬 실행
    continue_on_failure=True  # 실패 시 계속 진행
)
```

### ValidationResult 구조

```python
@dataclass
class ValidationResult:
    category: ValidationCategory      # 검증 카테고리
    name: str                        # 검증 항목명
    status: ValidationStatus         # 검증 상태
    message: str                     # 결과 메시지
    details: Dict[str, Any]          # 상세 정보
    execution_time: float            # 실행 시간
    recommendations: List[str]       # 권장사항
    severity: str                    # 심각도 (info/warning/error/critical)
```

## 💡 사용 예제

### 기본 시스템 검증

```python
from rfs.validation.validator import (
    SystemValidator, 
    ValidationSuite, 
    ValidationLevel
)
import asyncio

async def run_basic_validation():
    """기본 시스템 검증 실행"""
    validator = SystemValidator()
    
    # 기본 검증 스위트
    suite = ValidationSuite(
        name="기본 시스템 검증",
        description="핵심 기능 동작 확인",
        level=ValidationLevel.BASIC
    )
    
    # 검증 실행
    result = await validator.run_validation(suite)
    
    if result.is_success():
        report = result.unwrap()
        print(f"검증 완료: {report['summary']['success_rate']:.1f}% 성공")
        
        # 실패한 항목 확인
        if report['summary']['failed_tests'] > 0:
            print("실패한 검증 항목:")
            for detail in report['detailed_results']:
                if detail['status'] in ['fail', 'error']:
                    print(f"- {detail['name']}: {detail['message']}")
    else:
        print(f"검증 실패: {result.unwrap_err()}")

# 실행
asyncio.run(run_basic_validation())
```

### 종합 프로덕션 검증

```python
from rfs.validation.validator import (
    SystemValidator,
    ValidationSuite,
    ValidationLevel,
    ValidationCategory
)

async def production_validation():
    """프로덕션 배포 전 종합 검증"""
    validator = SystemValidator(project_path=".")
    
    # 종합 검증 스위트
    suite = ValidationSuite(
        name="프로덕션 배포 검증",
        description="프로덕션 환경 배포 전 모든 시스템 검증",
        level=ValidationLevel.COMPREHENSIVE,
        categories=[
            ValidationCategory.FUNCTIONAL,
            ValidationCategory.INTEGRATION,
            ValidationCategory.PERFORMANCE,
            ValidationCategory.SECURITY,
            ValidationCategory.COMPATIBILITY
        ],
        timeout=600,  # 10분 타임아웃
        parallel=True,
        continue_on_failure=True
    )
    
    # 검증 실행
    result = await validator.run_validation(suite)
    
    if result.is_success():
        report = result.unwrap()
        
        # 결과 분석
        summary = report['summary']
        print(f"검증 결과: {summary['overall_status']}")
        print(f"성공률: {summary['success_rate']:.1f}%")
        print(f"총 테스트: {summary['total_tests']}")
        print(f"통과: {summary['passed_tests']}")
        print(f"실패: {summary['failed_tests']}")
        print(f"경고: {summary['warning_tests']}")
        
        # 심각한 문제가 있으면 배포 중단
        if summary['critical_issues'] > 0:
            print("❌ 심각한 문제 발견 - 배포 중단 필요")
            return False
        elif summary['failed_tests'] > 0:
            print("⚠️  일부 검증 실패 - 검토 후 배포")
            return False
        else:
            print("✅ 모든 검증 통과 - 배포 가능")
            return True
    
    return False

# 실행 및 배포 결정
if asyncio.run(production_validation()):
    print("프로덕션 배포 진행")
else:
    print("배포 중단 - 문제 해결 후 재시도")
```

### 특정 카테고리 검증

```python
async def security_validation():
    """보안 검증만 실행"""
    validator = SystemValidator()
    
    # 보안 검증 전용 스위트
    suite = ValidationSuite(
        name="보안 검증",
        description="시스템 보안 상태 점검",
        level=ValidationLevel.CRITICAL,
        categories=[ValidationCategory.SECURITY],
        timeout=180
    )
    
    result = await validator.run_validation(suite)
    
    if result.is_success():
        report = result.unwrap()
        
        # 보안 관련 권장사항 출력
        if report['recommendations']:
            print("보안 권장사항:")
            for rec in report['recommendations']:
                print(f"- {rec}")
        
        # 심각한 보안 문제 확인
        critical_security_issues = [
            r for r in report['detailed_results']
            if r['category'] == 'security' and r['severity'] == 'critical'
        ]
        
        if critical_security_issues:
            print("🚨 심각한 보안 문제 발견!")
            for issue in critical_security_issues:
                print(f"- {issue['name']}: {issue['message']}")
    
    return result

# 보안 검증 실행
await security_validation()
```

### 성능 벤치마킹

```python
async def performance_benchmark():
    """성능 벤치마크 실행"""
    validator = SystemValidator()
    
    # 성능 검증 스위트
    suite = ValidationSuite(
        name="성능 벤치마크",
        description="시스템 성능 측정 및 분석",
        level=ValidationLevel.COMPREHENSIVE,
        categories=[ValidationCategory.PERFORMANCE],
        timeout=300
    )
    
    result = await validator.run_validation(suite)
    
    if result.is_success():
        report = result.unwrap()
        
        # 성능 메트릭 분석
        performance_results = [
            r for r in report['detailed_results']
            if r['category'] == 'performance'
        ]
        
        print("성능 벤치마크 결과:")
        for perf_result in performance_results:
            print(f"- {perf_result['name']}: {perf_result['message']}")
            
            if 'import_time_seconds' in perf_result.get('details', {}):
                import_time = perf_result['details']['import_time_seconds']
                print(f"  임포트 시간: {import_time:.3f}초")
            
            if 'memory_mb' in perf_result.get('details', {}):
                memory_usage = perf_result['details']['memory_mb']
                print(f"  메모리 사용량: {memory_usage:.1f}MB")
    
    return result

# 성능 벤치마크 실행
await performance_benchmark()
```

### 커스텀 검증 로직

```python
from rfs.validation.validator import (
    SystemValidator, 
    ValidationResult, 
    ValidationStatus, 
    ValidationCategory
)

class CustomValidator(SystemValidator):
    """커스텀 검증기"""
    
    async def _run_custom_validation(self, suite) -> list[ValidationResult]:
        """커스텀 검증 로직"""
        results = []
        
        try:
            # 1. 데이터베이스 연결 검증
            db_result = await self._validate_database_connection()
            results.append(db_result)
            
            # 2. 외부 API 접근 검증
            api_result = await self._validate_external_apis()
            results.append(api_result)
            
            # 3. 비즈니스 로직 검증
            business_result = await self._validate_business_logic()
            results.append(business_result)
            
        except Exception as e:
            results.append(ValidationResult(
                category=ValidationCategory.FUNCTIONAL,
                name="커스텀 검증",
                status=ValidationStatus.ERROR,
                message=f"커스텀 검증 중 오류: {str(e)}",
                severity="error"
            ))
        
        return results
    
    async def _validate_database_connection(self) -> ValidationResult:
        """데이터베이스 연결 상태 검증"""
        try:
            # 실제 데이터베이스 연결 테스트
            # connection = await get_db_connection()
            # await connection.ping()
            
            return ValidationResult(
                category=ValidationCategory.INTEGRATION,
                name="데이터베이스 연결",
                status=ValidationStatus.PASS,
                message="데이터베이스 연결 정상",
                details={"connection_time": 0.05},
                severity="info"
            )
        except Exception as e:
            return ValidationResult(
                category=ValidationCategory.INTEGRATION,
                name="데이터베이스 연결",
                status=ValidationStatus.FAIL,
                message=f"데이터베이스 연결 실패: {str(e)}",
                severity="critical",
                recommendations=["데이터베이스 서버 상태 확인", "연결 설정 검토"]
            )
    
    async def _validate_external_apis(self) -> ValidationResult:
        """외부 API 접근성 검증"""
        try:
            # 외부 API 호출 테스트
            apis = [
                "https://api.example1.com/health",
                "https://api.example2.com/status"
            ]
            
            failed_apis = []
            for api in apis:
                # API 호출 시뮬레이션
                # response = await http_client.get(api)
                # if response.status_code != 200:
                #     failed_apis.append(api)
                pass
            
            if failed_apis:
                return ValidationResult(
                    category=ValidationCategory.INTEGRATION,
                    name="외부 API 접근성",
                    status=ValidationStatus.WARNING,
                    message=f"{len(failed_apis)}개 API 접근 불가",
                    details={"failed_apis": failed_apis},
                    severity="warning"
                )
            else:
                return ValidationResult(
                    category=ValidationCategory.INTEGRATION,
                    name="외부 API 접근성",
                    status=ValidationStatus.PASS,
                    message="모든 외부 API 접근 가능",
                    severity="info"
                )
        
        except Exception as e:
            return ValidationResult(
                category=ValidationCategory.INTEGRATION,
                name="외부 API 접근성",
                status=ValidationStatus.ERROR,
                message=f"API 접근성 검증 실패: {str(e)}",
                severity="error"
            )

# 커스텀 검증기 사용
async def run_custom_validation():
    custom_validator = CustomValidator()
    
    suite = ValidationSuite(
        name="커스텀 시스템 검증",
        description="특화된 비즈니스 로직 검증"
    )
    
    result = await custom_validator.run_validation(suite)
    return result
```

### 검증 결과 저장 및 분석

```python
import json
from datetime import datetime

async def validation_with_report():
    """검증 실행 후 상세 리포트 생성"""
    validator = SystemValidator()
    
    suite = ValidationSuite(
        name="일일 시스템 검증",
        description="매일 자동 실행되는 시스템 건강 상태 확인",
        level=ValidationLevel.STANDARD
    )
    
    # 검증 실행
    result = await validator.run_validation(suite)
    
    if result.is_success():
        report = result.unwrap()
        
        # 리포트 파일 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"validation_report_{timestamp}.json"
        
        save_result = await validator.save_report(report, report_file)
        if save_result.is_success():
            print(f"리포트 저장됨: {save_result.unwrap()}")
        
        # 트렌드 분석 데이터 생성
        trend_data = {
            "timestamp": datetime.now().isoformat(),
            "success_rate": report['summary']['success_rate'],
            "total_tests": report['summary']['total_tests'],
            "failed_tests": report['summary']['failed_tests'],
            "critical_issues": report['summary']['critical_issues'],
            "categories": {}
        }
        
        # 카테고리별 성과 추적
        for category, stats in report.get('category_stats', {}).items():
            trend_data['categories'][category] = {
                "success_rate": stats['success_rate'],
                "total": stats['total'],
                "failed": stats['failed']
            }
        
        # 트렌드 데이터 저장 (실제로는 DB에 저장)
        trend_file = f"validation_trend_{timestamp}.json"
        with open(trend_file, 'w') as f:
            json.dump(trend_data, f, indent=2)
        
        print(f"트렌드 데이터 저장됨: {trend_file}")
        
        return report
    else:
        print(f"검증 실패: {result.unwrap_err()}")
        return None

# 검증 및 리포트 생성
report = await validation_with_report()
```

### CI/CD 파이프라인 통합

```python
import sys
import asyncio

async def ci_validation_gate():
    """CI/CD 파이프라인용 검증 게이트"""
    validator = SystemValidator()
    
    # CI 환경용 빠른 검증
    suite = ValidationSuite(
        name="CI 검증 게이트",
        description="빌드 및 배포 승인을 위한 필수 검증",
        level=ValidationLevel.STANDARD,
        categories=[
            ValidationCategory.FUNCTIONAL,
            ValidationCategory.SECURITY
        ],
        timeout=120,  # 2분 제한
        parallel=True,
        continue_on_failure=False  # 실패 시 즉시 중단
    )
    
    result = await validator.run_validation(suite)
    
    if result.is_success():
        report = result.unwrap()
        summary = report['summary']
        
        # CI 결과 출력 (GitHub Actions, Jenkins 등에서 확인)
        print(f"::notice title=Validation Results::{summary['passed_tests']}/{summary['total_tests']} tests passed")
        
        if summary['overall_status'] == 'PASS':
            print("::notice title=CI Gate::✅ All validations passed - Build approved")
            sys.exit(0)  # 성공
        elif summary['critical_issues'] > 0:
            print(f"::error title=CI Gate::❌ {summary['critical_issues']} critical issues found")
            # 실패한 중요 검증 항목 출력
            for detail in report['detailed_results']:
                if detail['severity'] == 'critical' and detail['status'] in ['fail', 'error']:
                    print(f"::error title=Critical Issue::{detail['name']} - {detail['message']}")
            sys.exit(1)  # 실패
        else:
            print(f"::warning title=CI Gate::⚠️ {summary['failed_tests']} tests failed - Review required")
            sys.exit(1)  # 실패
    else:
        print(f"::error title=Validation Error::{result.unwrap_err()}")
        sys.exit(1)  # 실패

# CI 환경에서 실행
if __name__ == "__main__":
    asyncio.run(ci_validation_gate())
```

## 🎨 베스트 프랙티스

### 1. 검증 스위트 구성

```python
# ✅ 좋은 예 - 목적별 검증 스위트 분리
development_suite = ValidationSuite(
    name="개발 환경 검증",
    level=ValidationLevel.BASIC,
    categories=[ValidationCategory.FUNCTIONAL],
    timeout=60
)

staging_suite = ValidationSuite(
    name="스테이징 검증", 
    level=ValidationLevel.STANDARD,
    categories=[
        ValidationCategory.FUNCTIONAL,
        ValidationCategory.INTEGRATION,
        ValidationCategory.PERFORMANCE
    ],
    timeout=180
)

production_suite = ValidationSuite(
    name="프로덕션 검증",
    level=ValidationLevel.COMPREHENSIVE,
    categories=list(ValidationCategory),
    timeout=600
)
```

### 2. 검증 결과 활용

```python
# ✅ 좋은 예 - 결과에 따른 적절한 액션
async def deploy_with_validation():
    result = await validator.run_validation(production_suite)
    
    if result.is_success():
        report = result.unwrap()
        
        if report['summary']['overall_status'] == 'PASS':
            await deploy_to_production()
        elif report['summary']['critical_issues'] == 0:
            # 경고만 있는 경우 수동 승인
            approval = await request_manual_approval(report)
            if approval:
                await deploy_to_production()
        else:
            await block_deployment(report)
    else:
        await handle_validation_error(result.unwrap_err())
```

### 3. 커스텀 검증 구현

```python
# ✅ 좋은 예 - 비즈니스 요구사항에 맞는 검증
class ECommerceValidator(SystemValidator):
    async def _run_business_validation(self, suite):
        results = []
        
        # 재고 시스템 검증
        inventory_result = await self._validate_inventory_system()
        results.append(inventory_result)
        
        # 결제 시스템 검증
        payment_result = await self._validate_payment_gateway()
        results.append(payment_result)
        
        # 주문 처리 파이프라인 검증
        order_result = await self._validate_order_pipeline()
        results.append(order_result)
        
        return results
```

## ⚠️ 주의사항

### 1. 검증 시간 관리
- 각 검증 카테고리별로 적절한 타임아웃 설정
- 병렬 실행으로 전체 검증 시간 단축
- CI/CD 파이프라인에서는 빠른 검증 우선

### 2. 검증 품질 보장
- 거짓 양성(False Positive) 최소화
- 실제 문제를 놓치지 않도록 충분한 테스트 케이스 포함
- 정기적인 검증 로직 업데이트

### 3. 리소스 사용량 고려
- 검증 실행 시 시스템 리소스 사용량 모니터링
- 프로덕션 환경에 영향을 주지 않도록 주의
- 적절한 검증 주기 설정

### 4. 보안 고려사항
- 검증 과정에서 민감한 정보 노출 방지
- 검증 결과에 시스템 내부 정보 포함 시 접근 제어
- 검증 로그의 보안 관리

## 🔗 관련 문서
- [핵심 패턴](./01-core-patterns.md) - Result 패턴을 통한 검증 결과 처리
- [보안](./11-security.md) - 보안 검증 및 취약점 스캔
- [모니터링](./08-monitoring.md) - 검증 메트릭 및 알림
- [배포](./05-deployment.md) - 배포 파이프라인 검증 통합