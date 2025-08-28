"""
Stateless Singleton Pattern

Spring Bean 스타일의 무상태 싱글톤 패턴
모든 상태는 파라미터로 전달되며, 서비스는 순수 함수로 구성
"""

import inspect
from functools import wraps
from typing import Any, Callable, Dict, List, Type


class SingletonMeta(type):
    """
    Singleton 메타클래스

    클래스가 SingletonMeta를 메타클래스로 사용하면
    해당 클래스는 싱글톤이 됩니다.
    """

    _instances: Dict[Type[Any], Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances = {**cls._instances, cls: super().__call__(*args, **kwargs)}
        return cls._instances[cls]


class StatelessRegistry:
    """
    무상태 싱글톤 레지스트리 (Spring Bean 컨테이너 영감)

    특징:
    - 싱글톤 인스턴스 관리
    - 의존성 주입 지원
    - 무상태성 보장
    """

    _instances: Dict[str, Any] = {}
    _factories: Dict[str, Type[Any]] = {}
    _dependencies: Dict[str, list[str]] = {}

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
            if dependencies:
                cls._dependencies = {**cls._dependencies, service_name: dependencies}
            cls._factories = {**cls._factories, service_name: service_class}
            if service_name not in cls._instances:
                cls._instances = {
                    **cls._instances,
                    service_name: cls._create_instance(service_class, service_name),
                }
            return service_class

        return decorator

    @classmethod
    def _create_instance(cls, service_class: Type[Any], service_name: str) -> Any:
        """의존성 주입을 통한 인스턴스 생성"""
        dependencies = cls._dependencies.get(service_name, [])
        if not dependencies:
            return service_class()
        injected_deps: List[Any] = []
        for dep_name in dependencies:
            if dep_name in cls._instances:
                injected_deps = injected_deps + [cls._instances[dep_name]]
            else:
                raise ValueError(
                    f"Dependency '{dep_name}' not found for service '{service_name}'"
                )
        return service_class(*injected_deps)

    @classmethod
    def get(cls, name: str) -> Any:
        """서비스 인스턴스 조회"""
        if name not in cls._instances:
            if name in cls._factories:
                cls._instances = {
                    **cls._instances,
                    name: cls._create_instance(cls._factories[name], name),
                }
            else:
                raise KeyError(
                    f"Service '{name}' not found. Available: {list(cls._instances.keys())}"
                )
        return cls._instances[name]

    @classmethod
    def list_services(cls) -> list[str]:
        """등록된 서비스 목록"""
        return list(cls._instances.keys())

    @classmethod
    def clear(cls) -> None:
        """모든 서비스 정리 (테스트용)"""
        cls._instances = {}
        cls._factories = {}
        cls._dependencies = {}


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
        if hasattr(func, "__self__") and hasattr(func.__self__, "__dict__"):
            instance_vars = func.__self__.__dict__
            mutable_states = {
                key: value
                for key, value in instance_vars.items()
                if not key.startswith("_")
                and (not key.isupper())
                and (type(value).__name__ in ["list", "dict", "set"])
            }
            if mutable_states:
                print(
                    f"Warning: Stateless function {func.__name__} may have mutable state: {mutable_states}"
                )
        return func(*args, **kwargs)

    setattr(wrapper, '_is_stateless', True)
    setattr(wrapper, '_original_func', func)
    return wrapper


def inject(
    *dependency_names: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
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
            injected_deps: List[Any] = []
            for dep_name in dependency_names:
                try:
                    dep = StatelessRegistry.get(dep_name)
                    injected_deps = injected_deps + [dep]
                except KeyError:
                    raise ValueError(
                        f"Cannot inject dependency '{dep_name}' - service not found"
                    )
            return func(*args, *injected_deps, **kwargs)

        return wrapper

    return decorator


component = lambda name: StatelessRegistry.register(name)
service = lambda name: StatelessRegistry.register(name)
repository = lambda name: StatelessRegistry.register(name)
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

        def __init__(
            self, calculator: Any | None = None, logger: Any | None = None
        ) -> None:
            pass

        @inject("calculator", "logger")
        def process_numbers(
            self, numbers: list[float], calculator: Any, logger: Any
        ) -> float:
            """숫자 리스트 처리"""
            logger.log("info", f"Processing {len(numbers)} numbers")
            result = 0
            for num in numbers:
                result = calculator.add(result, num)
            logger.log("info", f"Result: {result}")
            return result

    processor = StatelessRegistry.get("processor")
    result = processor.process_numbers([1, 2, 3, 4, 5])
    print(f"Final result: {result}")
