"""
RFS Readable HOF Scanning System

텍스트 스캔 및 패턴 매칭 시스템을 구현합니다.
정규표현식 패턴들을 사용하여 텍스트나 파일에서 정보를 추출하고,
결과를 필터링 및 그룹화할 수 있는 플루언트 인터페이스를 제공합니다.

사용 예:
    results = (scan_for(patterns)
               .in_text(content)
               .extract(create_violation)
               .filter_above_threshold("medium")
               .to_result())
"""

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Pattern, Union
from collections import defaultdict
import os

from .base import FluentBase, ChainableResult, success, failure
from .types import Extractor, RiskLevel, ViolationInfo, ScanResult, RISK_LEVEL_ORDER, is_risk_above_threshold

class Scanner(FluentBase[List[Pattern]]):
    """
    텍스트 스캔을 위한 플루언트 인터페이스
    
    여러 정규표현식 패턴들을 보유하고 텍스트나 파일에서 스캔할 수 있게 합니다.
    """
    
    def in_text(self, text: str) -> 'TextScanner':
        """
        텍스트에서 스캔을 수행합니다.
        
        Args:
            text: 스캔할 텍스트
            
        Returns:
            TextScanner 인스턴스
        """
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
        
        return TextScanner(self._value, text)
    
    def in_file(self, file_path: str, encoding: str = 'utf-8') -> 'FileScanner':
        """
        파일에서 스캔을 수행합니다.
        
        Args:
            file_path: 스캔할 파일 경로
            encoding: 파일 인코딩 (기본값: utf-8)
            
        Returns:
            FileScanner 인스턴스
        """
        return FileScanner(self._value, file_path, encoding)
    
    def in_files(self, file_paths: List[str], encoding: str = 'utf-8') -> 'MultiFileScanner':
        """
        여러 파일에서 스캔을 수행합니다.
        
        Args:
            file_paths: 스캔할 파일 경로들
            encoding: 파일 인코딩 (기본값: utf-8)
            
        Returns:
            MultiFileScanner 인스턴스
        """
        return MultiFileScanner(self._value, file_paths, encoding)
    
    def in_data(self, data: Any) -> 'DataScanner':
        """
        구조화된 데이터에서 스캔을 수행합니다.
        
        Args:
            data: 스캔할 데이터 (객체, 딕셔너리 등)
            
        Returns:
            DataScanner 인스턴스
        """
        return DataScanner(getattr(self, '_data_patterns', []), data)

class TextScanner(FluentBase[str]):
    """
    텍스트 스캔 결과 처리 클래스
    
    주어진 텍스트에서 패턴들을 찾고 결과를 처리하는 메서드들을 제공합니다.
    """
    patterns: List[Pattern]
    
    def __init__(self, patterns: List[Pattern], text: str):
        """
        텍스트 스캐너를 초기화합니다.
        
        Args:
            patterns: 검색할 패턴들
            text: 스캔할 텍스트
        """
        super().__init__(text)
        self.patterns = patterns or []
    
    def extract(self, extractor: Extractor) -> 'ExtractionResult':
        """
        매치된 결과에서 정보를 추출합니다.
        
        Args:
            extractor: 매치 결과로부터 정보를 추출하는 함수
            
        Returns:
            추출 결과를 담은 ExtractionResult
        """
        matches = []
        
        for pattern in self.patterns:
            try:
                pattern_matches = pattern.finditer(self._value)
                for match in pattern_matches:
                    try:
                        extracted = extractor(match, pattern)
                        if extracted is not None:
                            matches.append(extracted)
                    except Exception as e:
                        # 개별 추출 실패는 에러로 기록하되 계속 진행
                        error_item = {
                            'error': f"추출 실패: {str(e)}",
                            'pattern': str(pattern.pattern),
                            'match_text': match.group(),
                            'position': match.span(),
                            'type': 'extraction_error'
                        }
                        matches.append(error_item)
            except Exception as e:
                # 패턴 매칭 실패
                error_item = {
                    'error': f"패턴 매칭 실패: {str(e)}",
                    'pattern': str(pattern.pattern) if hasattr(pattern, 'pattern') else str(pattern),
                    'type': 'pattern_error'
                }
                matches.append(error_item)
        
        return ExtractionResult(matches)
    
    def collect_matches(self) -> List[re.Match]:
        """
        모든 매치 결과를 수집합니다.
        
        Returns:
            모든 매치 객체들의 리스트
        """
        matches = []
        
        for pattern in self.patterns:
            try:
                pattern_matches = list(pattern.finditer(self._value))
                matches.extend(pattern_matches)
            except Exception:
                # 오류 발생 시 해당 패턴은 건너뛰고 계속 진행
                continue
        
        return matches
    
    def collect_scan_results(self) -> List[ScanResult]:
        """
        패턴별 스캔 결과를 수집합니다.
        
        Returns:
            패턴별 ScanResult 리스트
        """
        results = []
        
        for pattern in self.patterns:
            try:
                matches = list(pattern.finditer(self._value))
                results.append(ScanResult(pattern, matches))
            except Exception:
                # 오류 발생 시 빈 결과로 추가
                results.append(ScanResult(pattern, []))
        
        return results
    
    def count_matches(self) -> int:
        """총 매치 수를 반환합니다."""
        return len(self.collect_matches())
    
    def count_by_pattern(self) -> Dict[str, int]:
        """패턴별 매치 수를 반환합니다."""
        results = {}
        
        for pattern in self.patterns:
            try:
                matches = list(pattern.finditer(self._value))
                results[pattern.pattern] = len(matches)
            except Exception:
                results[pattern.pattern] = 0
        
        return results
    
    def has_matches(self) -> bool:
        """매치되는 패턴이 있는지 확인합니다."""
        return self.count_matches() > 0

class FileScanner(FluentBase[str]):
    """
    파일 스캔 결과 처리 클래스
    
    파일을 읽어서 텍스트 스캔을 수행합니다.
    """
    patterns: List[Pattern]
    encoding: str
    
    def __init__(self, patterns: List[Pattern], file_path: str, encoding: str = 'utf-8'):
        """
        파일 스캐너를 초기화합니다.
        
        Args:
            patterns: 검색할 패턴들
            file_path: 스캔할 파일 경로
            encoding: 파일 인코딩
        """
        super().__init__(file_path)
        self.patterns = patterns or []
        self.encoding = encoding
    
    def extract(self, extractor: Extractor) -> 'ExtractionResult':
        """
        파일에서 매치 결과를 추출합니다.
        
        Args:
            extractor: 매치 결과로부터 정보를 추출하는 함수
            
        Returns:
            추출 결과를 담은 ExtractionResult
        """
        try:
            if not os.path.exists(self._value):
                return ExtractionResult([{
                    'error': f"파일을 찾을 수 없습니다: {self._value}",
                    'file_path': self._value,
                    'type': 'file_not_found'
                }])
            
            with open(self._value, 'r', encoding=self.encoding) as f:
                content = f.read()
            
            text_scanner = TextScanner(self.patterns, content)
            result = text_scanner.extract(extractor)
            
            # 파일 정보를 결과에 추가
            for item in result._value:
                if isinstance(item, dict):
                    item['file_path'] = self._value
                elif hasattr(item, '__dict__'):
                    item.file_path = self._value
            
            return result
            
        except Exception as e:
            return ExtractionResult([{
                'error': f"파일 읽기 오류: {str(e)}",
                'file_path': self._value,
                'type': 'file_read_error'
            }])

class MultiFileScanner(FluentBase[List[str]]):
    """
    다중 파일 스캔 처리 클래스
    
    여러 파일에서 동시에 스캔을 수행합니다.
    """
    patterns: List[Pattern]
    encoding: str
    
    def __init__(self, patterns: List[Pattern], file_paths: List[str], encoding: str = 'utf-8'):
        """
        다중 파일 스캐너를 초기화합니다.
        
        Args:
            patterns: 검색할 패턴들
            file_paths: 스캔할 파일 경로들
            encoding: 파일 인코딩
        """
        super().__init__(file_paths)
        self.patterns = patterns or []
        self.encoding = encoding
    
    def extract(self, extractor: Extractor) -> 'ExtractionResult':
        """
        모든 파일에서 매치 결과를 추출합니다.
        
        Args:
            extractor: 매치 결과로부터 정보를 추출하는 함수
            
        Returns:
            모든 파일의 추출 결과를 합친 ExtractionResult
        """
        all_matches = []
        
        for file_path in self._value:
            file_scanner = FileScanner(self.patterns, file_path, self.encoding)
            result = file_scanner.extract(extractor)
            all_matches.extend(result._value)
        
        return ExtractionResult(all_matches)

class ExtractionResult(FluentBase[List[Any]]):
    """
    추출 결과 처리 클래스
    
    스캔으로부터 추출된 결과들을 필터링, 그룹화, 정렬하는 메서드들을 제공합니다.
    """
    
    def group_by_risk(self) -> Dict[RiskLevel, List[Any]]:
        """
        위험 수준별로 그룹화합니다.
        
        Returns:
            위험 수준을 키로 하는 딕셔너리
        """
        groups = defaultdict(list)
        
        for item in self._value:
            risk_level = self._extract_risk_level(item)
            groups[risk_level].append(item)
        
        return dict(groups)
    
    def filter_above_threshold(self, threshold: RiskLevel) -> 'ExtractionResult':
        """
        임계값 이상의 위험 수준을 가진 항목들만 필터링합니다.
        
        Args:
            threshold: 임계값 위험 수준
            
        Returns:
            필터링된 ExtractionResult
        """
        filtered_items = []
        
        for item in self._value:
            risk_level = self._extract_risk_level(item)
            if is_risk_above_threshold(risk_level, threshold):
                filtered_items.append(item)
        
        return ExtractionResult(filtered_items)
    
    def sort_by_risk(self, descending: bool = True) -> 'ExtractionResult':
        """
        위험 수준별로 정렬합니다.
        
        Args:
            descending: True이면 높은 위험부터, False이면 낮은 위험부터
            
        Returns:
            정렬된 ExtractionResult
        """
        def get_risk_order(item):
            risk_level = self._extract_risk_level(item)
            return RISK_LEVEL_ORDER.get(risk_level, 0)
        
        sorted_items = sorted(self._value, key=get_risk_order, reverse=descending)
        return ExtractionResult(sorted_items)
    
    def filter_by_type(self, item_type: str) -> 'ExtractionResult':
        """
        특정 타입의 항목들만 필터링합니다.
        
        Args:
            item_type: 필터링할 타입
            
        Returns:
            필터링된 ExtractionResult
        """
        filtered_items = []
        
        for item in self._value:
            if isinstance(item, dict) and item.get('type') == item_type:
                filtered_items.append(item)
            elif hasattr(item, 'type') and getattr(item, 'type') == item_type:
                filtered_items.append(item)
        
        return ExtractionResult(filtered_items)
    
    def exclude_errors(self) -> 'ExtractionResult':
        """
        에러 항목들을 제외합니다.
        
        Returns:
            에러가 제외된 ExtractionResult
        """
        filtered_items = []
        
        for item in self._value:
            is_error = False
            
            if isinstance(item, dict):
                is_error = 'error' in item or item.get('type', '').endswith('_error')
            elif hasattr(item, 'error'):
                is_error = True
            
            if not is_error:
                filtered_items.append(item)
        
        return ExtractionResult(filtered_items)
    
    def count(self) -> int:
        """결과 개수를 반환합니다."""
        return len(self._value)
    
    def is_empty(self) -> bool:
        """결과가 비어있는지 확인합니다."""
        return len(self._value) == 0
    
    def to_chainable_result(self) -> ChainableResult[List[Any]]:
        """ChainableResult로 변환합니다."""
        return success(self._value)
    
    def _extract_risk_level(self, item: Any) -> RiskLevel:
        """항목에서 위험 수준을 추출합니다."""
        if isinstance(item, dict):
            return item.get('risk_level', 'low')
        elif isinstance(item, ViolationInfo):
            return item.risk_level
        elif hasattr(item, 'risk_level'):
            return getattr(item, 'risk_level', 'low')
        else:
            return 'low'

# 메인 진입점 함수
def scan_for(patterns: Union[List[Pattern], List[str]]) -> Scanner:
    """
    패턴들을 스캔하기 위한 시작점입니다.
    
    Args:
        patterns: 검색할 패턴들 (Pattern 객체들 또는 정규표현식 문자열들)
        
    Returns:
        Scanner 인스턴스
        
    Example:
        >>> results = scan_for([re.compile(r'password'), re.compile(r'secret')]).in_text(text).extract(create_violation)
        >>> violations = scan_for(['error', 'warning']).in_file('app.log').extract(create_log_entry)
    """
    # 문자열 패턴들을 Pattern 객체로 변환
    compiled_patterns = []
    for pattern in patterns:
        if isinstance(pattern, str):
            try:
                compiled_patterns.append(re.compile(pattern))
            except re.error as e:
                # 잘못된 정규표현식인 경우 리터럴 문자열로 처리
                compiled_patterns.append(re.compile(re.escape(pattern)))
        else:
            compiled_patterns.append(pattern)
    
    return Scanner(compiled_patterns)

# 편의 함수들
def create_security_violation(match: re.Match, pattern: Pattern) -> dict:
    """
    보안 위반 사항 생성 헬퍼 함수입니다.
    
    Args:
        match: 정규표현식 매치 객체
        pattern: 매치된 패턴
        
    Returns:
        보안 위반 정보 딕셔너리
    """
    return {
        'rule_name': getattr(pattern, 'name', str(pattern.pattern)),
        'matched_text': match.group(),
        'position': match.span(),
        'risk_level': getattr(pattern, 'risk_level', 'medium'),
        'description': getattr(pattern, 'description', '보안 규칙 위반'),
        'type': 'security_violation'
    }

def create_log_entry(match: re.Match, pattern: Pattern) -> dict:
    """
    로그 엔트리 생성 헬퍼 함수입니다.
    
    Args:
        match: 정규표현식 매치 객체
        pattern: 매치된 패턴
        
    Returns:
        로그 엔트리 정보 딕셔너리
    """
    return {
        'pattern': pattern.pattern,
        'matched_text': match.group(),
        'position': match.span(),
        'groups': match.groups(),
        'type': 'log_entry'
    }

def simple_extract(match: re.Match, pattern: Pattern) -> dict:
    """
    간단한 추출 헬퍼 함수입니다.
    
    Args:
        match: 정규표현식 매치 객체
        pattern: 매치된 패턴
        
    Returns:
        기본 매치 정보 딕셔너리
    """
    return {
        'pattern': pattern.pattern,
        'text': match.group(),
        'start': match.start(),
        'end': match.end(),
        'groups': match.groups(),
        'type': 'match'
    }

def scan_data_for(pattern_funcs: List[Callable[[Any], bool]]) -> Scanner:
    """
    데이터 패턴들을 스캔하기 위한 시작점입니다.
    
    정규표현식 대신 함수를 사용하여 구조화된 데이터를 검사할 수 있습니다.
    
    Args:
        pattern_funcs: 데이터 패턴을 확인하는 함수들의 리스트
        
    Returns:
        Scanner: 스캔 플루언트 인터페이스
        
    Example:
        >>> results = scan_data_for([
        ...     lambda obj: hasattr(obj, 'password'),
        ...     lambda obj: getattr(obj, 'is_admin', False)
        ... ]).in_data(user_object).extract(security_analyzer)
    """
    # 함수를 패턴으로 사용하는 특수한 Scanner 생성
    scanner = Scanner([])
    # 함수 패턴들을 별도로 저장
    scanner._data_patterns = pattern_funcs
    return scanner

@dataclass
class DataScanner:
    """구조화된 데이터 스캔 결과 처리"""
    patterns: List[Callable]  # 데이터 패턴은 함수로 표현
    data: Any
    
    def extract(self, extractor: Callable) -> 'ExtractionResult':
        """데이터에서 정보 추출"""
        matches = []
        for pattern_func in self.patterns:
            if pattern_func(self.data):
                matches.append(extractor(self.data))
        return ExtractionResult(matches)

@dataclass  
class ExtractionResult:
    """추출 결과 처리"""
    items: List[Any]
    
    def group_by(self, key_func: Callable[[Any], str]) -> Dict[str, List[Any]]:
        """키 함수에 따라 그룹화"""
        groups = defaultdict(list)
        for item in self.items:
            key = key_func(item)
            groups[key].append(item)
        return dict(groups)
    
    def group_by_risk(self) -> Dict[str, List[Any]]:
        """위험 수준별로 그룹화 (편의 함수)"""
        return self.group_by(lambda item: getattr(item, 'risk_level', 'unknown'))
    
    def filter_by(self, predicate: Callable[[Any], bool]) -> 'ExtractionResult':
        """조건에 따라 필터링"""
        filtered_items = [item for item in self.items if predicate(item)]
        return ExtractionResult(filtered_items)
    
    def filter_above_threshold(self, threshold: str) -> 'ExtractionResult':
        """임계값 이상 필터링 (편의 함수)"""
        risk_order = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        threshold_level = risk_order.get(threshold.lower(), 0)
        
        def above_threshold(item):
            item_risk = getattr(item, 'risk_level', 'low').lower()
            return risk_order.get(item_risk, 0) >= threshold_level
        
        return self.filter_by(above_threshold)
    
    def transform(self, transformer: Callable[[Any], Any]) -> 'ExtractionResult':
        """결과 변환"""
        transformed_items = [transformer(item) for item in self.items]
        return ExtractionResult(transformed_items)
    
    def take(self, count: int) -> 'ExtractionResult':
        """처음 N개 항목만 선택"""
        return ExtractionResult(self.items[:count])
    
    def sort_by(self, key_func: Callable[[Any], Any], reverse: bool = False) -> 'ExtractionResult':
        """정렬"""
        sorted_items = sorted(self.items, key=key_func, reverse=reverse)
        return ExtractionResult(sorted_items)
    
    def to_list(self) -> List[Any]:
        """리스트로 변환"""
        return self.items
    
    def to_result(self) -> ChainableResult[List[Any]]:
        """Result로 변환"""
        try:
            return success(self.items)
        except Exception as e:
            return failure(f"추출 결과 변환 실패: {str(e)}")
    
    def count(self) -> int:
        """항목 개수"""
        return len(self.items)