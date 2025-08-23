"""
RFS Security Module (RFS v4.1)

보안 시스템 - 인증, 인가, 암호화, 취약점 스캐닝
"""

from .auth import (
    # 인증 시스템
    AuthenticationManager,
    AuthProvider,
    JWTAuthProvider,
    OAuth2Provider,
    authenticate,
    authorize,
    
    # 인증 데코레이터
    require_auth,
    require_role,
    require_permission,
    
    # 토큰 관리
    TokenManager,
    JWTToken,
    RefreshToken,
    
    # 사용자 관리
    User,
    Role,
    Permission,
    UserSession,
    
    # 비밀번호 헬퍼
    hash_password as auth_hash_password,
    verify_password as auth_verify_password
)

from .crypto import (
    # 암호화
    CryptoManager,
    encrypt,
    decrypt,
    hash_password,
    verify_password,
    generate_salt,
    generate_key,
    
    # 해싱
    HashAlgorithm,
    hash_data,
    verify_hash,
    
    # 서명
    sign_data,
    verify_signature,
    generate_keypair,
    
    # 암호화 결과
    EncryptionResult,
    KeyPair
)

from .scanner import SecurityScanner, VulnerabilityReport, ThreatLevel

from .hardening import (
    SecurityHardening, SecurityPolicy, HardeningResult,
    SecurityLevel, ComplianceStandard,
    create_security_policy, apply_security_hardening
)

from .audit import (
    # 감사 로그
    AuditLogger,
    AuditEvent,
    AuditLevel,
    AuditEventType,
    
    # 감사 저장소
    AuditStorage,
    MemoryAuditStorage,
    FileAuditStorage,
    
    # 감사 데코레이터
    audit_log,
    track_access,
    monitor_changes,
    
    # 감사 헬퍼
    get_audit_logger
)

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
    "get_audit_logger"
]