#!/usr/bin/env python3
"""
RFS Framework LLM 통합 간단한 사용 예제

기본적인 LLM 사용법을 보여주는 간단한 예제입니다.
"""

import asyncio
import os
from rfs.core.result import Result, Success, Failure


async def simple_openai_example():
    """OpenAI 간단 사용 예제"""
    print("🤖 OpenAI 간단 사용 예제")
    
    try:
        from rfs.llm import OpenAIProvider, LLMManager
        
        # API 키 확인
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
            return
        
        # 1. 직접 제공자 사용
        provider = OpenAIProvider(api_key=api_key)
        
        result = await provider.generate(
            prompt="Python에서 함수형 프로그래밍의 핵심 개념 3가지를 간단히 설명해주세요.",
            model="gpt-3.5-turbo",
            max_tokens=200
        )
        
        if result.is_success():
            response = result.unwrap()
            print(f"응답: {response['response']}")
            print(f"사용된 토큰: {response.get('usage', {}).get('total_tokens', 'N/A')}")
        else:
            print(f"오류: {result.unwrap_error()}")
        
        # 2. LLM Manager 사용
        print("\n🎯 LLM Manager를 통한 사용")
        
        manager = LLMManager()
        await manager.register_provider("openai", provider)
        
        result2 = await manager.generate(
            provider="openai",
            prompt="FastAPI의 장점을 3가지 나열해주세요.",
            model="gpt-3.5-turbo",
            max_tokens=150
        )
        
        if result2.is_success():
            response2 = result2.unwrap()
            print(f"Manager 응답: {response2['response']}")
        
    except ImportError:
        print("❌ OpenAI 라이브러리가 설치되지 않았습니다: pip install openai")
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")


async def simple_template_example():
    """템플릿 간단 사용 예제"""
    print("\n📝 템플릿 간단 사용 예제")
    
    try:
        from rfs.llm import PromptTemplateManager, LLMManager, OpenAIProvider
        
        # API 키 확인
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
            return
        
        # 설정
        manager = LLMManager()
        provider = OpenAIProvider(api_key=api_key)
        await manager.register_provider("openai", provider)
        
        template_manager = PromptTemplateManager()
        await template_manager.register_common_templates()
        
        # 코드 리뷰 템플릿 사용
        code_sample = '''
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
'''
        
        result = await template_manager.render_and_generate(
            template_name="code_review",
            provider="openai",
            manager=manager,
            variables={
                "code": code_sample,
                "language": "Python",
                "focus_areas": ["성능", "메모리 사용"]
            },
            model="gpt-3.5-turbo"
        )
        
        if result.is_success():
            review = result.unwrap()
            print(f"코드 리뷰 결과:\n{review['response']}")
        else:
            print(f"오류: {result.unwrap_error()}")
            
    except ImportError:
        print("❌ 필요한 라이브러리가 설치되지 않았습니다: pip install openai jinja2")
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")


async def simple_chain_example():
    """체인 간단 사용 예제"""
    print("\n🔗 체인 간단 사용 예제")
    
    try:
        from rfs.llm import LLMManager, OpenAIProvider
        from rfs.llm.chains.base import SimpleLLMChain
        from rfs.llm.chains.sequential import SequentialChain
        
        # API 키 확인
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
            return
        
        # 설정
        manager = LLMManager()
        provider = OpenAIProvider(api_key=api_key)
        await manager.register_provider("openai", provider)
        
        # 체인 생성
        brainstorm_chain = SimpleLLMChain(
            manager=manager,
            provider="openai",
            model="gpt-3.5-turbo",
            name="아이디어_도출"
        )
        
        refine_chain = SimpleLLMChain(
            manager=manager,
            provider="openai",
            model="gpt-3.5-turbo",
            name="아이디어_정제"
        )
        
        # 순차 체인 구성
        sequential_chain = SequentialChain([brainstorm_chain, refine_chain])
        
        # 실행
        result = await sequential_chain.run({
            "topic": "온라인 학습 플랫폼",
            "prompt": "온라인 학습 플랫폼의 핵심 기능 3가지를 제안해주세요."
        })
        
        if result.is_success():
            output = result.unwrap()
            print("체인 실행 결과:")
            print(f"최종 응답: {output.get('response', 'N/A')}")
            
            # 실행 히스토리 확인
            execution_info = output.get('_sequential_execution', {})
            print(f"실행된 체인 수: {execution_info.get('chain_count', 0)}")
        else:
            print(f"오류: {result.unwrap_error()}")
            
    except ImportError:
        print("❌ 필요한 라이브러리가 설치되지 않았습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")


async def simple_rag_example():
    """RAG 간단 사용 예제"""
    print("\n📚 RAG 간단 사용 예제")
    
    try:
        from rfs.llm import LLMManager, OpenAIProvider
        from rfs.llm.rag.chroma import ChromaVectorStore
        from rfs.llm.rag.engine import RAGEngine
        
        # API 키 확인
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
            return
        
        # 설정
        manager = LLMManager()
        provider = OpenAIProvider(api_key=api_key)
        await manager.register_provider("openai", provider)
        
        # 벡터 스토어와 RAG 엔진
        vector_store = ChromaVectorStore(
            collection_name="simple_demo",
            persist_directory="./simple_chroma_data"
        )
        
        rag_engine = RAGEngine(
            vector_store=vector_store,
            llm_manager=manager
        )
        
        # 샘플 문서 추가
        documents = [
            "FastAPI는 현대적인 Python 웹 프레임워크입니다. 빠른 성능과 자동 문서 생성이 특징입니다.",
            "Django는 배터리 포함 철학의 Python 웹 프레임워크입니다. ORM과 관리자 인터페이스를 제공합니다.",
            "Flask는 마이크로 웹 프레임워크입니다. 최소한의 기능으로 시작하여 확장 가능합니다."
        ]
        
        for i, doc in enumerate(documents):
            await rag_engine.add_to_knowledge_base(
                text=doc,
                doc_id=f"doc_{i}",
                metadata={"source": f"document_{i}"}
            )
        
        print("✅ 문서 추가 완료")
        
        # 질문하기
        question = "FastAPI와 Django의 차이점은 무엇인가요?"
        
        result = await rag_engine.generate_answer(
            question=question,
            provider="openai",
            model="gpt-3.5-turbo",
            template="basic"
        )
        
        if result.is_success():
            answer_data = result.unwrap()
            print(f"\n질문: {question}")
            print(f"답변: {answer_data['answer']}")
            print(f"참조 문서 수: {len(answer_data.get('sources', []))}")
        else:
            print(f"오류: {result.unwrap_error()}")
            
    except ImportError:
        print("❌ 필요한 라이브러리가 설치되지 않았습니다: pip install openai chromadb")
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")


async def simple_monitoring_example():
    """모니터링 간단 사용 예제"""
    print("\n📊 모니터링 간단 사용 예제")
    
    try:
        from rfs.llm import LLMManager, OpenAIProvider
        from rfs.llm.monitoring import get_metrics_collector, get_response_cache
        
        # API 키 확인
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
            return
        
        # 설정
        manager = LLMManager()
        provider = OpenAIProvider(api_key=api_key)
        await manager.register_provider("openai", provider)
        
        # 모니터링 시스템
        metrics_collector = get_metrics_collector()
        response_cache = get_response_cache()
        
        # 몇 번의 LLM 호출
        prompts = [
            "Hello World",
            "Python 함수형 프로그래밍이란?",
            "FastAPI 사용법"
        ]
        
        print("LLM 호출 중...")
        for prompt in prompts:
            result = await manager.generate(
                provider="openai",
                prompt=prompt,
                model="gpt-3.5-turbo",
                max_tokens=50
            )
            
            if result.is_success():
                print(f"✅ '{prompt[:20]}...' 완료")
            else:
                print(f"❌ '{prompt[:20]}...' 실패")
        
        # 메트릭 확인
        metrics_summary = metrics_collector.get_summary()
        if metrics_summary.is_success():
            summary = metrics_summary.unwrap()
            print(f"\n📊 메트릭 요약:")
            print(f"  - 총 호출 수: {summary.total_calls}")
            print(f"  - 성공률: {summary.success_rate:.1f}%")
            print(f"  - 평균 응답 시간: {summary.avg_duration_ms:.1f}ms")
            print(f"  - 총 토큰 사용: {summary.total_tokens}")
            print(f"  - 총 비용: ${summary.total_cost:.4f}")
        
        # 캐시 통계
        cache_stats = await response_cache.get_cache_stats()
        if cache_stats.is_success():
            stats = cache_stats.unwrap()
            print(f"\n💾 캐시 통계:")
            print(f"  - 히트: {stats['hits']}")
            print(f"  - 미스: {stats['misses']}")
            print(f"  - 히트율: {stats['hit_rate']:.1f}%")
            print(f"  - 캐시된 키 수: {stats['total_keys']}")
        
    except ImportError:
        print("❌ 필요한 라이브러리가 설치되지 않았습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")


async def main():
    """모든 간단 예제 실행"""
    print("🚀 RFS Framework LLM 간단 사용 예제들\n")
    
    examples = [
        ("OpenAI 기본 사용", simple_openai_example),
        ("템플릿 사용", simple_template_example),
        ("체인 워크플로우", simple_chain_example),
        ("RAG 시스템", simple_rag_example),
        ("모니터링", simple_monitoring_example),
    ]
    
    for name, example_func in examples:
        try:
            print(f"\n{'='*60}")
            print(f"📖 {name}")
            print('='*60)
            await example_func()
            
        except Exception as e:
            print(f"❌ {name} 예제 실행 실패: {str(e)}")
    
    print(f"\n{'='*60}")
    print("🎉 모든 예제 완료!")
    print("\n💡 더 자세한 예제는 'llm_integration_example.py'를 참조하세요.")


if __name__ == "__main__":
    # 환경변수 안내
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  환경변수 설정 안내:")
        print("   export OPENAI_API_KEY='your-api-key'")
        print("   export ANTHROPIC_API_KEY='your-api-key'  # 옵션")
        print("\n📦 필요한 패키지 설치:")
        print("   pip install openai anthropic chromadb jinja2")
        print("\n" + "="*60)
    
    asyncio.run(main())