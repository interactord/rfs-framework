"""
순차 실행 체인

여러 LLM 체인을 순서대로 실행하는 체인입니다.
이전 체인의 출력이 다음 체인의 입력으로 전달됩니다.
"""

from typing import Dict, Any, List, Optional
from rfs.core.result import Result, Success, Failure
from .base import LLMChain


class SequentialChain(LLMChain):
    """순차 실행 체인
    
    여러 체인을 순서대로 실행하며, 각 체인의 출력이 
    다음 체인의 입력으로 전달됩니다.
    """
    
    def __init__(self, chains: List[LLMChain], name: Optional[str] = None):
        super().__init__(name)
        if not chains:
            raise ValueError("최소 하나 이상의 체인이 필요합니다")
        
        self.chains = chains
        self.metadata.update({
            "chain_count": len(chains),
            "chain_names": [chain.name for chain in chains]
        })
    
    async def run(
        self, 
        inputs: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Result[Dict[str, Any], str]:
        """순차적으로 체인들을 실행"""
        try:
            current_inputs = inputs.copy()
            execution_history = []
            
            # 실행 컨텍스트 준비
            run_context = context or {}
            run_context.update({
                "sequential_chain": True,
                "total_chains": len(self.chains),
                "execution_history": execution_history
            })
            
            # 각 체인을 순서대로 실행
            for i, chain in enumerate(self.chains):
                # 체인별 컨텍스트 업데이트
                chain_context = run_context.copy()
                chain_context.update({
                    "current_chain_index": i,
                    "current_chain_name": chain.name,
                    "is_first_chain": i == 0,
                    "is_last_chain": i == len(self.chains) - 1
                })
                
                # 체인 실행
                result = await chain.run(current_inputs, chain_context)
                
                if result.is_failure():
                    error_msg = result.unwrap_error()
                    
                    # 실패한 체인 정보 추가
                    detailed_error = f"체인 {i+1}/{len(self.chains)} ('{chain.name}') 실행 실패: {error_msg}"
                    
                    return Failure(detailed_error)
                
                # 성공한 경우, 결과를 다음 체인의 입력으로 설정
                chain_output = result.unwrap()
                
                # 실행 히스토리 기록
                execution_record = {
                    "chain_index": i,
                    "chain_name": chain.name,
                    "chain_type": chain.__class__.__name__,
                    "input_keys": list(current_inputs.keys()),
                    "output_keys": list(chain_output.keys()),
                    "success": True
                }
                execution_history.append(execution_record)
                
                # 다음 체인을 위한 입력 준비
                current_inputs = chain_output
            
            # 최종 결과에 실행 정보 추가
            current_inputs["_sequential_execution"] = {
                "chain_count": len(self.chains),
                "execution_history": execution_history,
                "success": True
            }
            
            return Success(current_inputs)
            
        except Exception as e:
            return Failure(f"SequentialChain 실행 중 예외 발생: {str(e)}")
    
    def add_chain(self, chain: LLMChain) -> 'SequentialChain':
        """체인 추가
        
        Args:
            chain: 추가할 체인
            
        Returns:
            SequentialChain: 자기 자신 (메소드 체이닝용)
        """
        self.chains.append(chain)
        self.metadata.update({
            "chain_count": len(self.chains),
            "chain_names": [chain.name for chain in self.chains]
        })
        return self
    
    def insert_chain(self, index: int, chain: LLMChain) -> 'SequentialChain':
        """특정 위치에 체인 삽입
        
        Args:
            index: 삽입할 위치
            chain: 삽입할 체인
            
        Returns:
            SequentialChain: 자기 자신
        """
        self.chains.insert(index, chain)
        self.metadata.update({
            "chain_count": len(self.chains),
            "chain_names": [chain.name for chain in self.chains]
        })
        return self
    
    def remove_chain(self, index: int) -> 'SequentialChain':
        """체인 제거
        
        Args:
            index: 제거할 체인의 인덱스
            
        Returns:
            SequentialChain: 자기 자신
        """
        if 0 <= index < len(self.chains):
            self.chains.pop(index)
            self.metadata.update({
                "chain_count": len(self.chains),
                "chain_names": [chain.name for chain in self.chains]
            })
        return self
    
    def get_chain_summary(self) -> Dict[str, Any]:
        """체인 구성 요약 정보 반환
        
        Returns:
            Dict[str, Any]: 체인 요약 정보
        """
        return {
            "type": "SequentialChain",
            "name": self.name,
            "chain_count": len(self.chains),
            "chains": [
                {
                    "index": i,
                    "name": chain.name,
                    "type": chain.__class__.__name__,
                    "metadata": chain.metadata
                }
                for i, chain in enumerate(self.chains)
            ]
        }


class ConditionalSequentialChain(SequentialChain):
    """조건부 순차 실행 체인
    
    각 체인 실행 전에 조건을 확인하여 실행 여부를 결정하는 순차 체인입니다.
    """
    
    def __init__(
        self, 
        chains: List[LLMChain], 
        conditions: List[callable],
        name: Optional[str] = None
    ):
        super().__init__(chains, name)
        
        if len(conditions) != len(chains):
            raise ValueError("체인 수와 조건 함수 수가 일치해야 합니다")
        
        self.conditions = conditions
    
    async def run(
        self, 
        inputs: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Result[Dict[str, Any], str]:
        """조건을 확인하면서 순차적으로 체인들을 실행"""
        try:
            current_inputs = inputs.copy()
            execution_history = []
            skipped_chains = []
            
            run_context = context or {}
            run_context.update({
                "conditional_sequential_chain": True,
                "total_chains": len(self.chains),
                "execution_history": execution_history,
                "skipped_chains": skipped_chains
            })
            
            for i, (chain, condition) in enumerate(zip(self.chains, self.conditions)):
                # 조건 확인
                try:
                    should_execute = condition(current_inputs)
                except Exception as e:
                    return Failure(f"체인 {i+1}의 조건 함수 실행 실패: {str(e)}")
                
                if not should_execute:
                    # 체인 건너뛰기
                    skip_record = {
                        "chain_index": i,
                        "chain_name": chain.name,
                        "reason": "조건 불만족"
                    }
                    skipped_chains.append(skip_record)
                    continue
                
                # 체인 실행
                chain_context = run_context.copy()
                chain_context.update({
                    "current_chain_index": i,
                    "current_chain_name": chain.name
                })
                
                result = await chain.run(current_inputs, chain_context)
                
                if result.is_failure():
                    return result
                
                # 결과 처리
                chain_output = result.unwrap()
                execution_history.append({
                    "chain_index": i,
                    "chain_name": chain.name,
                    "condition_met": True,
                    "success": True
                })
                
                current_inputs = chain_output
            
            # 최종 결과 구성
            current_inputs["_conditional_execution"] = {
                "executed_chains": len(execution_history),
                "skipped_chains": len(skipped_chains),
                "execution_history": execution_history,
                "skipped_chain_info": skipped_chains
            }
            
            return Success(current_inputs)
            
        except Exception as e:
            return Failure(f"ConditionalSequentialChain 실행 실패: {str(e)}")