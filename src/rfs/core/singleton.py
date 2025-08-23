"""
Stateless Singleton Pattern

Spring Bean 스타일의 무상태 싱글톤 패턴
모든 상태는 파라미터로 전달되며, 서비스는 순수 함수로 구성
"""

from typing import Dict, Any, Type, Callable
from functools import wraps
import inspect

class StatelessRegistry:
    """
    무상태 싱글톤 레지스트리 (Spring Bean 컨테이너 영감)
    
    특징:
    - 싱글톤 인스턴스 관리
    - 의존성 주입 지원
    - 무상태성 보장
    """
    
    _instances: Dict[str, Any] = {}
    _factories: Dict[str, Callable] = {}
    _dependencies: Dict[str, list] = {}
    
    @classmethod
    def register(cls, name: str | None = None, dependencies: list[str] | None = None):
        """
        무상태 서비스 등록 데코레이터
        
        Args:
            name: 서비스 이름 (기본값: 클래스명)
            dependencies: 의존성 목록
        """
        def decorator(service_class: Type[Any]) -> Type[Any]:
            service_name = name or service_class.__name__
            
            # 의존성 정보 저장
            if dependencies:
                cls._dependencies[service_name] = dependencies
            
            # 팩토리 함수 저장
            cls._factories[service_name] = service_class
            
            # 즉시 인스턴스 생성 (지연 로딩도 가능)
            if service_name not in cls._instances:
                cls._instances[service_name] = cls._create_instance(service_class, service_name)
            
            return service_class
        return decorator
    
    @classmethod
    def _create_instance(cls, service_class: Type[Any], service_name: str) -> Any:
        """의존성 주입을 통한 인스턴스 생성"""
        dependencies = cls._dependencies.get(service_name, [])
        
        if not dependencies:
            return service_class()
        
        # 의존성 해결
        injected_deps = []
        for dep_name in dependencies:
            if dep_name in cls._instances:
                injected_deps.append(cls._instances[dep_name])
            else:
                raise ValueError(f"Dependency '{dep_name}' not found for service '{service_name}'")
        
        return service_class(*injected_deps)
    
    @classmethod
    def get(cls, name: str) -> Any:
        """서비스 인스턴스 조회"""
        if name not in cls._instances:
            # 지연 로딩 시도
            if name in cls._factories:
                cls._instances[name] = cls._create_instance(cls._factories[name], name)
            else:
                raise KeyError(f"Service '{name}' not found. Available: {list(cls._instances.keys())}")
        
        return cls._instances[name]
    
    @classmethod
    def list_services(cls) -> list[str]:
        """등록된 서비스 목록"""
        return list(cls._instances.keys())
    
    @classmethod
    def clear(cls) -> None:
        """모든 서비스 정리 (테스트용)"""
        cls._instances.clear()
        cls._factories.clear()
        cls._dependencies.clear()

def stateless(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    무상태 함수 데코레이터
    
    이 데코레이터는:
    1. 함수가 상태를 유지하지 않음을 명시
    2. 모든 데이터는 파라미터로 전달
    3. 순수 함수임을 보장
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # 상태 검증 (개발 모드에서만)
        if hasattr(func, '__self__') and hasattr(func.__self__, '__dict__'):
            instance_vars = func.__self__.__dict__
            # 설정이나 상수가 아닌 변경 가능한 상태가 있는지 체크
            mutable_states = {
                key: value for key, value in instance_vars.items()
                if not key.startswith('_') and not key.isupper() and 
                isinstance(value, list | dict | set)
            }
            if mutable_states:
                print(f"Warning: Stateless function {func.__name__} may have mutable state: {mutable_states}")
        
        return func(*args, **kwargs)
    
    # 메타데이터 추가
    wrapper._is_stateless = True
    wrapper._original_func = func
    
    return wrapper

def inject(*dependency_names: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    의존성 주입 데코레이터
    
    사용 예:
    @inject('calculator', 'logger')
    def process_data(data, calculator, logger):
        ...
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 의존성 자동 주입
            injected_deps = []
            for dep_name in dependency_names:
                try:
                    dep = StatelessRegistry.get(dep_name)
                    injected_deps.append(dep)
                except KeyError:
                    raise ValueError(f"Cannot inject dependency '{dep_name}' - service not found")
            
            # 원본 함수 호출 (의존성을 추가 인자로 전달)
            return func(*args, *injected_deps, **kwargs)
        
        return wrapper
    return decorator

# 미리 정의된 데코레이터들
component = lambda name: StatelessRegistry.register(name)
service = lambda name: StatelessRegistry.register(name)
repository = lambda name: StatelessRegistry.register(name)

# 사용 예제
if __name__ == "__main__":
    
    @StatelessRegistry.register("calculator")
    class Calculator:
        """무상태 계산 서비스"""
        
        @stateless
        def add(self, a: float, b: float) -> float:
            return a + b
        
        @stateless
        def multiply(self, a: float, b: float) -> float:
            return a * b
        
        @stateless
        def divide(self, a: float, b: float) -> float:
            if b == 0:
                raise ValueError("Division by zero")
            return a / b
    
    @service("logger")
    class Logger:
        """무상태 로깅 서비스"""
        
        @stateless
        def log(self, level: str, message: str) -> None:
            print(f"[{level.upper()}] {message}")
    
    @component("processor")
    class DataProcessor:
        """무상태 데이터 처리 서비스"""
        
        def __init__(self, calculator: Any | None = None, logger: Any | None = None) -> None:
            # 의존성은 생성자에서 주입받지만 상태로 저장하지 않음
            pass
        
        @inject('calculator', 'logger')
        def process_numbers(self, numbers: list[float], calculator: Any, logger: Any) -> float:
            """숫자 리스트 처리"""
            logger.log('info', f'Processing {len(numbers)} numbers')
            
            result = 0
            for num in numbers:
                result = calculator.add(result, num)
            
            logger.log('info', f'Result: {result}')
            return result
    
    # 사용
    processor = StatelessRegistry.get('processor')
    result = processor.process_numbers([1, 2, 3, 4, 5])
    print(f"Final result: {result}")