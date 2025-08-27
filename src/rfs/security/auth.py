"""
RFS Authentication & Authorization (RFS v4.1)

인증 및 인가 시스템
"""

import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from ..core.enhanced_logging import get_logger
from ..core.result import Failure, Result, Success

logger = get_logger(__name__)


class AuthMethod(Enum):
    """인증 방법"""

    JWT = "jwt"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    API_KEY = "api_key"
    SAML = "saml"


class TokenType(Enum):
    """토큰 타입"""

    ACCESS = "access"
    REFRESH = "refresh"
    RESET = "reset"
    VERIFY = "verify"


@dataclass
class Permission:
    """권한"""

    name: str
    resource: str
    action: str

    def __str__(self) -> str:
        return f"{self.resource}:{self.action}"


@dataclass
class Role:
    """역할"""

    name: str
    permissions: Set[Permission]
    description = None

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions

    def has_permission_for(self, resource: str, action: str) -> bool:
        for perm in self.permissions:
            if perm.resource == resource and perm.action == action:
                return True
        return False


@dataclass
class User:
    """사용자"""

    id: str
    username: str
    email: str
    roles: Set[Role]
    is_active = True
    is_verified = False
    created_at = None
    last_login = None

    def has_role(self, role_name: str) -> bool:
        return any((role.name == role_name for role in self.roles))

    def has_permission(self, permission: Permission) -> bool:
        return any((role.has_permission(permission) for role in self.roles))

    def has_permission_for(self, resource: str, action: str) -> bool:
        return any((role.has_permission_for(resource, action) for role in self.roles))


@dataclass
class UserSession:
    """사용자 세션"""

    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    ip_address = None
    user_agent = None
    is_active = True

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


@dataclass
class JWTToken:
    """JWT 토큰"""

    token: str
    payload: Dict[str, Any]
    expires_at: datetime
    token_type: TokenType

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


@dataclass
class RefreshToken:
    """리프레시 토큰"""

    token: str
    user_id: str
    expires_at: datetime
    is_used = False

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


class AuthProvider(ABC):
    """인증 제공자 추상 클래스"""

    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> Result[User, str]:
        """사용자 인증"""
        pass

    @abstractmethod
    async def validate_token(self, token: str) -> Result[User, str]:
        """토큰 검증"""
        pass


class JWTAuthProvider(AuthProvider):
    """JWT 인증 제공자"""

    def __init__(self, secret_key: str, algorithm="HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm

    def _encode_jwt(self, payload: Dict[str, Any]) -> str:
        """JWT 인코딩"""
        header = {"alg": self.algorithm, "typ": "JWT"}
        header_b64 = (
            base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        )
        payload_b64 = (
            base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        )
        message = f"{header_b64}.{payload_b64}"
        signature = hmac.new(
            self.secret_key.encode(), message.encode(), hashlib.sha256
        ).digest()
        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        return f"{message}.{signature_b64}"

    def _decode_jwt(self, token: str) -> Result[Dict[str, Any], str]:
        """JWT 디코딩"""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return Failure("잘못된 JWT 형식")
            header_b64, payload_b64, signature_b64 = parts
            message = f"{header_b64}.{payload_b64}"
            expected_signature = hmac.new(
                self.secret_key.encode(), message.encode(), hashlib.sha256
            ).digest()
            signature_b64 = signature_b64 + "=" * (4 - len(signature_b64) % 4)
            actual_signature = base64.urlsafe_b64decode(signature_b64)
            if not hmac.compare_digest(expected_signature, actual_signature):
                return Failure("JWT 서명 검증 실패")
            payload_b64 = payload_b64 + "=" * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            if "exp" in payload:
                if datetime.fromtimestamp(payload.get("exp")) < datetime.now():
                    return Failure("JWT 토큰 만료")
            return Success(payload)
        except Exception as e:
            return Failure(f"JWT 디코딩 실패: {str(e)}")

    async def authenticate(self, credentials: Dict[str, Any]) -> Result[User, str]:
        """JWT 기반 인증"""
        token = credentials.get("token")
        if not token:
            return Failure("토큰이 제공되지 않음")
        return await self.validate_token(token)

    async def validate_token(self, token: str) -> Result[User, str]:
        """JWT 토큰 검증"""
        decode_result = self._decode_jwt(token)
        if decode_result.is_failure():
            return decode_result
        payload = decode_result.unwrap()
        user_id = payload.get("sub")
        username = payload.get("username")
        email = payload.get("email")
        if not user_id:
            return Failure("JWT에 사용자 ID가 없음")
        roles: Set[Any] = set()
        role_names = payload.get("roles", [])
        for role_name in role_names:
            permissions = set(
                [Permission(name=f"{role_name}_perm", resource="*", action="*")]
            )
            roles.add(Role(name=role_name, permissions=permissions))
        user = User(
            id=user_id,
            username=username or user_id,
            email=email or f"{user_id}@example.com",
            roles=roles,
            is_active=payload.get("active", True),
            is_verified=payload.get("verified", False),
        )
        return Success(user)

    def generate_token(self, user: User, expires_in=3600) -> JWTToken:
        """JWT 토큰 생성"""
        now = datetime.now()
        expires_at = now + timedelta(seconds=expires_in)
        payload = {
            "sub": user.id,
            "username": user.username,
            "email": user.email,
            "roles": [role.name for role in user.roles],
            "active": user.is_active,
            "verified": user.is_verified,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = self._encode_jwt(payload)
        return JWTToken(
            token=token,
            payload=payload,
            expires_at=expires_at,
            token_type=TokenType.ACCESS,
        )


class OAuth2Provider(AuthProvider):
    """OAuth2 인증 제공자"""

    def __init__(
        self, client_id: str, client_secret: str, authorize_url: str, token_url: str
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorize_url = authorize_url
        self.token_url = token_url

    async def authenticate(self, credentials: Dict[str, Any]) -> Result[User, str]:
        """OAuth2 인증"""
        code = credentials.get("code")
        if not code:
            return Failure("OAuth2 authorization code가 제공되지 않음")
        return Failure("OAuth2 인증 미구현")

    async def validate_token(self, token: str) -> Result[User, str]:
        """OAuth2 토큰 검증"""
        return Failure("OAuth2 토큰 검증 미구현")


class TokenManager:
    """토큰 관리자"""

    def __init__(self, jwt_provider: JWTAuthProvider):
        self.jwt_provider = jwt_provider
        self.refresh_tokens = {}

    def generate_access_token(self, user: User, expires_in=3600) -> JWTToken:
        """액세스 토큰 생성"""
        return self.jwt_provider.generate_token(user, expires_in)

    def generate_refresh_token(self, user: User, expires_in=86400 * 30) -> RefreshToken:
        """리프레시 토큰 생성"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        refresh_token = RefreshToken(
            token=token, user_id=user.id, expires_at=expires_at
        )
        self.refresh_tokens = {**self.refresh_tokens, token: refresh_token}
        return refresh_token

    async def refresh_access_token(self, refresh_token: str) -> Result[JWTToken, str]:
        """리프레시 토큰으로 액세스 토큰 갱신"""
        if refresh_token not in self.refresh_tokens:
            return Failure("유효하지 않은 리프레시 토큰")
        token_obj = self.refresh_tokens[refresh_token]
        if token_obj.is_expired():
            del self.refresh_tokens[refresh_token]
            return Failure("만료된 리프레시 토큰")
        if token_obj.is_used:
            del self.refresh_tokens[refresh_token]
            return Failure("이미 사용된 리프레시 토큰")
        token_obj.is_used = True
        user = User(
            id=token_obj.user_id,
            username=token_obj.user_id,
            email=f"{token_obj.user_id}@example.com",
            roles=set(),
        )
        new_access_token = self.generate_access_token(user)
        return Success(new_access_token)

    def revoke_token(self, token: str):
        """토큰 폐기"""
        if token in self.refresh_tokens:
            del self.refresh_tokens[token]


class AuthenticationManager:
    """인증 관리자"""

    def __init__(self):
        self.providers = {}
        self.sessions = {}
        self.token_manager = None

    def register_provider(self, method: AuthMethod, provider: AuthProvider):
        """인증 제공자 등록"""
        self.providers = {**self.providers, method: provider}
        if type(provider).__name__ == "JWTAuthProvider":
            self.token_manager = TokenManager(provider)

    async def authenticate(
        self, method: AuthMethod, credentials: Dict[str, Any]
    ) -> Result[User, str]:
        """사용자 인증"""
        if method not in self.providers:
            return Failure(f"지원하지 않는 인증 방법: {method}")
        provider = self.providers[method]
        auth_result = await provider.authenticate(credentials)
        if auth_result.is_success():
            user = auth_result.unwrap()
            user.last_login = datetime.now()
            await logger.log_info(f"사용자 인증 성공: {user.username}")
        else:
            await logger.log_warning(f"사용자 인증 실패: {auth_result.unwrap_err()}")
        return auth_result

    async def validate_token(self, method: AuthMethod, token: str) -> Result[User, str]:
        """토큰 검증"""
        if method not in self.providers:
            return Failure(f"지원하지 않는 인증 방법: {method}")
        provider = self.providers[method]
        return await provider.validate_token(token)

    def create_session(
        self,
        user: User,
        ip_address=None,
        user_agent=None,
        expires_in=3600,
    ) -> UserSession:
        """사용자 세션 생성"""
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        session = UserSession(
            session_id=session_id,
            user_id=user.id,
            created_at=datetime.now(),
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.sessions = {**self.sessions, session_id: session}
        return session

    def get_session(self, session_id: str) -> Optional[UserSession]:
        """세션 조회"""
        session = self.sessions.get(session_id)
        if session and session.is_expired():
            del self.sessions[session_id]
            return None
        return session

    def revoke_session(self, session_id: str) -> bool:
        """세션 폐기"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False


def require_auth(
    auth_manager: AuthenticationManager, method: AuthMethod = AuthMethod.JWT
):
    """인증 필요 데코레이터"""

    def decorator(func):

        async def wrapper(*args, **kwargs):
            token = kwargs.get("token")
            if not token:
                return Failure("인증 토큰 필요")
            auth_result = await auth_manager.validate_token(method, token)
            if auth_result.is_failure():
                return auth_result
            user = auth_result.unwrap()
            kwargs["user"] = {"user": user}
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_role(role_name: str):
    """역할 필요 데코레이터"""

    def decorator(func):

        async def wrapper(*args, **kwargs):
            user = kwargs.get("user")
            if not user or not user.has_role(role_name):
                return Failure(f"권한 부족: {role_name} 역할 필요")
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_permission(resource: str, action: str):
    """권한 필요 데코레이터"""

    def decorator(func):

        async def wrapper(*args, **kwargs):
            user = kwargs.get("user")
            if not user or not user.has_permission_for(resource, action):
                return Failure(f"권한 부족: {resource}:{action} 권한 필요")
            return await func(*args, **kwargs)

        return wrapper

    return decorator


async def authenticate(
    auth_manager: AuthenticationManager, method: AuthMethod, credentials: Dict[str, Any]
) -> Result[User, str]:
    """사용자 인증 헬퍼"""
    return await auth_manager.authenticate(method, credentials)


async def authorize(user: User, resource: str, action: str) -> Result[bool, str]:
    """사용자 권한 확인 헬퍼"""
    if user.has_permission_for(resource, action):
        return Success(True)
    return Failure(f"권한 부족: {resource}:{action}")


def hash_password(password: str, salt=None) -> str:
    """비밀번호 해싱"""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}:{hashed.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    try:
        salt, hash_hex = hashed_password.split(":")
        expected_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 100000
        )
        return hmac.compare_digest(expected_hash.hex(), hash_hex)
    except ValueError:
        return False
