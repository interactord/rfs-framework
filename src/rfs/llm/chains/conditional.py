"""
조건부 실행 체인

조건에 따라 다른 체인을 실행하는 체인입니다.
if-else 로직을 체인으로 구현합니다.
"""

from typing import Dict, Any, Optional, Callable, Union
from rfs.core.result import Result, Success, Failure
from .base import LLMChain


class ConditionalChain(LLMChain):
    """조건부 실행 체인
    
    주어진 조건 함수의 결과에 따라 다른 체인을 실행합니다.
    """
    
    def __init__(
        self,
        condition: Callable[[Dict[str, Any]], bool],
        if_chain: LLMChain,
        else_chain: Optional[LLMChain] = None,
        name: Optional[str] = None
    ):
        super().__init__(name)
        self.condition = condition
        self.if_chain = if_chain
        self.else_chain = else_chain
        
        self.metadata.update({
            "has_if_chain": self.if_chain is not None,
            "has_else_chain": self.else_chain is not None,
            "if_chain_name": self.if_chain.name if self.if_chain else None,
            "else_chain_name": self.else_chain.name if self.else_chain else None
        })
    
    async def run(
        self, 
        inputs: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Result[Dict[str, Any], str]:
        """조건을 평가하고 해당하는 체인을 실행"""
        try:
            # 조건 평가
            try:
                condition_result = self.condition(inputs)
            except Exception as e:
                return Failure(f"조건 함수 실행 실패: {str(e)}")
            
            # 실행 컨텍스트 준비
            run_context = context or {}
            run_context.update({
                "conditional_chain": True,
                "condition_result": condition_result
            })
            
            # 조건에 따라 체인 선택 및 실행
            if condition_result:
                # True인 경우 if_chain 실행
                if self.if_chain:
                    run_context["selected_branch"] = "if"
                    run_context["selected_chain"] = self.if_chain.name
                    
                    result = await self.if_chain.run(inputs, run_context)
                    
                    if result.is_success():
                        output = result.unwrap()
                        output["_conditional_execution"] = {
                            "condition_result": True,
                            "executed_branch": "if",
                            "executed_chain": self.if_chain.name
                        }
                        return Success(output)
                    else:
                        return result
                else:
                    # if_chain이 없으면 입력을 그대로 반환
                    output = inputs.copy()
                    output["_conditional_execution"] = {
                        "condition_result": True,
                        "executed_branch": "if",
                        "executed_chain": None,
                        "note": "if_chain이 없어서 입력을 그대로 반환"
                    }
                    return Success(output)
            else:
                # False인 경우 else_chain 실행
                if self.else_chain:
                    run_context["selected_branch"] = "else"
                    run_context["selected_chain"] = self.else_chain.name
                    
                    result = await self.else_chain.run(inputs, run_context)
                    
                    if result.is_success():
                        output = result.unwrap()
                        output["_conditional_execution"] = {
                            "condition_result": False,
                            "executed_branch": "else",
                            "executed_chain": self.else_chain.name
                        }
                        return Success(output)
                    else:
                        return result
                else:
                    # else_chain이 없으면 입력을 그대로 반환
                    output = inputs.copy()
                    output["_conditional_execution"] = {
                        "condition_result": False,
                        "executed_branch": "else",
                        "executed_chain": None,
                        "note": "else_chain이 없어서 입력을 그대로 반환"
                    }
                    return Success(output)
                    
        except Exception as e:
            return Failure(f"ConditionalChain 실행 실패: {str(e)}")
    
    def set_else_chain(self, else_chain: LLMChain) -> 'ConditionalChain':
        """else 체인 설정
        
        Args:
            else_chain: 조건이 False일 때 실행할 체인
            
        Returns:
            ConditionalChain: 자기 자신
        """
        self.else_chain = else_chain
        self.metadata.update({
            "has_else_chain": True,
            "else_chain_name": else_chain.name
        })
        return self
    
    def get_chain_summary(self) -> Dict[str, Any]:
        """체인 구성 요약 정보 반환"""
        return {
            "type": "ConditionalChain",
            "name": self.name,
            "has_if_chain": self.if_chain is not None,
            "has_else_chain": self.else_chain is not None,
            "if_chain": {
                "name": self.if_chain.name,
                "type": self.if_chain.__class__.__name__
            } if self.if_chain else None,
            "else_chain": {
                "name": self.else_chain.name,
                "type": self.else_chain.__class__.__name__
            } if self.else_chain else None
        }


class SwitchChain(LLMChain):
    """스위치 체인
    
    여러 조건과 체인을 매핑하여 switch-case 같은 로직을 구현합니다.
    """
    
    def __init__(
        self,
        cases: Dict[Any, LLMChain],
        selector: Callable[[Dict[str, Any]], Any],
        default_chain: Optional[LLMChain] = None,
        name: Optional[str] = None
    ):
        super().__init__(name)
        self.cases = cases
        self.selector = selector
        self.default_chain = default_chain
        
        self.metadata.update({
            "case_count": len(cases),
            "case_keys": list(cases.keys()),
            "has_default": default_chain is not None,
            "default_chain_name": default_chain.name if default_chain else None
        })
    
    async def run(
        self, 
        inputs: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Result[Dict[str, Any], str]:
        """선택자 함수의 결과에 따라 해당하는 케이스 체인을 실행"""
        try:
            # 선택자 함수 실행
            try:
                selected_key = self.selector(inputs)
            except Exception as e:
                return Failure(f"선택자 함수 실행 실패: {str(e)}")
            
            # 실행 컨텍스트 준비
            run_context = context or {}
            run_context.update({
                "switch_chain": True,
                "selected_key": selected_key,
                "available_cases": list(self.cases.keys())
            })
            
            # 해당하는 케이스 찾기
            if selected_key in self.cases:
                # 일치하는 케이스 실행
                selected_chain = self.cases[selected_key]
                run_context["selected_case"] = selected_key
                run_context["selected_chain"] = selected_chain.name
                
                result = await selected_chain.run(inputs, run_context)
                
                if result.is_success():
                    output = result.unwrap()
                    output["_switch_execution"] = {
                        "selected_key": selected_key,
                        "executed_chain": selected_chain.name,
                        "case_matched": True
                    }
                    return Success(output)
                else:
                    return result
            
            elif self.default_chain:
                # 기본 케이스 실행
                run_context["selected_case"] = "default"
                run_context["selected_chain"] = self.default_chain.name
                
                result = await self.default_chain.run(inputs, run_context)
                
                if result.is_success():
                    output = result.unwrap()
                    output["_switch_execution"] = {
                        "selected_key": selected_key,
                        "executed_chain": self.default_chain.name,
                        "case_matched": False,
                        "used_default": True
                    }
                    return Success(output)
                else:
                    return result
            
            else:
                # 매칭되는 케이스가 없고 기본 케이스도 없음
                output = inputs.copy()
                output["_switch_execution"] = {
                    "selected_key": selected_key,
                    "executed_chain": None,
                    "case_matched": False,
                    "used_default": False,
                    "note": f"키 '{selected_key}'에 해당하는 케이스가 없고 기본 케이스도 없음"
                }
                return Success(output)
                
        except Exception as e:
            return Failure(f"SwitchChain 실행 실패: {str(e)}")
    
    def add_case(self, key: Any, chain: LLMChain) -> 'SwitchChain':
        """케이스 추가
        
        Args:
            key: 케이스 키
            chain: 해당 케이스에서 실행할 체인
            
        Returns:
            SwitchChain: 자기 자신
        """
        self.cases[key] = chain
        self.metadata.update({
            "case_count": len(self.cases),
            "case_keys": list(self.cases.keys())
        })
        return self
    
    def remove_case(self, key: Any) -> 'SwitchChain':
        """케이스 제거
        
        Args:
            key: 제거할 케이스 키
            
        Returns:
            SwitchChain: 자기 자신
        """
        if key in self.cases:
            del self.cases[key]
            self.metadata.update({
                "case_count": len(self.cases),
                "case_keys": list(self.cases.keys())
            })
        return self
    
    def set_default_chain(self, chain: LLMChain) -> 'SwitchChain':
        """기본 체인 설정
        
        Args:
            chain: 기본으로 실행할 체인
            
        Returns:
            SwitchChain: 자기 자신
        """
        self.default_chain = chain
        self.metadata.update({
            "has_default": True,
            "default_chain_name": chain.name
        })
        return self
    
    def get_chain_summary(self) -> Dict[str, Any]:
        """체인 구성 요약 정보 반환"""
        return {
            "type": "SwitchChain",
            "name": self.name,
            "case_count": len(self.cases),
            "cases": {
                key: {
                    "name": chain.name,
                    "type": chain.__class__.__name__
                }
                for key, chain in self.cases.items()
            },
            "default_chain": {
                "name": self.default_chain.name,
                "type": self.default_chain.__class__.__name__
            } if self.default_chain else None
        }