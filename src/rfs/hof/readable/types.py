"""
RFS Readable HOF Types and Protocols

이 모듈은 readable HOF 라이브러리에서 사용하는 타입 정의와 프로토콜을 제공합니다.
플루언트 인터페이스, 규칙 시스템, 검증 시스템에서 공통으로 사용되는 타입들을 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional, Pattern, Protocol, TypeVar, Union
import re

# 기본 타입 변수들
T = TypeVar('T')  # 일반적인 타입
U = TypeVar('U')  # 변환된 타입  
V = TypeVar('V')  # 추가 타입
R = TypeVar('R')  # 결과 타입
E = TypeVar('E')  # 에러 타입

# 규칙 시스템 타입들
class Rule(Protocol):
    """규칙 인터페이스를 정의하는 프로토콜"""
    
    @property
    def name(self) -> str:
        """규칙의 이름"""
        ...
    
    def apply(self, target: T) -> Any:
        """규칙을 대상에 적용하여 결과를 반환"""
        ...

class Validator(Protocol):
    """검증기 인터페이스를 정의하는 프로토콜"""
    
    def validate(self, obj: Any) -> bool:
        """객체를 검증하여 통과 여부를 반환"""
        ...

class Extractor(Protocol):
    """추출기 인터페이스를 정의하는 프로토콜"""
    
    def __call__(self, match: re.Match, pattern: Pattern) -> Any:
        """매치 결과와 패턴으로부터 정보를 추출"""
        ...

# 위험 수준 타입
RiskLevel = Union["low", "medium", "high", "critical"]

# 컬렉션 타입들
ProcessorFunction = Callable[[Any], Any]
PredicateFunction = Callable[[Any], bool]
TransformFunction = Callable[[T], U]

# 에러 정보 타입
class ErrorInfo:
    """에러 정보를 담는 데이터 클래스"""
    
    def __init__(self, message: str, error_type: str = "unknown", context: Optional[Any] = None):
        self.message = message
        self.error_type = error_type
        self.context = context
    
    def __str__(self) -> str:
        return f"{self.error_type}: {self.message}"
    
    def __repr__(self) -> str:
        return f"ErrorInfo(message='{self.message}', error_type='{self.error_type}', context={self.context})"

# 위반 정보 타입
class ViolationInfo:
    """규칙 위반 정보를 담는 데이터 클래스"""
    
    def __init__(
        self, 
        rule_name: str, 
        message: str, 
        risk_level: RiskLevel = "medium",
        position: Optional[tuple] = None,
        matched_text: Optional[str] = None,
        context: Optional[Any] = None
    ):
        self.rule_name = rule_name
        self.message = message
        self.risk_level = risk_level
        self.position = position
        self.matched_text = matched_text
        self.context = context
    
    def to_dict(self) -> dict:
        """딕셔너리로 변환"""
        return {
            'rule_name': self.rule_name,
            'message': self.message,
            'risk_level': self.risk_level,
            'position': self.position,
            'matched_text': self.matched_text,
            'context': self.context
        }
    
    def __str__(self) -> str:
        return f"{self.risk_level.upper()}: {self.rule_name} - {self.message}"
    
    def __repr__(self) -> str:
        return f"ViolationInfo(rule_name='{self.rule_name}', risk_level='{self.risk_level}', message='{self.message}')"

# 스캔 결과 타입
class ScanResult:
    """스캔 결과를 담는 데이터 클래스"""
    
    def __init__(self, pattern: Pattern, matches: List[re.Match]):
        self.pattern = pattern
        self.matches = matches
    
    @property
    def count(self) -> int:
        """매치 수"""
        return len(self.matches)
    
    def __str__(self) -> str:
        return f"ScanResult(pattern={self.pattern.pattern}, matches={self.count})"
    
    def __repr__(self) -> str:
        return f"ScanResult(pattern=re.compile({self.pattern.pattern!r}), matches={self.matches})"

# 처리 단계 타입
class ProcessingStep(ABC):
    """배치 처리 단계의 추상 기본 클래스"""
    
    @abstractmethod
    def process(self, data: Any) -> Any:
        """데이터를 처리하여 결과를 반환"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """처리 단계의 이름"""
        pass

# 설정 타입들
class Config(Protocol):
    """설정 객체 프로토콜"""
    
    def get(self, key: str, default: Any = None) -> Any:
        """설정값을 가져옴"""
        ...
    
    def has(self, key: str) -> bool:
        """설정값 존재 여부 확인"""
        ...

# 위험 수준 순서 정의 (낮은 것부터 높은 것 순서)
RISK_LEVEL_ORDER = {
    "low": 1,
    "medium": 2, 
    "high": 3,
    "critical": 4
}

def compare_risk_level(level1: RiskLevel, level2: RiskLevel) -> int:
    """두 위험 수준을 비교 (-1: level1이 낮음, 0: 같음, 1: level1이 높음)"""
    order1 = RISK_LEVEL_ORDER.get(level1, 0)
    order2 = RISK_LEVEL_ORDER.get(level2, 0)
    
    if order1 < order2:
        return -1
    elif order1 > order2:
        return 1
    else:
        return 0

def is_risk_above_threshold(level: RiskLevel, threshold: RiskLevel) -> bool:
    """위험 수준이 임계값 이상인지 확인"""
    return compare_risk_level(level, threshold) >= 0