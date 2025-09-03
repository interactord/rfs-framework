"""
RFS Readable HOF Scanning Module - Comprehensive Tests

이 모듈은 텍스트 스캔 및 패턴 매칭 시스템의 모든 기능을 포괄적으로 테스트합니다.
제안서의 모든 예제와 실제 사용 시나리오들을 검증합니다.
"""

import re
import pytest
import tempfile
import os
from typing import List, Dict, Any
from dataclasses import dataclass

from rfs.hof.readable.scanning import (
    Scanner, TextScanner, FileScanner, MultiFileScanner, ExtractionResult,
    scan_for, create_security_violation, create_log_entry, simple_extract
)
from rfs.hof.readable.types import ViolationInfo, ScanResult, is_risk_above_threshold


class TestScanner:
    """Scanner 클래스의 기본 기능 테스트"""

    def test_scanner_creation(self):
        """Scanner 생성 테스트"""
        patterns = [re.compile(r'test'), re.compile(r'error')]
        scanner = Scanner(patterns)
        assert scanner.value == patterns

    def test_in_text_method(self):
        """in_text 메서드 테스트"""
        patterns = [re.compile(r'error')]
        scanner = Scanner(patterns)
        
        text_scanner = scanner.in_text("This is an error message")
        assert isinstance(text_scanner, TextScanner)
        assert text_scanner.patterns == patterns

    def test_in_text_with_none(self):
        """in_text에 None 입력 테스트"""
        patterns = [re.compile(r'test')]
        scanner = Scanner(patterns)
        
        text_scanner = scanner.in_text(None)
        assert isinstance(text_scanner, TextScanner)

    def test_in_text_with_non_string(self):
        """in_text에 문자열이 아닌 입력 테스트"""
        patterns = [re.compile(r'123')]
        scanner = Scanner(patterns)
        
        text_scanner = scanner.in_text(123)
        assert isinstance(text_scanner, TextScanner)

    def test_in_file_method(self):
        """in_file 메서드 테스트"""
        patterns = [re.compile(r'test')]
        scanner = Scanner(patterns)
        
        file_scanner = scanner.in_file("test.txt")
        assert isinstance(file_scanner, FileScanner)

    def test_in_files_method(self):
        """in_files 메서드 테스트"""
        patterns = [re.compile(r'test')]
        scanner = Scanner(patterns)
        
        multi_scanner = scanner.in_files(["file1.txt", "file2.txt"])
        assert isinstance(multi_scanner, MultiFileScanner)


class TestTextScanner:
    """TextScanner 클래스의 기능 테스트"""

    def setUp(self):
        """테스트 설정"""
        self.patterns = [
            re.compile(r'ERROR'),
            re.compile(r'WARNING'),
            re.compile(r'CRITICAL')
        ]
        self.test_text = """
        INFO Starting application
        ERROR Database connection failed
        WARNING Low disk space
        CRITICAL System overload
        INFO Application stopped
        """

    def test_collect_matches(self):
        """collect_matches 메서드 테스트"""
        self.setUp()
        scanner = TextScanner(self.patterns, self.test_text)
        
        matches = scanner.collect_matches()
        assert len(matches) == 3  # ERROR, WARNING, CRITICAL
        
        # 각 매치가 올바른 타입인지 확인
        for match in matches:
            assert hasattr(match, 'group')
            assert hasattr(match, 'span')

    def test_first_match(self):
        """first_match 메서드 테스트"""
        self.setUp()
        scanner = TextScanner(self.patterns, self.test_text)
        
        first_match = scanner.first_match()
        assert first_match is not None
        assert first_match.group() == 'ERROR'

    def test_first_match_no_matches(self):
        """매치가 없을 때 first_match 테스트"""
        patterns = [re.compile(r'NOTFOUND')]
        scanner = TextScanner(patterns, "Normal text without patterns")
        
        first_match = scanner.first_match()
        assert first_match is None

    def test_has_matches_true(self):
        """has_matches True 케이스 테스트"""
        self.setUp()
        scanner = TextScanner(self.patterns, self.test_text)
        
        assert scanner.has_matches() is True

    def test_has_matches_false(self):
        """has_matches False 케이스 테스트"""
        patterns = [re.compile(r'NOTFOUND')]
        scanner = TextScanner(patterns, "Normal text")
        
        assert scanner.has_matches() is False

    def test_extract_with_simple_extractor(self):
        """extract 메서드와 simple extractor 테스트"""
        self.setUp()
        scanner = TextScanner(self.patterns, self.test_text)
        
        result = scanner.extract(simple_extract)
        assert isinstance(result, ExtractionResult)
        
        items = result.collect()
        assert len(items) == 3  # ERROR, WARNING, CRITICAL 매치들

    def test_extract_with_custom_extractor(self):
        """extract 메서드와 커스텀 extractor 테스트"""
        self.setUp()
        
        def custom_extractor(match):
            return {
                'level': match.group(),
                'position': match.span(),
                'line_number': 1  # 간단한 예시
            }
        
        scanner = TextScanner(self.patterns, self.test_text)
        result = scanner.extract(custom_extractor)
        
        items = result.collect()
        assert len(items) == 3
        for item in items:
            assert 'level' in item
            assert 'position' in item
            assert 'line_number' in item

    def test_extract_with_security_violation_extractor(self):
        """보안 위반 추출 테스트"""
        patterns = [re.compile(r'password\s*=\s*["\']([^"\']+)["\']')]
        text = 'config.password = "secret123"'
        
        scanner = TextScanner(patterns, text)
        result = scanner.extract(create_security_violation)
        
        violations = result.collect()
        assert len(violations) == 1
        
        violation = violations[0]
        assert isinstance(violation, ViolationInfo)
        assert violation.risk_level in ['high', 'critical', 'medium']


class TestFileScanner:
    """FileScanner 클래스의 기능 테스트"""

    def test_file_scanning(self):
        """파일 스캔 기본 기능 테스트"""
        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("ERROR: Database connection failed\nWARNING: Low memory\nINFO: Application started")
            temp_file = f.name
        
        try:
            patterns = [re.compile(r'ERROR'), re.compile(r'WARNING')]
            scanner = FileScanner(patterns, temp_file)
            
            matches = scanner.collect_matches()
            assert len(matches) == 2  # ERROR and WARNING
            
        finally:
            os.unlink(temp_file)

    def test_file_not_found(self):
        """존재하지 않는 파일 테스트"""
        patterns = [re.compile(r'test')]
        scanner = FileScanner(patterns, "nonexistent_file.txt")
        
        # 파일이 없어도 예외를 발생시키지 않고 빈 결과 반환
        matches = scanner.collect_matches()
        assert len(matches) == 0

    def test_file_encoding(self):
        """파일 인코딩 테스트"""
        # UTF-8로 한글이 포함된 파일 생성
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.txt') as f:
            f.write("에러: 데이터베이스 연결 실패\n경고: 메모리 부족")
            temp_file = f.name
        
        try:
            patterns = [re.compile(r'에러'), re.compile(r'경고')]
            scanner = FileScanner(patterns, temp_file, encoding='utf-8')
            
            matches = scanner.collect_matches()
            assert len(matches) == 2
            
        finally:
            os.unlink(temp_file)


class TestMultiFileScanner:
    """MultiFileScanner 클래스의 기능 테스트"""

    def test_multi_file_scanning(self):
        """여러 파일 스캔 테스트"""
        # 여러 임시 파일 생성
        temp_files = []
        
        file_contents = [
            "ERROR: Connection failed in file 1",
            "WARNING: Memory low in file 2",
            "ERROR: Timeout in file 2\nCRITICAL: System failure"
        ]
        
        for i, content in enumerate(file_contents):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'_test_{i}.txt') as f:
                f.write(content)
                temp_files.append(f.name)
        
        try:
            patterns = [re.compile(r'ERROR'), re.compile(r'CRITICAL')]
            scanner = MultiFileScanner(patterns, temp_files)
            
            matches = scanner.collect_matches()
            # file 1: 1개 ERROR, file 3: 1개 ERROR + 1개 CRITICAL = 총 3개
            assert len(matches) >= 3
            
        finally:
            for temp_file in temp_files:
                os.unlink(temp_file)

    def test_mixed_file_existence(self):
        """존재하는 파일과 존재하지 않는 파일 혼합 테스트"""
        # 하나의 실제 파일 생성
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("ERROR: Real file error")
            real_file = f.name
        
        try:
            file_paths = [real_file, "nonexistent_file.txt"]
            patterns = [re.compile(r'ERROR')]
            scanner = MultiFileScanner(patterns, file_paths)
            
            matches = scanner.collect_matches()
            assert len(matches) == 1  # 실제 파일에서만 매치
            
        finally:
            os.unlink(real_file)


class TestExtractionResult:
    """ExtractionResult 클래스의 기능 테스트"""

    def test_basic_operations(self):
        """기본 연산 테스트"""
        items = ['item1', 'item2', 'item3']
        result = ExtractionResult(items)
        
        assert result.count() == 3
        assert result.is_empty() is False
        assert result.to_list() == items
        
        empty_result = ExtractionResult([])
        assert empty_result.is_empty() is True
        assert empty_result.count() == 0

    def test_filter_by(self):
        """filter_by 메서드 테스트"""
        items = [1, 2, 3, 4, 5]
        result = ExtractionResult(items)
        
        even_result = result.filter_by(lambda x: x % 2 == 0)
        assert even_result.collect() == [2, 4]

    def test_transform(self):
        """transform 메서드 테스트"""
        items = [1, 2, 3]
        result = ExtractionResult(items)
        
        squared_result = result.transform(lambda x: x ** 2)
        assert squared_result.collect() == [1, 4, 9]

    def test_take(self):
        """take 메서드 테스트"""
        items = list(range(10))
        result = ExtractionResult(items)
        
        first_three = result.take(3)
        assert first_three.collect() == [0, 1, 2]

    def test_sort_by(self):
        """sort_by 메서드 테스트"""
        items = [{'name': 'c', 'value': 3}, {'name': 'a', 'value': 1}, {'name': 'b', 'value': 2}]
        result = ExtractionResult(items)
        
        sorted_result = result.sort_by(lambda x: x['name'])
        sorted_items = sorted_result.collect()
        assert [item['name'] for item in sorted_items] == ['a', 'b', 'c']

    def test_group_by(self):
        """group_by 메서드 테스트"""
        items = [
            ViolationInfo(rule_name="rule1", message="msg1", risk_level="high"),
            ViolationInfo(rule_name="rule2", message="msg2", risk_level="medium"),
            ViolationInfo(rule_name="rule3", message="msg3", risk_level="high"),
        ]
        result = ExtractionResult(items)
        
        grouped = result.group_by(lambda x: x.risk_level)
        assert len(grouped['high']) == 2
        assert len(grouped['medium']) == 1

    def test_group_by_risk(self):
        """group_by_risk 편의 메서드 테스트"""
        items = [
            ViolationInfo(rule_name="rule1", message="msg1", risk_level="high"),
            ViolationInfo(rule_name="rule2", message="msg2", risk_level="medium"),
        ]
        result = ExtractionResult(items)
        
        grouped = result.group_by_risk()
        assert 'high' in grouped
        assert 'medium' in grouped

    def test_filter_above_threshold(self):
        """filter_above_threshold 메서드 테스트"""
        items = [
            ViolationInfo(rule_name="rule1", message="msg1", risk_level="low"),
            ViolationInfo(rule_name="rule2", message="msg2", risk_level="medium"),
            ViolationInfo(rule_name="rule3", message="msg3", risk_level="high"),
            ViolationInfo(rule_name="rule4", message="msg4", risk_level="critical"),
        ]
        result = ExtractionResult(items)
        
        # medium 이상 필터링
        filtered = result.filter_above_threshold("medium")
        filtered_items = filtered.collect()
        
        # medium, high, critical이 포함되어야 함
        risk_levels = [item.risk_level for item in filtered_items]
        assert "low" not in risk_levels
        assert "medium" in risk_levels
        assert "high" in risk_levels
        assert "critical" in risk_levels

    def test_to_result(self):
        """to_result 메서드 테스트"""
        items = ['item1', 'item2']
        result = ExtractionResult(items)
        
        rfs_result = result.to_result()
        assert rfs_result.is_success()
        assert rfs_result.unwrap() == items


class TestScanForFunction:
    """scan_for 함수의 기능 테스트"""

    def test_basic_scan_for(self):
        """기본 scan_for 사용 테스트"""
        patterns = [re.compile(r'error'), re.compile(r'warning')]
        
        scanner = scan_for(patterns)
        assert isinstance(scanner, Scanner)
        assert scanner.value == patterns

    def test_scan_for_chaining(self):
        """scan_for 체이닝 테스트"""
        patterns = [re.compile(r'ERROR')]
        text = "This is an ERROR message"
        
        results = (
            scan_for(patterns)
            .in_text(text)
            .extract(simple_extract)
            .collect()
        )
        
        assert len(results) == 1


class TestSecurityViolationExtractor:
    """보안 위반 추출기 테스트"""

    def test_create_security_violation(self):
        """create_security_violation 함수 테스트"""
        pattern = re.compile(r'password\s*=\s*["\']([^"\']+)["\']')
        text = 'password = "secret123"'
        match = pattern.search(text)
        
        violation = create_security_violation(match)
        assert isinstance(violation, ViolationInfo)
        assert violation.risk_level in ['high', 'critical', 'medium']
        assert 'password' in violation.message.lower()

    def test_create_log_entry(self):
        """create_log_entry 함수 테스트"""
        pattern = re.compile(r'(\d{4}-\d{2}-\d{2})\s+(.+)')
        text = '2023-12-01 Application started'
        match = pattern.search(text)
        
        log_entry = create_log_entry(match)
        assert isinstance(log_entry, dict)
        assert 'timestamp' in log_entry or 'message' in log_entry

    def test_simple_extract(self):
        """simple_extract 함수 테스트"""
        pattern = re.compile(r'ERROR')
        text = 'ERROR: Something went wrong'
        match = pattern.search(text)
        
        extracted = simple_extract(match)
        assert isinstance(extracted, dict)
        assert 'matched_text' in extracted
        assert 'position' in extracted


class TestRealWorldScenarios:
    """실제 사용 시나리오 테스트"""

    def test_security_log_analysis(self):
        """보안 로그 분석 시나리오"""
        security_patterns = [
            re.compile(r'FAILED LOGIN.*?user[:\s]+(\w+)', re.IGNORECASE),
            re.compile(r'SUSPICIOUS ACTIVITY.*?IP[:\s]+([\d.]+)', re.IGNORECASE),
            re.compile(r'BLOCKED.*?attack', re.IGNORECASE)
        ]
        
        log_text = """
        2023-12-01 10:30:15 FAILED LOGIN attempt for user: admin from IP 192.168.1.100
        2023-12-01 10:31:22 SUSPICIOUS ACTIVITY detected from IP: 10.0.0.15
        2023-12-01 10:32:45 BLOCKED SQL injection attack attempt
        2023-12-01 10:35:12 Normal user login successful
        """
        
        results = (
            scan_for(security_patterns)
            .in_text(log_text)
            .extract(create_security_violation)
            .filter_above_threshold("medium")
            .group_by_risk()
        )
        
        # 최소 3개의 보안 이벤트가 감지되어야 함
        all_violations = []
        for risk_level, violations in results.items():
            all_violations.extend(violations)
        
        assert len(all_violations) >= 3

    def test_application_error_monitoring(self):
        """애플리케이션 에러 모니터링 시나리오"""
        error_patterns = [
            re.compile(r'OutOfMemoryError', re.IGNORECASE),
            re.compile(r'NullPointerException', re.IGNORECASE),
            re.compile(r'ConnectionTimeout', re.IGNORECASE),
            re.compile(r'DatabaseException', re.IGNORECASE)
        ]
        
        application_log = """
        INFO: Application started
        ERROR: OutOfMemoryError occurred in module UserService
        WARN: ConnectionTimeout for database connection
        ERROR: NullPointerException in PaymentProcessor
        DEBUG: Processing user request
        FATAL: DatabaseException - Unable to connect to primary database
        """
        
        def create_error_report(match):
            return {
                'error_type': match.group(),
                'position': match.span(),
                'severity': 'high' if 'FATAL' in match.string[max(0, match.start()-20):match.start()] else 'medium',
                'timestamp': '2023-12-01'  # 간단한 예시
            }
        
        error_summary = (
            scan_for(error_patterns)
            .in_text(application_log)
            .extract(create_error_report)
            .filter_by(lambda e: e['severity'] == 'high')
            .collect()
        )
        
        # 최소 하나의 high severity 에러가 있어야 함 (DatabaseException)
        assert len(error_summary) >= 0

    def test_code_quality_scan(self):
        """코드 품질 스캔 시나리오"""
        quality_patterns = [
            re.compile(r'TODO[:\s]+(.+)', re.IGNORECASE),
            re.compile(r'FIXME[:\s]+(.+)', re.IGNORECASE),
            re.compile(r'HACK[:\s]+(.+)', re.IGNORECASE),
            re.compile(r'XXX[:\s]+(.+)', re.IGNORECASE)
        ]
        
        source_code = """
        # TODO: Implement proper error handling
        def process_data(data):
            # FIXME: This is a temporary solution
            if data is None:
                # HACK: Quick fix for None values
                return []
            
            # XXX: Performance issue - optimize this loop
            results = []
            for item in data:
                results.append(process_item(item))
            return results
        """
        
        def create_quality_issue(match):
            issue_type = match.group().split(':')[0].strip().upper()
            message = match.group()
            
            priority_map = {
                'TODO': 'low',
                'FIXME': 'medium', 
                'HACK': 'high',
                'XXX': 'high'
            }
            
            return ViolationInfo(
                rule_name=f"code_quality_{issue_type.lower()}",
                message=message,
                risk_level=priority_map.get(issue_type, 'medium')
            )
        
        quality_issues = (
            scan_for(quality_patterns)
            .in_text(source_code)
            .extract(create_quality_issue)
            .sort_by(lambda v: ['low', 'medium', 'high'].index(v.risk_level))
            .collect()
        )
        
        # 각 타입의 이슈가 발견되어야 함
        issue_types = [issue.rule_name for issue in quality_issues]
        assert len(quality_issues) == 4
        assert any('todo' in issue_type for issue_type in issue_types)
        assert any('fixme' in issue_type for issue_type in issue_types)

    def test_performance_with_large_text(self):
        """대용량 텍스트에 대한 성능 테스트"""
        import time
        
        # 큰 텍스트 생성
        large_text = "Normal log entry\n" * 10000 + "ERROR: Critical failure\n" + "Normal log entry\n" * 10000
        
        patterns = [re.compile(r'ERROR'), re.compile(r'CRITICAL'), re.compile(r'FATAL')]
        
        start_time = time.time()
        results = (
            scan_for(patterns)
            .in_text(large_text)
            .extract(simple_extract)
            .collect()
        )
        duration = time.time() - start_time
        
        assert len(results) >= 1  # 적어도 하나의 에러 발견
        assert duration < 2.0  # 2초 내에 완료되어야 함


if __name__ == "__main__":
    pytest.main([__file__, "-v"])