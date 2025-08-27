"""
사용자 관리 시스템
새로운 함수형 개발 규칙 적용 실무 예제

Rule 1: 소단위 개발 - 사용자 생성, 인증, 권한 관리를 작은 함수로 분해
Rule 2: 파이프라인 통합 - 사용자 등록부터 활성화까지 파이프라인으로 연결
Rule 3: 설정/DI HOF - 역할별 권한과 정책을 설정 기반으로 주입
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from enum import Enum

from rfs.hof.core import pipe, curry, compose
from rfs.hof.collections import compact_map, partition, first, group_by
from rfs.hof.monads import Maybe, Result
from rfs.core.result import Success, Failure
from rfs.core.config import get_config


# =============================================================================
# Rule 1: 소단위 개발 - 도메인 모델과 작은 함수들
# =============================================================================

class UserRole(Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"
    GUEST = "guest"


class AccountStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


@dataclass
class User:
    user_id: str
    email: str
    username: str
    password_hash: str
    role: UserRole
    status: AccountStatus
    created_at: datetime
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0


@dataclass
class PermissionCheck:
    user: User
    resource: str
    action: str
    context: Dict = None


# 소단위 검증 함수들 (5-15줄 제한)

@curry
def validate_email_format(email: str) -> Result[str, str]:
    """이메일 형식을 검증합니다."""
    if not email or '@' not in email:
        return Failure("유효하지 않은 이메일 형식입니다")
    
    local, domain = email.split('@', 1)
    if not local or not domain or '.' not in domain:
        return Failure("이메일 도메인이 잘못되었습니다")
    
    return Success(email.lower())


@curry
def validate_password_strength(min_length: int, password: str) -> Result[str, str]:
    """비밀번호 강도를 검증합니다."""
    if len(password) < min_length:
        return Failure(f"비밀번호는 최소 {min_length}자 이상이어야 합니다")
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    if not all([has_upper, has_lower, has_digit]):
        return Failure("비밀번호는 대문자, 소문자, 숫자를 포함해야 합니다")
    
    return Success(password)


def validate_username_uniqueness(username: str) -> Result[str, str]:
    """사용자명 중복을 검사합니다."""
    if _username_exists(username):
        return Failure("이미 사용 중인 사용자명입니다")
    return Success(username)


def validate_email_uniqueness(email: str) -> Result[str, str]:
    """이메일 중복을 검사합니다."""
    if _email_exists(email):
        return Failure("이미 등록된 이메일입니다")
    return Success(email)


def hash_password(password: str) -> Result[str, str]:
    """비밀번호를 해시합니다."""
    try:
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode('utf-8'), 
            salt.encode('utf-8'), 
            100000
        )
        return Success(f"{salt}:{password_hash.hex()}")
    except Exception as e:
        return Failure(f"비밀번호 해시 실패: {str(e)}")


def verify_password(password: str, password_hash: str) -> Result[bool, str]:
    """비밀번호를 검증합니다."""
    try:
        salt, stored_hash = password_hash.split(':', 1)
        computed_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        is_valid = computed_hash.hex() == stored_hash
        return Success(is_valid)
    except Exception as e:
        return Failure(f"비밀번호 검증 실패: {str(e)}")


def generate_user_id() -> str:
    """사용자 ID를 생성합니다."""
    return f"user_{secrets.token_hex(8)}"


def create_user_object(user_data: dict) -> Result[User, str]:
    """사용자 객체를 생성합니다."""
    try:
        user = User(
            user_id=generate_user_id(),
            email=user_data['email'],
            username=user_data['username'],
            password_hash=user_data['password_hash'],
            role=UserRole(user_data.get('role', 'user')),
            status=AccountStatus.PENDING,
            created_at=datetime.now()
        )
        return Success(user)
    except Exception as e:
        return Failure(f"사용자 객체 생성 실패: {str(e)}")


def save_user_to_database(user: User) -> Result[User, str]:
    """사용자를 데이터베이스에 저장합니다."""
    try:
        _save_user_to_db(user)
        return Success(user)
    except Exception as e:
        return Failure(f"사용자 저장 실패: {str(e)}")


def send_activation_email(user: User) -> Result[User, str]:
    """활성화 이메일을 발송합니다."""
    try:
        activation_token = _generate_activation_token(user.user_id)
        _send_email(
            to=user.email,
            subject="계정 활성화",
            body=f"활성화 링크: https://example.com/activate/{activation_token}"
        )
        return Success(user)
    except Exception as e:
        return Failure(f"활성화 이메일 발송 실패: {str(e)}")


def check_account_lockout(user: User) -> Result[User, str]:
    """계정 잠금 상태를 확인합니다."""
    max_attempts = get_config('security.max_login_attempts', 5)
    
    if user.failed_login_attempts >= max_attempts:
        return Failure("계정이 잠금되었습니다. 관리자에게 문의하세요")
    
    return Success(user)


def update_login_attempt(user: User, success: bool) -> Result[User, str]:
    """로그인 시도 정보를 업데이트합니다."""
    try:
        if success:
            updated_user = User(
                **user.__dict__,
                last_login=datetime.now(),
                failed_login_attempts=0
            )
        else:
            updated_user = User(
                **user.__dict__,
                failed_login_attempts=user.failed_login_attempts + 1
            )
        
        _update_user_in_db(updated_user)
        return Success(updated_user)
    except Exception as e:
        return Failure(f"로그인 정보 업데이트 실패: {str(e)}")


def generate_session_token(user: User) -> Result[str, str]:
    """세션 토큰을 생성합니다."""
    try:
        token = secrets.token_urlsafe(32)
        expiry = datetime.now() + timedelta(hours=24)
        
        _store_session(token, user.user_id, expiry)
        return Success(token)
    except Exception as e:
        return Failure(f"세션 토큰 생성 실패: {str(e)}")


# =============================================================================
# Rule 2: 파이프라인 통합 - 복합 워크플로우
# =============================================================================

def create_user_registration_pipeline():
    """사용자 등록 파이프라인을 생성합니다."""
    
    # Rule 3: 설정에서 정책 가져오기
    min_password_length = get_config('security.min_password_length', 8)
    password_validator = validate_password_strength(min_password_length)
    
    def validate_registration_data(data: dict) -> Result[dict, str]:
        """등록 데이터를 검증합니다."""
        email = data.get('email', '')
        username = data.get('username', '')
        password = data.get('password', '')
        
        # 각 필드를 순차적으로 검증 (파이프라인)
        email_result = (
            validate_email_format(email)
            .bind(validate_email_uniqueness)
        )
        
        if email_result.is_failure():
            return email_result
        
        username_result = validate_username_uniqueness(username)
        if username_result.is_failure():
            return username_result
        
        password_result = password_validator(password)
        if password_result.is_failure():
            return password_result
        
        return Success({
            'email': email_result.unwrap(),
            'username': username_result.unwrap(),
            'password': password_result.unwrap(),
            'role': data.get('role', 'user')
        })
    
    def hash_password_field(data: dict) -> Result[dict, str]:
        """비밀번호를 해시합니다."""
        password_hash_result = hash_password(data['password'])
        if password_hash_result.is_failure():
            return password_hash_result
        
        return Success({
            **data,
            'password_hash': password_hash_result.unwrap()
        })
    
    # 전체 등록 파이프라인
    return pipe(
        validate_registration_data,
        lambda result: result.bind(hash_password_field),
        lambda result: result.bind(create_user_object),
        lambda result: result.bind(save_user_to_database),
        lambda result: result.bind(send_activation_email)
    )


def create_login_pipeline():
    """로그인 처리 파이프라인을 생성합니다."""
    
    def authenticate_credentials(credentials: dict) -> Result[User, str]:
        """자격 증명을 인증합니다."""
        email = credentials.get('email', '')
        password = credentials.get('password', '')
        
        user = _get_user_by_email(email)
        if not user:
            return Failure("사용자를 찾을 수 없습니다")
        
        # 계정 잠금 확인
        lockout_check = check_account_lockout(user)
        if lockout_check.is_failure():
            return lockout_check
        
        # 비밀번호 검증
        password_check = verify_password(password, user.password_hash)
        if password_check.is_failure():
            return password_check
        
        is_valid = password_check.unwrap()
        if not is_valid:
            # 실패한 로그인 시도 기록
            update_login_attempt(user, False)
            return Failure("잘못된 비밀번호입니다")
        
        return Success(user)
    
    def create_user_session(user: User) -> Result[dict, str]:
        """사용자 세션을 생성합니다."""
        # 성공한 로그인 기록
        update_result = update_login_attempt(user, True)
        if update_result.is_failure():
            return update_result
        
        updated_user = update_result.unwrap()
        
        # 세션 토큰 생성
        token_result = generate_session_token(updated_user)
        if token_result.is_failure():
            return token_result
        
        return Success({
            'user': updated_user,
            'session_token': token_result.unwrap(),
            'expires_at': (datetime.now() + timedelta(hours=24)).isoformat()
        })
    
    return pipe(
        authenticate_credentials,
        lambda result: result.bind(create_user_session)
    )


# =============================================================================
# Rule 3: 설정/DI HOF - 권한 관리와 정책 주입
# =============================================================================

@curry
def check_role_permission(required_role: UserRole, user: User) -> Result[User, str]:
    """역할 기반 권한을 확인합니다."""
    role_hierarchy = {
        UserRole.GUEST: 0,
        UserRole.USER: 1,
        UserRole.MODERATOR: 2,
        UserRole.ADMIN: 3
    }
    
    user_level = role_hierarchy.get(user.role, 0)
    required_level = role_hierarchy.get(required_role, 0)
    
    if user_level < required_level:
        return Failure(f"권한이 부족합니다. {required_role.value} 이상 필요")
    
    return Success(user)


@curry
def with_permission_policy(policy_name: str, permission_check: PermissionCheck) -> Result[bool, str]:
    """권한 정책을 적용합니다."""
    policies = get_config(f'permissions.policies.{policy_name}', {})
    
    user_role = permission_check.user.role.value
    resource = permission_check.resource
    action = permission_check.action
    
    # 정책 룰 확인
    role_permissions = policies.get(user_role, {})
    resource_permissions = role_permissions.get(resource, [])
    
    if action in resource_permissions:
        return Success(True)
    
    return Failure(f"권한 없음: {user_role}는 {resource}에서 {action} 불가")


@curry
def with_rate_limiting(limit_config: str, user: User) -> Result[User, str]:
    """사용량 제한을 적용합니다."""
    limits = get_config(f'rate_limits.{limit_config}', {})
    user_role = user.role.value
    
    # 역할별 제한 확인
    role_limits = limits.get(user_role, {})
    current_usage = _get_user_usage(user.user_id)
    
    for limit_type, limit_value in role_limits.items():
        if current_usage.get(limit_type, 0) >= limit_value:
            return Failure(f"사용량 한계 초과: {limit_type}")
    
    return Success(user)


def create_permission_checker(resource: str, action: str):
    """권한 검사기를 생성합니다."""
    
    @curry
    def check_permissions(policy_name: str, user: User) -> Result[bool, str]:
        """사용자 권한을 검사합니다."""
        permission_check = PermissionCheck(
            user=user,
            resource=resource,
            action=action
        )
        
        return with_permission_policy(policy_name, permission_check)
    
    return check_permissions


def create_admin_workflow():
    """관리자 전용 워크플로우를 생성합니다."""
    admin_permission = check_role_permission(UserRole.ADMIN)
    admin_rate_limiter = with_rate_limiting('admin_operations')
    
    def admin_operation(user: User, operation: callable, *args) -> Result[any, str]:
        """관리자 작업을 실행합니다."""
        # 권한 검사 파이프라인
        permission_result = (
            admin_permission(user)
            .bind(admin_rate_limiter)
        )
        
        if permission_result.is_failure():
            return permission_result
        
        try:
            # 실제 작업 수행
            result = operation(*args)
            _log_admin_action(user.user_id, operation.__name__, args)
            return Success(result)
        except Exception as e:
            return Failure(f"관리자 작업 실패: {str(e)}")
    
    return admin_operation


def create_user_profile_updater():
    """사용자 프로필 업데이트 워크플로우를 생성합니다."""
    profile_permission = create_permission_checker('user_profile', 'update')
    profile_rate_limiter = with_rate_limiting('profile_updates')
    
    def update_user_profile(user: User, profile_data: dict) -> Result[User, str]:
        """사용자 프로필을 업데이트합니다."""
        # 권한 및 제한 검사
        checks = pipe(
            lambda u: profile_permission('user_operations', u),
            lambda result: result.bind(lambda _: profile_rate_limiter(user))
        )
        
        permission_result = checks(user)
        if permission_result.is_failure():
            return permission_result
        
        try:
            # 프로필 데이터 검증
            validated_data = _validate_profile_data(profile_data)
            
            # 사용자 정보 업데이트
            updated_user = _update_user_profile(user, validated_data)
            
            return Success(updated_user)
        except Exception as e:
            return Failure(f"프로필 업데이트 실패: {str(e)}")
    
    return update_user_profile


# =============================================================================
# 사용 예제 및 통합 테스트
# =============================================================================

def example_usage():
    """함수형 사용자 관리 시스템 사용 예제"""
    
    print("=== RFS Framework 함수형 사용자 관리 시스템 ===")
    print("새로운 함수형 개발 규칙 적용 예제\n")
    
    # Rule 2: 파이프라인으로 사용자 등록
    registration_pipeline = create_user_registration_pipeline()
    
    registration_data = {
        'email': 'user@example.com',
        'username': 'testuser',
        'password': 'SecurePass123',
        'role': 'user'
    }
    
    print("1. 사용자 등록 처리 중...")
    reg_result = registration_pipeline(registration_data)
    
    if reg_result.is_success():
        new_user = reg_result.unwrap()
        print(f"✅ 사용자 등록 성공!")
        print(f"   사용자 ID: {new_user.user_id}")
        print(f"   이메일: {new_user.email}")
        print(f"   상태: {new_user.status.value}")
        print(f"   역할: {new_user.role.value}\n")
    else:
        print(f"❌ 등록 실패: {reg_result.unwrap_error()}\n")
        return
    
    # Rule 2: 파이프라인으로 로그인 처리
    login_pipeline = create_login_pipeline()
    
    login_credentials = {
        'email': 'user@example.com',
        'password': 'SecurePass123'
    }
    
    print("2. 로그인 처리 중...")
    login_result = login_pipeline(login_credentials)
    
    if login_result.is_success():
        session_data = login_result.unwrap()
        user = session_data['user']
        print(f"✅ 로그인 성공!")
        print(f"   세션 토큰: {session_data['session_token'][:16]}...")
        print(f"   만료 시간: {session_data['expires_at']}")
        print(f"   마지막 로그인: {user.last_login}\n")
    else:
        print(f"❌ 로그인 실패: {login_result.unwrap_error()}\n")
        return
    
    # Rule 3: 설정 기반 권한 검사
    permission_checker = create_permission_checker('user_profile', 'read')
    user = session_data['user']
    
    print("3. 권한 검사 중...")
    perm_result = permission_checker('user_operations', user)
    
    if perm_result.is_success():
        print("✅ 권한 검사 통과!")
        print(f"   사용자 {user.username}는 프로필 읽기 권한이 있습니다\n")
    else:
        print(f"❌ 권한 부족: {perm_result.unwrap_error()}\n")
    
    # Rule 3: 설정 기반 프로필 업데이트
    profile_updater = create_user_profile_updater()
    
    profile_updates = {
        'display_name': '테스트 사용자',
        'bio': '함수형 프로그래밍을 배우고 있습니다',
        'preferences': {
            'language': 'ko',
            'theme': 'dark'
        }
    }
    
    print("4. 프로필 업데이트 중...")
    update_result = profile_updater(user, profile_updates)
    
    if update_result.is_success():
        updated_user = update_result.unwrap()
        print("✅ 프로필 업데이트 성공!")
        print(f"   업데이트된 사용자: {updated_user.username}")
    else:
        print(f"❌ 프로필 업데이트 실패: {update_result.unwrap_error()}")


# =============================================================================
# Mock functions (실제 구현에서는 별도 모듈에서 제공)
# =============================================================================

def _username_exists(username: str) -> bool:
    """사용자명 존재 여부를 확인합니다 (Mock)."""
    return username in ['admin', 'test', 'user123']


def _email_exists(email: str) -> bool:
    """이메일 존재 여부를 확인합니다 (Mock)."""
    return email in ['admin@example.com', 'test@example.com']


def _save_user_to_db(user: User) -> bool:
    """사용자를 데이터베이스에 저장합니다 (Mock)."""
    print(f"💾 DB 저장: {user.username} ({user.email})")
    return True


def _update_user_in_db(user: User) -> bool:
    """사용자 정보를 업데이트합니다 (Mock)."""
    return True


def _generate_activation_token(user_id: str) -> str:
    """활성화 토큰을 생성합니다 (Mock)."""
    return secrets.token_urlsafe(32)


def _send_email(to: str, subject: str, body: str) -> bool:
    """이메일을 발송합니다 (Mock)."""
    print(f"📧 이메일 발송: {to} - {subject}")
    return True


def _get_user_by_email(email: str) -> Optional[User]:
    """이메일로 사용자를 조회합니다 (Mock)."""
    if email == 'user@example.com':
        return User(
            user_id='user_12345',
            email=email,
            username='testuser',
            password_hash='salt:hash',  # 실제로는 적절한 해시
            role=UserRole.USER,
            status=AccountStatus.ACTIVE,
            created_at=datetime.now() - timedelta(days=30)
        )
    return None


def _store_session(token: str, user_id: str, expiry: datetime) -> bool:
    """세션을 저장합니다 (Mock)."""
    print(f"🔐 세션 저장: {user_id} -> {token[:16]}... (만료: {expiry})")
    return True


def _get_user_usage(user_id: str) -> dict:
    """사용자 사용량을 조회합니다 (Mock)."""
    return {
        'api_calls': 10,
        'profile_updates': 2,
        'login_attempts': 1
    }


def _log_admin_action(user_id: str, action: str, args: tuple) -> None:
    """관리자 작업을 로깅합니다 (Mock)."""
    print(f"🔒 관리자 작업 로그: {user_id} -> {action}")


def _validate_profile_data(data: dict) -> dict:
    """프로필 데이터를 검증합니다 (Mock)."""
    return data


def _update_user_profile(user: User, data: dict) -> User:
    """사용자 프로필을 업데이트합니다 (Mock)."""
    return user


if __name__ == "__main__":
    example_usage()