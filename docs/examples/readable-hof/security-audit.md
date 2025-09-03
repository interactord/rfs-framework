# 보안 감사 시스템 예제

Readable HOF를 사용하여 전체 프로젝트의 보안 감사를 수행하는 완전한 예제입니다.

## 전체 코드

```python
"""
RFS Readable HOF를 활용한 종합 보안 감사 시스템

이 예제는 다음 기능을 포함합니다:
- 코드 규칙 위반 검사
- 보안 패턴 스캔
- 설정 파일 검증
- 의존성 취약점 검사
- 포괄적인 보고서 생성
"""

import re
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from rfs.hof.readable import (
    apply_rules_to, scan_for, validate_config, extract_from,
    required, range_check, custom_check, email_check,
    create_security_violation, create_log_entry
)
from rfs.core.result import Result, Success, Failure


class SecurityAuditSystem:
    """종합 보안 감사 시스템"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.security_rules = self._load_security_rules()
        self.vulnerability_patterns = self._load_vulnerability_patterns()
        self.config_rules = self._load_config_validation_rules()
    
    def perform_comprehensive_audit(self) -> Dict[str, Any]:
        """포괄적인 보안 감사 수행"""
        print("🔍 포괄적인 보안 감사를 시작합니다...")
        
        # 1. 코드 규칙 위반 검사
        print("📝 코드 규칙 위반을 검사하는 중...")
        code_violations = self._check_code_rules()
        
        # 2. 보안 패턴 스캔
        print("🔎 보안 패턴을 스캔하는 중...")
        security_issues = self._scan_security_patterns()
        
        # 3. 설정 파일 검증
        print("⚙️ 설정 파일을 검증하는 중...")
        config_issues = self._validate_configurations()
        
        # 4. 의존성 검사
        print("📦 의존성 취약점을 검사하는 중...")
        dependency_issues = self._check_dependencies()
        
        # 5. 리포트 생성
        return self._generate_audit_report({
            "code_violations": code_violations,
            "security_issues": security_issues,
            "config_issues": config_issues,
            "dependency_issues": dependency_issues
        })
    
    def _check_code_rules(self) -> List[Dict]:
        """코드 규칙 위반 검사"""
        all_violations = []
        
        # Python 소스 파일 찾기
        python_files = list(self.project_path.rglob("*.py"))
        
        for file_path in python_files:
            if self._should_skip_file(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Readable HOF로 규칙 적용
                violations = (apply_rules_to(content)
                             .using(self.security_rules)
                             .with_context({
                                 "file_path": str(file_path),
                                 "file_size": len(content),
                                 "line_count": content.count('\n')
                             })
                             .collect_violations()
                             .filter_above_threshold("low"))
                
                all_violations.extend(violations.collect())
                
            except Exception as e:
                print(f"⚠️ 파일 처리 오류 {file_path}: {e}")
        
        return all_violations
    
    def _scan_security_patterns(self) -> List[Dict]:
        """보안 패턴 스캔"""
        all_issues = []
        
        # 다양한 파일 타입에서 보안 패턴 검색
        file_patterns = {
            "*.py": self.vulnerability_patterns["python"],
            "*.js": self.vulnerability_patterns["javascript"],
            "*.jsx": self.vulnerability_patterns["react"],
            "*.ts": self.vulnerability_patterns["typescript"],
            "*.env": self.vulnerability_patterns["environment"],
            "*.yml": self.vulnerability_patterns["yaml"],
            "*.yaml": self.vulnerability_patterns["yaml"],
        }
        
        for pattern, scan_patterns in file_patterns.items():
            files = list(self.project_path.rglob(pattern))
            
            for file_path in files:
                if self._should_skip_file(file_path):
                    continue
                    
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Readable HOF로 패턴 스캔
                    issues = (scan_for(scan_patterns)
                             .in_text(content)
                             .extract(lambda match, pattern_name: {
                                 "file_path": str(file_path),
                                 "line_number": content[:match.start()].count('\n') + 1,
                                 "match_text": match.group(0),
                                 "pattern_name": pattern_name,
                                 "severity": self._calculate_severity(pattern_name),
                                 "description": self._get_pattern_description(pattern_name),
                                 "recommendation": self._get_recommendation(pattern_name)
                             })
                             .filter_above_threshold("low")
                             .sort_by_severity())
                    
                    all_issues.extend(issues.collect())
                    
                except Exception as e:
                    print(f"⚠️ 스캔 오류 {file_path}: {e}")
        
        return all_issues
    
    def _validate_configurations(self) -> List[Dict]:
        """설정 파일 검증"""
        config_issues = []
        
        # 설정 파일 찾기
        config_files = [
            *self.project_path.rglob("*.env"),
            *self.project_path.rglob("config.py"),
            *self.project_path.rglob("settings.py"),
            *self.project_path.rglob("*.yml"),
            *self.project_path.rglob("*.yaml"),
            *self.project_path.rglob("*.json"),
        ]
        
        for config_file in config_files:
            if self._should_skip_file(config_file):
                continue
                
            try:
                config_data = self._load_config_file(config_file)
                
                # Readable HOF로 설정 검증
                result = validate_config(config_data).against_rules(
                    self.config_rules.get(config_file.suffix, [])
                )
                
                if result.is_failure():
                    config_issues.append({
                        "file": str(config_file),
                        "type": "validation_failure",
                        "errors": result.unwrap_error(),
                        "severity": "medium",
                        "recommendation": "설정 파일의 필수 항목을 확인하고 올바른 값으로 설정하세요."
                    })
                    
            except Exception as e:
                config_issues.append({
                    "file": str(config_file),
                    "type": "parsing_error", 
                    "errors": str(e),
                    "severity": "high",
                    "recommendation": "설정 파일의 구문을 확인하고 유효한 형식으로 수정하세요."
                })
        
        return config_issues
    
    def _check_dependencies(self) -> List[Dict]:
        """의존성 취약점 검사"""
        dependency_issues = []
        
        # 의존성 파일 찾기
        dependency_files = [
            self.project_path / "requirements.txt",
            self.project_path / "pyproject.toml",
            self.project_path / "package.json",
            self.project_path / "Pipfile",
        ]
        
        for dep_file in dependency_files:
            if not dep_file.exists():
                continue
                
            try:
                dependencies = self._parse_dependency_file(dep_file)
                
                # 배치 처리로 의존성 검사
                issues = (extract_from(dependencies)
                         .flatten_batches()
                         .transform_to(self._check_dependency_vulnerability)
                         .filter_by(lambda item: item is not None)
                         .collect())
                
                dependency_issues.extend(issues)
                
            except Exception as e:
                dependency_issues.append({
                    "file": str(dep_file),
                    "type": "dependency_check_error",
                    "error": str(e),
                    "severity": "medium"
                })
        
        return dependency_issues
    
    def _generate_audit_report(self, audit_results: Dict) -> Dict[str, Any]:
        """감사 리포트 생성"""
        
        # 결과 요약
        summary = (extract_from(audit_results.values())
                  .flatten_batches()
                  .group_by(lambda item: item.get("severity", "unknown"))
                  .transform_to(lambda group: {
                      "severity": group["key"],
                      "count": len(group["items"]),
                      "percentage": len(group["items"]) / sum(len(v) for v in audit_results.values()) * 100
                  })
                  .sort_by(lambda item: {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(item["severity"], 0))
                  .collect())
        
        # 우선순위 이슈들
        priority_issues = (extract_from(audit_results.values())
                          .flatten_batches()
                          .filter_by(lambda item: item.get("severity") in ["critical", "high"])
                          .sort_by(lambda item: (
                              {"critical": 4, "high": 3}.get(item["severity"], 0),
                              item.get("file_path", "")
                          ))
                          .limit(10)
                          .collect())
        
        report = {
            "audit_timestamp": datetime.now().isoformat(),
            "project_path": str(self.project_path),
            "summary": {
                "total_issues": sum(len(v) for v in audit_results.values()),
                "by_severity": summary,
                "by_category": {
                    "code_violations": len(audit_results["code_violations"]),
                    "security_issues": len(audit_results["security_issues"]), 
                    "config_issues": len(audit_results["config_issues"]),
                    "dependency_issues": len(audit_results["dependency_issues"])
                }
            },
            "priority_issues": priority_issues,
            "detailed_results": audit_results,
            "recommendations": self._generate_recommendations(audit_results)
        }
        
        return report
    
    # ========== 헬퍼 메서드들 ==========
    
    def _load_security_rules(self) -> List:
        """보안 규칙 로드"""
        return [
            # 하드코딩된 시크릿 검사
            lambda content: self._check_hardcoded_secrets(content),
            
            # SQL 인젝션 패턴 검사
            lambda content: self._check_sql_injection_patterns(content),
            
            # XSS 취약점 검사
            lambda content: self._check_xss_patterns(content),
            
            # 안전하지 않은 함수 사용 검사
            lambda content: self._check_unsafe_functions(content),
            
            # 디버그 정보 노출 검사
            lambda content: self._check_debug_exposure(content),
        ]
    
    def _load_vulnerability_patterns(self) -> Dict:
        """취약점 패턴 로드"""
        return {
            "python": [
                re.compile(r'password\s*=\s*["\']([^"\']{8,})["\']', re.IGNORECASE),
                re.compile(r'api_key\s*[:=]\s*["\']([^"\']{16,})["\']', re.IGNORECASE),
                re.compile(r'secret\s*[:=]\s*["\']([^"\']{16,})["\']', re.IGNORECASE),
                re.compile(r'token\s*[:=]\s*["\']([^"\']{16,})["\']', re.IGNORECASE),
                re.compile(r'eval\s*\(', re.IGNORECASE),
                re.compile(r'exec\s*\(', re.IGNORECASE),
                re.compile(r'__import__\s*\(', re.IGNORECASE),
            ],
            "javascript": [
                re.compile(r'console\.log\s*\(.*password', re.IGNORECASE),
                re.compile(r'localStorage\.setItem\s*\(\s*["\'][^"\']*password', re.IGNORECASE),
                re.compile(r'eval\s*\(', re.IGNORECASE),
                re.compile(r'innerHTML\s*=.*\+', re.IGNORECASE),
            ],
            "environment": [
                re.compile(r'^[A-Z_]+_PASSWORD=.+$', re.MULTILINE),
                re.compile(r'^[A-Z_]+_SECRET=.+$', re.MULTILINE),
                re.compile(r'^[A-Z_]+_KEY=.+$', re.MULTILINE),
            ],
            "yaml": [
                re.compile(r'password:\s*.+', re.IGNORECASE),
                re.compile(r'secret:\s*.+', re.IGNORECASE),
                re.compile(r'token:\s*.+', re.IGNORECASE),
            ]
        }
    
    def _load_config_validation_rules(self) -> Dict:
        """설정 검증 규칙 로드"""
        return {
            ".py": [
                custom_check("DEBUG", lambda x: x is False, "프로덕션에서는 DEBUG=False"),
                required("SECRET_KEY", "SECRET_KEY가 설정되어야 합니다"),
                custom_check("SECRET_KEY", 
                           lambda x: len(str(x)) >= 50,
                           "SECRET_KEY는 50자 이상이어야 합니다"),
            ],
            ".env": [
                required("DATABASE_URL", "데이터베이스 URL이 필요합니다"),
                custom_check("DATABASE_URL",
                           lambda x: x.startswith(('postgresql://', 'mysql://', 'sqlite:///')),
                           "유효한 데이터베이스 URL 형식이어야 합니다"),
            ],
            ".json": [
                required("name", "프로젝트 이름이 필요합니다"),
                custom_check("version",
                           lambda x: re.match(r'^\d+\.\d+\.\d+$', str(x)),
                           "유효한 버전 형식이어야 합니다 (x.y.z)"),
            ]
        }
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """파일을 건너뛸지 확인"""
        skip_patterns = [
            "*/venv/*", "*/env/*", "*/.env/*",
            "*/node_modules/*", "*/.git/*",
            "*/__pycache__/*", "*.pyc",
            "*/test/*", "*/tests/*",
            "*/.pytest_cache/*",
            "*/migrations/*"
        ]
        
        file_str = str(file_path)
        return any(file_str.match(pattern) for pattern in skip_patterns)
    
    def _load_config_file(self, file_path: Path) -> Dict:
        """설정 파일 로드"""
        if file_path.suffix == '.json':
            with open(file_path, 'r') as f:
                return json.load(f)
        elif file_path.suffix in ['.yml', '.yaml']:
            import yaml
            with open(file_path, 'r') as f:
                return yaml.safe_load(f) or {}
        elif file_path.suffix == '.env':
            config = {}
            with open(file_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        config[key] = value
            return config
        else:
            return {}
    
    def _check_hardcoded_secrets(self, content: str) -> bool:
        """하드코딩된 시크릿 검사"""
        patterns = [
            r'password\s*=\s*["\'][^"\']{4,}["\']',
            r'secret\s*=\s*["\'][^"\']{8,}["\']',
            r'api_key\s*=\s*["\'][^"\']{16,}["\']',
        ]
        return any(re.search(p, content, re.IGNORECASE) for p in patterns)
    
    def _check_sql_injection_patterns(self, content: str) -> bool:
        """SQL 인젝션 패턴 검사"""
        patterns = [
            r'execute\s*\(\s*["\'].*%s.*["\']',
            r'query\s*\(\s*["\'].*\+.*["\']',
            r'cursor\.execute\s*\([^)]*\+',
        ]
        return any(re.search(p, content, re.IGNORECASE) for p in patterns)
    
    def _calculate_severity(self, pattern_name: str) -> str:
        """패턴별 심각도 계산"""
        severity_map = {
            "hardcoded_password": "high",
            "sql_injection": "high", 
            "xss_vulnerability": "high",
            "eval_usage": "medium",
            "debug_exposure": "low",
            "unsafe_function": "medium"
        }
        return severity_map.get(pattern_name, "low")
    
    def _get_pattern_description(self, pattern_name: str) -> str:
        """패턴 설명 반환"""
        descriptions = {
            "hardcoded_password": "소스코드에 하드코딩된 비밀번호가 발견되었습니다",
            "sql_injection": "SQL 인젝션 취약점 가능성이 있습니다",
            "xss_vulnerability": "XSS 공격 취약점이 있을 수 있습니다",
            "eval_usage": "안전하지 않은 eval() 함수 사용",
            "debug_exposure": "디버그 정보가 노출될 수 있습니다",
        }
        return descriptions.get(pattern_name, "알 수 없는 보안 이슈")
    
    def _generate_recommendations(self, audit_results: Dict) -> List[str]:
        """권장사항 생성"""
        recommendations = []
        
        total_issues = sum(len(v) for v in audit_results.values())
        
        if audit_results["code_violations"]:
            recommendations.append(
                "🔧 코드 규칙 위반을 수정하고 정적 분석 도구를 CI/CD에 통합하세요."
            )
        
        if audit_results["security_issues"]:
            recommendations.append(
                "🛡️ 발견된 보안 취약점을 즉시 수정하고 보안 코드 리뷰를 강화하세요."
            )
            
        if audit_results["config_issues"]:
            recommendations.append(
                "⚙️ 설정 파일을 검토하고 보안 설정을 강화하세요."
            )
            
        if audit_results["dependency_issues"]:
            recommendations.append(
                "📦 취약한 의존성을 업데이트하고 정기적인 의존성 감사를 수행하세요."
            )
        
        if total_issues > 50:
            recommendations.append(
                "📊 발견된 이슈가 많습니다. 우선순위별로 단계적으로 해결하세요."
            )
        
        return recommendations


# 사용 예제
async def main():
    """보안 감사 시스템 실행 예제"""
    
    # 1. 감사 시스템 초기화
    project_path = "/path/to/your/project"
    audit_system = SecurityAuditSystem(project_path)
    
    # 2. 포괄적인 감사 수행
    audit_results = audit_system.perform_comprehensive_audit()
    
    # 3. 결과 출력
    print("\n" + "="*80)
    print("🔍 RFS 보안 감사 리포트")
    print("="*80)
    
    summary = audit_results["summary"]
    print(f"📊 총 발견된 이슈: {summary['total_issues']}개")
    print(f"📁 프로젝트 경로: {audit_results['project_path']}")
    print(f"⏰ 감사 시간: {audit_results['audit_timestamp']}")
    
    print("\n🏷️ 카테고리별 이슈:")
    for category, count in summary["by_category"].items():
        print(f"  • {category}: {count}개")
    
    print("\n⚠️ 심각도별 이슈:")
    for severity_info in summary["by_severity"]:
        severity = severity_info["severity"]
        count = severity_info["count"]
        percentage = severity_info["percentage"]
        print(f"  • {severity}: {count}개 ({percentage:.1f}%)")
    
    print("\n🚨 우선순위 이슈 (상위 10개):")
    for i, issue in enumerate(audit_results["priority_issues"], 1):
        print(f"{i:2d}. [{issue['severity'].upper()}] {issue.get('file_path', 'Unknown')}")
        print(f"    {issue.get('description', 'No description')}")
    
    print("\n💡 권장사항:")
    for i, recommendation in enumerate(audit_results["recommendations"], 1):
        print(f"{i}. {recommendation}")
    
    # 4. JSON 리포트 저장
    import json
    report_path = Path("security_audit_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(audit_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 상세 리포트가 {report_path}에 저장되었습니다.")
    
    return audit_results


if __name__ == "__main__":
    # 비동기 실행
    asyncio.run(main())
```

## 실행 결과 예시

```
🔍 포괄적인 보안 감사를 시작합니다...
📝 코드 규칙 위반을 검사하는 중...
🔎 보안 패턴을 스캔하는 중...
⚙️ 설정 파일을 검증하는 중...
📦 의존성 취약점을 검사하는 중...

================================================================================
🔍 RFS 보안 감사 리포트
================================================================================
📊 총 발견된 이슈: 23개
📁 프로젝트 경로: /path/to/your/project
⏰ 감사 시간: 2024-01-15T14:30:22.123456

🏷️ 카테고리별 이슈:
  • code_violations: 8개
  • security_issues: 12개
  • config_issues: 2개
  • dependency_issues: 1개

⚠️ 심각도별 이슈:
  • high: 3개 (13.0%)
  • medium: 8개 (34.8%)
  • low: 12개 (52.2%)

🚨 우선순위 이슈 (상위 10개):
 1. [HIGH] src/auth/login.py
    소스코드에 하드코딩된 비밀번호가 발견되었습니다
 2. [HIGH] src/database/queries.py
    SQL 인젝션 취약점 가능성이 있습니다
 3. [HIGH] config/settings.py
    프로덕션에서는 DEBUG=False

💡 권장사항:
1. 🔧 코드 규칙 위반을 수정하고 정적 분석 도구를 CI/CD에 통합하세요.
2. 🛡️ 발견된 보안 취약점을 즉시 수정하고 보안 코드 리뷰를 강화하세요.
3. ⚙️ 설정 파일을 검토하고 보안 설정을 강화하세요.
4. 📦 취약한 의존성을 업데이트하고 정기적인 의존성 감사를 수행하세요.

💾 상세 리포트가 security_audit_report.json에 저장되었습니다.
```

## 핵심 기능

### 1. Readable HOF 패턴 활용

- **apply_rules_to()**: 코드 규칙 위반 검사
- **scan_for()**: 보안 패턴 스캔
- **validate_config()**: 설정 검증
- **extract_from()**: 의존성 배치 처리

### 2. 자연어 같은 체이닝

```python
violations = (apply_rules_to(content)
             .using(self.security_rules)
             .with_context({"file_path": file_path})
             .collect_violations()
             .filter_above_threshold("low"))
```

### 3. 포괄적 보안 검사

- 하드코딩된 시크릿 탐지
- SQL 인젝션 패턴 검사
- XSS 취약점 탐지
- 안전하지 않은 함수 사용 검사
- 설정 파일 검증
- 의존성 취약점 분석

이 예제는 Readable HOF의 강력함을 보여주며, 복잡한 보안 감사 로직을 읽기 쉽고 유지보수하기 쉬운 선언적 코드로 구현하는 방법을 제시합니다.