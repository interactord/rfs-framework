"""
Flux - Reactive Stream for 0-N items

Inspired by Spring Reactor Flux
"""

from typing import TypeVar, Generic, Callable, List, AsyncIterator, Optional, Any
import asyncio
from functools import reduce

T = TypeVar('T')
R = TypeVar('R')

class Flux(Generic[T]):
    """
    0개 이상의 데이터를 비동기로 방출하는 리액티브 스트림
    
    Spring Reactor의 Flux를 Python으로 구현
    """
    
    def __init__(self, source: Callable[[], AsyncIterator[T]] = None):
        self.source = source or self._empty_source
    
    @staticmethod
    async def _empty_source():
        """빈 소스"""
        return
        yield  # Make it a generator
    
    @staticmethod
    def just(*items: T) -> 'Flux[T]':
        """고정 값들로 Flux 생성"""
        async def generator():
            for item in items:
                yield item
        return Flux(generator)
    
    @staticmethod
    def from_iterable(items: List[T]) -> 'Flux[T]':
        """Iterable로부터 Flux 생성"""
        async def generator():
            for item in items:
                yield item
        return Flux(generator)
    
    @staticmethod
    def range(start: int, count: int) -> 'Flux[int]':
        """숫자 범위로 Flux 생성"""
        async def generator():
            for i in range(start, start + count):
                yield i
        return Flux(generator)
    
    @staticmethod
    def interval(period: float) -> 'Flux[int]':
        """주기적으로 숫자를 방출하는 Flux"""
        async def generator():
            counter = 0
            while True:
                yield counter
                counter += 1
                await asyncio.sleep(period)
        return Flux(generator)
    
    def map(self, mapper: Callable[[T], R]) -> 'Flux[R]':
        """각 항목을 변환"""
        async def mapped():
            async for item in self.source():
                yield mapper(item)
        return Flux(mapped)
    
    def filter(self, predicate: Callable[[T], bool]) -> 'Flux[T]':
        """조건에 맞는 항목만 통과"""
        async def filtered():
            async for item in self.source():
                if predicate(item):
                    yield item
        return Flux(filtered)
    
    def flat_map(self, mapper: Callable[[T], 'Flux[R]']) -> 'Flux[R]':
        """각 항목을 Flux로 변환 후 평탄화"""
        async def flat_mapped():
            async for item in self.source():
                inner_flux = mapper(item)
                async for inner_item in inner_flux.source():
                    yield inner_item
        return Flux(flat_mapped)
    
    def take(self, count: int) -> 'Flux[T]':
        """처음 N개 항목만 가져오기"""
        async def taken():
            counter = 0
            async for item in self.source():
                if counter >= count:
                    break
                yield item
                counter += 1
        return Flux(taken)
    
    def skip(self, count: int) -> 'Flux[T]':
        """처음 N개 항목 건너뛰기"""
        async def skipped():
            counter = 0
            async for item in self.source():
                if counter < count:
                    counter += 1
                    continue
                yield item
        return Flux(skipped)
    
    def distinct(self) -> 'Flux[T]':
        """중복 제거"""
        async def distinct_items():
            seen = set()
            async for item in self.source():
                if item not in seen:
                    seen.add(item)
                    yield item
        return Flux(distinct_items)
    
    def reduce(self, initial: R, reducer: Callable[[R, T], R]) -> 'Flux[R]':
        """모든 항목을 단일 값으로 축소"""
        async def reduced():
            accumulator = initial
            async for item in self.source():
                accumulator = reducer(accumulator, item)
            yield accumulator
        return Flux(reduced)
    
    def buffer(self, size: int) -> 'Flux[List[T]]':
        """항목들을 버퍼 크기만큼 묶기"""
        async def buffered():
            buffer = []
            async for item in self.source():
                buffer.append(item)
                if len(buffer) >= size:
                    yield buffer
                    buffer = []
            if buffer:  # 남은 항목들
                yield buffer
        return Flux(buffered)
    
    def zip_with(self, other: 'Flux[R]') -> 'Flux[tuple[T, R]]':
        """다른 Flux와 zip으로 결합"""
        async def zipped():
            async for item1, item2 in self._zip_async_iterators(
                self.source(), other.source()
            ):
                yield (item1, item2)
        return Flux(zipped)
    
    @staticmethod
    async def _zip_async_iterators(iter1: AsyncIterator[T], iter2: AsyncIterator[R]):
        """두 비동기 반복자를 zip으로 결합"""
        try:
            while True:
                item1 = await iter1.__anext__()
                item2 = await iter2.__anext__()
                yield (item1, item2)
        except StopAsyncIteration:
            pass
    
    async def collect_list(self) -> List[T]:
        """모든 항목을 리스트로 수집"""
        result = []
        async for item in self.source():
            result.append(item)
        return result
    
    async def collect_set(self) -> set[T]:
        """모든 항목을 셋으로 수집"""
        result = set()
        async for item in self.source():
            result.add(item)
        return result
    
    async def count(self) -> int:
        """항목 개수 계산"""
        count = 0
        async for _ in self.source():
            count += 1
        return count
    
    async def any(self, predicate: Callable[[T], bool]) -> bool:
        """조건을 만족하는 항목이 있는지 확인"""
        async for item in self.source():
            if predicate(item):
                return True
        return False
    
    async def all(self, predicate: Callable[[T], bool]) -> bool:
        """모든 항목이 조건을 만족하는지 확인"""
        async for item in self.source():
            if not predicate(item):
                return False
        return True
    
    async def subscribe(self, 
                        on_next: Callable[[T], None] = None,
                        on_error: Callable[[Exception], None] = None,
                        on_complete: Callable[[], None] = None) -> None:
        """
        스트림 구독
        
        Args:
            on_next: 각 항목에 대한 콜백
            on_error: 에러 발생 시 콜백
            on_complete: 완료 시 콜백
        """
        try:
            async for item in self.source():
                if on_next:
                    on_next(item)
            if on_complete:
                on_complete()
        except Exception as e:
            if on_error:
                on_error(e)
            else:
                raise
    
    def __aiter__(self):
        """비동기 반복자 지원"""
        return self.source()
    
    def __repr__(self) -> str:
        return f"Flux({self.__class__.__name__})"