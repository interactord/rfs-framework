# 접근 제어 (Access Control)

## 📌 개요

RFS Framework의 접근 제어 시스템은 RBAC(역할 기반)과 ABAC(속성 기반) 접근 제어를 제공합니다. 데코레이터 기반의 선언적 보안 모델로 인증, 인가, 소유권 검증을 지원합니다.

## 🎯 핵심 개념

### 인증 vs 인가
- **인증(Authentication)**: 사용자가 누구인지 확인
- **인가(Authorization)**: 사용자가 특정 작업을 수행할 권한이 있는지 확인

### 역할 기반 접근 제어 (RBAC)
- **역할(Role)**: 사용자에게 할당되는 권한 집합
- **권한(Permission)**: 특정 리소스에 대한 작업 권한
- **계층적 역할**: 상위 역할이 하위 역할의 권한을 포함

### 속성 기반 접근 제어 (ABAC)
- **속성(Attribute)**: 사용자, 리소스, 환경의 특성
- **정책(Policy)**: 속성 기반의 접근 제어 규칙
- **동적 제어**: 컨텍스트에 따른 동적 권한 부여

## 📚 API 레퍼런스

### 역할 정의

```python
from rfs.security.access_control import Role

class Role(Enum):
    SUPER_ADMIN = "super_admin"    # 최고 관리자 (레벨 100)
    ADMIN = "admin"                # 관리자 (레벨 80)
    MODERATOR = "moderator"        # 운영자 (레벨 60)
    USER = "user"                  # 일반 사용자 (레벨 40)
    GUEST = "guest"               # 게스트 (레벨 20)
    SERVICE = "service"           # 서비스 계정 (레벨 90)
```

### 권한 정의

```python
from rfs.security.access_control import Permission

class Permission(Enum):
    # 읽기 권한
    READ = "read"
    READ_OWN = "read_own"
    READ_ALL = "read_all"
    
    # 쓰기 권한
    WRITE = "write"
    WRITE_OWN = "write_own"
    WRITE_ALL = "write_all"
    
    # 삭제 권한
    DELETE = "delete"
    DELETE_OWN = "delete_own"
    DELETE_ALL = "delete_all"
    
    # 관리 권한
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    MANAGE_PERMISSIONS = "manage_permissions"
    MANAGE_SYSTEM = "manage_system"
```

### 데코레이터 API

| 데코레이터 | 설명 | 주요 매개변수 |
|-----------|------|--------------|
| `@RequiresAuthentication` | 인증 필수 | `allow_service_account`, `check_verified` |
| `@RequiresRole` | 역할 기반 제어 | `*required_roles`, `require_all`, `allow_higher` |
| `@RequiresPermission` | 권한 기반 제어 | `*required_permissions`, `require_all` |
| `@RequiresOwnership` | 소유권 검증 | `resource_id_param`, `owner_field`, `allow_admin` |

## 💡 사용 예제

### 기본 인증 제어

```python
from rfs.security.access_control import (
    RequiresAuthentication,
    RequiresRole,
    RequiresPermission,
    Role,
    Permission,
    User,
    set_current_user
)
from rfs.core.result import Result, Success, Failure

# 사용자 생성 및 설정
user = User(
    id="user123",
    username="john_doe",
    email="john@example.com",
    roles={Role.USER},
    permissions={Permission.READ, Permission.WRITE_OWN}
)

# 현재 사용자 설정
set_current_user(user)

@RequiresAuthentication()
async def get_profile() -> Result[dict, str]:
    """프로필 조회 - 인증 필요"""
    return Success({"name": "John Doe", "email": "john@example.com"})

# 실행
try:
    result = await get_profile()
    print(result.unwrap())  # {'name': 'John Doe', 'email': 'john@example.com'}
except AuthenticationError as e:
    print(f"인증 오류: {e}")
```

### 역할 기반 접근 제어

```python
@RequiresRole(Role.ADMIN)
async def delete_user(user_id: str) -> Result[str, str]:
    """사용자 삭제 - 관리자만 가능"""
    try:
        # 사용자 삭제 로직
        await remove_user_from_db(user_id)
        return Success(f"사용자 {user_id} 삭제 완료")
    except Exception as e:
        return Failure(str(e))

@RequiresRole(Role.MODERATOR, Role.ADMIN, require_all=False)
async def moderate_content(content_id: str) -> Result[str, str]:
    """콘텐츠 조정 - 운영자 또는 관리자"""
    return Success(f"콘텐츠 {content_id} 조정 완료")

# 관리자 사용자로 실행
admin_user = User(
    id="admin1",
    username="admin",
    email="admin@example.com",
    roles={Role.ADMIN}
)
set_current_user(admin_user)

result = await delete_user("user123")
print(result.unwrap())  # "사용자 user123 삭제 완료"
```

### 권한 기반 접근 제어

```python
@RequiresPermission(Permission.WRITE_ALL)
async def create_global_announcement(message: str) -> Result[dict, str]:
    """전역 공지사항 생성 - 전체 쓰기 권한 필요"""
    announcement = {
        "id": "announce123",
        "message": message,
        "type": "global"
    }
    return Success(announcement)

@RequiresPermission(Permission.READ, Permission.WRITE_OWN, require_all=True)
async def update_own_post(post_id: str, updates: dict) -> Result[dict, str]:
    """자신의 게시글 수정 - 읽기와 개인 쓰기 권한 모두 필요"""
    try:
        # 게시글 업데이트 로직
        updated_post = {"id": post_id, **updates}
        return Success(updated_post)
    except Exception as e:
        return Failure(str(e))

# 권한이 있는 사용자로 설정
user_with_perms = User(
    id="user456",
    username="writer",
    email="writer@example.com",
    roles={Role.USER},
    permissions={Permission.READ, Permission.WRITE_OWN, Permission.WRITE_ALL}
)
set_current_user(user_with_perms)

# 실행
result = await create_global_announcement("시스템 업데이트 공지")
print(result.unwrap())
```

### 소유권 기반 접근 제어

```python
@RequiresOwnership(
    resource_id_param="post_id",
    owner_field="author_id",
    allow_admin=True
)
async def delete_post(post_id: str, author_id: str) -> Result[str, str]:
    """게시글 삭제 - 작성자 또는 관리자만 가능"""
    try:
        # 게시글 삭제 로직
        await remove_post_from_db(post_id)
        return Success(f"게시글 {post_id} 삭제 완료")
    except Exception as e:
        return Failure(str(e))

# 커스텀 소유권 확인 함수
async def check_document_ownership(user: User, resource_id: str) -> bool:
    """문서 소유권 확인"""
    document = await get_document_from_db(resource_id)
    return document and document.owner_id == user.id

@RequiresOwnership(
    resource_id_param="document_id",
    custom_checker=check_document_ownership,
    allow_admin=True
)
async def edit_document(document_id: str) -> Result[dict, str]:
    """문서 편집 - 소유자만 가능"""
    return Success({"message": f"문서 {document_id} 편집 완료"})

# 소유자로 실행
owner_user = User(
    id="user789",
    username="document_owner",
    email="owner@example.com",
    roles={Role.USER}
)
set_current_user(owner_user)

# 자신의 게시글 삭제 (author_id가 현재 사용자 ID와 일치)
result = await delete_post("post123", author_id="user789")
print(result.unwrap())
```

### 복합 보안 제어

```python
@RequiresAuthentication(check_verified=True)
@RequiresRole(Role.MODERATOR, Role.ADMIN, require_all=False)
@RequiresPermission(Permission.MANAGE_USERS)
async def suspend_user(
    target_user_id: str, 
    reason: str,
    current_user: User = None  # 자동으로 주입됨
) -> Result[dict, str]:
    """사용자 계정 정지 - 복합 보안 제어"""
    try:
        # 자신을 정지시키려는 시도 방지
        if current_user.id == target_user_id:
            return Failure("자신의 계정을 정지시킬 수 없습니다")
        
        # 상위 역할 사용자 정지 방지
        target_user = await get_user_from_db(target_user_id)
        if target_user.has_role(Role.SUPER_ADMIN):
            return Failure("최고 관리자 계정은 정지시킬 수 없습니다")
        
        # 계정 정지 실행
        suspension_result = {
            "target_user_id": target_user_id,
            "suspended_by": current_user.id,
            "reason": reason,
            "suspended_at": datetime.now().isoformat()
        }
        
        await suspend_user_in_db(target_user_id, suspension_result)
        
        return Success(suspension_result)
        
    except Exception as e:
        return Failure(f"사용자 정지 실패: {str(e)}")

# 권한이 있는 운영자로 설정
moderator = User(
    id="mod1",
    username="moderator",
    email="mod@example.com",
    roles={Role.MODERATOR},
    permissions={Permission.MANAGE_USERS},
    is_verified=True
)
set_current_user(moderator)

result = await suspend_user("spam_user123", "스팸 활동")
print(result.unwrap())
```

### JWT 토큰 기반 인증

```python
from rfs.security.access_control import TokenManager, get_token_manager
import jwt

# 토큰 매니저 설정
token_manager = TokenManager(
    secret_key="your-super-secret-key",
    access_token_expire=3600,    # 1시간
    refresh_token_expire=604800  # 7일
)

# 사용자 로그인 및 토큰 생성
async def login_user(username: str, password: str) -> Result[dict, str]:
    """사용자 로그인"""
    try:
        # 사용자 인증
        user = await authenticate_user_credentials(username, password)
        if not user:
            return Failure("잘못된 인증 정보")
        
        # JWT 토큰 생성
        access_token = token_manager.create_access_token(user)
        refresh_token = token_manager.create_refresh_token(user)
        
        # 현재 사용자 설정
        set_current_user(user)
        
        return Success({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "user": {
                "id": user.id,
                "username": user.username,
                "roles": [role.value for role in user.roles]
            }
        })
        
    except Exception as e:
        return Failure(f"로그인 실패: {str(e)}")

# 토큰 검증 미들웨어
async def verify_token_middleware(token: str) -> Result[User, str]:
    """JWT 토큰 검증"""
    try:
        # 토큰 검증
        payload = token_manager.verify_token(token)
        if not payload:
            return Failure("유효하지 않은 토큰")
        
        # 사용자 정보 로드
        user = await get_user_by_id(payload["user_id"])
        if not user or not user.is_active:
            return Failure("비활성 사용자")
        
        # 현재 사용자 설정
        set_current_user(user)
        
        return Success(user)
        
    except Exception as e:
        return Failure(f"토큰 검증 실패: {str(e)}")

# 토큰 갱신
async def refresh_access_token(refresh_token: str) -> Result[dict, str]:
    """액세스 토큰 갱신"""
    try:
        # 리프레시 토큰 검증
        payload = token_manager.verify_token(refresh_token, "refresh")
        if not payload:
            return Failure("유효하지 않은 리프레시 토큰")
        
        # 사용자 로드
        user = await get_user_by_id(payload["user_id"])
        if not user or not user.is_active:
            return Failure("비활성 사용자")
        
        # 새 액세스 토큰 생성
        new_access_token = token_manager.create_access_token(user)
        
        return Success({
            "access_token": new_access_token,
            "token_type": "Bearer",
            "expires_in": 3600
        })
        
    except Exception as e:
        return Failure(f"토큰 갱신 실패: {str(e)}")
```

### 동적 권한 제어

```python
from datetime import datetime, time

class DynamicAccessController:
    """동적 접근 제어"""
    
    @staticmethod
    async def check_business_hours() -> bool:
        """업무 시간 확인"""
        now = datetime.now().time()
        business_start = time(9, 0)  # 오전 9시
        business_end = time(18, 0)   # 오후 6시
        return business_start <= now <= business_end
    
    @staticmethod
    async def check_ip_whitelist(user_ip: str) -> bool:
        """IP 화이트리스트 확인"""
        allowed_ips = ["192.168.1.0/24", "10.0.0.0/8"]
        # IP 범위 확인 로직 (실제로는 ipaddress 모듈 사용)
        return True  # 간소화
    
    @staticmethod
    async def check_security_level(user: User, required_level: int) -> bool:
        """보안 레벨 확인"""
        user_level = getattr(user, 'security_level', 0)
        return user_level >= required_level

def RequiresBusinessHours():
    """업무 시간 중에만 접근 허용"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not await DynamicAccessController.check_business_hours():
                raise AuthorizationError("업무 시간 중에만 접근 가능합니다")
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def RequiresSecureNetwork(ip_param: str = "user_ip"):
    """안전한 네트워크에서만 접근 허용"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            user_ip = kwargs.get(ip_param)
            if user_ip and not await DynamicAccessController.check_ip_whitelist(user_ip):
                raise AuthorizationError("허용되지 않은 IP에서의 접근입니다")
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# 동적 제어 적용
@RequiresAuthentication()
@RequiresRole(Role.ADMIN)
@RequiresBusinessHours()
@RequiresSecureNetwork()
async def perform_maintenance(
    maintenance_type: str,
    user_ip: str = None
) -> Result[str, str]:
    """시스템 유지보수 - 복합 동적 제어"""
    try:
        # 유지보수 작업 실행
        maintenance_id = f"maint_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        result = f"유지보수 작업 시작: {maintenance_type} (ID: {maintenance_id})"
        return Success(result)
        
    except Exception as e:
        return Failure(f"유지보수 작업 실패: {str(e)}")
```

### 리소스별 세부 권한 제어

```python
from enum import Enum
from typing import Dict, Set

class ResourceType(Enum):
    USER = "user"
    POST = "post" 
    COMMENT = "comment"
    FILE = "file"
    SYSTEM = "system"

class ResourcePermissionManager:
    """리소스별 권한 관리"""
    
    def __init__(self):
        # 역할별 리소스 권한 매트릭스
        self.permission_matrix: Dict[Role, Dict[ResourceType, Set[Permission]]] = {
            Role.SUPER_ADMIN: {
                ResourceType.USER: {Permission.READ_ALL, Permission.WRITE_ALL, Permission.DELETE_ALL},
                ResourceType.POST: {Permission.READ_ALL, Permission.WRITE_ALL, Permission.DELETE_ALL},
                ResourceType.COMMENT: {Permission.READ_ALL, Permission.WRITE_ALL, Permission.DELETE_ALL},
                ResourceType.FILE: {Permission.READ_ALL, Permission.WRITE_ALL, Permission.DELETE_ALL},
                ResourceType.SYSTEM: {Permission.MANAGE_SYSTEM}
            },
            Role.ADMIN: {
                ResourceType.USER: {Permission.READ_ALL, Permission.WRITE_ALL, Permission.DELETE_ALL},
                ResourceType.POST: {Permission.READ_ALL, Permission.WRITE_ALL, Permission.DELETE_ALL},
                ResourceType.COMMENT: {Permission.READ_ALL, Permission.WRITE_ALL, Permission.DELETE_ALL},
                ResourceType.FILE: {Permission.READ_ALL, Permission.WRITE_OWN, Permission.DELETE_OWN}
            },
            Role.MODERATOR: {
                ResourceType.POST: {Permission.READ_ALL, Permission.WRITE_ALL, Permission.DELETE_ALL},
                ResourceType.COMMENT: {Permission.READ_ALL, Permission.WRITE_ALL, Permission.DELETE_ALL},
                ResourceType.USER: {Permission.READ_ALL}
            },
            Role.USER: {
                ResourceType.POST: {Permission.READ, Permission.WRITE_OWN, Permission.DELETE_OWN},
                ResourceType.COMMENT: {Permission.READ, Permission.WRITE_OWN, Permission.DELETE_OWN},
                ResourceType.FILE: {Permission.READ, Permission.WRITE_OWN, Permission.DELETE_OWN},
                ResourceType.USER: {Permission.READ_OWN}
            }
        }
    
    def has_resource_permission(
        self, 
        user: User, 
        resource_type: ResourceType, 
        permission: Permission
    ) -> bool:
        """사용자의 특정 리소스에 대한 권한 확인"""
        for role in user.roles:
            if role in self.permission_matrix:
                resource_perms = self.permission_matrix[role].get(resource_type, set())
                if permission in resource_perms:
                    return True
        
        # 직접 권한도 확인
        return permission in user.permissions

# 글로벌 권한 매니저
resource_permission_manager = ResourcePermissionManager()

def RequiresResourcePermission(
    resource_type: ResourceType, 
    permission: Permission
):
    """리소스별 세부 권한 확인"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                raise AuthenticationError("Authentication required")
            
            if not resource_permission_manager.has_resource_permission(
                user, resource_type, permission
            ):
                raise AuthorizationError(
                    f"Permission {permission.value} required for {resource_type.value}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# 리소스별 권한 제어 적용
@RequiresResourcePermission(ResourceType.POST, Permission.DELETE_ALL)
async def delete_any_post(post_id: str) -> Result[str, str]:
    """모든 게시글 삭제 권한 필요"""
    return Success(f"게시글 {post_id} 삭제 완료")

@RequiresResourcePermission(ResourceType.USER, Permission.READ_ALL)
async def list_all_users() -> Result[list, str]:
    """모든 사용자 조회 권한 필요"""
    users = await get_all_users_from_db()
    return Success(users)
```

## 🎨 베스트 프랙티스

### 1. 계층적 권한 설계

```python
# ✅ 좋은 예 - 명확한 권한 계층
@RequiresRole(Role.ADMIN)  # 관리자는 자동으로 하위 역할 권한 포함
async def admin_function():
    pass

@RequiresPermission(Permission.WRITE_OWN)  # 최소 권한 원칙
async def update_own_profile():
    pass
```

### 2. 에러 처리

```python
# ✅ 좋은 예 - 적절한 에러 처리
@RequiresRole(Role.MODERATOR)
async def moderate_content(content_id: str) -> Result[str, str]:
    try:
        # 권한이 있는 경우에만 실행
        result = await perform_moderation(content_id)
        return Success(result)
    except AuthenticationError:
        return Failure("로그인이 필요합니다")
    except AuthorizationError:
        return Failure("권한이 부족합니다")
    except Exception as e:
        return Failure(f"작업 실행 실패: {str(e)}")
```

### 3. 보안 로깅

```python
from rfs.core.logging_decorators import AuditLogged, AuditEventType

# ✅ 좋은 예 - 민감한 작업에 감사 로그 추가
@RequiresRole(Role.ADMIN)
@AuditLogged(
    event_type=AuditEventType.SECURITY_EVENT,
    resource_type="user_role",
    include_changes=True
)
async def change_user_role(
    target_user_id: str, 
    new_role: Role,
    user_id: str = None  # 감사 로그용
) -> Result[str, str]:
    """사용자 역할 변경 - 보안 이벤트 로깅"""
    # 역할 변경 로직
    return Success(f"사용자 {target_user_id}의 역할을 {new_role.value}로 변경")
```

### 4. 테스트 친화적 설계

```python
# ✅ 좋은 예 - 테스트용 사용자 설정 유틸리티
def create_test_user(
    roles: Set[Role] = None,
    permissions: Set[Permission] = None
) -> User:
    """테스트용 사용자 생성"""
    return User(
        id="test_user",
        username="test",
        email="test@example.com",
        roles=roles or {Role.USER},
        permissions=permissions or set(),
        is_active=True,
        is_verified=True
    )

# 테스트에서 사용
async def test_admin_function():
    # 관리자 권한으로 테스트
    admin_user = create_test_user(roles={Role.ADMIN})
    set_current_user(admin_user)
    
    result = await admin_only_function()
    assert result.is_success()
    
    # 권한 정리
    clear_auth_context()
```

## ⚠️ 주의사항

### 1. 권한 에스컬레이션 방지
- 사용자가 자신의 권한을 상승시킬 수 없도록 제한
- 관리자도 최고 관리자 권한을 획득할 수 없도록 설계

### 2. 세션 관리
- JWT 토큰의 적절한 만료 시간 설정
- 리프레시 토큰 로테이션 구현
- 로그아웃 시 토큰 무효화

### 3. 보안 감사
- 모든 권한 변경사항 로깅
- 민감한 작업에 대한 감사 추적
- 비정상적인 접근 패턴 모니터링

### 4. 성능 고려사항
- 권한 확인 로직의 성능 최적화
- 캐싱을 통한 반복 권한 확인 최소화
- 데이터베이스 쿼리 최적화

## 🔗 관련 문서
- [로깅](./07-logging.md) - 보안 이벤트 감사 로깅
- [보안](./11-security.md) - 종합 보안 패턴
- [유효성 검사](./09-validation.md) - 입력 데이터 검증
- [모니터링](./08-monitoring.md) - 보안 메트릭 수집