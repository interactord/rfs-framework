# 보안 패턴 (Security Patterns)

## 📌 개요

RFS Framework의 보안 시스템은 종합적인 보안 패턴과 도구를 제공합니다. 코드 취약점 스캔, 암호화, 보안 강화, 감사 추적을 통해 엔터프라이즈급 보안을 구현합니다.

## 🎯 핵심 개념

### 보안 계층
- **애플리케이션 보안**: 코드 레벨 보안 패턴
- **데이터 보안**: 암호화, 해싱, 키 관리
- **네트워크 보안**: 통신 보안, TLS/SSL
- **인증/인가**: 사용자 인증 및 권한 관리
- **감사 추적**: 보안 이벤트 로깅 및 모니터링

### 위협 모델링
- **STRIDE**: Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege
- **OWASP Top 10**: 웹 애플리케이션 보안 위험
- **CWE**: 공통 약점 열거
- **CVSS**: 공통 취약점 점수 시스템

### 보안 수준
- **CRITICAL**: 즉시 수정 필요 (90-100점)
- **HIGH**: 높은 우선순위 (70-89점)
- **MEDIUM**: 중간 우선순위 (50-69점)
- **LOW**: 낮은 우선순위 (30-49점)
- **INFO**: 정보성 (10-29점)

## 📚 API 레퍼런스

### SecurityScanner 클래스

```python
from rfs.security.scanner import SecurityScanner, ThreatLevel, VulnerabilityType

# 보안 스캐너 생성
scanner = SecurityScanner(project_path="./")
```

### 취약점 타입

```python
class VulnerabilityType(Enum):
    CODE_INJECTION = "code_injection"           # 코드 인젝션
    XSS = "xss"                                # 크로스 사이트 스크립팅
    SQLI = "sql_injection"                     # SQL 인젝션
    PATH_TRAVERSAL = "path_traversal"          # 경로 조작
    WEAK_CRYPTO = "weak_cryptography"          # 약한 암호화
    INSECURE_CONFIG = "insecure_configuration" # 안전하지 않은 설정
    HARDCODED_SECRET = "hardcoded_secret"      # 하드코딩된 시크릿
    DEPENDENCY_VULN = "dependency_vulnerability" # 의존성 취약점
    PERMISSION_ISSUE = "permission_issue"       # 권한 문제
    INFORMATION_LEAK = "information_leakage"    # 정보 누출
```

## 💡 사용 예제

### 종합 보안 스캔

```python
from rfs.security.scanner import SecurityScanner
import asyncio

async def comprehensive_security_scan():
    """종합 보안 스캔 실행"""
    scanner = SecurityScanner(project_path=".")
    
    # 전체 보안 스캔
    result = await scanner.run_security_scan()
    
    if result.is_success():
        vulnerabilities = result.unwrap()
        
        print(f"총 {len(vulnerabilities)}개 취약점 발견")
        
        # 심각도별 분류
        critical_vulns = [v for v in vulnerabilities if v.threat_level == ThreatLevel.CRITICAL]
        high_vulns = [v for v in vulnerabilities if v.threat_level == ThreatLevel.HIGH]
        
        print(f"심각: {len(critical_vulns)}개")
        print(f"높음: {len(high_vulns)}개")
        
        # 상위 5개 취약점 출력
        top_vulnerabilities = vulnerabilities[:5]
        for i, vuln in enumerate(top_vulnerabilities, 1):
            print(f"{i}. {vuln.title}")
            print(f"   파일: {vuln.file_path}:{vuln.line_number}")
            print(f"   위험도: {vuln.risk_score}/100")
            print(f"   권장사항: {vuln.remediation[0] if vuln.remediation else 'N/A'}")
            print()
        
        # 리포트 생성
        report_result = await scanner.generate_security_report()
        if report_result.is_success():
            print(f"보안 리포트 생성: {report_result.unwrap()}")
        
        return vulnerabilities
    else:
        print(f"보안 스캔 실패: {result.unwrap_err()}")
        return []

# 실행
vulnerabilities = await comprehensive_security_scan()
```

### 특정 유형 스캔

```python
async def scan_specific_types():
    """특정 보안 유형만 스캔"""
    scanner = SecurityScanner()
    
    # 코드 취약점과 시크릿만 스캔
    result = await scanner.run_security_scan(
        scan_types=['code', 'secrets']
    )
    
    if result.is_success():
        vulnerabilities = result.unwrap()
        
        # 코드 인젝션 취약점
        code_injection_vulns = [
            v for v in vulnerabilities 
            if v.vuln_type == VulnerabilityType.CODE_INJECTION
        ]
        
        print(f"코드 인젝션 취약점: {len(code_injection_vulns)}개")
        for vuln in code_injection_vulns:
            print(f"- {vuln.title} ({vuln.file_path}:{vuln.line_number})")
            print(f"  코드: {vuln.code_snippet}")
            print(f"  수정방법: {'; '.join(vuln.remediation)}")
        
        # 하드코딩된 시크릿
        secret_vulns = [
            v for v in vulnerabilities 
            if v.vuln_type == VulnerabilityType.HARDCODED_SECRET
        ]
        
        print(f"\n하드코딩된 시크릿: {len(secret_vulns)}개")
        for vuln in secret_vulns:
            print(f"- {vuln.title} ({vuln.file_path}:{vuln.line_number})")
    
    return result

# 실행
await scan_specific_types()
```

### 코드 보안 패턴

```python
from rfs.security.crypto import SecureCrypto
from rfs.security.validation_decorators import Sanitized, ValidatedInput
from rfs.core.result import Result, Success, Failure

# 안전한 암호화
class SecureUserService:
    def __init__(self):
        self.crypto = SecureCrypto()
    
    @ValidatedInput(
        rules={
            'password': {'min_length': 8, 'complexity': True},
            'email': {'format': 'email'}
        }
    )
    async def create_user(
        self, 
        email: str, 
        password: str,
        user_data: dict
    ) -> Result[dict, str]:
        """사용자 생성 (보안 검증 포함)"""
        try:
            # 비밀번호 해싱 (안전한 방법)
            password_hash = self.crypto.hash_password(password)
            
            # 민감한 데이터 암호화
            encrypted_data = {}
            if 'ssn' in user_data:
                encrypted_data['ssn'] = self.crypto.encrypt(user_data['ssn'])
            
            user = {
                'id': self._generate_secure_id(),
                'email': email,
                'password_hash': password_hash,
                'encrypted_data': encrypted_data,
                'created_at': datetime.now().isoformat()
            }
            
            return Success(user)
            
        except Exception as e:
            return Failure(f"사용자 생성 실패: {str(e)}")
    
    @Sanitized(fields=['query'])
    async def search_users(self, query: str) -> Result[list, str]:
        """사용자 검색 (SQL 인젝션 방지)"""
        try:
            # 매개변수화된 쿼리 사용 (SQL 인젝션 방지)
            safe_query = """
                SELECT id, email, created_at 
                FROM users 
                WHERE email LIKE %s 
                ORDER BY created_at DESC
            """
            
            # 안전한 쿼리 실행
            results = await self.db.execute(safe_query, (f"%{query}%",))
            
            return Success(results)
            
        except Exception as e:
            return Failure(f"사용자 검색 실패: {str(e)}")

# 사용
user_service = SecureUserService()

# 안전한 사용자 생성
result = await user_service.create_user(
    email="user@example.com",
    password="SecurePass123!",
    user_data={"name": "John Doe", "ssn": "123-45-6789"}
)
```

### 파일 업로드 보안

```python
from rfs.security.validation_decorators import SecureFileUpload
import mimetypes
import hashlib

class SecureFileHandler:
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.pdf', '.txt'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    UPLOAD_DIR = "/secure/uploads"
    
    @SecureFileUpload(
        allowed_extensions=['.jpg', '.jpeg', '.png', '.pdf'],
        max_size=MAX_FILE_SIZE,
        scan_malware=True
    )
    async def upload_file(self, file_data: bytes, filename: str) -> Result[dict, str]:
        """안전한 파일 업로드"""
        try:
            # 파일 확장자 검증
            _, ext = os.path.splitext(filename.lower())
            if ext not in self.ALLOWED_EXTENSIONS:
                return Failure(f"허용되지 않은 파일 형식: {ext}")
            
            # MIME 타입 검증
            detected_type, _ = mimetypes.guess_type(filename)
            if not detected_type or not self._is_safe_mime_type(detected_type):
                return Failure("안전하지 않은 파일 타입")
            
            # 파일 크기 검증
            if len(file_data) > self.MAX_FILE_SIZE:
                return Failure("파일 크기 초과")
            
            # 바이러스 스캔 시뮬레이션
            if await self._scan_for_malware(file_data):
                return Failure("악성 코드 탐지됨")
            
            # 안전한 파일명 생성
            safe_filename = self._generate_safe_filename(filename)
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            # 파일 저장
            file_path = os.path.join(self.UPLOAD_DIR, safe_filename)
            await self._save_file_securely(file_path, file_data)
            
            return Success({
                'filename': safe_filename,
                'original_filename': filename,
                'size': len(file_data),
                'hash': file_hash,
                'upload_time': datetime.now().isoformat()
            })
            
        except Exception as e:
            return Failure(f"파일 업로드 실패: {str(e)}")
    
    def _is_safe_mime_type(self, mime_type: str) -> bool:
        """안전한 MIME 타입 확인"""
        safe_types = {
            'image/jpeg', 'image/png', 'image/gif',
            'application/pdf', 'text/plain'
        }
        return mime_type in safe_types
    
    async def _scan_for_malware(self, file_data: bytes) -> bool:
        """멀웨어 스캔 (실제로는 ClamAV 등 사용)"""
        # 시뮬레이션: 특정 시그니처 확인
        suspicious_signatures = [b'<script>', b'<?php', b'eval(']
        
        for signature in suspicious_signatures:
            if signature in file_data:
                return True
        
        return False
    
    def _generate_safe_filename(self, original: str) -> str:
        """안전한 파일명 생성"""
        # 위험한 문자 제거
        safe_chars = re.sub(r'[^a-zA-Z0-9._-]', '', original)
        
        # UUID 추가로 고유성 보장
        name, ext = os.path.splitext(safe_chars)
        return f"{name}_{uuid.uuid4().hex[:8]}{ext}"
    
    async def _save_file_securely(self, file_path: str, file_data: bytes) -> None:
        """안전한 파일 저장"""
        # 디렉토리 생성 (안전한 권한으로)
        os.makedirs(os.path.dirname(file_path), mode=0o750, exist_ok=True)
        
        # 파일 저장 (안전한 권한으로)
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        # 파일 권한 설정 (읽기 전용)
        os.chmod(file_path, 0o640)

# 사용
file_handler = SecureFileHandler()

# 파일 업로드
with open("example.pdf", "rb") as f:
    file_data = f.read()

result = await file_handler.upload_file(file_data, "document.pdf")
if result.is_success():
    print(f"파일 업로드 성공: {result.unwrap()}")
```

### API 보안

```python
from rfs.security.auth import JWTAuth
from rfs.security.validation_decorators import RateLimited, CSRFProtected
from rfs.web.middleware import SecurityMiddleware

class SecureAPIHandler:
    def __init__(self):
        self.jwt_auth = JWTAuth(secret_key=os.environ['JWT_SECRET'])
    
    @RateLimited(requests_per_minute=60, per_user=True)
    @CSRFProtected()
    async def create_post(
        self, 
        request: dict,
        user_token: str
    ) -> Result[dict, str]:
        """게시글 생성 (보안 검증 포함)"""
        try:
            # JWT 토큰 검증
            user_result = await self.jwt_auth.verify_token(user_token)
            if user_result.is_failure():
                return user_result
            
            user = user_result.unwrap()
            
            # 입력 검증 및 새니타이제이션
            title = self._sanitize_html(request.get('title', ''))
            content = self._sanitize_html(request.get('content', ''))
            
            if not title or len(title) > 200:
                return Failure("제목이 유효하지 않습니다")
            
            if not content or len(content) > 10000:
                return Failure("내용이 유효하지 않습니다")
            
            # XSS 방지
            safe_title = self._escape_html(title)
            safe_content = self._escape_html(content)
            
            # 게시글 생성
            post = {
                'id': str(uuid.uuid4()),
                'title': safe_title,
                'content': safe_content,
                'author_id': user['id'],
                'created_at': datetime.now().isoformat(),
                'ip_address': self._hash_ip(request.get('ip_address', ''))
            }
            
            # 데이터베이스 저장 (매개변수화된 쿼리)
            await self._save_post_safely(post)
            
            return Success({
                'id': post['id'],
                'title': post['title'],
                'created_at': post['created_at']
            })
            
        except Exception as e:
            return Failure(f"게시글 생성 실패: {str(e)}")
    
    def _sanitize_html(self, text: str) -> str:
        """HTML 새니타이제이션"""
        import html
        # 기본 HTML 이스케이프
        sanitized = html.escape(text)
        
        # 추가 위험 패턴 제거
        patterns_to_remove = [
            r'javascript:',
            r'vbscript:',
            r'onload=',
            r'onerror=',
            r'<script[^>]*>.*?</script>',
        ]
        
        for pattern in patterns_to_remove:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        return sanitized.strip()
    
    def _escape_html(self, text: str) -> str:
        """HTML 이스케이프"""
        import html
        return html.escape(text, quote=True)
    
    def _hash_ip(self, ip_address: str) -> str:
        """IP 주소 해싱 (개인정보 보호)"""
        return hashlib.sha256(
            (ip_address + os.environ.get('IP_SALT', '')).encode()
        ).hexdigest()[:16]
    
    async def _save_post_safely(self, post: dict) -> None:
        """안전한 게시글 저장"""
        query = """
            INSERT INTO posts (id, title, content, author_id, created_at, ip_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        
        await self.db.execute(query, (
            post['id'],
            post['title'], 
            post['content'],
            post['author_id'],
            post['created_at'],
            post['ip_address']
        ))

# 보안 미들웨어 설정
security_middleware = SecurityMiddleware({
    'enable_hsts': True,
    'enable_csp': True,
    'csp_policy': "default-src 'self'; script-src 'self' 'unsafe-inline'",
    'enable_csrf_protection': True,
    'rate_limiting': {
        'enabled': True,
        'requests_per_minute': 100
    }
})
```

### 보안 설정 검증

```python
class SecurityConfigValidator:
    """보안 설정 검증"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.vulnerabilities = []
    
    async def validate_all(self) -> List[dict]:
        """전체 보안 설정 검증"""
        self.vulnerabilities = []
        
        await self._check_environment_variables()
        await self._check_file_permissions()
        await self._check_network_settings()
        await self._check_database_config()
        
        return self.vulnerabilities
    
    async def _check_environment_variables(self):
        """환경 변수 보안 검사"""
        dangerous_patterns = {
            'DEBUG': ['true', '1', 'yes'],
            'SECRET_KEY': ['secret', 'default', 'change_me'],
            'DATABASE_URL': ['localhost', '127.0.0.1'],
            'ALLOWED_HOSTS': ['*', 'all']
        }
        
        for var_name, dangerous_values in dangerous_patterns.items():
            value = os.environ.get(var_name, '').lower()
            
            if value in dangerous_values:
                self.vulnerabilities.append({
                    'type': 'insecure_config',
                    'severity': 'high',
                    'description': f'환경 변수 {var_name}이 안전하지 않은 값으로 설정됨',
                    'value': value,
                    'recommendations': [
                        f'{var_name}을 프로덕션에 적합한 값으로 변경',
                        '환경별 설정 파일 분리',
                        '시크릿 관리 시스템 도입'
                    ]
                })
    
    async def _check_file_permissions(self):
        """파일 권한 검사"""
        sensitive_files = [
            '.env', 'config.py', 'settings.py',
            'private_key.pem', '*.key'
        ]
        
        for file_pattern in sensitive_files:
            files = glob.glob(file_pattern)
            
            for file_path in files:
                try:
                    stat_info = os.stat(file_path)
                    
                    # 다른 사용자가 읽을 수 있는지 확인
                    if stat_info.st_mode & 0o004:
                        self.vulnerabilities.append({
                            'type': 'permission_issue',
                            'severity': 'medium',
                            'description': f'파일 {file_path}이 다른 사용자에게 읽기 권한 부여됨',
                            'file': file_path,
                            'permissions': oct(stat_info.st_mode)[-3:],
                            'recommendations': [
                                f'chmod 600 {file_path}',
                                '민감한 파일의 접근 권한 제한'
                            ]
                        })
                        
                except OSError:
                    continue

# 사용
validator = SecurityConfigValidator(".")
vulnerabilities = await validator.validate_all()

print(f"보안 설정 검증 결과: {len(vulnerabilities)}개 이슈 발견")
for vuln in vulnerabilities:
    print(f"- {vuln['description']} (심각도: {vuln['severity']})")
```

### 보안 감사 및 모니터링

```python
from rfs.security.audit import SecurityAuditor
from rfs.core.logging_decorators import AuditLogged, AuditEventType

class SecurityMonitor:
    """보안 모니터링"""
    
    def __init__(self):
        self.auditor = SecurityAuditor()
        self.suspicious_activities = []
    
    @AuditLogged(
        event_type=AuditEventType.SECURITY_EVENT,
        resource_type="security_monitor",
        include_changes=True
    )
    async def detect_suspicious_activity(
        self, 
        user_id: str,
        ip_address: str,
        action: str,
        user_agent: str
    ) -> Result[dict, str]:
        """의심스러운 활동 탐지"""
        try:
            risk_score = 0
            alerts = []
            
            # 1. 비정상적인 로그인 패턴
            recent_logins = await self._get_recent_logins(user_id, hours=24)
            
            # 여러 IP에서 로그인
            unique_ips = set(login['ip_address'] for login in recent_logins)
            if len(unique_ips) > 5:
                risk_score += 30
                alerts.append("24시간 내 여러 IP에서 로그인 시도")
            
            # 지리적으로 불가능한 로그인
            if await self._check_impossible_travel(recent_logins):
                risk_score += 50
                alerts.append("지리적으로 불가능한 로그인 패턴")
            
            # 2. 비정상적인 요청 패턴
            if await self._check_rate_limit_abuse(user_id, ip_address):
                risk_score += 40
                alerts.append("비정상적으로 많은 요청")
            
            # 3. 비정상적인 User-Agent
            if await self._check_suspicious_user_agent(user_agent):
                risk_score += 20
                alerts.append("의심스러운 User-Agent")
            
            # 4. 알려진 악성 IP
            if await self._check_malicious_ip(ip_address):
                risk_score += 60
                alerts.append("알려진 악성 IP에서 접근")
            
            # 보안 이벤트 기록
            security_event = {
                'event_id': str(uuid.uuid4()),
                'user_id': user_id,
                'ip_address': ip_address,
                'action': action,
                'risk_score': risk_score,
                'alerts': alerts,
                'timestamp': datetime.now().isoformat(),
                'requires_action': risk_score >= 70
            }
            
            if security_event['requires_action']:
                # 자동 보안 조치
                await self._take_security_action(security_event)
            
            self.suspicious_activities.append(security_event)
            
            return Success(security_event)
            
        except Exception as e:
            return Failure(f"보안 모니터링 실패: {str(e)}")
    
    async def _check_impossible_travel(self, logins: List[dict]) -> bool:
        """지리적으로 불가능한 이동 확인"""
        if len(logins) < 2:
            return False
        
        # 실제로는 IP 지리정보 서비스 사용
        for i in range(1, len(logins)):
            prev_login = logins[i-1]
            curr_login = logins[i]
            
            # 시간 차이 계산
            time_diff = (
                datetime.fromisoformat(curr_login['timestamp']) -
                datetime.fromisoformat(prev_login['timestamp'])
            ).total_seconds() / 3600  # 시간 단위
            
            # 거리 계산 (시뮬레이션)
            distance_km = self._calculate_distance(
                prev_login['ip_address'],
                curr_login['ip_address']
            )
            
            # 물리적으로 불가능한 속도 (시속 800km 이상)
            if distance_km / max(time_diff, 0.1) > 800:
                return True
        
        return False
    
    async def _take_security_action(self, event: dict):
        """자동 보안 조치"""
        if event['risk_score'] >= 90:
            # 계정 임시 잠금
            await self._lock_user_account(event['user_id'])
            
            # 보안팀에 알림
            await self._notify_security_team(event)
            
        elif event['risk_score'] >= 70:
            # 추가 인증 요구
            await self._require_additional_auth(event['user_id'])
            
            # 세션 무효화
            await self._invalidate_user_sessions(event['user_id'])

# 사용
monitor = SecurityMonitor()

# 의심스러운 활동 탐지
result = await monitor.detect_suspicious_activity(
    user_id="user123",
    ip_address="192.168.1.100",
    action="login",
    user_agent="Mozilla/5.0..."
)

if result.is_success():
    event = result.unwrap()
    if event['requires_action']:
        print(f"보안 경고: 위험도 {event['risk_score']}")
        print(f"경고사항: {', '.join(event['alerts'])}")
```

## 🎨 베스트 프랙티스

### 1. 심층 방어 (Defense in Depth)

```python
# ✅ 좋은 예 - 다층 보안
@RequiresAuthentication()
@RequiresRole(Role.USER)
@RateLimited(requests_per_minute=30)
@ValidatedInput(rules={'data': {'max_length': 1000}})
@Sanitized(fields=['data'])
async def secure_endpoint(data: str, current_user: User) -> Result[dict, str]:
    """다층 보안이 적용된 엔드포인트"""
    # 비즈니스 로직
    pass
```

### 2. 입력 검증과 새니타이제이션

```python
# ✅ 좋은 예 - 완전한 입력 검증
def validate_and_sanitize_input(user_input: str) -> Result[str, str]:
    # 1. 길이 검증
    if len(user_input) > 1000:
        return Failure("입력이 너무 깁니다")
    
    # 2. 문자 검증 (화이트리스트 방식)
    allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?-')
    if not all(c in allowed_chars for c in user_input):
        return Failure("허용되지 않은 문자가 포함되었습니다")
    
    # 3. HTML 이스케이프
    import html
    sanitized = html.escape(user_input, quote=True)
    
    return Success(sanitized)
```

### 3. 안전한 암호화

```python
# ✅ 좋은 예 - 안전한 암호화 사용
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os

class SecureEncryption:
    def __init__(self, password: str):
        # PBKDF2로 키 유도
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self.cipher = Fernet(key)
        self.salt = salt
    
    def encrypt(self, data: str) -> str:
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        return self.cipher.decrypt(encrypted_data.encode()).decode()
```

### 4. 보안 로깅

```python
# ✅ 좋은 예 - 보안 이벤트 로깅
@AuditLogged(
    event_type=AuditEventType.SECURITY_EVENT,
    resource_type="authentication",
    include_user_info=True
)
async def handle_failed_login(username: str, ip_address: str):
    """실패한 로그인 시도 처리"""
    
    # 실패 횟수 증가
    await increment_failed_attempts(username, ip_address)
    
    # 계정 잠금 확인
    if await should_lock_account(username):
        await lock_account(username)
        
        # 보안 경고 로그
        logger.security_warning(
            f"Account locked due to repeated failed login attempts",
            extra={
                'username': username,
                'ip_address': ip_address,
                'event_type': 'account_lockout'
            }
        )
```

## ⚠️ 주의사항

### 1. 시크릿 관리
- 코드에 하드코딩된 비밀번호, API 키 절대 금지
- 환경 변수나 시크릿 관리 시스템 사용
- 정기적인 키 로테이션 구현

### 2. 입력 검증
- 모든 외부 입력에 대한 검증 필수
- 화이트리스트 방식 우선 사용
- 클라이언트 측 검증만으로는 불충분

### 3. 에러 메시지
- 공격자에게 시스템 내부 정보 노출 방지
- 일반적이고 모호한 에러 메시지 사용
- 상세한 오류는 로그에만 기록

### 4. 보안 업데이트
- 의존성 라이브러리 정기적 업데이트
- 보안 취약점 스캔 자동화
- 보안 패치 적용 프로세스 구축

## 🔗 관련 문서
- [접근 제어](./10-access-control.md) - 인증 및 권한 관리
- [로깅](./07-logging.md) - 보안 감사 로그
- [유효성 검사](./09-validation.md) - 입력 검증 시스템
- [모니터링](./08-monitoring.md) - 보안 메트릭 수집