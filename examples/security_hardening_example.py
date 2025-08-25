"""
Security Hardening Examples (RFS v4.0.3)

보안 강화 시스템 사용 예제:
- 보안 정책 생성
- 보안 강화 적용
- 컴플라이언스 검증
- 비밀번호 정책
- 보안 점수 계산
"""

import asyncio
from rfs import (
    SecurityHardening, SecurityPolicy, SecurityLevel, ComplianceStandard,
    create_security_policy, apply_security_hardening
)


async def basic_security_hardening_example():
    """기본 보안 강화 예제"""
    print("🛡️ 기본 보안 강화 예제")
    
    # 기본 보안 정책 생성
    policy = SecurityPolicy(
        name="basic_policy",
        level=SecurityLevel.STANDARD,
        min_password_length=12,
        require_mfa=False,
        session_timeout_minutes=30
    )
    
    # 보안 강화 적용
    hardening = SecurityHardening(policy)
    result = hardening.apply_hardening()
    
    if result.is_success():
        hardening_result = result.value
        print(f"   ✅ 보안 강화 완료")
        print(f"   📊 보안 점수: {hardening_result.success_rate:.1f}%")
        print(f"   ✅ 통과한 검사: {hardening_result.passed_checks}")
        print(f"   ❌ 실패한 검사: {hardening_result.failed_checks}")
        
        if hardening_result.warnings:
            print(f"   ⚠️ 경고사항: {len(hardening_result.warnings)}개")
            for warning in hardening_result.warnings[:3]:  # 처음 3개만
                print(f"     • {warning}")
                
        if hardening_result.recommendations:
            print(f"   💡 권장사항: {len(hardening_result.recommendations)}개")
            for rec in hardening_result.recommendations[:3]:  # 처음 3개만
                print(f"     • {rec}")
    else:
        print(f"   ❌ 보안 강화 실패: {result.error}")
    
    print()


async def high_security_example():
    """고급 보안 설정 예제"""
    print("🔐 고급 보안 설정 예제")
    
    # 높은 보안 수준 정책
    policy = create_security_policy(
        name="high_security_policy",
        level=SecurityLevel.HIGH,
        min_password_length=16,
        require_mfa=True,
        require_uppercase=True,
        require_lowercase=True, 
        require_numbers=True,
        require_special_chars=True,
        session_timeout_minutes=15,
        max_login_attempts=3,
        encryption_algorithm="AES-256",
        require_https=True,
        enable_audit_logging=True
    )
    
    # 헬퍼 함수를 사용한 보안 강화
    result = apply_security_hardening(policy)
    
    if result.is_success():
        hardening_result = result.value
        print(f"   🔒 고급 보안 강화 적용 완료")
        print(f"   📈 보안 점수: {hardening_result.success_rate:.1f}%")
        print(f"   🛡️ 보안 수준: {policy.level.value}")
        print(f"   🔐 암호화: {policy.encryption_algorithm}")
        print(f"   👥 MFA 필수: {'Yes' if policy.require_mfa else 'No'}")
        print(f"   ⏰ 세션 타임아웃: {policy.session_timeout_minutes}분")
        
        if hardening_result.remediation_actions:
            print(f"   🔧 적용된 보안 조치: {len(hardening_result.remediation_actions)}개")
            for action in hardening_result.remediation_actions[:3]:
                print(f"     ✅ {action}")
    else:
        print(f"   ❌ 고급 보안 강화 실패: {result.error}")
    
    print()


async def compliance_validation_example():
    """컴플라이언스 검증 예제"""
    print("📋 컴플라이언스 검증 예제")
    
    # 다중 컴플라이언스 표준을 만족하는 정책
    policy = SecurityPolicy(
        name="compliance_policy",
        level=SecurityLevel.CRITICAL,
        min_password_length=16,
        require_mfa=True,
        require_data_encryption_at_rest=True,
        require_data_encryption_in_transit=True,
        enable_audit_logging=True,
        audit_retention_days=2555,  # 7년 (GDPR/SOX 요구사항)
        compliance_standards=[
            ComplianceStandard.PCI_DSS,
            ComplianceStandard.GDPR,
            ComplianceStandard.HIPAA,
            ComplianceStandard.SOC2
        ]
    )
    
    hardening = SecurityHardening(policy)
    result = hardening.apply_hardening()
    
    if result.is_success():
        hardening_result = result.value
        print(f"   📊 컴플라이언스 검증 결과:")
        print(f"     전체 보안 점수: {hardening_result.success_rate:.1f}%")
        print(f"     컴플라이언스 준수: {'✅ 준수' if hardening_result.is_compliant else '❌ 미준수'}")
        
        print(f"   📋 표준별 검증 결과:")
        for standard, status in hardening_result.compliance_status.items():
            emoji = "✅" if status else "❌"
            print(f"     {emoji} {standard}: {'준수' if status else '미준수'}")
        
        if hardening_result.critical_issues:
            print(f"   🚨 치명적 이슈: {len(hardening_result.critical_issues)}개")
            for issue in hardening_result.critical_issues:
                print(f"     💥 {issue}")
    else:
        print(f"   ❌ 컴플라이언스 검증 실패: {result.error}")
    
    print()


async def password_security_example():
    """비밀번호 보안 예제"""
    print("🔑 비밀번호 보안 예제")
    
    # 엄격한 비밀번호 정책
    policy = SecurityPolicy(
        name="strict_password_policy",
        min_password_length=14,
        require_uppercase=True,
        require_lowercase=True,
        require_numbers=True,
        require_special_chars=True,
        password_history=10,  # 최근 10개 비밀번호 기억
        password_expiry_days=60  # 60일마다 변경
    )
    
    hardening = SecurityHardening(policy)
    
    # 다양한 비밀번호 테스트
    test_passwords = [
        "weak123",                    # 너무 약함
        "StrongPassword123",          # 특수문자 없음
        "Strong@P4ssw0rd!2025",      # 강력한 비밀번호
        "MyVerySecure&Complex#Pass1", # 매우 강력
        "abc"                        # 매우 약함
    ]
    
    print("   🧪 비밀번호 테스트 결과:")
    for password in test_passwords:
        result = hardening.validate_password(password)
        status = "✅ 통과" if result.is_success() else "❌ 실패"
        display_pwd = password[:8] + "..." if len(password) > 8 else password
        
        print(f"     {status} '{display_pwd}': ", end="")
        if result.is_failure():
            print(result.error)
        else:
            print("정책을 만족합니다")
    
    # 보안 토큰 생성 예제
    print(f"\n   🎲 보안 토큰 생성:")
    token_16 = hardening.generate_secure_token(16)
    token_32 = hardening.generate_secure_token(32)
    print(f"     16바이트: {token_16}")
    print(f"     32바이트: {token_32}")
    
    # 비밀번호 해싱 및 검증
    print(f"\n   🔒 비밀번호 해싱 및 검증:")
    test_password = "MySecurePassword123!"
    hashed = hardening.hash_password(test_password)
    is_valid = hardening.verify_password(test_password, hashed)
    is_invalid = hardening.verify_password("WrongPassword", hashed)
    
    print(f"     원본 비밀번호: {test_password}")
    print(f"     해시된 비밀번호: {hashed[:50]}...")
    print(f"     올바른 비밀번호 검증: {'✅' if is_valid else '❌'}")
    print(f"     잘못된 비밀번호 검증: {'❌' if not is_invalid else '✅'}")
    
    print()


async def security_monitoring_example():
    """보안 모니터링 예제"""
    print("📊 보안 모니터링 예제")
    
    # 여러 보안 수준으로 테스트
    security_levels = [
        SecurityLevel.BASIC,
        SecurityLevel.STANDARD,
        SecurityLevel.HIGH,
        SecurityLevel.CRITICAL
    ]
    
    print("   📈 보안 수준별 점수 비교:")
    for level in security_levels:
        policy = SecurityPolicy(
            name=f"{level.value}_policy",
            level=level,
            min_password_length=12 if level == SecurityLevel.BASIC else 16,
            require_mfa=level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL],
            require_data_encryption_at_rest=level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL],
            enable_audit_logging=level != SecurityLevel.BASIC
        )
        
        hardening = SecurityHardening(policy)
        result = hardening.apply_hardening()
        
        if result.is_success():
            score = result.value.success_rate
            print(f"     {level.value.upper()}: {score:.1f}% 보안 점수")
        
    # 보안 강화 이력 조회
    sample_hardening = SecurityHardening()
    history = sample_hardening.get_hardening_history()
    overall_score = sample_hardening.get_security_score()
    
    print(f"\n   📚 보안 강화 이력:")
    print(f"     총 강화 실행 횟수: {len(history)}회")
    print(f"     전체 보안 점수: {overall_score:.1f}%")
    
    print()


async def security_recommendations_example():
    """보안 권장사항 예제"""
    print("💡 보안 권장사항 예제")
    
    # 보안이 취약한 정책으로 시뮬레이션
    weak_policy = SecurityPolicy(
        name="weak_policy",
        level=SecurityLevel.BASIC,
        min_password_length=6,       # 너무 짧음
        require_mfa=False,           # MFA 미사용
        session_timeout_minutes=120, # 너무 긺
        password_expiry_days=365,    # 너무 긺
        max_login_attempts=10,       # 너무 관대함
        require_https=False          # HTTPS 미사용
    )
    
    hardening = SecurityHardening(weak_policy)
    result = hardening.apply_hardening()
    
    if result.is_success():
        hardening_result = result.value
        print(f"   🔍 취약한 보안 설정 분석 결과:")
        print(f"     보안 점수: {hardening_result.success_rate:.1f}% (낮음)")
        print(f"     총 검사 항목: {hardening_result.total_checks}개")
        print(f"     실패한 검사: {hardening_result.failed_checks}개")
        
        print(f"\n   ⚠️ 주요 보안 이슈:")
        for issue in hardening_result.critical_issues:
            print(f"     🚨 {issue}")
        
        print(f"\n   💡 보안 개선 권장사항:")
        for rec in hardening_result.recommendations:
            print(f"     💡 {rec}")
        
        print(f"\n   🔧 적용 가능한 보안 조치:")
        for action in hardening_result.remediation_actions:
            print(f"     🛠️ {action}")
    
    print()


async def main():
    """모든 보안 예제 실행"""
    print("🔐 RFS Framework - Security Hardening 예제")
    print("=" * 60)
    
    await basic_security_hardening_example()
    await high_security_example()
    await compliance_validation_example()
    await password_security_example()
    await security_monitoring_example()
    await security_recommendations_example()
    
    print("✅ 모든 Security Hardening 예제 완료!")


if __name__ == "__main__":
    asyncio.run(main())