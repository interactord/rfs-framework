"""
Reactive Operators

공통 연산자들과 유틸리티 함수들
"""

import asyncio
from typing import Callable, List, Optional, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class Operators:
    """리액티브 연산자 유틸리티"""

    @staticmethod
    def combine_latest(*sources) -> "Flux":
        """여러 소스의 최신 값들을 결합"""
        from .flux import Flux

        async def combined():
            latest_values = [None] * len(sources)

            async def monitor_source(index, source):
                async for value in source:
                    latest_values[index] = {index: value}
                    if all((v is not None for v in latest_values)):
                        yield tuple(latest_values)

            tasks = [
                asyncio.create_task(monitor_source(i, source))
                for i, source in enumerate(sources)
            ]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        return Flux(combined)

    @staticmethod
    def merge(*sources) -> "Flux":
        """여러 Flux를 하나로 병합"""
        from .flux import Flux

        async def merged():

            async def iterate_source(source):
                async for item in source:
                    yield item

            source_coroutines = [iterate_source(source) for source in sources]
            for coro in asyncio.as_completed(source_coroutines):
                async for item in await coro:
                    yield item

        return Flux(merged)

    @staticmethod
    def concat(*sources) -> "Flux":
        """여러 Flux를 순차적으로 연결"""
        from .flux import Flux

        async def concatenated():
            for source in sources:
                async for item in source:
                    yield item

        return Flux(concatenated)

    @staticmethod
    def zip(*sources) -> "Flux":
        """여러 소스를 zip으로 결합"""
        from .flux import Flux

        async def zipped():
            iterators = [source.__aiter__() for source in sources]
            while True:
                try:
                    values = await asyncio.gather(*[it.__anext__() for it in iterators])
                    yield tuple(values)
                except StopAsyncIteration:
                    break

        return Flux(zipped)
