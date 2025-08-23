"""
Reactive Operators

공통 연산자들과 유틸리티 함수들
"""

from typing import TypeVar, List, Callable, Optional
import asyncio

T = TypeVar('T')
R = TypeVar('R')

class Operators:
    """리액티브 연산자 유틸리티"""
    
    @staticmethod
    def combine_latest(*sources) -> 'Flux':
        """여러 소스의 최신 값들을 결합"""
        from .flux import Flux
        
        async def combined():
            # 각 소스의 최신 값을 저장
            latest_values = [None] * len(sources)
            
            # 모든 소스를 동시에 구독
            async def monitor_source(index, source):
                async for value in source:
                    latest_values[index] = value
                    # 모든 소스에서 최소 1개 값이 오면 결합된 값 방출
                    if all(v is not None for v in latest_values):
                        yield tuple(latest_values)
            
            # 모든 소스를 병렬로 모니터링
            tasks = [
                asyncio.create_task(monitor_source(i, source))
                for i, source in enumerate(sources)
            ]
            
            # 첫 번째 완료되는 태스크를 기다림
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        
        return Flux(combined)
    
    @staticmethod 
    def merge(*sources) -> 'Flux':
        """여러 Flux를 하나로 병합"""
        from .flux import Flux
        
        async def merged():
            # 모든 소스를 병렬로 실행
            async def iterate_source(source):
                async for item in source:
                    yield item
            
            # 모든 소스의 코루틴을 생성
            source_coroutines = [iterate_source(source) for source in sources]
            
            # 병렬로 모든 소스에서 값을 받아옴
            for coro in asyncio.as_completed(source_coroutines):
                async for item in await coro:
                    yield item
        
        return Flux(merged)
    
    @staticmethod
    def concat(*sources) -> 'Flux':
        """여러 Flux를 순차적으로 연결"""
        from .flux import Flux
        
        async def concatenated():
            for source in sources:
                async for item in source:
                    yield item
        
        return Flux(concatenated)
    
    @staticmethod
    def zip(*sources) -> 'Flux':
        """여러 소스를 zip으로 결합"""
        from .flux import Flux
        
        async def zipped():
            iterators = [source.__aiter__() for source in sources]
            
            while True:
                try:
                    # 모든 이터레이터에서 동시에 값을 가져옴
                    values = await asyncio.gather(
                        *[it.__anext__() for it in iterators]
                    )
                    yield tuple(values)
                except StopAsyncIteration:
                    break
        
        return Flux(zipped)