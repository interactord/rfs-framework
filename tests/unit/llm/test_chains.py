"""
LLM 체인 시스템 단위 테스트

체인 워크플로우의 실행과 관리 기능을 테스트합니다.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any

from rfs.core.result import Success, Failure


@pytest.mark.asyncio
class TestLLMChain:
    """기본 LLM 체인 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.chains.base import LLMChain, SimpleLLMChain
            from rfs.llm.manager import LLMManager
            self.chain_class = LLMChain
            self.simple_chain_class = SimpleLLMChain
            self.manager_class = LLMManager
            self.has_chains = True
        except ImportError:
            self.has_chains = False
    
    async def test_simple_chain_success(self):
        """SimpleLLMChain 성공 테스트"""
        if not self.has_chains:
            pytest.skip("체인 모듈을 사용할 수 없습니다")
        
        # Mock LLM Manager
        mock_manager = Mock(spec=self.manager_class)
        mock_manager.generate = AsyncMock(return_value=Success({
            "response": "테스트 응답입니다.",
            "model": "test-model",
            "usage": {"total_tokens": 15}
        }))
        
        # SimpleLLMChain 생성
        chain = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model",
            name="테스트_체인"
        )
        
        # 체인 실행
        result = await chain.run({
            "prompt": "테스트 프롬프트"
        })
        
        assert result.is_success()
        output = result.unwrap()
        assert output["response"] == "테스트 응답입니다."
        assert output["model"] == "test-model"
        
        # LLM Manager가 올바르게 호출되었는지 확인
        mock_manager.generate.assert_called_once_with(
            provider="test",
            prompt="테스트 프롬프트",
            model="test-model"
        )
    
    async def test_simple_chain_with_additional_params(self):
        """추가 매개변수와 함께 SimpleLLMChain 테스트"""
        if not self.has_chains:
            pytest.skip("체인 모듈을 사용할 수 없습니다")
        
        mock_manager = Mock(spec=self.manager_class)
        mock_manager.generate = AsyncMock(return_value=Success({
            "response": "테스트 응답",
            "model": "test-model"
        }))
        
        chain = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model",
            name="테스트_체인"
        )
        
        result = await chain.run({
            "prompt": "테스트 프롬프트",
            "max_tokens": 100,
            "temperature": 0.5
        })
        
        assert result.is_success()
        
        # 추가 매개변수가 전달되었는지 확인
        call_args = mock_manager.generate.call_args
        assert call_args[1]["max_tokens"] == 100
        assert call_args[1]["temperature"] == 0.5
    
    async def test_simple_chain_failure(self):
        """SimpleLLMChain 실패 테스트"""
        if not self.has_chains:
            pytest.skip("체인 모듈을 사용할 수 없습니다")
        
        mock_manager = Mock(spec=self.manager_class)
        mock_manager.generate = AsyncMock(return_value=Failure("API 호출 실패"))
        
        chain = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model"
        )
        
        result = await chain.run({
            "prompt": "테스트 프롬프트"
        })
        
        assert result.is_failure()
        error_message = result.unwrap_error()
        assert "API 호출 실패" in error_message


@pytest.mark.asyncio
class TestSequentialChain:
    """순차 체인 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.chains.sequential import SequentialChain
            from rfs.llm.chains.base import SimpleLLMChain
            from rfs.llm.manager import LLMManager
            self.sequential_class = SequentialChain
            self.simple_chain_class = SimpleLLMChain
            self.manager_class = LLMManager
            self.has_sequential = True
        except ImportError:
            self.has_sequential = False
    
    async def test_sequential_chain_success(self):
        """순차 체인 성공 테스트"""
        if not self.has_sequential:
            pytest.skip("순차 체인 모듈을 사용할 수 없습니다")
        
        # Mock LLM Manager
        mock_manager = Mock(spec=self.manager_class)
        
        # 각 체인별로 다른 응답 설정
        responses = [
            Success({
                "response": "첫 번째 응답",
                "model": "test-model"
            }),
            Success({
                "response": "두 번째 응답", 
                "model": "test-model"
            }),
            Success({
                "response": "세 번째 응답",
                "model": "test-model"
            })
        ]
        mock_manager.generate = AsyncMock(side_effect=responses)
        
        # 체인들 생성
        chain1 = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model",
            name="체인_1"
        )
        
        chain2 = self.simple_chain_class(
            manager=mock_manager,
            provider="test", 
            model="test-model",
            name="체인_2"
        )
        
        chain3 = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model",
            name="체인_3"
        )
        
        # 순차 체인 생성
        sequential_chain = self.sequential_class([chain1, chain2, chain3])
        
        # 실행
        result = await sequential_chain.run({
            "prompt": "초기 프롬프트"
        })
        
        assert result.is_success()
        output = result.unwrap()
        
        # 마지막 체인의 응답이 최종 출력이어야 함
        assert output["response"] == "세 번째 응답"
        
        # 실행 히스토리 확인
        execution_info = output["_sequential_execution"]
        assert execution_info["chain_count"] == 3
        assert len(execution_info["execution_history"]) == 3
        assert execution_info["success"] is True
        
        # 모든 체인이 호출되었는지 확인
        assert mock_manager.generate.call_count == 3
    
    async def test_sequential_chain_failure_middle(self):
        """중간 체인 실패 시 순차 체인 테스트"""
        if not self.has_sequential:
            pytest.skip("순차 체인 모듈을 사용할 수 없습니다")
        
        mock_manager = Mock(spec=self.manager_class)
        
        # 두 번째 체인에서 실패
        responses = [
            Success({"response": "첫 번째 응답", "model": "test-model"}),
            Failure("두 번째 체인 실패"),
            Success({"response": "세 번째 응답", "model": "test-model"})  # 호출되지 않아야 함
        ]
        mock_manager.generate = AsyncMock(side_effect=responses)
        
        # 체인들 생성
        chains = []
        for i in range(3):
            chain = self.simple_chain_class(
                manager=mock_manager,
                provider="test",
                model="test-model",
                name=f"체인_{i+1}"
            )
            chains.append(chain)
        
        sequential_chain = self.sequential_class(chains)
        
        # 실행
        result = await sequential_chain.run({
            "prompt": "초기 프롬프트"
        })
        
        assert result.is_failure()
        error_message = result.unwrap_error()
        assert "두 번째 체인 실패" in error_message
        assert "체인 2/3" in error_message  # 어느 체인에서 실패했는지 표시
        
        # 첫 번째와 두 번째 체인만 호출되었는지 확인
        assert mock_manager.generate.call_count == 2
    
    async def test_sequential_chain_empty(self):
        """빈 체인 목록으로 순차 체인 생성 테스트"""
        if not self.has_sequential:
            pytest.skip("순차 체인 모듈을 사용할 수 없습니다")
        
        with pytest.raises(ValueError, match="최소 하나 이상의 체인이 필요합니다"):
            self.sequential_class([])


@pytest.mark.asyncio 
class TestParallelChain:
    """병렬 체인 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.chains.parallel import ParallelChain
            from rfs.llm.chains.base import SimpleLLMChain
            from rfs.llm.manager import LLMManager
            self.parallel_class = ParallelChain
            self.simple_chain_class = SimpleLLMChain
            self.manager_class = LLMManager
            self.has_parallel = True
        except ImportError:
            self.has_parallel = False
    
    async def test_parallel_chain_success_merge(self):
        """병렬 체인 성공 (merge 전략) 테스트"""
        if not self.has_parallel:
            pytest.skip("병렬 체인 모듈을 사용할 수 없습니다")
        
        mock_manager = Mock(spec=self.manager_class)
        
        # 각 체인별 응답
        responses = [
            Success({"response": "첫 번째 응답", "model": "test-model", "extra1": "data1"}),
            Success({"response": "두 번째 응답", "model": "test-model", "extra2": "data2"}),
            Success({"response": "세 번째 응답", "model": "test-model", "extra3": "data3"})
        ]
        mock_manager.generate = AsyncMock(side_effect=responses)
        
        # 체인들 생성
        chains = []
        for i in range(3):
            chain = self.simple_chain_class(
                manager=mock_manager,
                provider="test",
                model="test-model",
                name=f"체인_{i+1}"
            )
            chains.append(chain)
        
        # 병렬 체인 생성 (merge 전략)
        parallel_chain = self.parallel_class(chains, merge_strategy="merge")
        
        # 실행
        result = await parallel_chain.run({
            "prompt": "초기 프롬프트"
        })
        
        assert result.is_success()
        output = result.unwrap()
        
        # 모든 응답이 병합되었는지 확인
        assert "extra1" in output or "체인_1_extra1" in output
        assert "extra2" in output or "체인_2_extra2" in output  
        assert "extra3" in output or "체인_3_extra3" in output
        
        # 병렬 실행 정보 확인
        parallel_info = output["_parallel_execution"]
        assert parallel_info["total_chains"] == 3
        assert parallel_info["successful_chains"] == 3
        assert parallel_info["failed_chains"] == 0
        assert parallel_info["merge_strategy"] == "merge"
        
        # 모든 체인이 호출되었는지 확인
        assert mock_manager.generate.call_count == 3
    
    async def test_parallel_chain_success_separate(self):
        """병렬 체인 성공 (separate 전략) 테스트"""
        if not self.has_parallel:
            pytest.skip("병렬 체인 모듈을 사용할 수 없습니다")
        
        mock_manager = Mock(spec=self.manager_class)
        
        responses = [
            Success({"response": "첫 번째 응답", "model": "test-model"}),
            Success({"response": "두 번째 응답", "model": "test-model"})
        ]
        mock_manager.generate = AsyncMock(side_effect=responses)
        
        # 체인들 생성
        chain1 = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model",
            name="체인_1"
        )
        
        chain2 = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model", 
            name="체인_2"
        )
        
        # 병렬 체인 생성 (separate 전략)
        parallel_chain = self.parallel_class([chain1, chain2], merge_strategy="separate")
        
        # 실행
        result = await parallel_chain.run({
            "prompt": "초기 프롬프트"
        })
        
        assert result.is_success()
        output = result.unwrap()
        
        # separate 전략으로 각 체인의 결과가 별도로 저장되었는지 확인
        assert "parallel_results" in output
        assert "체인_1" in output["parallel_results"]
        assert "체인_2" in output["parallel_results"]
        
        assert output["parallel_results"]["체인_1"]["response"] == "첫 번째 응답"
        assert output["parallel_results"]["체인_2"]["response"] == "두 번째 응답"
    
    async def test_parallel_chain_failure_fail_fast(self):
        """병렬 체인 실패 (fail_fast=True) 테스트"""
        if not self.has_parallel:
            pytest.skip("병렬 체인 모듈을 사용할 수 없습니다")
        
        mock_manager = Mock(spec=self.manager_class)
        
        # 하나는 성공, 하나는 실패
        responses = [
            Success({"response": "성공 응답", "model": "test-model"}),
            Failure("체인 실행 실패")
        ]
        mock_manager.generate = AsyncMock(side_effect=responses)
        
        chain1 = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model",
            name="성공_체인"
        )
        
        chain2 = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model",
            name="실패_체인"
        )
        
        # fail_fast=True로 병렬 체인 생성
        parallel_chain = self.parallel_class([chain1, chain2], fail_fast=True)
        
        # 실행
        result = await parallel_chain.run({
            "prompt": "초기 프롬프트"
        })
        
        assert result.is_failure()
        error_message = result.unwrap_error()
        assert "실패_체인" in error_message or "체인 실행 실패" in error_message
    
    async def test_parallel_chain_failure_continue(self):
        """병렬 체인 실패 (fail_fast=False) 테스트"""
        if not self.has_parallel:
            pytest.skip("병렬 체인 모듈을 사용할 수 없습니다")
        
        mock_manager = Mock(spec=self.manager_class)
        
        # 하나는 성공, 하나는 실패
        responses = [
            Success({"response": "성공 응답", "model": "test-model"}),
            Failure("체인 실행 실패")
        ]
        mock_manager.generate = AsyncMock(side_effect=responses)
        
        chain1 = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model",
            name="성공_체인"
        )
        
        chain2 = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model",
            name="실패_체인"
        )
        
        # fail_fast=False로 병렬 체인 생성  
        parallel_chain = self.parallel_class([chain1, chain2], fail_fast=False)
        
        # 실행
        result = await parallel_chain.run({
            "prompt": "초기 프롬프트"
        })
        
        assert result.is_success()
        output = result.unwrap()
        
        # 병렬 실행 정보에서 실패 정보 확인
        parallel_info = output["_parallel_execution"]
        assert parallel_info["successful_chains"] == 1
        assert parallel_info["failed_chains"] == 1
        assert "failures" in parallel_info


@pytest.mark.asyncio
class TestConditionalChain:
    """조건부 체인 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from rfs.llm.chains.conditional import ConditionalChain
            from rfs.llm.chains.base import SimpleLLMChain
            from rfs.llm.manager import LLMManager
            self.conditional_class = ConditionalChain
            self.simple_chain_class = SimpleLLMChain
            self.manager_class = LLMManager
            self.has_conditional = True
        except ImportError:
            self.has_conditional = False
    
    async def test_conditional_chain_if_true(self):
        """조건이 True일 때 조건부 체인 테스트"""
        if not self.has_conditional:
            pytest.skip("조건부 체인 모듈을 사용할 수 없습니다")
        
        mock_manager = Mock(spec=self.manager_class)
        mock_manager.generate = AsyncMock(return_value=Success({
            "response": "IF 체인 응답",
            "model": "test-model"
        }))
        
        # IF 체인
        if_chain = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model",
            name="IF_체인"
        )
        
        # 조건 함수 (항상 True)
        def condition(inputs: Dict) -> bool:
            return inputs.get("execute_if", False)
        
        # 조건부 체인 생성
        conditional_chain = self.conditional_class(
            condition=condition,
            if_chain=if_chain
        )
        
        # 조건이 True인 경우 실행
        result = await conditional_chain.run({
            "execute_if": True,
            "prompt": "테스트 프롬프트"
        })
        
        assert result.is_success()
        output = result.unwrap()
        
        assert output["response"] == "IF 체인 응답"
        
        # 조건부 실행 정보 확인
        conditional_info = output["_conditional_execution"]
        assert conditional_info["condition_result"] is True
        assert conditional_info["executed_branch"] == "if"
        assert conditional_info["executed_chain"] == "IF_체인"
        
        # IF 체인이 호출되었는지 확인
        mock_manager.generate.assert_called_once()
    
    async def test_conditional_chain_if_false_with_else(self):
        """조건이 False이고 ELSE 체인이 있을 때 테스트"""
        if not self.has_conditional:
            pytest.skip("조건부 체인 모듈을 사용할 수 없습니다")
        
        mock_manager = Mock(spec=self.manager_class)
        
        # IF와 ELSE 체인에서 다른 응답
        responses = [
            Success({"response": "ELSE 체인 응답", "model": "test-model"})
        ]
        mock_manager.generate = AsyncMock(side_effect=responses)
        
        if_chain = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model",
            name="IF_체인"
        )
        
        else_chain = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model",
            name="ELSE_체인"
        )
        
        # 조건 함수 (항상 False)
        def condition(inputs: Dict) -> bool:
            return inputs.get("execute_if", True)  # 기본값을 True로 하여 False가 되도록
        
        conditional_chain = self.conditional_class(
            condition=condition,
            if_chain=if_chain,
            else_chain=else_chain
        )
        
        # 조건이 False인 경우 실행
        result = await conditional_chain.run({
            "execute_if": False,
            "prompt": "테스트 프롬프트"
        })
        
        assert result.is_success()
        output = result.unwrap()
        
        assert output["response"] == "ELSE 체인 응답"
        
        # 조건부 실행 정보 확인
        conditional_info = output["_conditional_execution"]
        assert conditional_info["condition_result"] is False
        assert conditional_info["executed_branch"] == "else"
        assert conditional_info["executed_chain"] == "ELSE_체인"
    
    async def test_conditional_chain_condition_exception(self):
        """조건 함수에서 예외 발생 시 테스트"""
        if not self.has_conditional:
            pytest.skip("조건부 체인 모듈을 사용할 수 없습니다")
        
        mock_manager = Mock(spec=self.manager_class)
        
        if_chain = self.simple_chain_class(
            manager=mock_manager,
            provider="test",
            model="test-model"
        )
        
        # 예외를 발생시키는 조건 함수
        def failing_condition(inputs: Dict) -> bool:
            raise ValueError("조건 평가 실패")
        
        conditional_chain = self.conditional_class(
            condition=failing_condition,
            if_chain=if_chain
        )
        
        result = await conditional_chain.run({
            "prompt": "테스트 프롬프트"
        })
        
        assert result.is_failure()
        error_message = result.unwrap_error()
        assert "조건 함수 실행 실패" in error_message
        assert "조건 평가 실패" in error_message