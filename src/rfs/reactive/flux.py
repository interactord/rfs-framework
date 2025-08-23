"""
Flux - Reactive Stream for 0-N items

Inspired by Spring Reactor Flux
"""

from typing import TypeVar, Generic, Callable, List, AsyncIterator, Optional, Any, Union
import asyncio
from functools import reduce
import time
from concurrent.futures import ThreadPoolExecutor

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
    
    # ============= 고급 연산자 추가 =============
    
    def parallel(self, parallelism: int = None) -> 'Flux[T]':
        """
        병렬 처리를 위한 Flux
        
        Args:
            parallelism: 병렬 처리 수준 (None이면 CPU 코어 수)
        """
        if parallelism is None:
            parallelism = asyncio.get_event_loop().run_in_executor(None, lambda: None).__sizeof__()
            parallelism = min(parallelism, 8)  # 최대 8개로 제한
        
        async def parallel_source():
            tasks = []
            async for item in self.source():
                # 각 항목을 비동기 태스크로 변환
                task = asyncio.create_task(self._process_item(item))
                tasks.append(task)
                
                # 병렬 처리 수준만큼 태스크가 쌓이면 실행
                if len(tasks) >= parallelism:
                    results = await asyncio.gather(*tasks)
                    for result in results:
                        yield result
                    tasks = []
            
            # 남은 태스크 처리
            if tasks:
                results = await asyncio.gather(*tasks)
                for result in results:
                    yield result
        
        return Flux(parallel_source)
    
    async def _process_item(self, item: T) -> T:
        """항목 처리 (오버라이드 가능)"""
        return item
    
    def window(self, size: Optional[int] = None, duration: Optional[float] = None) -> 'Flux[Flux[T]]':
        """
        윈도우 처리 - 항목들을 시간 또는 개수 기준으로 묶기
        
        Args:
            size: 윈도우 크기
            duration: 시간 윈도우 (초)
        """
        async def windowed():
            if size is not None:
                # 크기 기반 윈도우
                window_items = []
                async for item in self.source():
                    window_items.append(item)
                    if len(window_items) >= size:
                        yield Flux.from_iterable(window_items)
                        window_items = []
                if window_items:
                    yield Flux.from_iterable(window_items)
            
            elif duration is not None:
                # 시간 기반 윈도우
                window_items = []
                start_time = time.time()
                async for item in self.source():
                    window_items.append(item)
                    if time.time() - start_time >= duration:
                        yield Flux.from_iterable(window_items)
                        window_items = []
                        start_time = time.time()
                if window_items:
                    yield Flux.from_iterable(window_items)
            
            else:
                # 전체를 하나의 윈도우로
                all_items = await self.collect_list()
                yield Flux.from_iterable(all_items)
        
        return Flux(windowed)
    
    def on_error_continue(self, error_handler: Callable[[Exception], None] = None) -> 'Flux[T]':
        """
        에러 발생 시 계속 진행
        
        Args:
            error_handler: 에러 처리 함수
        """
        async def error_continued():
            async for item in self.source():
                try:
                    yield item
                except Exception as e:
                    if error_handler:
                        error_handler(e)
                    # 에러 무시하고 계속
                    continue
        
        return Flux(error_continued)
    
    def sample(self, duration: float) -> 'Flux[T]':
        """
        주기적으로 최신 값만 방출 (샘플링)
        
        Args:
            duration: 샘플링 주기 (초)
        """
        async def sampled():
            latest = None
            has_value = False
            last_emit = time.time()
            
            async for item in self.source():
                latest = item
                has_value = True
                
                current_time = time.time()
                if current_time - last_emit >= duration:
                    if has_value:
                        yield latest
                        has_value = False
                    last_emit = current_time
            
            # 마지막 값 방출
            if has_value:
                yield latest
        
        return Flux(sampled)
    
    def throttle(self, elements: int, duration: float) -> 'Flux[T]':
        """
        시간당 방출 개수 제한 (스로틀링)
        
        Args:
            elements: 최대 방출 개수
            duration: 기간 (초)
        """
        async def throttled():
            count = 0
            start_time = time.time()
            
            async for item in self.source():
                current_time = time.time()
                
                # 시간 윈도우 리셋
                if current_time - start_time >= duration:
                    count = 0
                    start_time = current_time
                
                # 제한 내에서만 방출
                if count < elements:
                    yield item
                    count += 1
                else:
                    # 대기
                    wait_time = duration - (current_time - start_time)
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                    count = 0
                    start_time = time.time()
                    yield item
                    count += 1
        
        return Flux(throttled)
    
    def merge_with(self, *others: 'Flux[T]') -> 'Flux[T]':
        """
        여러 Flux를 병합 (동시 방출)
        
        Args:
            *others: 병합할 다른 Flux들
        """
        async def merged():
            # 모든 소스를 비동기 태스크로 변환
            tasks = []
            
            async def collect_from_source(source):
                items = []
                async for item in source():
                    items.append(item)
                return items
            
            # 자신 포함 모든 소스 수집
            tasks.append(collect_from_source(self.source))
            for other in others:
                tasks.append(collect_from_source(other.source))
            
            # 병렬로 모든 소스 수집
            all_results = await asyncio.gather(*tasks)
            
            # 순서대로 방출
            for results in all_results:
                for item in results:
                    yield item
        
        return Flux(merged)
    
    def concat_with(self, *others: 'Flux[T]') -> 'Flux[T]':
        """
        여러 Flux를 연결 (순차 방출)
        
        Args:
            *others: 연결할 다른 Flux들
        """
        async def concatenated():
            # 자신의 항목들 먼저 방출
            async for item in self.source():
                yield item
            
            # 다른 Flux들의 항목 순차적으로 방출
            for other in others:
                async for item in other.source():
                    yield item
        
        return Flux(concatenated)
    
    def on_error_return(self, default_value: T) -> 'Flux[T]':
        """
        에러 발생 시 기본값 반환
        
        Args:
            default_value: 에러 시 반환할 기본값
        """
        async def error_handled():
            try:
                async for item in self.source():
                    yield item
            except Exception:
                yield default_value
        
        return Flux(error_handled)
    
    def retry(self, max_attempts: int = 3) -> 'Flux[T]':
        """
        에러 발생 시 재시도
        
        Args:
            max_attempts: 최대 재시도 횟수
        """
        async def retried():
            attempts = 0
            while attempts < max_attempts:
                try:
                    async for item in self.source():
                        yield item
                    break  # 성공하면 종료
                except Exception as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        raise e
                    # 재시도 전 대기
                    await asyncio.sleep(0.1 * attempts)
        
        return Flux(retried)
    
    def __aiter__(self):
        """비동기 반복자 지원"""
        return self.source()
    
    def __repr__(self) -> str:
        return f"Flux({self.__class__.__name__})"