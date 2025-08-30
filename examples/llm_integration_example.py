#!/usr/bin/env python3
"""
RFS Framework LLM 통합 사용 예제

LLM 통합 모듈의 주요 기능들을 보여주는 종합적인 예제입니다.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any

from rfs.core.result import Result, Success, Failure
from rfs.core.config import Config, get_config
from rfs.hof.core import pipe, curry
from rfs.hof.collections import compact_map, first


# LLM 관련 import (조건부)
try:
    from rfs.llm import (
        LLMManager, 
        OpenAIProvider, 
        AnthropicProvider,
        PromptTemplateManager,
        RAGEngine,
        SequentialChain,
        ParallelChain,
        ConditionalChain,
        get_metrics_collector,
        get_response_cache
    )
    from rfs.llm.rag.chroma import ChromaVectorStore
    HAS_LLM = True
except ImportError:
    print("LLM 모듈을 사용하려면 추가 의존성을 설치하세요:")
    print("pip install openai anthropic chromadb jinja2")
    HAS_LLM = False


class LLMIntegrationDemo:
    """LLM 통합 데모 클래스"""
    
    def __init__(self):
        self.llm_manager = None
        self.template_manager = None
        self.rag_engine = None
        self.metrics_collector = None
        self.response_cache = None
    
    async def setup(self) -> Result[None, str]:
        """데모 환경 설정"""
        if not HAS_LLM:
            return Failure("LLM 모듈이 설치되지 않았습니다")
        
        try:
            # 1. LLM Manager 설정
            self.llm_manager = LLMManager()
            
            # OpenAI 제공자 등록 (API 키가 있는 경우)
            openai_api_key = get_config("llm.providers.openai.api_key", None)
            if openai_api_key:
                openai_provider = OpenAIProvider(api_key=openai_api_key)
                await self.llm_manager.register_provider("openai", openai_provider)
                print("✅ OpenAI 제공자 등록 완료")
            
            # Anthropic 제공자 등록 (API 키가 있는 경우)
            anthropic_api_key = get_config("llm.providers.anthropic.api_key", None)
            if anthropic_api_key:
                anthropic_provider = AnthropicProvider(api_key=anthropic_api_key)
                await self.llm_manager.register_provider("anthropic", anthropic_provider)
                print("✅ Anthropic 제공자 등록 완료")
            
            # 2. 템플릿 매니저 설정
            self.template_manager = PromptTemplateManager()
            await self.template_manager.register_common_templates()
            print("✅ 프롬프트 템플릿 등록 완료")
            
            # 3. RAG 엔진 설정
            vector_store = ChromaVectorStore(
                collection_name="demo_collection",
                persist_directory="./chroma_data"
            )
            self.rag_engine = RAGEngine(
                vector_store=vector_store,
                llm_manager=self.llm_manager
            )
            print("✅ RAG 엔진 설정 완료")
            
            # 4. 모니터링 설정
            self.metrics_collector = get_metrics_collector()
            self.response_cache = get_response_cache()
            print("✅ 모니터링 시스템 설정 완료")
            
            return Success(None)
            
        except Exception as e:
            return Failure(f"설정 실패: {str(e)}")
    
    async def demo_basic_llm_usage(self) -> Result[Dict[str, Any], str]:
        """기본 LLM 사용법 데모"""
        print("\n🔥 기본 LLM 사용법 데모")
        
        try:
            results = {}
            
            # 단순 텍스트 생성
            prompt = "Python에서 함수형 프로그래밍의 장점을 3가지로 요약해주세요."
            
            # OpenAI 사용 (가능한 경우)
            if await self.llm_manager.has_provider("openai"):
                openai_result = await self.llm_manager.generate(
                    "openai", 
                    prompt,
                    model="gpt-3.5-turbo",
                    max_tokens=200
                )
                
                if openai_result.is_success():
                    results["openai_response"] = openai_result.unwrap()["response"]
                    print(f"OpenAI 응답: {results['openai_response'][:100]}...")
            
            # Anthropic 사용 (가능한 경우)
            if await self.llm_manager.has_provider("anthropic"):
                anthropic_result = await self.llm_manager.generate(
                    "anthropic",
                    prompt,
                    model="claude-3-haiku-20240307",
                    max_tokens=200
                )
                
                if anthropic_result.is_success():
                    results["anthropic_response"] = anthropic_result.unwrap()["response"]
                    print(f"Anthropic 응답: {results['anthropic_response'][:100]}...")
            
            return Success(results)
            
        except Exception as e:
            return Failure(f"기본 LLM 사용 데모 실패: {str(e)}")
    
    async def demo_template_usage(self) -> Result[Dict[str, Any], str]:
        """템플릿 사용법 데모"""
        print("\n📝 템플릿 사용법 데모")
        
        try:
            results = {}
            
            # 코드 리뷰 템플릿 사용
            code_to_review = """
def calculate_fibonacci(n):
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
"""
            
            # 템플릿 렌더링 및 생성
            if await self.llm_manager.has_provider("openai"):
                review_result = await self.template_manager.render_and_generate(
                    template_name="code_review",
                    provider="openai",
                    manager=self.llm_manager,
                    variables={
                        "code": code_to_review,
                        "language": "Python",
                        "focus_areas": ["성능", "가독성", "베스트 프랙티스"]
                    },
                    model="gpt-3.5-turbo"
                )
                
                if review_result.is_success():
                    results["code_review"] = review_result.unwrap()["response"]
                    print(f"코드 리뷰 결과: {results['code_review'][:150]}...")
            
            # 요약 템플릿 사용
            text_to_summarize = """
            함수형 프로그래밍은 수학적 함수의 개념을 기반으로 하는 프로그래밍 패러다임입니다.
            주요 특징으로는 불변성, 순수 함수, 고차 함수, 함수 합성 등이 있습니다.
            Python에서는 map, filter, reduce 같은 내장 함수와 함께 lambda를 사용하여
            함수형 프로그래밍 스타일을 구현할 수 있습니다. 또한 itertools 모듈은
            함수형 프로그래밍에 유용한 많은 도구들을 제공합니다.
            """
            
            if await self.llm_manager.has_provider("openai"):
                summary_result = await self.template_manager.render_and_generate(
                    template_name="summarization",
                    provider="openai",
                    manager=self.llm_manager,
                    variables={
                        "text": text_to_summarize,
                        "length": "짧게",
                        "style": "기술적"
                    },
                    model="gpt-3.5-turbo"
                )
                
                if summary_result.is_success():
                    results["summary"] = summary_result.unwrap()["response"]
                    print(f"요약 결과: {results['summary']}")
            
            return Success(results)
            
        except Exception as e:
            return Failure(f"템플릿 사용 데모 실패: {str(e)}")
    
    async def demo_rag_usage(self) -> Result[Dict[str, Any], str]:
        """RAG 사용법 데모"""
        print("\n📚 RAG (Retrieval Augmented Generation) 사용법 데모")
        
        try:
            results = {}
            
            # 샘플 문서들을 지식 베이스에 추가
            sample_docs = [
                {
                    "content": "RFS Framework는 함수형 프로그래밍 패턴을 지원하는 Python 프레임워크입니다. Result 패턴을 통해 명시적 에러 처리를 제공합니다.",
                    "metadata": {"source": "rfs_overview", "type": "documentation"}
                },
                {
                    "content": "Result 패턴에서 Success와 Failure를 사용하여 함수의 성공/실패를 명시적으로 처리할 수 있습니다. 이는 예외 처리보다 안전한 방식입니다.",
                    "metadata": {"source": "result_pattern", "type": "documentation"}
                },
                {
                    "content": "HOF(Higher-Order Functions) 라이브러리는 함수 합성, 커링, 파이프라인 등의 함수형 프로그래밍 도구를 제공합니다.",
                    "metadata": {"source": "hof_library", "type": "documentation"}
                }
            ]
            
            # 문서들을 지식 베이스에 추가
            for i, doc in enumerate(sample_docs):
                add_result = await self.rag_engine.add_to_knowledge_base(
                    text=doc["content"],
                    doc_id=f"doc_{i}",
                    metadata=doc["metadata"]
                )
                
                if add_result.is_failure():
                    print(f"문서 추가 실패: {add_result.unwrap_error()}")
            
            print("✅ 샘플 문서들을 지식 베이스에 추가했습니다.")
            
            # RAG 질의 응답
            questions = [
                "RFS Framework의 주요 특징은 무엇인가요?",
                "Result 패턴이 예외 처리보다 좋은 이유는?",
                "HOF 라이브러리에는 어떤 기능들이 있나요?"
            ]
            
            if await self.llm_manager.has_provider("openai"):
                for question in questions:
                    rag_result = await self.rag_engine.generate_answer(
                        question=question,
                        provider="openai",
                        model="gpt-3.5-turbo",
                        template="basic"
                    )
                    
                    if rag_result.is_success():
                        answer_data = rag_result.unwrap()
                        results[f"question_{len(results)}"] = {
                            "question": question,
                            "answer": answer_data["answer"],
                            "sources": [doc["metadata"] for doc in answer_data.get("sources", [])]
                        }
                        print(f"\n질문: {question}")
                        print(f"답변: {answer_data['answer'][:200]}...")
            
            return Success(results)
            
        except Exception as e:
            return Failure(f"RAG 사용 데모 실패: {str(e)}")
    
    async def demo_chain_workflows(self) -> Result[Dict[str, Any], str]:
        """체인 워크플로우 데모"""
        print("\n🔗 체인 워크플로우 데모")
        
        try:
            results = {}
            
            if not await self.llm_manager.has_provider("openai"):
                return Success({"message": "OpenAI 제공자가 필요합니다"})
            
            # 1. 순차 체인 예제
            from rfs.llm.chains.base import SimpleLLMChain
            
            # 아이디어 생성 체인
            idea_chain = SimpleLLMChain(
                manager=self.llm_manager,
                provider="openai",
                model="gpt-3.5-turbo",
                name="아이디어_생성"
            )
            
            # 아이디어 평가 체인
            evaluation_chain = SimpleLLMChain(
                manager=self.llm_manager,
                provider="openai", 
                model="gpt-3.5-turbo",
                name="아이디어_평가"
            )
            
            # 개선 제안 체인
            improvement_chain = SimpleLLMChain(
                manager=self.llm_manager,
                provider="openai",
                model="gpt-3.5-turbo", 
                name="개선_제안"
            )
            
            # 순차 체인 구성
            sequential_chain = SequentialChain([
                idea_chain,
                evaluation_chain, 
                improvement_chain
            ])
            
            # 순차 체인 실행
            sequential_result = await sequential_chain.run({
                "topic": "Python으로 웹 API를 개발할 때 성능을 최적화하는 방법",
                "prompt": "주제에 대한 3가지 실용적인 아이디어를 제안해주세요."
            })
            
            if sequential_result.is_success():
                results["sequential_chain"] = sequential_result.unwrap()
                print("✅ 순차 체인 실행 완료")
            
            # 2. 병렬 체인 예제
            pros_chain = SimpleLLMChain(
                manager=self.llm_manager,
                provider="openai",
                model="gpt-3.5-turbo",
                name="장점_분석"
            )
            
            cons_chain = SimpleLLMChain(
                manager=self.llm_manager,
                provider="openai",
                model="gpt-3.5-turbo",
                name="단점_분석"
            )
            
            # 병렬 체인 구성
            parallel_chain = ParallelChain([pros_chain, cons_chain])
            
            # 병렬 체인 실행
            parallel_result = await parallel_chain.run({
                "topic": "FastAPI vs Django",
                "prompt": "FastAPI와 Django의 특징을 분석해주세요."
            })
            
            if parallel_result.is_success():
                results["parallel_chain"] = parallel_result.unwrap()
                print("✅ 병렬 체인 실행 완료")
            
            return Success(results)
            
        except Exception as e:
            return Failure(f"체인 워크플로우 데모 실패: {str(e)}")
    
    async def demo_monitoring_and_caching(self) -> Result[Dict[str, Any], str]:
        """모니터링 및 캐싱 데모"""
        print("\n📊 모니터링 및 캐싱 데모")
        
        try:
            results = {}
            
            # 1. 메트릭 수집 데모
            if await self.llm_manager.has_provider("openai"):
                # 몇 번의 LLM 호출로 메트릭 생성
                test_prompts = [
                    "Hello, world!",
                    "Python에서 비동기 프로그래밍이란?",
                    "함수형 프로그래밍의 핵심 개념 설명"
                ]
                
                for prompt in test_prompts:
                    await self.llm_manager.generate(
                        "openai",
                        prompt,
                        model="gpt-3.5-turbo",
                        max_tokens=50
                    )
                
                # 메트릭 요약 조회
                metrics_summary = self.metrics_collector.get_summary()
                if metrics_summary.is_success():
                    results["metrics_summary"] = {
                        "total_calls": metrics_summary.unwrap().total_calls,
                        "success_rate": metrics_summary.unwrap().success_rate,
                        "avg_duration_ms": metrics_summary.unwrap().avg_duration_ms
                    }
                    print(f"✅ 메트릭 수집 완료: {results['metrics_summary']}")
            
            # 2. 캐시 데모
            cache_stats_before = await self.response_cache.get_cache_stats()
            
            # 동일한 프롬프트를 두 번 호출 (첫 번째는 미스, 두 번째는 히트)
            test_prompt = "캐시 테스트용 프롬프트입니다."
            
            if await self.llm_manager.has_provider("openai"):
                # 첫 번째 호출 (캐시 미스)
                first_call = await self.llm_manager.generate(
                    "openai",
                    test_prompt,
                    model="gpt-3.5-turbo",
                    max_tokens=30
                )
                
                # 두 번째 호출 (캐시 히트 - 실제로는 구현에 따라 다름)
                second_call = await self.llm_manager.generate(
                    "openai", 
                    test_prompt,
                    model="gpt-3.5-turbo",
                    max_tokens=30
                )
            
            cache_stats_after = await self.response_cache.get_cache_stats()
            
            if cache_stats_after.is_success():
                results["cache_stats"] = cache_stats_after.unwrap()
                print(f"✅ 캐시 통계: {results['cache_stats']}")
            
            return Success(results)
            
        except Exception as e:
            return Failure(f"모니터링 및 캐싱 데모 실패: {str(e)}")
    
    async def run_all_demos(self) -> Result[Dict[str, Any], str]:
        """모든 데모 실행"""
        print("🚀 RFS Framework LLM 통합 데모 시작\n")
        
        # 설정
        setup_result = await self.setup()
        if setup_result.is_failure():
            return setup_result
        
        all_results = {}
        
        # 각 데모 실행
        demos = [
            ("basic_llm", self.demo_basic_llm_usage),
            ("templates", self.demo_template_usage), 
            ("rag", self.demo_rag_usage),
            ("chains", self.demo_chain_workflows),
            ("monitoring", self.demo_monitoring_and_caching)
        ]
        
        for demo_name, demo_func in demos:
            try:
                print(f"\n{'='*50}")
                result = await demo_func()
                
                if result.is_success():
                    all_results[demo_name] = result.unwrap()
                else:
                    all_results[demo_name] = {"error": result.unwrap_error()}
                    print(f"❌ {demo_name} 데모 실패: {result.unwrap_error()}")
                    
            except Exception as e:
                all_results[demo_name] = {"error": str(e)}
                print(f"❌ {demo_name} 데모 예외 발생: {str(e)}")
        
        print(f"\n{'='*50}")
        print("🎉 모든 데모 완료!")
        
        return Success(all_results)


async def main():
    """메인 함수"""
    demo = LLMIntegrationDemo()
    result = await demo.run_all_demos()
    
    if result.is_success():
        print("\n✅ 데모가 성공적으로 완료되었습니다.")
        # 결과를 JSON 파일로 저장 (옵션)
        import json
        with open("llm_demo_results.json", "w", encoding="utf-8") as f:
            json.dump(result.unwrap(), f, ensure_ascii=False, indent=2, default=str)
        print("📁 결과가 'llm_demo_results.json'에 저장되었습니다.")
    else:
        print(f"❌ 데모 실행 실패: {result.unwrap_error()}")


if __name__ == "__main__":
    # 비동기 메인 함수 실행
    asyncio.run(main())