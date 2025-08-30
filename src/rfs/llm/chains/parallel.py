"""
병렬 실행 체인

여러 LLM 체인을 동시에 실행하는 체인입니다.
모든 체인이 완료되면 결과를 통합합니다.
"""

import asyncio
from typing import Dict, Any, List, Optional, Union
from rfs.core.result import Result, Success, Failure
from .base import LLMChain


class ParallelChain(LLMChain):
    """병렬 실행 체인
    
    여러 체인을 동시에 실행하여 성능을 향상시킵니다.
    모든 체인의 결과를 통합하여 반환합니다.
    """
    
    def __init__(
        self, 
        chains: List[LLMChain], 
        merge_strategy: str = "merge",
        fail_fast: bool = True,
        name: Optional[str] = None
    ):
        super().__init__(name)
        if not chains:
            raise ValueError("최소 하나 이상의 체인이 필요합니다")
        
        self.chains = chains
        self.merge_strategy = merge_strategy  # merge, separate, first_success
        self.fail_fast = fail_fast  # True면 하나라도 실패하면 전체 실패
        
        self.metadata.update({
            "chain_count": len(chains),
            "chain_names": [chain.name for chain in chains],
            "merge_strategy": merge_strategy,
            "fail_fast": fail_fast
        })
    
    async def run(
        self, 
        inputs: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Result[Dict[str, Any], str]:
        """병렬로 체인들을 실행"""
        try:
            # 실행 컨텍스트 준비
            run_context = context or {}
            run_context.update({
                "parallel_chain": True,
                "total_chains": len(self.chains),
                "merge_strategy": self.merge_strategy
            })
            
            # 모든 체인을 병렬로 실행
            tasks = []
            for i, chain in enumerate(self.chains):
                chain_context = run_context.copy()
                chain_context.update({
                    "chain_index": i,
                    "chain_name": chain.name
                })
                
                task = asyncio.create_task(
                    chain.run(inputs.copy(), chain_context),
                    name=f"chain_{i}_{chain.name}"
                )
                tasks.append(task)
            
            # 모든 태스크 완료 대기
            if self.fail_fast:
                # 하나라도 실패하면 즉시 실패 반환
                results = await asyncio.gather(*tasks, return_exceptions=True)
            else:
                # 모든 체인 완료까지 대기
                results = await asyncio.gather(*tasks, return_exceptions=False)
            
            # 결과 처리
            return self._process_results(results, inputs)
            
        except Exception as e:
            return Failure(f"ParallelChain 실행 중 예외 발생: {str(e)}")
    
    def _process_results(
        self, 
        results: List[Union[Result, Exception]], 
        original_inputs: Dict[str, Any]
    ) -> Result[Dict[str, Any], str]:
        """병렬 실행 결과를 처리"""
        successful_results = []
        failed_results = []
        execution_summary = []
        
        for i, result in enumerate(results):
            chain_name = self.chains[i].name
            
            if isinstance(result, Exception):
                # 예외 발생
                failed_results.append({
                    "chain_index": i,
                    "chain_name": chain_name,
                    "error": str(result)
                })
                execution_summary.append({
                    "chain_index": i,
                    "chain_name": chain_name,
                    "success": False,
                    "error": str(result)
                })
            elif isinstance(result, Result):
                if result.is_success():
                    # 성공
                    chain_output = result.unwrap()
                    successful_results.append({
                        "chain_index": i,
                        "chain_name": chain_name,
                        "output": chain_output
                    })
                    execution_summary.append({
                        "chain_index": i,
                        "chain_name": chain_name,
                        "success": True,
                        "output_keys": list(chain_output.keys())
                    })
                else:
                    # 실패
                    error_msg = result.unwrap_error()
                    failed_results.append({
                        "chain_index": i,
                        "chain_name": chain_name,
                        "error": error_msg
                    })
                    execution_summary.append({
                        "chain_index": i,
                        "chain_name": chain_name,
                        "success": False,
                        "error": error_msg
                    })
        
        # fail_fast 모드에서 실패가 있으면 실패 반환
        if self.fail_fast and failed_results:
            error_details = "; ".join([
                f"{fr['chain_name']}: {fr['error']}" for fr in failed_results
            ])
            return Failure(f"ParallelChain 실행 실패 - {error_details}")
        
        # 결과 통합
        merged_output = self._merge_results(
            successful_results, 
            failed_results, 
            original_inputs,
            execution_summary
        )
        
        return Success(merged_output)
    
    def _merge_results(
        self, 
        successful_results: List[Dict[str, Any]], 
        failed_results: List[Dict[str, Any]],
        original_inputs: Dict[str, Any],
        execution_summary: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """결과 병합 전략에 따라 결과를 통합"""
        base_output = original_inputs.copy()
        
        if self.merge_strategy == "merge":
            # 모든 성공한 결과를 하나로 병합
            for result_info in successful_results:
                output = result_info["output"]
                # 키 충돌 방지를 위해 체인 이름을 prefix로 사용
                chain_name = result_info["chain_name"]
                for key, value in output.items():
                    if key in base_output and key != "response":
                        # 키 충돌 시 체인 이름을 prefix로 추가
                        new_key = f"{chain_name}_{key}"
                        base_output[new_key] = value
                    else:
                        base_output[key] = value
        
        elif self.merge_strategy == "separate":
            # 각 체인의 결과를 별도로 저장
            base_output["parallel_results"] = {}
            for result_info in successful_results:
                chain_name = result_info["chain_name"]
                base_output["parallel_results"][chain_name] = result_info["output"]
        
        elif self.merge_strategy == "first_success":
            # 첫 번째 성공한 결과만 사용
            if successful_results:
                first_success = successful_results[0]["output"]
                base_output.update(first_success)
        
        # 실행 정보 추가
        base_output["_parallel_execution"] = {
            "total_chains": len(self.chains),
            "successful_chains": len(successful_results),
            "failed_chains": len(failed_results),
            "merge_strategy": self.merge_strategy,
            "execution_summary": execution_summary
        }
        
        if failed_results:
            base_output["_parallel_execution"]["failures"] = failed_results
        
        return base_output
    
    def add_chain(self, chain: LLMChain) -> 'ParallelChain':
        """체인 추가
        
        Args:
            chain: 추가할 체인
            
        Returns:
            ParallelChain: 자기 자신
        """
        self.chains.append(chain)
        self.metadata.update({
            "chain_count": len(self.chains),
            "chain_names": [chain.name for chain in self.chains]
        })
        return self
    
    def remove_chain(self, index: int) -> 'ParallelChain':
        """체인 제거
        
        Args:
            index: 제거할 체인의 인덱스
            
        Returns:
            ParallelChain: 자기 자신
        """
        if 0 <= index < len(self.chains):
            self.chains.pop(index)
            self.metadata.update({
                "chain_count": len(self.chains),
                "chain_names": [chain.name for chain in self.chains]
            })
        return self
    
    def set_merge_strategy(self, strategy: str) -> 'ParallelChain':
        """병합 전략 설정
        
        Args:
            strategy: 병합 전략 (merge, separate, first_success)
            
        Returns:
            ParallelChain: 자기 자신
        """
        valid_strategies = ["merge", "separate", "first_success"]
        if strategy not in valid_strategies:
            raise ValueError(f"유효하지 않은 병합 전략: {strategy}. 사용 가능한 전략: {valid_strategies}")
        
        self.merge_strategy = strategy
        self.metadata["merge_strategy"] = strategy
        return self
    
    def get_chain_summary(self) -> Dict[str, Any]:
        """체인 구성 요약 정보 반환"""
        return {
            "type": "ParallelChain",
            "name": self.name,
            "chain_count": len(self.chains),
            "merge_strategy": self.merge_strategy,
            "fail_fast": self.fail_fast,
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


class RacingParallelChain(ParallelChain):
    """경쟁 병렬 체인
    
    여러 체인을 병렬로 실행하되, 첫 번째로 완료되는 체인의 결과만 반환합니다.
    나머지 체인들은 자동으로 취소됩니다.
    """
    
    def __init__(self, chains: List[LLMChain], name: Optional[str] = None):
        super().__init__(chains, merge_strategy="first_success", name=name)
    
    async def run(
        self, 
        inputs: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Result[Dict[str, Any], str]:
        """첫 번째 완료되는 체인의 결과를 반환"""
        try:
            run_context = context or {}
            run_context.update({
                "racing_parallel_chain": True,
                "total_chains": len(self.chains)
            })
            
            # 모든 체인을 병렬로 실행
            tasks = []
            for i, chain in enumerate(self.chains):
                chain_context = run_context.copy()
                chain_context.update({
                    "chain_index": i,
                    "chain_name": chain.name
                })
                
                task = asyncio.create_task(
                    chain.run(inputs.copy(), chain_context),
                    name=f"racing_chain_{i}_{chain.name}"
                )
                tasks.append(task)
            
            # 첫 번째 완료 대기
            done, pending = await asyncio.wait(
                tasks, 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 나머지 태스크 취소
            for task in pending:
                task.cancel()
                
            # 완료된 첫 번째 태스크 결과 반환
            completed_task = list(done)[0]
            result = await completed_task
            
            if result.is_failure():
                return result
            
            # 성공한 경우 결과에 경주 정보 추가
            output = result.unwrap()
            winning_chain_index = tasks.index(completed_task)
            winning_chain = self.chains[winning_chain_index]
            
            output["_racing_execution"] = {
                "total_chains": len(self.chains),
                "winning_chain": {
                    "index": winning_chain_index,
                    "name": winning_chain.name,
                    "type": winning_chain.__class__.__name__
                },
                "cancelled_chains": len(pending)
            }
            
            return Success(output)
            
        except Exception as e:
            return Failure(f"RacingParallelChain 실행 실패: {str(e)}")