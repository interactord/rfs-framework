"""
RFS Framework - 보안 및 검증 예제

이 예제는 RFS Framework의 보안 기능과 시스템 검증 기능을 통합적으로 보여줍니다:
- 접근 제어 (RBAC/ABAC)
- 입력 검증 및 살균
- 보안 스캐닝 및 취약점 검사
- JWT 토큰 관리
- 레이트 리미팅 및 보안 정책
- 포괄적인 시스템 검증
"""

import asyncio
import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

# RFS 프레임워크 보안 컴포넌트
from rfs.core.result import Result, Success, Failure
from rfs.security.access_control import (
    RequiresRole, RequiresPermission, RequiresAuthentication, RequiresOwnership,
    RoleBasedAccessControl, AttributeBasedAccessControl,
    JWTTokenManager, SecurityContext
)
from rfs.security.validation_decorators import (
    ValidateInput, SanitizeInput, ValidateSchema, RateLimited
)
from rfs.security.scanner import SecurityScanner, VulnerabilityType
from rfs.validation.validator import SystemValidator, ValidationCategory

# 기타 필요한 컴포넌트
from rfs.core.annotations import Component
from rfs.core.logging_decorators import AuditLogged, ErrorLogged


# ================================================
# 도메인 모델 및 권한 정의
# ================================================

class UserRole(str, Enum):
    """사용자 역할"""
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"
    GUEST = "guest"


class Permission(str, Enum):
    """권한 정의"""
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    ADMIN_PANEL = "admin:panel"
    MODERATE_CONTENT = "content:moderate"


@dataclass
class User:
    """사용자 모델"""
    id: str
    email: str
    name: str
    role: UserRole
    permissions: List[Permission]
    created_at: datetime
    is_active=True
    
    def has_permission(self, permission: Permission) -> bool:
        """권한 확인"""
        return permission in self.permissions
    
    def has_role(self, role: UserRole) -> bool:
        """역할 확인"""
        return self.role == role


@dataclass
class SecurityEvent:
    """보안 이벤트"""
    event_type: str
    user_id: str
    ip_address: str
    timestamp: datetime
    details: Dict[str, Any]
    severity="info"


# ================================================
# JWT 토큰 관리
# ================================================

class SecureTokenManager:
    """보안 토큰 관리자"""
    
    def __init__(self):
        # 실제로는 환경 변수나 Secret Manager에서 가져와야 함
        self.secret_key = secrets.token_urlsafe(32)
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7
        
        self.token_manager = JWTTokenManager(
            secret_key=self.secret_key,
            algorithm=self.algorithm
        )
    
    @AuditLogged("token_created")
    async def create_access_token(self, user: User) -> Result[str, str]:
        """액세스 토큰 생성"""
        try:
            payload = {
                "sub": user.id,
                "email": user.email,
                "role": user.role.value,
                "permissions": [p.value for p in user.permissions],
                "exp": datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes),
                "iat": datetime.utcnow(),
                "type": "access"
            }
            
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            return Success(token)
            
        except Exception as e:
            return Failure(f"토큰 생성 실패: {str(e)}")
    
    @AuditLogged("token_validated")
    async def validate_token(self, token: str) -> Result[Dict[str, Any], str]:
        """토큰 검증"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # 토큰 타입 확인
            if payload.get("type") != "access":
                return Failure("잘못된 토큰 타입")
            
            return Success(payload)
            
        except jwt.ExpiredSignatureError:
            return Failure("토큰이 만료되었습니다")
        except jwt.InvalidTokenError:
            return Failure("잘못된 토큰입니다")
        except Exception as e:
            return Failure(f"토큰 검증 실패: {str(e)}")
    
    async def create_refresh_token(self, user: User) -> Result[str, str]:
        """리프레시 토큰 생성"""
        try:
            payload = {
                "sub": user.id,
                "exp": datetime.utcnow() + timedelta(days=self.refresh_token_expire_days),
                "iat": datetime.utcnow(),
                "type": "refresh"
            }
            
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            return Success(token)
            
        except Exception as e:
            return Failure(f"리프레시 토큰 생성 실패: {str(e)}")


# ================================================
# 사용자 관리 서비스 (보안 적용)
# ================================================

class SecureUserService:
    """보안이 적용된 사용자 서비스"""
    
    def __init__(self, token_manager: SecureTokenManager):
        self.token_manager = token_manager
        self.users_db = {}
        self.security_events = []
        self.failed_login_attempts = {}  # IP별 실패 횟수
    
    @ValidateInput({
        "email": {"type": "email", "required": True},
        "password": {"type": "string", "min_length": 8, "required": True},
        "name": {"type": "string", "min_length": 2, "max_length": 100, "required": True}
    })
    @SanitizeInput(["name", "email"])
    @RateLimited(max_calls=5, period=timedelta(minutes=1))
    @AuditLogged("user_registration_attempt")
    async def register_user(
        self,
        user_data: dict,
        client_ip="127.0.0.1"
    ) -> Result[dict, str]:
        """사용자 등록"""
        try:
            # 중복 이메일 확인
            if user_data["email"] in self.users_db:
                await self._log_security_event(
                    "duplicate_email_registration",
                    None,
                    client_ip,
                    {"email": user_data["email"]}
                )
                return Failure("이미 등록된 이메일입니다")
            
            # 비밀번호 해싱
            password_hash = self._hash_password(user_data["password"])
            
            # 사용자 생성
            user = User(
                id=f"user_{len(self.users_db) + 1}",
                email=user_data["email"],
                name=user_data["name"],
                role=UserRole.USER,
                permissions=[Permission.USER_READ],
                created_at=datetime.now()
            )
            
            # 저장
            self.users_db[user.email] = {
                "user": user,
                "password_hash": password_hash
            }
            
            # 보안 이벤트 로깅
            await self._log_security_event(
                "user_registered",
                user.id,
                client_ip,
                {"email": user.email, "role": user.role.value}
            )
            
            print(f"👤 사용자 등록: {user.email}")
            
            return Success({
                "user_id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role.value
            })
            
        except Exception as e:
            return Failure(f"사용자 등록 실패: {str(e)}")
    
    @ValidateInput({
        "email": {"type": "email", "required": True},
        "password": {"type": "string", "required": True}
    })
    @RateLimited(max_calls=10, period=timedelta(minutes=5))
    @AuditLogged("login_attempt")
    async def authenticate_user(
        self,
        credentials: dict,
        client_ip="127.0.0.1"
    ) -> Result[dict, str]:
        """사용자 인증"""
        email = credentials["email"]
        
        # 브루트 포스 공격 방지
        if self._is_ip_blocked(client_ip):
            await self._log_security_event(
                "blocked_ip_login_attempt",
                None,
                client_ip,
                {"email": email},
                "high"
            )
            return Failure("IP가 일시적으로 차단되었습니다")
        
        try:
            # 사용자 조회
            if email not in self.users_db:
                await self._record_failed_login(client_ip, email)
                return Failure("잘못된 인증 정보입니다")
            
            user_data = self.users_db[email]
            user = user_data["user"]
            
            # 비밀번호 검증
            if not self._verify_password(credentials["password"], user_data["password_hash"]):
                await self._record_failed_login(client_ip, email)
                return Failure("잘못된 인증 정보입니다")
            
            # 계정 활성화 확인
            if not user.is_active:
                await self._log_security_event(
                    "inactive_user_login_attempt",
                    user.id,
                    client_ip,
                    {"email": email},
                    "medium"
                )
                return Failure("비활성화된 계정입니다")
            
            # 토큰 생성
            access_token_result = await self.token_manager.create_access_token(user)
            if access_token_result.is_failure():
                return access_token_result
            
            refresh_token_result = await self.token_manager.create_refresh_token(user)
            if refresh_token_result.is_failure():
                return refresh_token_result
            
            # 성공 로그인 처리
            self._reset_failed_attempts(client_ip)
            
            await self._log_security_event(
                "successful_login",
                user.id,
                client_ip,
                {"email": email, "role": user.role.value}
            )
            
            print(f"🔐 로그인 성공: {user.email}")
            
            return Success({
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "role": user.role.value
                },
                "access_token": access_token_result.value,
                "refresh_token": refresh_token_result.value,
                "expires_in": self.token_manager.access_token_expire_minutes * 60
            })
            
        except Exception as e:
            return Failure(f"인증 실패: {str(e)}")
    
    @RequiresAuthentication()
    @RequiresPermission(Permission.USER_READ)
    async def get_user_profile(self, user_id: str, current_user: User) -> Result[dict, str]:
        """사용자 프로필 조회"""
        # 자신의 프로필이거나 관리자인 경우만 허용
        if user_id != current_user.id and current_user.role != UserRole.ADMIN:
            return Failure("권한이 없습니다")
        
        # 사용자 검색
        for user_data in self.users_db.values():
            user = user_data["user"]
            if user.id == user_id:
                return Success({
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "role": user.role.value,
                    "created_at": user.created_at.isoformat(),
                    "is_active": user.is_active
                })
        
        return Failure("사용자를 찾을 수 없습니다")
    
    @RequiresAuthentication()
    @RequiresRole(UserRole.ADMIN)
    async def list_security_events(self, current_user: User) -> Result[List[dict], str]:
        """보안 이벤트 목록 조회 (관리자만)"""
        return Success([
            {
                "event_type": event.event_type,
                "user_id": event.user_id,
                "timestamp": event.timestamp.isoformat(),
                "ip_address": event.ip_address,
                "severity": event.severity,
                "details": event.details
            }
            for event in self.security_events[-100:]  # 최근 100개
        ])
    
    def _hash_password(self, password: str) -> str:
        """비밀번호 해싱"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}:{password_hash.hex()}"
    
    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """비밀번호 검증"""
        try:
            salt, hash_part = stored_hash.split(':')
            password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return password_hash.hex() == hash_part
        except:
            return False
    
    def _is_ip_blocked(self, ip: str) -> bool:
        """IP 차단 여부 확인"""
        attempts = self.failed_login_attempts.get(ip, {"count": 0, "last_attempt": None})
        
        # 5회 이상 실패 시 30분 차단
        if attempts["count"] >= 5:
            if attempts["last_attempt"]:
                time_diff = datetime.now() - attempts["last_attempt"]
                return time_diff < timedelta(minutes=30)
        
        return False
    
    async def _record_failed_login(self, ip: str, email: str):
        """실패한 로그인 기록"""
        if ip not in self.failed_login_attempts:
            self.failed_login_attempts[ip] = {"count": 0, "last_attempt": None}
        
        self.failed_login_attempts[ip]["count"] += 1
        self.failed_login_attempts[ip]["last_attempt"] = datetime.now()
        
        await self._log_security_event(
            "failed_login_attempt",
            None,
            ip,
            {"email": email, "attempt_count": self.failed_login_attempts[ip]["count"]},
            "medium"
        )
    
    def _reset_failed_attempts(self, ip: str):
        """실패 횟수 리셋"""
        if ip in self.failed_login_attempts:
            del self.failed_login_attempts[ip]
    
    async def _log_security_event(
        self,
        event_type: str,
        user_id: Optional[str],
        ip_address: str,
        details: Dict[str, Any],
        severity="info"
    ):
        """보안 이벤트 로깅"""
        event = SecurityEvent(
            event_type=event_type,
            user_id=user_id or "anonymous",
            ip_address=ip_address,
            timestamp=datetime.now(),
            details=details,
            severity=severity
        )
        
        self.security_events.append(event)
        
        # 심각한 이벤트는 즉시 알림
        if severity in ["high", "critical"]:
            print(f"🚨 보안 경고 [{severity.upper()}] {event_type}: {details}")


# ================================================
# 컨텐츠 관리 서비스 (ABAC 적용)
# ================================================

class ContentService:
    """컨텐츠 관리 서비스"""
    
    def __init__(self):
        self.contents = {}
        self.abac = AttributeBasedAccessControl()
        
        # ABAC 정책 정의
        self._setup_abac_policies()
    
    def _setup_abac_policies(self):
        """ABAC 정책 설정"""
        # 정책 1: 자신의 컨텐츠는 읽기/수정 가능
        self.abac.add_policy(
            "own_content_access",
            lambda subject, resource, action, context: (
                subject.get("user_id") == resource.get("author_id")
                and action in ["read", "update"]
            )
        )
        
        # 정책 2: 모든 사용자는 공개 컨텐츠 읽기 가능
        self.abac.add_policy(
            "public_content_read",
            lambda subject, resource, action, context: (
                resource.get("visibility") == "public"
                and action == "read"
            )
        )
        
        # 정책 3: 모더레이터는 모든 컨텐츠 수정 가능
        self.abac.add_policy(
            "moderator_content_access",
            lambda subject, resource, action, context: (
                subject.get("role") == "moderator"
                and action in ["read", "update", "delete"]
            )
        )
    
    @RequiresAuthentication()
    @ValidateInput({
        "title": {"type": "string", "min_length": 1, "max_length": 200, "required": True},
        "content": {"type": "string", "min_length": 1, "required": True},
        "visibility": {"type": "string", "choices": ["public", "private"], "default": "public"}
    })
    @SanitizeInput(["title", "content"])
    @AuditLogged("content_created")
    async def create_content(
        self,
        content_data: dict,
        current_user: User
    ) -> Result[dict, str]:
        """컨텐츠 생성"""
        try:
            content_id = f"content_{len(self.contents) + 1}"
            
            content = {
                "id": content_id,
                "title": content_data["title"],
                "content": content_data["content"],
                "visibility": content_data.get("visibility", "public"),
                "author_id": current_user.id,
                "author_name": current_user.name,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            self.contents[content_id] = content
            
            print(f"📝 컨텐츠 생성: {content['title']} by {current_user.name}")
            
            return Success(content)
            
        except Exception as e:
            return Failure(f"컨텐츠 생성 실패: {str(e)}")
    
    @RequiresAuthentication()
    async def get_content(
        self,
        content_id: str,
        current_user: User
    ) -> Result[dict, str]:
        """컨텐츠 조회 (ABAC 적용)"""
        if content_id not in self.contents:
            return Failure("컨텐츠를 찾을 수 없습니다")
        
        content = self.contents[content_id]
        
        # ABAC 정책 검사
        subject = {
            "user_id": current_user.id,
            "role": current_user.role.value
        }
        
        resource = {
            "author_id": content["author_id"],
            "visibility": content["visibility"]
        }
        
        access_granted = await self.abac.check_access(
            subject=subject,
            resource=resource,
            action="read",
            context={}
        )
        
        if not access_granted:
            return Failure("컨텐츠에 접근할 권한이 없습니다")
        
        return Success(content)
    
    @RequiresAuthentication()
    @ValidateSchema({
        "type": "object",
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "content": {"type": "string", "minLength": 1},
            "visibility": {"type": "string", "enum": ["public", "private"]}
        }
    })
    @SanitizeInput(["title", "content"])
    @AuditLogged("content_updated")
    async def update_content(
        self,
        content_id: str,
        update_data: dict,
        current_user: User
    ) -> Result[dict, str]:
        """컨텐츠 수정 (ABAC 적용)"""
        if content_id not in self.contents:
            return Failure("컨텐츠를 찾을 수 없습니다")
        
        content = self.contents[content_id]
        
        # ABAC 정책 검사
        subject = {
            "user_id": current_user.id,
            "role": current_user.role.value
        }
        
        resource = {
            "author_id": content["author_id"],
            "visibility": content["visibility"]
        }
        
        access_granted = await self.abac.check_access(
            subject=subject,
            resource=resource,
            action="update",
            context={}
        )
        
        if not access_granted:
            return Failure("컨텐츠를 수정할 권한이 없습니다")
        
        # 컨텐츠 업데이트
        for key, value in update_data.items():
            if key in ["title", "content", "visibility"]:
                content[key] = value
        
        content["updated_at"] = datetime.now().isoformat()
        
        print(f"✏️ 컨텐츠 수정: {content['title']} by {current_user.name}")
        
        return Success(content)


# ================================================
# 보안 스캐너 및 시스템 검증
# ================================================

class ComprehensiveSecurityScanner:
    """통합 보안 스캐너"""
    
    def __init__(self):
        self.scanner = SecurityScanner()
        self.validator = SystemValidator()
    
    async def scan_application_security(self, app_path="./") -> Result[dict, str]:
        """애플리케이션 보안 스캔"""
        print("🔍 보안 스캔 시작...")
        
        try:
            # 코드 보안 스캔
            code_scan_result = await self.scanner.scan_directory(app_path)
            
            # 의존성 취약점 스캔
            dependency_scan_result = await self.scanner.scan_dependencies()
            
            # 설정 보안 검사
            config_scan_result = await self.scanner.scan_configuration()
            
            # 비밀키 검사
            secret_scan_result = await self.scanner.scan_secrets(app_path)
            
            # 전체 결과 통합
            total_vulnerabilities = (
                len(code_scan_result.get("vulnerabilities", [])) +
                len(dependency_scan_result.get("vulnerabilities", [])) +
                len(config_scan_result.get("vulnerabilities", [])) +
                len(secret_scan_result.get("vulnerabilities", []))
            )
            
            security_score = max(0, 100 - (total_vulnerabilities * 10))
            
            result = {
                "security_score": security_score,
                "total_vulnerabilities": total_vulnerabilities,
                "scans": {
                    "code": code_scan_result,
                    "dependencies": dependency_scan_result,
                    "configuration": config_scan_result,
                    "secrets": secret_scan_result
                },
                "recommendations": self._generate_security_recommendations(
                    code_scan_result,
                    dependency_scan_result,
                    config_scan_result,
                    secret_scan_result
                )
            }
            
            print(f"🛡️ 보안 스캔 완료 - 점수: {security_score}/100")
            
            return Success(result)
            
        except Exception as e:
            return Failure(f"보안 스캔 실패: {str(e)}")
    
    async def validate_system_security(self) -> Result[dict, str]:
        """시스템 보안 검증"""
        print("✅ 시스템 보안 검증 시작...")
        
        try:
            # 기능 검증
            functional_result = await self.validator.validate_category(
                ValidationCategory.FUNCTIONAL
            )
            
            # 보안 검증
            security_result = await self.validator.validate_category(
                ValidationCategory.SECURITY
            )
            
            # 성능 검증
            performance_result = await self.validator.validate_category(
                ValidationCategory.PERFORMANCE
            )
            
            # 호환성 검증
            compatibility_result = await self.validator.validate_category(
                ValidationCategory.COMPATIBILITY
            )
            
            # 전체 검증 결과
            all_results = [
                functional_result,
                security_result,
                performance_result,
                compatibility_result
            ]
            
            total_checks = sum(len(result.get("checks", [])) for result in all_results)
            passed_checks = sum(
                len([check for check in result.get("checks", []) if check.get("passed", False)])
                for result in all_results
            )
            
            validation_score = (passed_checks / total_checks * 100) if total_checks > 0 else 0
            
            result = {
                "validation_score": validation_score,
                "total_checks": total_checks,
                "passed_checks": passed_checks,
                "categories": {
                    "functional": functional_result,
                    "security": security_result,
                    "performance": performance_result,
                    "compatibility": compatibility_result
                }
            }
            
            print(f"✅ 시스템 검증 완료 - 점수: {validation_score:.1f}/100")
            
            return Success(result)
            
        except Exception as e:
            return Failure(f"시스템 검증 실패: {str(e)}")
    
    def _generate_security_recommendations(self, *scan_results) -> List[str]:
        """보안 권장사항 생성"""
        recommendations = []
        
        # 각 스캔 결과 분석하여 권장사항 생성
        for scan_result in scan_results:
            vulnerabilities = scan_result.get("vulnerabilities", [])
            
            for vuln in vulnerabilities:
                vuln_type = vuln.get("type", "")
                
                if vuln_type == "SQL_INJECTION":
                    recommendations.append("매개변수화된 쿼리 사용")
                elif vuln_type == "XSS":
                    recommendations.append("입력 데이터 이스케이핑 및 검증")
                elif vuln_type == "HARDCODED_SECRET":
                    recommendations.append("비밀키를 환경 변수로 이동")
                elif vuln_type == "WEAK_CRYPTO":
                    recommendations.append("강력한 암호화 알고리즘 사용")
                elif vuln_type == "INSECURE_TRANSPORT":
                    recommendations.append("HTTPS 사용 강제")
        
        return list(set(recommendations))  # 중복 제거


# ================================================
# 메인 보안 애플리케이션
# ================================================

class SecureApplication:
    """보안이 적용된 애플리케이션"""
    
    def __init__(self):
        self.token_manager = SecureTokenManager()
        self.user_service = SecureUserService(self.token_manager)
        self.content_service = ContentService()
        self.security_scanner = ComprehensiveSecurityScanner()
    
    async def demonstrate_security_features(self):
        """보안 기능 데모"""
        print("\n🛡️ RFS Framework 보안 기능 데모")
        print("=" * 50)
        
        # 1. 사용자 등록
        print("\n1. 안전한 사용자 등록 (입력 검증 + 살균)")
        
        registration_result = await self.user_service.register_user({
            "email": "alice@example.com",
            "password": "SecurePass123!",
            "name": "Alice Johnson"
        }, "192.168.1.100")
        
        if registration_result.is_success():
            print(f"✅ 등록 성공: {registration_result.value['email']}")
        else:
            print(f"❌ 등록 실패: {registration_result.error}")
        
        # 2. 사용자 인증
        print("\n2. JWT 기반 인증 (브루트포스 방지)")
        
        auth_result = await self.user_service.authenticate_user({
            "email": "alice@example.com",
            "password": "SecurePass123!"
        }, "192.168.1.100")
        
        if auth_result.is_success():
            user_data = auth_result.value
            access_token = user_data["access_token"]
            print(f"🔐 인증 성공: {user_data['user']['email']}")
            print(f"토큰 만료: {user_data['expires_in']}초")
        else:
            print(f"❌ 인증 실패: {auth_result.error}")
            return
        
        # 3. 토큰 검증
        print("\n3. JWT 토큰 검증")
        
        token_validation_result = await self.token_manager.validate_token(access_token)
        if token_validation_result.is_success():
            payload = token_validation_result.value
            print(f"✅ 토큰 유효: 사용자 {payload['email']}, 역할 {payload['role']}")
        else:
            print(f"❌ 토큰 검증 실패: {token_validation_result.error}")
        
        # 4. RBAC/ABAC를 통한 컨텐츠 관리
        print("\n4. 접근 제어 (RBAC/ABAC)")
        
        # 현재 사용자 객체 생성 (토큰에서 추출)
        current_user = User(
            id=payload["sub"],
            email=payload["email"],
            name="Alice Johnson",
            role=UserRole(payload["role"]),
            permissions=[Permission(p) for p in payload["permissions"]],
            created_at=datetime.now()
        )
        
        # 컨텐츠 생성
        content_result = await self.content_service.create_content({
            "title": "보안 가이드",
            "content": "RFS Framework의 보안 기능을 설명합니다.",
            "visibility": "private"
        }, current_user)
        
        if content_result.is_success():
            content = content_result.value
            print(f"📝 컨텐츠 생성: {content['title']}")
            
            # 자신의 컨텐츠 조회 (허용)
            read_result = await self.content_service.get_content(
                content["id"],
                current_user
            )
            
            if read_result.is_success():
                print("✅ 자신의 컨텐츠 읽기 성공")
            else:
                print(f"❌ 컨텐츠 읽기 실패: {read_result.error}")
        
        # 5. 보안 이벤트 로그 조회 (실패 예시)
        print("\n5. 권한 검사 (관리자 권한 필요)")
        
        # 일반 사용자가 보안 이벤트 조회 시도 (실패해야 함)
        try:
            security_events_result = await self.user_service.list_security_events(current_user)
            print("❌ 권한 검사 실패 - 일반 사용자가 관리자 기능에 접근함")
        except Exception as e:
            print("✅ 권한 검사 성공 - 접근이 올바르게 차단됨")
        
        # 6. 보안 스캔
        print("\n6. 보안 스캔 및 시스템 검증")
        
        scan_result = await self.security_scanner.scan_application_security("./")
        if scan_result.is_success():
            scan_data = scan_result.value
            print(f"🔍 보안 점수: {scan_data['security_score']}/100")
            print(f"발견된 취약점: {scan_data['total_vulnerabilities']}개")
            
            if scan_data["recommendations"]:
                print("권장사항:")
                for rec in scan_data["recommendations"]:
                    print(f"  • {rec}")
        
        # 7. 시스템 검증
        validation_result = await self.security_scanner.validate_system_security()
        if validation_result.is_success():
            validation_data = validation_result.value
            print(f"✅ 시스템 검증 점수: {validation_data['validation_score']:.1f}/100")
            print(f"통과한 검사: {validation_data['passed_checks']}/{validation_data['total_checks']}")
        
        print("\n✅ 보안 기능 데모 완료!")
    
    async def simulate_attack_scenarios(self):
        """공격 시나리오 시뮬레이션"""
        print("\n🚨 공격 시나리오 시뮬레이션")
        print("=" * 40)
        
        # 1. 브루트포스 공격 시뮬레이션
        print("\n1. 브루트포스 공격 방어 테스트")
        
        attacker_ip = "192.168.1.999"
        
        for attempt in range(7):  # 6회 시도 (5회 초과 시 차단)
            result = await self.user_service.authenticate_user({
                "email": "alice@example.com",
                "password": "wrong_password"
            }, attacker_ip)
            
            print(f"시도 {attempt + 1}: {result.error}")
            
            # 6번째 시도부터는 IP 차단 메시지가 나와야 함
            if attempt >= 5 and "차단" in result.error:
                print("✅ 브루트포스 방어 성공!")
                break
        
        # 2. SQL 인젝션 시도 (입력 검증으로 방어)
        print("\n2. 입력 검증 테스트")
        
        malicious_input = "'; DROP TABLE users; --"
        
        result = await self.user_service.register_user({
            "email": f"hacker{malicious_input}@example.com",
            "password": "password123",
            "name": f"Evil{malicious_input}"
        })
        
        if result.is_success():
            print("❌ 입력 검증 실패 - 악성 입력이 통과됨")
        else:
            print("✅ 입력 검증 성공 - 악성 입력이 차단됨")
        
        print("\n✅ 공격 시뮬레이션 완료!")


async def main():
    """메인 실행"""
    app = SecureApplication()
    
    print("🛡️ RFS Framework - 보안 및 검증 예제 시작")
    
    # 보안 기능 데모
    await app.demonstrate_security_features()
    
    # 공격 시나리오 시뮬레이션
    await app.simulate_attack_scenarios()


if __name__ == "__main__":
    print("🔐 RFS Framework - 보안 및 검증 통합 예제")
    print("=" * 60)
    print("이 예제는 다음 보안 기능들을 보여줍니다:")
    print("• JWT 토큰 기반 인증 및 권한 부여")
    print("• RBAC/ABAC 접근 제어")
    print("• 입력 검증 및 살균 (@ValidateInput, @SanitizeInput)")
    print("• 레이트 리미팅 및 브루트포스 방어")
    print("• 보안 이벤트 로깅 및 감사")
    print("• 코드 보안 스캐닝 및 취약점 검사")
    print("• 포괄적인 시스템 검증")
    print("• 공격 시나리오 방어 시뮬레이션")
    print("=" * 60)
    
    asyncio.run(main())