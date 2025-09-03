"""
RFS Readable HOF Base Classes Tests

기본 플루언트 인터페이스 클래스들의 단위 테스트입니다.
"""

import pytest
from rfs.core.result import Success, Failure

from rfs.hof.readable.base import FluentBase, ChainableResult, success, failure, from_result
from rfs.hof.readable.types import ErrorInfo


class TestFluentBase:
    """FluentBase 클래스 테스트"""
    
    class ConcreteFluentBase(FluentBase):
        """테스트용 구체적인 FluentBase 구현"""
        pass
    
    def test_initialization(self):
        """기본 초기화 테스트"""
        value = "test_value"
        fluent = self.ConcreteFluentBase(value)
        assert fluent.value == value
    
    def test_map_transformation(self):
        """map 메서드 테스트"""
        fluent = self.ConcreteFluentBase("hello")
        result = fluent.map(str.upper)
        assert result.value == "HELLO"
        assert isinstance(result, self.ConcreteFluentBase)
    
    def test_map_with_error(self):
        """map 에러 처리 테스트"""
        def failing_func(x):
            raise ValueError("Test error")
        
        fluent = self.ConcreteFluentBase("test")
        result = fluent.map(failing_func)
        
        assert isinstance(result.value, ErrorInfo)
        assert "변환 실패" in result.value.message
    
    def test_tap_success(self):
        """tap 메서드 성공 테스트"""
        side_effect_result = []
        
        def side_effect(x):
            side_effect_result.append(x.upper())
        
        fluent = self.ConcreteFluentBase("hello")
        result = fluent.tap(side_effect)
        
        assert result.value == "hello"  # 값은 변경되지 않음
        assert side_effect_result == ["HELLO"]  # 부수 효과는 발생
    
    def test_tap_with_error(self):
        """tap 에러 무시 테스트"""
        def failing_side_effect(x):
            raise ValueError("Side effect error")
        
        fluent = self.ConcreteFluentBase("test")
        result = fluent.tap(failing_side_effect)
        
        # tap에서는 에러를 무시하고 원본 값 유지
        assert result.value == "test"
    
    def test_to_result_success(self):
        """성공 케이스의 to_result 테스트"""
        fluent = self.ConcreteFluentBase("test")
        result = fluent.to_result()
        
        assert result.is_success()
        assert result.unwrap() == "test"
    
    def test_to_result_with_error_info(self):
        """ErrorInfo가 있는 경우의 to_result 테스트"""
        error_info = ErrorInfo("Test error", "test_error")
        fluent = self.ConcreteFluentBase(error_info)
        result = fluent.to_result()
        
        assert result.is_failure()
        assert result.unwrap_error() == "Test error"
    
    def test_if_present_with_value(self):
        """값이 있는 경우의 if_present 테스트"""
        called = []
        
        def func(x):
            called.append(x)
        
        fluent = self.ConcreteFluentBase("test")
        result = fluent.if_present(func)
        
        assert result.value == "test"
        assert called == ["test"]
    
    def test_if_present_with_none(self):
        """None 값의 if_present 테스트"""
        called = []
        
        def func(x):
            called.append(x)
        
        fluent = self.ConcreteFluentBase(None)
        result = fluent.if_present(func)
        
        assert result.value is None
        assert called == []  # 함수가 호출되지 않음
    
    def test_if_present_with_error_info(self):
        """ErrorInfo가 있는 경우의 if_present 테스트"""
        called = []
        
        def func(x):
            called.append(x)
        
        error_info = ErrorInfo("Test error")
        fluent = self.ConcreteFluentBase(error_info)
        result = fluent.if_present(func)
        
        assert isinstance(result.value, ErrorInfo)
        assert called == []  # 함수가 호출되지 않음
    
    def test_or_else_with_value(self):
        """값이 있는 경우의 or_else 테스트"""
        fluent = self.ConcreteFluentBase("original")
        result = fluent.or_else("default")
        
        assert result.value == "original"
    
    def test_or_else_with_none(self):
        """None 값의 or_else 테스트"""
        fluent = self.ConcreteFluentBase(None)
        result = fluent.or_else("default")
        
        assert result.value == "default"
    
    def test_or_else_with_error_info(self):
        """ErrorInfo가 있는 경우의 or_else 테스트"""
        error_info = ErrorInfo("Test error")
        fluent = self.ConcreteFluentBase(error_info)
        result = fluent.or_else("default")
        
        assert result.value == "default"


class TestChainableResult:
    """ChainableResult 클래스 테스트"""
    
    def test_successful_initialization(self):
        """성공 케이스 초기화 테스트"""
        result = ChainableResult(Success("test"))
        assert result.is_success()
        assert result.result.unwrap() == "test"
    
    def test_failure_initialization(self):
        """실패 케이스 초기화 테스트"""
        result = ChainableResult(Failure("error"))
        assert result.is_failure()
        assert result.result.unwrap_error() == "error"
    
    def test_successful_bind_chain(self):
        """성공적인 bind 체이닝 테스트"""
        chain = ChainableResult(Success("5"))
        result = (chain
                  .bind(lambda x: Success(int(x)))
                  .bind(lambda x: Success(x * 2)))
        
        assert result.is_success()
        assert result.result.unwrap() == 10
    
    def test_failure_propagation_in_bind(self):
        """bind에서 실패 전파 테스트"""
        chain = ChainableResult(Failure("초기 오류"))
        result = chain.bind(lambda x: Success(x.upper()))
        
        assert result.is_failure()
        assert result.result.unwrap_error() == "초기 오류"
    
    def test_bind_with_exception(self):
        """bind에서 예외 발생 테스트"""
        def failing_func(x):
            raise ValueError("Bind error")
        
        chain = ChainableResult(Success("test"))
        result = chain.bind(failing_func)
        
        assert result.is_failure()
        assert "bind 연산 실패" in result.result.unwrap_error()
    
    def test_successful_map(self):
        """성공적인 map 테스트"""
        chain = ChainableResult(Success(5))
        result = chain.map(lambda x: x * 3)
        
        assert result.is_success()
        assert result.result.unwrap() == 15
    
    def test_map_with_failure(self):
        """실패 상태에서의 map 테스트"""
        chain = ChainableResult(Failure("error"))
        result = chain.map(lambda x: x * 3)
        
        assert result.is_failure()
        assert result.result.unwrap_error() == "error"
    
    def test_map_with_exception(self):
        """map에서 예외 발생 테스트"""
        def failing_func(x):
            raise ValueError("Map error")
        
        chain = ChainableResult(Success("test"))
        result = chain.map(failing_func)
        
        assert result.is_failure()
        assert "map 연산 실패" in result.result.unwrap_error()
    
    def test_filter_success(self):
        """필터 성공 테스트"""
        chain = ChainableResult(Success(10))
        result = chain.filter(lambda x: x > 5, "값이 너무 작습니다")
        
        assert result.is_success()
        assert result.result.unwrap() == 10
    
    def test_filter_failure(self):
        """필터 실패 테스트"""
        chain = ChainableResult(Success(3))
        result = chain.filter(lambda x: x > 5, "값이 너무 작습니다")
        
        assert result.is_failure()
        assert result.result.unwrap_error() == "값이 너무 작습니다"
    
    def test_filter_with_initial_failure(self):
        """초기 실패 상태에서의 필터 테스트"""
        chain = ChainableResult(Failure("initial error"))
        result = chain.filter(lambda x: x > 5)
        
        assert result.is_failure()
        assert result.result.unwrap_error() == "initial error"
    
    def test_tap_success(self):
        """tap 성공 테스트"""
        side_effects = []
        
        def side_effect(x):
            side_effects.append(x)
        
        chain = ChainableResult(Success("test"))
        result = chain.tap(side_effect)
        
        assert result.is_success()
        assert result.result.unwrap() == "test"
        assert side_effects == ["test"]
    
    def test_tap_with_failure(self):
        """실패 상태에서의 tap 테스트"""
        side_effects = []
        
        def side_effect(x):
            side_effects.append(x)
        
        chain = ChainableResult(Failure("error"))
        result = chain.tap(side_effect)
        
        assert result.is_failure()
        assert side_effects == []  # tap이 실행되지 않음
    
    def test_unwrap_or_default_success(self):
        """성공 시 unwrap_or_default 테스트"""
        chain = ChainableResult(Success("value"))
        result = chain.unwrap_or_default("default")
        
        assert result == "value"
    
    def test_unwrap_or_default_failure(self):
        """실패 시 unwrap_or_default 테스트"""
        chain = ChainableResult(Failure("error"))
        result = chain.unwrap_or_default("default")
        
        assert result == "default"
    
    def test_unwrap_or_else_success(self):
        """성공 시 unwrap_or_else 테스트"""
        chain = ChainableResult(Success("value"))
        result = chain.unwrap_or_else(lambda err: f"fallback: {err}")
        
        assert result == "value"
    
    def test_unwrap_or_else_failure(self):
        """실패 시 unwrap_or_else 테스트"""
        chain = ChainableResult(Failure("error"))
        result = chain.unwrap_or_else(lambda err: f"fallback: {err}")
        
        assert result == "fallback: error"


class TestConvenienceFunctions:
    """편의 함수들 테스트"""
    
    def test_success_function(self):
        """success 함수 테스트"""
        result = success("test")
        
        assert isinstance(result, ChainableResult)
        assert result.is_success()
        assert result.result.unwrap() == "test"
    
    def test_failure_function(self):
        """failure 함수 테스트"""
        result = failure("error message")
        
        assert isinstance(result, ChainableResult)
        assert result.is_failure()
        assert result.result.unwrap_error() == "error message"
    
    def test_from_result_success(self):
        """from_result 성공 케이스 테스트"""
        original = Success("test")
        result = from_result(original)
        
        assert isinstance(result, ChainableResult)
        assert result.is_success()
        assert result.result.unwrap() == "test"
    
    def test_from_result_failure(self):
        """from_result 실패 케이스 테스트"""
        original = Failure("error")
        result = from_result(original)
        
        assert isinstance(result, ChainableResult)
        assert result.is_failure()
        assert result.result.unwrap_error() == "error"