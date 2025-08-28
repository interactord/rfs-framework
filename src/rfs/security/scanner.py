"""
Security Scanner (RFS v4)

RFS v4 보안 취약점 스캐닝 시스템
- 코드 취약점 분석
- 의존성 보안 검사
- 설정 보안 점검
- 네트워크 보안 검증
"""

import ast
import asyncio
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich.tree import Tree

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
from ..core.result import Failure, Result, Success

if RICH_AVAILABLE:
    console: Optional[Console] = Console()
else:
    console = None


class ThreatLevel(Enum):
    """위협 수준"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityType(Enum):
    """취약점 유형"""

    CODE_INJECTION = "code_injection"
    XSS = "xss"
    SQLI = "sql_injection"
    PATH_TRAVERSAL = "path_traversal"
    WEAK_CRYPTO = "weak_cryptography"
    INSECURE_CONFIG = "insecure_configuration"
    HARDCODED_SECRET = "hardcoded_secret"
    DEPENDENCY_VULN = "dependency_vulnerability"
    PERMISSION_ISSUE = "permission_issue"
    INFORMATION_LEAK = "information_leakage"


@dataclass
class VulnerabilityReport:
    """취약점 리포트"""

    vuln_id: str
    vuln_type: VulnerabilityType
    threat_level: ThreatLevel
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    cwe_id: Optional[str] = None
    cvss_score: Optional[float] = None
    remediation: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    confirmed: bool = False

    @property
    def risk_score(self) -> int:
        """위험 점수 계산 (1-100)"""
        base_scores = {
            ThreatLevel.CRITICAL: 90,
            ThreatLevel.HIGH: 70,
            ThreatLevel.MEDIUM: 50,
            ThreatLevel.LOW: 30,
            ThreatLevel.INFO: 10,
        }
        score = base_scores.get(self.threat_level, 50)
        if self.cvss_score:
            score = int((score + self.cvss_score * 10) / 2)
        return min(100, max(1, score))


class SecurityScanner:
    """보안 스캐너 메인 클래스"""

    def __init__(self, project_path=None):
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.vulnerabilities: List[VulnerabilityReport] = []
        self._load_security_patterns()

    def _load_security_patterns(self):
        """보안 패턴 로드"""
        self.dangerous_functions = {
            "eval",
            "exec",
            "compile",
            "__import__",
            "input",
            "raw_input",
            "file",
            "open",
            "subprocess.call",
            "subprocess.run",
            "os.system",
            "pickle.load",
            "pickle.loads",
            "yaml.load",
        }
        self.secret_patterns = [
            ("password\\s*=\\s*[\"\\'][^\"\\']{3,}[\"\\']", "hardcoded_password"),
            ("secret\\s*=\\s*[\"\\'][^\"\\']{10,}[\"\\']", "hardcoded_secret"),
            ("token\\s*=\\s*[\"\\'][^\"\\']{10,}[\"\\']", "hardcoded_token"),
            ("key\\s*=\\s*[\"\\'][^\"\\']{10,}[\"\\']", "hardcoded_key"),
            ("api_key\\s*=\\s*[\"\\'][^\"\\']{10,}[\"\\']", "hardcoded_api_key"),
            ("-----BEGIN [A-Z ]+-----", "embedded_certificate"),
            ("sk-[a-zA-Z0-9]{48}", "openai_api_key"),
            ("ghp_[a-zA-Z0-9]{36}", "github_token"),
            ("xoxb-[0-9]{13}-[0-9]{13}-[a-zA-Z0-9]{24}", "slack_token"),
        ]
        self.sqli_patterns = [
            "[\"\\'].*\\+.*[\"\\'].*WHERE",
            "cursor\\.execute\\s*\\(\\s*[\"\\'][^\"\\']*%[sf][^\"\\']*[\"\\']",
            "query\\s*=\\s*[\"\\'].*\\+.*[\"\\']",
            "SELECT.*FROM.*WHERE.*[\"\\'].*\\+.*[\"\\']",
        ]
        self.path_traversal_patterns = [
            "\\.\\./",
            "\\.\\.\\\\",
            "path.*\\+.*request",
            "filename.*request\\.",
            "os\\.path\\.join.*request\\.",
        ]

    async def run_security_scan(
        self, scan_types: Optional[List[str]] = None
    ) -> Result[List[VulnerabilityReport], str]:
        """보안 스캔 실행"""
        try:
            if console:
                console.print(
                    Panel(
                        f"🔒 RFS v4 보안 스캔 시작\n\n📁 프로젝트 경로: {self.project_path}\n🔍 스캔 유형: {(', '.join(scan_types) if scan_types else '전체 스캔')}\n⏰ 시작 시간: {datetime.now().strftime('%H:%M:%S')}",
                        title="보안 스캔",
                        border_style="red",
                    )
                )
            self.vulnerabilities = []
            scan_tasks: List[Tuple[str, Any]] = []
            if not scan_types or "code" in scan_types:
                scan_tasks.append(
                    ("코드 취약점 분석", self._scan_code_vulnerabilities)
                )
            if not scan_types or "dependencies" in scan_types:
                scan_tasks.append(
                    ("의존성 보안 검사", self._scan_dependency_vulnerabilities)
                )
            if not scan_types or "config" in scan_types:
                scan_tasks.append(
                    ("설정 보안 점검", self._scan_configuration_security)
                )
            if not scan_types or "files" in scan_types:
                scan_tasks.append(
                    ("파일 권한 검사", self._scan_file_permissions)
                )
            if not scan_types or "secrets" in scan_types:
                scan_tasks.append(
                    ("시크릿 탐지", self._scan_hardcoded_secrets)
                )
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console,
            ) as progress:
                for scan_name, scan_func in scan_tasks:
                    task = progress.add_task(f"{scan_name} 중...", total=100)
                    try:
                        vulnerabilities = await scan_func()
                        if vulnerabilities:
                            self.vulnerabilities.extend(vulnerabilities
                            )
                    except Exception as e:
                        if console:
                            console.print(
                                f"⚠️  {scan_name} 실패: {str(e)}", style="yellow"
                            )
                    progress.update(task, completed=100)
            self.vulnerabilities.sort(key=lambda v: v.risk_score, reverse=True)
            if console:
                await self._display_scan_results()
            return Success(self.vulnerabilities)
        except Exception as e:
            return Failure(f"보안 스캔 실패: {str(e)}")

    async def _scan_code_vulnerabilities(self) -> List[VulnerabilityReport]:
        """코드 취약점 분석"""
        vulnerabilities: List[VulnerabilityReport] = []
        try:
            python_files = list(self.project_path.rglob("*.py"))
            for py_file in python_files:
                try:
                    content = py_file.read_text(encoding="utf-8")
                    try:
                        tree = ast.parse(content)
                        file_vulnerabilities = await self._analyze_ast_vulnerabilities(
                            tree, py_file, content
                        )
                        vulnerabilities.extend(file_vulnerabilities)
                    except SyntaxError:
                        continue
                    pattern_vulnerabilities = (
                        await self._analyze_pattern_vulnerabilities(py_file, content)
                    )
                    vulnerabilities.extend(pattern_vulnerabilities)
                except Exception as e:
                    if console:
                        console.print(
                            f"⚠️  파일 분석 실패 {py_file}: {str(e)}", style="yellow"
                        )
        except Exception as e:
            if console:
                console.print(f"⚠️  코드 취약점 분석 실패: {str(e)}", style="yellow")
        return vulnerabilities

    async def _analyze_ast_vulnerabilities(
        self, tree: ast.AST, file_path: Path, content: str
    ) -> List[VulnerabilityReport]:
        """AST 기반 취약점 분석"""
        vulnerabilities: List[VulnerabilityReport] = []
        lines = content.split("\n")
        for node in ast.walk(tree):
            if type(node).__name__ == "Call":
                func_name = self._get_function_name(node.func)  # type: ignore[attr-defined]
                if func_name in self.dangerous_functions:
                    line_content = (
                        lines[node.lineno - 1] if hasattr(node, 'lineno') and node.lineno <= len(lines) else ""
                    )
                    severity = (
                        ThreatLevel.CRITICAL
                        if func_name in ["eval", "exec"]
                        else ThreatLevel.HIGH
                    )
                    vulnerabilities = vulnerabilities + [
                        VulnerabilityReport(
                            vuln_id=self._generate_vuln_id(file_path, getattr(node, 'lineno', 0)),
                            vuln_type=VulnerabilityType.CODE_INJECTION,
                            threat_level=severity,
                            title=f"위험한 함수 사용: {func_name}",
                            description=f"보안상 위험한 함수 '{func_name}'가 사용되었습니다",
                            file_path=str(file_path.relative_to(self.project_path)),
                            line_number=getattr(node, 'lineno', 0),
                            code_snippet=line_content.strip(),
                            cwe_id=(
                                "CWE-94" if func_name in ["eval", "exec"] else "CWE-78"
                            ),
                            remediation=[
                                f"{func_name} 함수 사용을 피하고 안전한 대안 사용",
                                "입력 검증 및 화이트리스트 방식 적용",
                                "최소 권한 원칙 적용",
                            ],
                            references=[
                                "https://owasp.org/www-project-top-ten/2017/A1_2017-Injection"
                            ],
                        )
                    ]
            if type(node).__name__ == "Str" and hasattr(node, 's') and len(getattr(node, 's', '')) > 8:
                node_s = getattr(node, 's', '')
                if any(
                    (
                        keyword in node_s.lower()
                        for keyword in ["password", "secret", "token", "key"]
                    )
                ):
                    line_content = (
                        lines[node.lineno - 1] if hasattr(node, 'lineno') and node.lineno <= len(lines) else ""
                    )
                    vulnerabilities = vulnerabilities + [
                        VulnerabilityReport(
                            vuln_id=self._generate_vuln_id(file_path, getattr(node, 'lineno', 0)),
                            vuln_type=VulnerabilityType.HARDCODED_SECRET,
                            threat_level=ThreatLevel.HIGH,
                            title="하드코딩된 시크릿 의심",
                            description="코드에 하드코딩된 시크릿이 포함되어 있을 수 있습니다",
                            file_path=str(file_path.relative_to(self.project_path)),
                            line_number=getattr(node, 'lineno', 0),
                            code_snippet=line_content.strip(),
                            cwe_id="CWE-798",
                            remediation=[
                                "환경 변수나 보안 저장소 사용",
                                "설정 파일을 .gitignore에 추가",
                                "시크릿 관리 시스템 도입",
                            ],
                        )
                    ]
        return vulnerabilities

    def _get_function_name(self, node: ast.AST) -> str:
        """함수 이름 추출"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                return f"{node.value.id}.{node.attr}"
            else:
                return node.attr
        return ""

    async def _analyze_pattern_vulnerabilities(
        self, file_path: Path, content: str
    ) -> List[VulnerabilityReport]:
        """패턴 기반 취약점 분석"""
        vulnerabilities: List[VulnerabilityReport] = []
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            for pattern in self.sqli_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    vulnerabilities.append(
                        VulnerabilityReport(
                            vuln_id=self._generate_vuln_id(file_path, i),
                            vuln_type=VulnerabilityType.SQLI,
                            threat_level=ThreatLevel.HIGH,
                            title="SQL 인젝션 취약점 의심",
                            description="SQL 인젝션 공격에 취약할 수 있는 코드가 발견되었습니다",
                            file_path=str(file_path.relative_to(self.project_path)),
                            line_number=i,
                            code_snippet=line.strip(),
                            cwe_id="CWE-89",
                            remediation=[
                                "매개변수화된 쿼리 사용",
                                "ORM 사용 권장",
                                "입력 검증 및 이스케이핑",
                            ],
                        )
                    )
            for pattern in self.path_traversal_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    vulnerabilities.append(
                        VulnerabilityReport(
                            vuln_id=self._generate_vuln_id(file_path, i),
                            vuln_type=VulnerabilityType.PATH_TRAVERSAL,
                            threat_level=ThreatLevel.MEDIUM,
                            title="경로 조작 취약점 의심",
                            description="경로 조작 공격에 취약할 수 있는 코드가 발견되었습니다",
                            file_path=str(file_path.relative_to(self.project_path)),
                            line_number=i,
                            code_snippet=line.strip(),
                            cwe_id="CWE-22",
                            remediation=[
                                "경로 정규화 및 검증",
                                "안전한 경로만 허용하는 화이트리스트 방식",
                                "chroot jail 사용 고려",
                            ],
                        )
                    )
        return vulnerabilities

    async def _scan_dependency_vulnerabilities(self) -> List[VulnerabilityReport]:
        """의존성 보안 검사"""
        vulnerabilities: List[VulnerabilityReport] = []
        try:
            requirements_file = self.project_path / "requirements.txt"
            if requirements_file.exists():
                dep_vulnerabilities = await self._check_python_dependencies(requirements_file)
                vulnerabilities.extend(dep_vulnerabilities)
            pyproject_file = self.project_path / "pyproject.toml"
            if pyproject_file.exists():
                pyproject_vulnerabilities = await self._check_pyproject_dependencies(pyproject_file)
                vulnerabilities.extend(pyproject_vulnerabilities)
        except Exception as e:
            if console:
                console.print(f"⚠️  의존성 검사 실패: {str(e)}", style="yellow")
        return vulnerabilities

    async def _check_python_dependencies(
        self, requirements_file: Path
    ) -> List[VulnerabilityReport]:
        """Python 의존성 검사"""
        vulnerabilities: List[VulnerabilityReport] = []
        try:
            try:
                result = subprocess.run(
                    ["safety", "check", "-r", str(requirements_file), "--json"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    try:
                        safety_data = json.loads(result.stdout)
                        for vuln in safety_data:
                            vulnerabilities = vulnerabilities + [
                                VulnerabilityReport(
                                    vuln_id=f"DEP-{vuln.get('id', 'unknown')}",
                                    vuln_type=VulnerabilityType.DEPENDENCY_VULN,
                                    threat_level=self._map_safety_severity(
                                        vuln.get("severity", "medium")
                                    ),
                                    title=f"취약한 패키지: {vuln.get('package', 'unknown')}",
                                    description=vuln.get(
                                        "advisory", "알려진 취약점이 있는 패키지입니다"
                                    ),
                                    file_path=str(
                                        requirements_file.relative_to(self.project_path)
                                    ),
                                    remediation=[
                                        f"패키지를 {vuln.get('fixed_in', '최신 버전')}으로 업데이트",
                                        "대안 패키지 검토",
                                    ],
                                )
                            ]
                    except json.JSONDecodeError:
                        pass
            except (subprocess.TimeoutExpired, FileNotFoundError):
                vulnerabilities = vulnerabilities + await self._manual_dependency_check(
                    requirements_file
                )
        except Exception as e:
            if console:
                console.print(f"⚠️  Python 의존성 검사 실패: {str(e)}", style="yellow")
        return vulnerabilities

    def _map_safety_severity(self, severity: str) -> ThreatLevel:
        """Safety 도구 심각도를 ThreatLevel로 매핑"""
        mapping = {
            "critical": ThreatLevel.CRITICAL,
            "high": ThreatLevel.HIGH,
            "medium": ThreatLevel.MEDIUM,
            "low": ThreatLevel.LOW,
        }
        return mapping.get(severity.lower(), ThreatLevel.MEDIUM)

    async def _manual_dependency_check(
        self, requirements_file: Path
    ) -> List[VulnerabilityReport]:
        """수동 의존성 검사"""
        vulnerabilities: List[VulnerabilityReport] = []
        try:
            content = requirements_file.read_text()
            known_vulnerabilities = {
                "django": ["<2.2.20", "<3.0.14", "<3.1.8"],
                "flask": ["<1.1.4"],
                "requests": ["<2.25.1"],
                "pyyaml": ["<5.4"],
                "pillow": ["<8.1.1"],
                "urllib3": ["<1.26.4"],
            }
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "==" in line:
                    package_name, version = line.split("==", 1)
                    package_name = package_name.strip()
                    if package_name.lower() in known_vulnerabilities:
                        vulnerabilities = vulnerabilities + [
                            VulnerabilityReport(
                                vuln_id=f"MANUAL-{package_name}-{version}",
                                vuln_type=VulnerabilityType.DEPENDENCY_VULN,
                                threat_level=ThreatLevel.MEDIUM,
                                title=f"취약할 수 있는 패키지: {package_name}",
                                description=f"{package_name} {version}은 알려진 취약점이 있을 수 있습니다",
                                file_path=str(
                                    requirements_file.relative_to(self.project_path)
                                ),
                                remediation=[
                                    f"{package_name} 패키지를 최신 버전으로 업데이트",
                                    "보안 패치가 적용된 버전 확인",
                                ],
                            )
                        ]
        except Exception as e:
            if console:
                console.print(f"⚠️  수동 의존성 검사 실패: {str(e)}", style="yellow")
        return vulnerabilities

    async def _check_pyproject_dependencies(
        self, pyproject_file: Path
    ) -> List[VulnerabilityReport]:
        """pyproject.toml 의존성 검사"""
        vulnerabilities: List[VulnerabilityReport] = []
        try:
            # 실제 구현에서는 toml 파싱 및 취약점 DB 조회가 필요
            # 여기서는 기본적인 구조만 제공
            pass
        except Exception as e:
            if console:
                console.print(f"⚠️  pyproject.toml 검사 실패: {str(e)}", style="yellow")
        return vulnerabilities

    async def _scan_configuration_security(self) -> List[VulnerabilityReport]:
        """설정 보안 점검"""
        vulnerabilities: List[VulnerabilityReport] = []
        try:
            env_files = list(self.project_path.glob(".env*"))
            for env_file in env_files:
                if env_file.is_file():
                    vulnerabilities = (
                        vulnerabilities + await self._check_env_file_security(env_file)
                    )
            config_files = [
                self.project_path / "config.py",
                self.project_path / "settings.py",
                self.project_path / "rfs.yaml",
                self.project_path / "docker-compose.yml",
            ]
            for config_file in config_files:
                if config_file.exists():
                    vulnerabilities = (
                        vulnerabilities
                        + await self._check_config_file_security(config_file)
                    )
        except Exception as e:
            if console:
                console.print(f"⚠️  설정 보안 점검 실패: {str(e)}", style="yellow")
        return vulnerabilities

    async def _check_env_file_security(
        self, env_file: Path
    ) -> List[VulnerabilityReport]:
        """환경 변수 파일 보안 검사"""
        vulnerabilities: List[VulnerabilityReport] = []
        try:
            content = env_file.read_text()
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "DEBUG=True" in line.upper() or "DEBUG=1" in line:
                    vulnerabilities = vulnerabilities + [
                        VulnerabilityReport(
                            vuln_id=self._generate_vuln_id(env_file, i),
                            vuln_type=VulnerabilityType.INSECURE_CONFIG,
                            threat_level=ThreatLevel.HIGH,
                            title="프로덕션에서 디버그 모드 활성화",
                            description="디버그 모드가 활성화되어 민감한 정보가 노출될 수 있습니다",
                            file_path=str(env_file.relative_to(self.project_path)),
                            line_number=i,
                            code_snippet=line,
                            cwe_id="CWE-489",
                            remediation=[
                                "프로덕션 환경에서는 DEBUG=False 설정",
                                "환경별 설정 파일 분리",
                            ],
                        )
                    ]
                if any(
                    (
                        weak in line.upper()
                        for weak in ["SECRET=123", "PASSWORD=PASSWORD", "KEY=KEY"]
                    )
                ):
                    vulnerabilities = vulnerabilities + [
                        VulnerabilityReport(
                            vuln_id=self._generate_vuln_id(env_file, i),
                            vuln_type=VulnerabilityType.WEAK_CRYPTO,
                            threat_level=ThreatLevel.CRITICAL,
                            title="약한 시크릿/패스워드 사용",
                            description="기본값이나 약한 시크릿이 사용되고 있습니다",
                            file_path=str(env_file.relative_to(self.project_path)),
                            line_number=i,
                            code_snippet=line,
                            cwe_id="CWE-798",
                            remediation=[
                                "강한 랜덤 시크릿 생성",
                                "시크릿 관리 도구 사용",
                                "정기적인 시크릿 로테이션",
                            ],
                        )
                    ]
        except Exception as e:
            if console:
                console.print(
                    f"⚠️  환경 파일 검사 실패 {env_file}: {str(e)}", style="yellow"
                )
        return vulnerabilities

    async def _check_config_file_security(
        self, config_file: Path
    ) -> List[VulnerabilityReport]:
        """설정 파일 보안 검사"""
        vulnerabilities: List[VulnerabilityReport] = []
        try:
            # 실제 구현에서는 설정 파일별 보안 체크가 필요
            # 여기서는 기본적인 구조만 제공
            pass
        except Exception as e:
            if console:
                console.print(f"⚠️  설정 파일 검사 실패 {config_file}: {str(e)}", style="yellow")
        return vulnerabilities

    async def _scan_file_permissions(self) -> List[VulnerabilityReport]:
        """파일 권한 검사"""
        vulnerabilities: List[VulnerabilityReport] = []
        try:
            sensitive_files = [
                ".env",
                ".env.local",
                ".env.production",
                "secrets.json",
                "credentials.json",
                "private_key.pem",
                "*.key",
                "*.pem",
            ]
            for pattern in sensitive_files:
                files = list(self.project_path.glob(pattern))
                for file_path in files:
                    if file_path.is_file():
                        try:
                            import stat

                            file_stat = file_path.stat()
                            if file_stat.st_mode & stat.S_IROTH:
                                vulnerabilities.extend([
                                    VulnerabilityReport(
                                        vuln_id=f"PERM-{file_path.name}",
                                        vuln_type=VulnerabilityType.PERMISSION_ISSUE,
                                        threat_level=ThreatLevel.HIGH,
                                        title=f"안전하지 않은 파일 권한: {file_path.name}",
                                        description="민감한 파일이 다른 사용자에게 읽기 권한이 있습니다",
                                        file_path=str(
                                            file_path.relative_to(self.project_path)
                                        ),
                                        remediation=[
                                            f"chmod 600 {file_path.name}",
                                            "민감한 파일의 접근 권한 제한",
                                        ],
                                    )
                                ])
                        except Exception as e:
                            if console:
                                console.print(
                                    f"⚠️  파일 권한 확인 실패 {file_path}: {str(e)}",
                                    style="yellow",
                                )
        except Exception as e:
            if console:
                console.print(f"⚠️  파일 권한 검사 실패: {str(e)}", style="yellow")
        return vulnerabilities

    async def _scan_hardcoded_secrets(self) -> List[VulnerabilityReport]:
        """하드코딩된 시크릿 탐지"""
        vulnerabilities: List[VulnerabilityReport] = []
        try:
            text_files: List[Path] = []
            for ext in [
                "*.py",
                "*.js",
                "*.ts",
                "*.yaml",
                "*.yml",
                "*.json",
                "*.txt",
                "*.md",
            ]:
                text_files.extend(self.project_path.rglob(ext))
            for file_path in text_files:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    lines = content.split("\n")
                    for i, line in enumerate(lines, 1):
                        for pattern, secret_type in self.secret_patterns:
                            matches = re.finditer(pattern, line, re.IGNORECASE)
                            for match in matches:
                                vulnerabilities.extend([
                                    VulnerabilityReport(
                                        vuln_id=self._generate_vuln_id(file_path, i),
                                        vuln_type=VulnerabilityType.HARDCODED_SECRET,
                                        threat_level=ThreatLevel.CRITICAL,
                                        title=f"하드코딩된 시크릿 탐지: {secret_type}",
                                        description=f"코드에 {secret_type}가 하드코딩되어 있습니다",
                                        file_path=str(
                                            file_path.relative_to(self.project_path)
                                        ),
                                        line_number=i,
                                        code_snippet=line.strip(),
                                        cwe_id="CWE-798",
                                        remediation=[
                                            "환경 변수 사용",
                                            "시크릿 관리 서비스 활용",
                                            "코드에서 시크릿 제거 후 .gitignore 추가",
                                        ],
                                    )
                                ])
                except Exception as e:
                    continue
        except Exception as e:
            if console:
                console.print(f"⚠️  시크릿 탐지 실패: {str(e)}", style="yellow")
        return vulnerabilities

    def _generate_vuln_id(self, file_path: Path, line_number: int) -> str:
        """취약점 ID 생성"""
        file_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
        return f"VULN-{file_hash}-{line_number}"

    async def _display_scan_results(self):
        """스캔 결과 표시"""
        if not console:
            return
        total_vulns = len(self.vulnerabilities)
        if total_vulns == 0:
            console.print(
                Panel(
                    "✅ 취약점이 발견되지 않았습니다!\n\n🛡️  RFS v4 프로젝트의 보안 상태가 양호합니다.",
                    title="보안 스캔 완료",
                    border_style="green",
                )
            )
            return
        severity_stats: Dict[ThreatLevel, int] = {}
        for level in ThreatLevel:
            count = sum((1 for v in self.vulnerabilities if v.threat_level == level))
            if count > 0:
                severity_stats[level] = count
        summary_table = Table(
            title=f"보안 스캔 결과 ({total_vulns}개 취약점)",
            show_header=True,
            header_style="bold red",
        )
        summary_table.add_column("심각도", style="cyan", width=12)
        summary_table.add_column("개수", justify="right", width=8)
        summary_table.add_column("비율", justify="right", width=10)
        summary_table.add_column("상태", justify="center", width=8)
        severity_colors: Dict[ThreatLevel, str] = {
            ThreatLevel.CRITICAL: "bright_red",
            ThreatLevel.HIGH: "red",
            ThreatLevel.MEDIUM: "yellow",
            ThreatLevel.LOW: "green",
            ThreatLevel.INFO: "blue",
        }
        for level, count in severity_stats.items():
            color = severity_colors.get(level, "white")
            percentage = count / total_vulns * 100
            summary_table.add_row(
                f"[{color}]{level.value.upper()}[/{color}]",
                str(count),
                f"{percentage:.1f}%",
                (
                    "🚨"
                    if level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]
                    else "⚠️" if level == ThreatLevel.MEDIUM else "ℹ️"
                ),
            )
        console.print(summary_table)
        console.print("\n🎯 우선 수정 권장 취약점:")
        top_vulnerabilities = self.vulnerabilities[:5]
        for i, vuln in enumerate(top_vulnerabilities, 1):
            color = severity_colors.get(vuln.threat_level, "white")
            detail_panel = Panel(
                f"**{vuln.description}**\n\n파일: {vuln.file_path or 'N/A'}"
                + (f" (라인 {vuln.line_number})" if vuln.line_number else "")
                + "\n"
                + (f"코드: `{vuln.code_snippet}`\n\n" if vuln.code_snippet else "\n")
                + f"**수정 방법:**\n"
                + "\n".join([f"• {rec}" for rec in vuln.remediation[:2]]),
                title=f"{i}. {vuln.title} (위험도: {vuln.risk_score}/100)",
                border_style=color,
            )
            console.print(detail_panel)
        critical_high = sum(
            (
                1
                for v in self.vulnerabilities
                if v.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]
            )
        )
        if critical_high > 0:
            console.print(
                Panel(
                    f"🚨 {critical_high}개의 심각한 취약점이 발견되었습니다!\n\n즉시 수정이 필요한 항목들을 우선적으로 해결하세요.\n상세한 리포트는 보안 팀과 공유하여 검토받으시기 바랍니다.",
                    title="보안 경고",
                    border_style="bright_red",
                )
            )
        else:
            console.print(
                Panel(
                    f"⚠️  {total_vulns}개의 취약점이 발견되었습니다.\n\n대부분 중간 또는 낮은 위험도이므로 계획적으로 수정하세요.\n정기적인 보안 스캔을 통해 보안 수준을 유지하시기 바랍니다.",
                    title="보안 점검 완료",
                    border_style="yellow",
                )
            )

    async def generate_security_report(self, output_path: Optional[str] = None) -> Result[str, str]:
        """보안 리포트 생성"""
        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"security_report_{timestamp}.json"
            report = {
                "scan_info": {
                    "timestamp": datetime.now().isoformat(),
                    "project_path": str(self.project_path),
                    "total_vulnerabilities": len(self.vulnerabilities),
                },
                "summary": {
                    level.value: sum(
                        (1 for v in self.vulnerabilities if v.threat_level == level)
                    )
                    for level in ThreatLevel
                },
                "vulnerabilities": [
                    {
                        "id": vuln.vuln_id,
                        "type": vuln.vuln_type.value,
                        "threat_level": vuln.threat_level.value,
                        "title": vuln.title,
                        "description": vuln.description,
                        "file_path": vuln.file_path,
                        "line_number": vuln.line_number,
                        "code_snippet": vuln.code_snippet,
                        "cwe_id": vuln.cwe_id,
                        "cvss_score": vuln.cvss_score,
                        "risk_score": vuln.risk_score,
                        "remediation": vuln.remediation,
                        "references": vuln.references,
                        "confirmed": vuln.confirmed,
                    }
                    for vuln in self.vulnerabilities
                ],
            }
            report_file = Path(output_path)
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            return Success(str(report_file.absolute()))
        except Exception as e:
            return Failure(f"보안 리포트 생성 실패: {str(e)}")

    def get_vulnerability_summary(self) -> Dict[str, Any]:
        """취약점 요약 정보 조회"""
        if not self.vulnerabilities:
            return {"total": 0, "by_severity": {}, "by_type": {}}
        by_severity: Dict[str, int] = {}
        for level in ThreatLevel:
            count = sum((1 for v in self.vulnerabilities if v.threat_level == level))
            if count > 0:
                by_severity[level.value] = count
        by_type: Dict[str, int] = {}
        for vuln_type in VulnerabilityType:
            count = sum((1 for v in self.vulnerabilities if v.vuln_type == vuln_type))
            if count > 0:
                by_type[vuln_type.value] = count
        risk_scores = [v.risk_score for v in self.vulnerabilities]
        return {
            "total": len(self.vulnerabilities),
            "by_severity": by_severity,
            "by_type": by_type,
            "risk_stats": {
                "max_risk": max(risk_scores),
                "avg_risk": sum(risk_scores) / len(risk_scores),
                "high_risk_count": sum((1 for score in risk_scores if score >= 70)),
            },
            "critical_files": [
                v.file_path
                for v in self.vulnerabilities
                if v.threat_level == ThreatLevel.CRITICAL and v.file_path
            ][:5],
        }
