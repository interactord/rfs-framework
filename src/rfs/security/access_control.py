"""
RFS v4.1 Access Control Decorators
접근 제어 어노테이션 구현

주요 기능:
- @RequiresRole: 역할 기반 접근 제어
- @RequiresPermission: 권한 기반 접근 제어
- @RequiresAuthentication: 인증 필수
- @RequiresOwnership: 소유권 검증
"""

import asyncio
import functools
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

import jwt

from ..core.result import Failure, Result, Success

logger = logging.getLogger(__name__)


class Role(Enum):
    """사용자 역할"""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"
    GUEST = "guest"
    SERVICE = "service"

    @property
    def level(self) -> int:
        """역할 레벨 (높을수록 권한이 많음)"""
        levels = {
            Role.SUPER_ADMIN: 100,
            Role.ADMIN: 80,
            Role.MODERATOR: 60,
            Role.USER: 40,
            Role.GUEST: 20,
            Role.SERVICE: 90,
        }
        return levels.get(self, 0)

    def has_role(self, required_role: "Role") -> bool:
        """해당 역할 이상의 권한이 있는지 확인"""
        return self.level >= required_role.level


class Permission(Enum):
    """권한"""

    READ = "read"
    READ_OWN = "read_own"
    READ_ALL = "read_all"
    WRITE = "write"
    WRITE_OWN = "write_own"
    WRITE_ALL = "write_all"
    DELETE = "delete"
    DELETE_OWN = "delete_own"
    DELETE_ALL = "delete_all"
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    MANAGE_PERMISSIONS = "manage_permissions"
    MANAGE_SYSTEM = "manage_system"
    EXECUTE = "execute"
    APPROVE = "approve"
    AUDIT = "audit"
    DEPLOY = "deploy"


@dataclass
class User:
    """사용자 정보"""

    id: str
    username: str
    email: str
    roles: Set[Role] = field(default_factory=set)
    permissions: Set[Permission] = field(default_factory=set)
    is_active = True
    is_verified = False
    created_at: datetime = field(default_factory=datetime.now)
    last_login = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_role(self, role: Union[Role, str]) -> bool:
        """역할 확인"""
        if type(role).__name__ == "str":
            role = Role(role)
        for user_role in self.roles:
            if user_role.has_role(role):
                return True
        return False

    def has_permission(self, permission: Union[Permission, str]) -> bool:
        """권한 확인"""
        if type(permission).__name__ == "str":
            permission = Permission(permission)
        if permission in self.permissions:
            return True
        if Role.SUPER_ADMIN in self.roles:
            return True
        if Role.ADMIN in self.roles and permission != Permission.MANAGE_SYSTEM:
            return True
        return False

    def has_any_role(self, roles: List[Union[Role, str]]) -> bool:
        """여러 역할 중 하나라도 있는지 확인"""
        for role in roles:
            if self.has_role(role):
                return True
        return False

    def has_all_permissions(self, permissions: List[Union[Permission, str]]) -> bool:
        """모든 권한이 있는지 확인"""
        for permission in permissions:
            if not self.has_permission(permission):
                return False
        return True


class AuthContext:
    """인증 컨텍스트"""

    def __init__(self):
        self._current_user = None
        self._token = None
        self._session_id = None

    @property
    def current_user(self) -> Optional[User]:
        """현재 사용자"""
        return self._current_user

    @current_user.setter
    def current_user(self, user: User):
        """사용자 설정"""
        self._current_user = user

    @property
    def is_authenticated(self) -> bool:
        """인증 여부"""
        return self._current_user is not None and self._current_user.is_active

    def clear(self):
        """컨텍스트 초기화"""
        self._current_user = None
        self._token = None
        self._session_id = None


_auth_context = AuthContext()


class AccessControlError(Exception):
    """접근 제어 에러"""

    pass


class AuthenticationError(AccessControlError):
    """인증 에러"""

    pass


class AuthorizationError(AccessControlError):
    """인가 에러"""

    pass


def get_current_user() -> Optional[User]:
    """현재 사용자 가져오기"""
    return _auth_context.current_user


def set_current_user(user: User) -> None:
    """현재 사용자 설정"""
    _auth_context.current_user = user


def clear_auth_context() -> None:
    """인증 컨텍스트 초기화"""
    _auth_context = {}


def RequiresAuthentication(allow_service_account=True, check_verified=False):
    """
    인증 필수 데코레이터

    Args:
        allow_service_account: 서비스 계정 허용 여부
        check_verified: 이메일 인증 확인 여부
    """

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                logger.warning(f"Unauthenticated access attempt to {func.__name__}")
                raise AuthenticationError("Authentication required")
            if not user.is_active:
                logger.warning(
                    f"Inactive user {user.username} attempted to access {func.__name__}"
                )
                raise AuthenticationError("User account is inactive")
            if check_verified and (not user.is_verified):
                logger.warning(
                    f"Unverified user {user.username} attempted to access {func.__name__}"
                )
                raise AuthenticationError("Email verification required")
            if not allow_service_account and Role.SERVICE in user.roles:
                logger.warning(
                    f"Service account {user.username} denied access to {func.__name__}"
                )
                raise AuthorizationError("Service accounts not allowed")
            if "current_user" not in kwargs:
                kwargs["current_user"] = {"current_user": user}
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                logger.warning(f"Unauthenticated access attempt to {func.__name__}")
                raise AuthenticationError("Authentication required")
            if not user.is_active:
                logger.warning(
                    f"Inactive user {user.username} attempted to access {func.__name__}"
                )
                raise AuthenticationError("User account is inactive")
            if check_verified and (not user.is_verified):
                logger.warning(
                    f"Unverified user {user.username} attempted to access {func.__name__}"
                )
                raise AuthenticationError("Email verification required")
            if not allow_service_account and Role.SERVICE in user.roles:
                logger.warning(
                    f"Service account {user.username} denied access to {func.__name__}"
                )
                raise AuthorizationError("Service accounts not allowed")
            if "current_user" not in kwargs:
                kwargs["current_user"] = {"current_user": user}
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def RequiresRole(
    *required_roles: Union[Role, str],
    require_all=False,
    allow_higher=True,
):
    """
    역할 기반 접근 제어 데코레이터

    Args:
        required_roles: 필요한 역할들
        require_all: 모든 역할 필요 여부 (False면 하나만 있어도 됨)
        allow_higher: 상위 역할 허용 여부
    """

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                logger.warning(f"Unauthenticated access attempt to {func.__name__}")
                raise AuthenticationError("Authentication required")
            roles = []
            for role in required_roles:
                if type(role).__name__ == "str":
                    roles = roles + [Role(role)]
                else:
                    roles = roles + [role]
            if require_all:
                for role in roles:
                    if not user.has_role(role):
                        logger.warning(
                            f"User {user.username} lacks role {role.value} for {func.__name__}"
                        )
                        raise AuthorizationError(f"Role {role.value} required")
            else:
                has_any = False
                for role in roles:
                    if user.has_role(role):
                        has_any = True
                        break
                if not has_any:
                    role_names = [r.value for r in roles]
                    logger.warning(
                        f"User {user.username} lacks any of roles {role_names} for {func.__name__}"
                    )
                    raise AuthorizationError(f"One of roles {role_names} required")
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                logger.warning(f"Unauthenticated access attempt to {func.__name__}")
                raise AuthenticationError("Authentication required")
            roles = []
            for role in required_roles:
                if type(role).__name__ == "str":
                    roles = roles + [Role(role)]
                else:
                    roles = roles + [role]
            if require_all:
                for role in roles:
                    if not user.has_role(role):
                        logger.warning(
                            f"User {user.username} lacks role {role.value} for {func.__name__}"
                        )
                        raise AuthorizationError(f"Role {role.value} required")
            else:
                has_any = False
                for role in roles:
                    if user.has_role(role):
                        has_any = True
                        break
                if not has_any:
                    role_names = [r.value for r in roles]
                    logger.warning(
                        f"User {user.username} lacks any of roles {role_names} for {func.__name__}"
                    )
                    raise AuthorizationError(f"One of roles {role_names} required")
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def RequiresPermission(*required_permissions: Union[Permission, str], require_all=True):
    """
    권한 기반 접근 제어 데코레이터

    Args:
        required_permissions: 필요한 권한들
        require_all: 모든 권한 필요 여부
    """

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                logger.warning(f"Unauthenticated access attempt to {func.__name__}")
                raise AuthenticationError("Authentication required")
            permissions = []
            for perm in required_permissions:
                if type(perm).__name__ == "str":
                    permissions = permissions + [Permission(perm)]
                else:
                    permissions = permissions + [perm]
            if require_all:
                for perm in permissions:
                    if not user.has_permission(perm):
                        logger.warning(
                            f"User {user.username} lacks permission {perm.value} for {func.__name__}"
                        )
                        raise AuthorizationError(f"Permission {perm.value} required")
            else:
                has_any = False
                for perm in permissions:
                    if user.has_permission(perm):
                        has_any = True
                        break
                if not has_any:
                    perm_names = [p.value for p in permissions]
                    logger.warning(
                        f"User {user.username} lacks any of permissions {perm_names} for {func.__name__}"
                    )
                    raise AuthorizationError(
                        f"One of permissions {perm_names} required"
                    )
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                logger.warning(f"Unauthenticated access attempt to {func.__name__}")
                raise AuthenticationError("Authentication required")
            permissions = []
            for perm in required_permissions:
                if type(perm).__name__ == "str":
                    permissions = permissions + [Permission(perm)]
                else:
                    permissions = permissions + [perm]
            if require_all:
                for perm in permissions:
                    if not user.has_permission(perm):
                        logger.warning(
                            f"User {user.username} lacks permission {perm.value} for {func.__name__}"
                        )
                        raise AuthorizationError(f"Permission {perm.value} required")
            else:
                has_any = False
                for perm in permissions:
                    if user.has_permission(perm):
                        has_any = True
                        break
                if not has_any:
                    perm_names = [p.value for p in permissions]
                    logger.warning(
                        f"User {user.username} lacks any of permissions {perm_names} for {func.__name__}"
                    )
                    raise AuthorizationError(
                        f"One of permissions {perm_names} required"
                    )
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def RequiresOwnership(
    resource_id_param="id",
    owner_field="user_id",
    allow_admin=True,
    custom_checker=None,
):
    """
    소유권 검증 데코레이터

    Args:
        resource_id_param: 리소스 ID 파라미터 이름
        owner_field: 소유자 필드 이름
        allow_admin: 관리자 허용 여부
        custom_checker: 커스텀 소유권 확인 함수
    """

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                logger.warning(f"Unauthenticated access attempt to {func.__name__}")
                raise AuthenticationError("Authentication required")
            if allow_admin and (
                Role.ADMIN in user.roles or Role.SUPER_ADMIN in user.roles
            ):
                return await func(*args, **kwargs)
            if custom_checker:
                resource_id = kwargs.get(resource_id_param)
                if resource_id:
                    is_owner = (
                        await custom_checker(user, resource_id)
                        if asyncio.iscoroutinefunction(custom_checker)
                        else custom_checker(user, resource_id)
                    )
                    if not is_owner:
                        logger.warning(
                            f"User {user.username} denied ownership access to resource {resource_id}"
                        )
                        raise AuthorizationError(
                            "Access denied: Not the resource owner"
                        )
            else:
                owner_id = kwargs.get(owner_field)
                if owner_id and owner_id != user.id:
                    logger.warning(
                        f"User {user.username} denied ownership access (owner: {owner_id})"
                    )
                    raise AuthorizationError("Access denied: Not the resource owner")
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                logger.warning(f"Unauthenticated access attempt to {func.__name__}")
                raise AuthenticationError("Authentication required")
            if allow_admin and (
                Role.ADMIN in user.roles or Role.SUPER_ADMIN in user.roles
            ):
                return func(*args, **kwargs)
            if custom_checker:
                resource_id = kwargs.get(resource_id_param)
                if resource_id:
                    is_owner = custom_checker(user, resource_id)
                    if not is_owner:
                        logger.warning(
                            f"User {user.username} denied ownership access to resource {resource_id}"
                        )
                        raise AuthorizationError(
                            "Access denied: Not the resource owner"
                        )
            else:
                owner_id = kwargs.get(owner_field)
                if owner_id and owner_id != user.id:
                    logger.warning(
                        f"User {user.username} denied ownership access (owner: {owner_id})"
                    )
                    raise AuthorizationError("Access denied: Not the resource owner")
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class TokenManager:
    """JWT 토큰 관리자"""

    def __init__(
        self,
        secret_key="your-secret-key",
        algorithm="HS256",
        access_token_expire=3600,
        refresh_token_expire=86400 * 7,
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire = access_token_expire
        self.refresh_token_expire = refresh_token_expire

    def create_access_token(self, user: User) -> str:
        """액세스 토큰 생성"""
        payload = {
            "user_id": user.id,
            "username": user.username,
            "roles": [role.value for role in user.roles],
            "exp": datetime.utcnow() + timedelta(seconds=self.access_token_expire),
            "iat": datetime.utcnow(),
            "type": "access",
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user: User) -> str:
        """리프레시 토큰 생성"""
        payload = {
            "user_id": user.id,
            "exp": datetime.utcnow() + timedelta(seconds=self.refresh_token_expire),
            "iat": datetime.utcnow(),
            "type": "refresh",
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str, token_type="access") -> Optional[Dict[str, Any]]:
        """토큰 검증"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != token_type:
                return None
            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"Invalid token: {e}")
            return None


_token_manager = TokenManager()


def get_token_manager() -> TokenManager:
    """토큰 관리자 가져오기"""
    return _token_manager


__all__ = [
    "RequiresAuthentication",
    "RequiresRole",
    "RequiresPermission",
    "RequiresOwnership",
    "Role",
    "Permission",
    "User",
    "AuthContext",
    "AccessControlError",
    "AuthenticationError",
    "AuthorizationError",
    "get_current_user",
    "set_current_user",
    "clear_auth_context",
    "TokenManager",
    "get_token_manager",
]
