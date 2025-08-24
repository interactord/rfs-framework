"""
RFS Security Module (RFS v4.1)

보안 시스템 - 인증, 인가, 암호화, 취약점 스캐닝
"""

from .audit import (  # 감사 로그; 감사 저장소; 감사 데코레이터; 감사 헬퍼
    AuditEvent,
    AuditEventType,
    AuditLevel,
    AuditLogger,
    AuditStorage,
    FileAuditStorage,
    MemoryAuditStorage,
    audit_log,
    get_audit_logger,
    monitor_changes,
    track_access,
)
from .auth import (
    AuthenticationManager,
    AuthProvider,
    JWTAuthProvider,
    JWTToken,
    OAuth2Provider,
    Permission,
    RefreshToken,
    Role,
    TokenManager,
    User,
    UserSession,
    authenticate,
    authorize,
)
from .auth import (
    hash_password as auth_hash_password,  # 인증 시스템; 인증 데코레이터; 토큰 관리; 사용자 관리; 비밀번호 헬퍼
)
from .auth import (
    require_auth,
    require_permission,
    require_role,
)
from .auth import verify_password as auth_verify_password
from .crypto import (  # 암호화; 해싱; 서명; 암호화 결과
    CryptoManager,
    EncryptionResult,
    HashAlgorithm,
    KeyPair,
    decrypt,
    encrypt,
    generate_key,
    generate_keypair,
    generate_salt,
    hash_data,
    hash_password,
    sign_data,
    verify_hash,
    verify_password,
    verify_signature,
)
from .hardening import (
    ComplianceStandard,
    HardeningResult,
    SecurityHardening,
    SecurityLevel,
    SecurityPolicy,
    apply_security_hardening,
    create_security_policy,
)
from .scanner import SecurityScanner, ThreatLevel, VulnerabilityReport

__all__ = [
    # Authentication
    "AuthenticationManager",
    "AuthProvider",
    "JWTAuthProvider",
    "OAuth2Provider",
    "authenticate",
    "authorize",
    "require_auth",
    "require_role",
    "require_permission",
    # Token Management
    "TokenManager",
    "JWTToken",
    "RefreshToken",
    # User Management
    "User",
    "Role",
    "Permission",
    "UserSession",
    "auth_hash_password",
    "auth_verify_password",
    # Cryptography
    "CryptoManager",
    "encrypt",
    "decrypt",
    "hash_password",
    "verify_password",
    "generate_salt",
    "generate_key",
    "HashAlgorithm",
    "hash_data",
    "verify_hash",
    "sign_data",
    "verify_signature",
    "generate_keypair",
    "EncryptionResult",
    "KeyPair",
    # Security Scanning
    "SecurityScanner",
    "VulnerabilityReport",
    "ThreatLevel",
    # Security Hardening
    "SecurityHardening",
    "SecurityPolicy",
    "HardeningResult",
    "SecurityLevel",
    "ComplianceStandard",
    "create_security_policy",
    "apply_security_hardening",
    # Audit Logging
    "AuditLogger",
    "AuditEvent",
    "AuditLevel",
    "AuditEventType",
    "AuditStorage",
    "MemoryAuditStorage",
    "FileAuditStorage",
    "audit_log",
    "track_access",
    "monitor_changes",
    "get_audit_logger",
]
