"""
Flux - Reactive Stream for 0-N items

Inspired by Spring Reactor Flux
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncIterator, Callable, Generic, List, Optional, Set, TypeVar, Union

# Import from HOF library
from ..hof.collections import fold_left
from ..hof.decorators import throttle as throttle_decorator

T = TypeVar("T")
R = TypeVar("R")


class Flux(Generic[T]):
    """
    0개 이상의 데이터를 비동기로 방출하는 리액티브 스트림

    Spring Reactor의 Flux를 Python으로 구현
    """

    def __init__(self, source: Optional[Callable[[], AsyncIterator[T]]] = None) -> None:
        self.source = source or self._empty_source

    @staticmethod
    async def _empty_source():
        """빈 소스"""
        return
        yield

    @staticmethod
    def just(*items: T) -> "Flux[T]":
        """고정 값들로 Flux 생성"""

        async def generator():
            for item in items:
                yield item

        return Flux(generator)

    @staticmethod
    def from_iterable(items: List[T]) -> "Flux[T]":
        """Iterable로부터 Flux 생성"""

        async def generator():
            for item in items:
                yield item

        return Flux(generator)

    @staticmethod
    def range(start: int, count: int) -> "Flux[int]":
        """숫자 범위로 Flux 생성"""

        async def generator():
            for i in range(start, start + count):
                yield i

        return Flux(generator)

    @staticmethod
    def empty() -> "Flux[T]":
        """빈 Flux 생성"""

        async def generator():
            return
            yield  # Make it a generator

        return Flux(generator)

    @staticmethod
    def interval(period: float) -> "Flux[int]":
        """주기적으로 숫자를 방출하는 Flux"""

        async def generator():
            counter = 0
            while True:
                yield counter
                counter = counter + 1
                await asyncio.sleep(period)

        return Flux(generator)

    def map(self, mapper: Callable[[T], R]) -> "Flux[R]":
        """각 항목을 변환"""

        async def mapped():
            async for item in self.source():
                yield mapper(item)

        return Flux(mapped)

    def filter(self, predicate: Callable[[T], bool]) -> "Flux[T]":
        """조건에 맞는 항목만 통과"""

        async def filtered():
            async for item in self.source():
                if predicate(item):
                    yield item

        return Flux(filtered)

    def flat_map(self, mapper: Callable[[T], "Flux[R]"]) -> "Flux[R]":
        """각 항목을 Flux로 변환 후 평탄화"""

        async def flat_mapped():
            async for item in self.source():
                inner_flux = mapper(item)
                async for inner_item in inner_flux.source():
                    yield inner_item

        return Flux(flat_mapped)

    def take(self, count: int) -> "Flux[T]":
        """처음 N개 항목만 가져오기"""

        async def taken():
            counter = 0
            async for item in self.source():
                if counter >= count:
                    break
                yield item
                counter = counter + 1

        return Flux(taken)

    def skip(self, count: int) -> "Flux[T]":
        """처음 N개 항목 건너뛰기"""

        async def skipped():
            counter = 0
            async for item in self.source():
                if counter < count:
                    counter = counter + 1
                    continue
                yield item

        return Flux(skipped)

    def distinct(self) -> "Flux[T]":
        """중복 제거"""

        async def distinct_items():
            seen: Set[Any] = set()
            async for item in self.source():
                if item not in seen:
                    seen.add(item)
                    yield item

        return Flux(distinct_items)

    def reduce(self, initial: R, reducer: Callable[[R, T], R]) -> "Flux[R]":
        """모든 항목을 단일 값으로 축소"""

        async def reduced():
            accumulator = initial
            async for item in self.source():
                accumulator = reducer(accumulator, item)
            yield accumulator

        return Flux(reduced)

    def buffer(self, size: int) -> "Flux[List[T]]":
        """항목들을 버퍼 크기만큼 묶기"""

        async def buffered():
            buffer = []
            async for item in self.source():
                buffer = buffer + [item]
                if len(buffer) >= size:
                    yield buffer
                    buffer = []
            if buffer:
                yield buffer

        return Flux(buffered)

    def zip_with(self, other: "Flux[R]") -> "Flux[tuple[T, R]]":
        """다른 Flux와 zip으로 결합"""

        async def zipped():
            async for item1, item2 in Flux._zip_async_iterators(
                self.source(), other.source()
            ):
                yield (item1, item2)

        return Flux(zipped)

    def zip(self, other: "Flux[R]") -> "Flux[tuple[T, R]]":
        """다른 Flux와 zip으로 결합 (zip_with의 별칭)"""

        # zip_with를 직접 호출하는 대신 동일한 로직을 재구현
        async def zipped():
            async for item1, item2 in Flux._zip_async_iterators(
                self.source(), other.source()
            ):
                yield (item1, item2)

        return Flux(zipped)

    @staticmethod
    def zip_all(*fluxes: "Flux") -> "Flux[tuple]":
        """여러 Flux를 zip으로 결합"""

        async def generator():
            iterators = [flux.source() for flux in fluxes]
            try:
                while True:
                    items = []
                    for iterator in iterators:
                        items.append(await iterator.__anext__())
                    yield tuple(items)
            except StopAsyncIteration:
                pass

        return Flux(generator)

    @staticmethod
    def merge(*fluxes: "Flux") -> "Flux":
        """여러 Flux를 병합"""

        async def generator():
            tasks = []
            queues = []

            for flux in fluxes:
                queue = asyncio.Queue()
                queues.append(queue)

                async def consume(flux, queue):
                    async for item in flux.source():
                        await queue.put(item)
                    await queue.put(None)  # End marker

                task = asyncio.create_task(consume(flux, queue))
                tasks.append(task)

            active_queues = len(queues)
            while active_queues > 0:
                for queue in queues:
                    try:
                        item = queue.get_nowait()
                        if item is None:
                            active_queues -= 1
                        else:
                            yield item
                    except asyncio.QueueEmpty:
                        await asyncio.sleep(0.01)

        return Flux(generator)

    @staticmethod
    def concat(*fluxes: "Flux") -> "Flux":
        """여러 Flux를 순차적으로 연결"""

        async def generator():
            for flux in fluxes:
                async for item in flux.source():
                    yield item

        return Flux(generator)

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
        result: List[T] = []
        async for item in self.source():
            result = result + [item]
        return result

    async def collect_set(self) -> set[T]:
        """모든 항목을 셋으로 수집"""
        result: Set[T] = set()
        async for item in self.source():
            result.add(item)
        return result

    async def count(self) -> int:
        """항목 개수 계산"""
        count = 0
        async for _ in self.source():
            count = count + 1
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

    async def subscribe(
        self,
        on_next: Optional[Callable[[T], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_complete: Optional[Callable[[], None]] = None,
    ) -> None:
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

    def parallel(self, parallelism: int = None) -> "Flux[T]":
        """
        병렬 처리를 위한 Flux

        Args:
            parallelism: 병렬 처리 수준 (None이면 CPU 코어 수)
        """
        if parallelism is None:
            parallelism = (
                asyncio.get_event_loop()
                .run_in_executor(None, lambda: None)
                .__sizeof__()
            )
            parallelism = min(parallelism, 8)

        async def parallel_source():
            tasks = []
            async for item in self.source():
                task = asyncio.create_task(self._process_item(item))
                tasks = tasks + [task]
                if len(tasks) >= parallelism:
                    results = await asyncio.gather(*tasks)
                    for result in results:
                        yield result
                    tasks = []
            if tasks:
                results = await asyncio.gather(*tasks)
                for result in results:
                    yield result

        return Flux(parallel_source)

    async def _process_item(self, item: T) -> T:
        """항목 처리 (오버라이드 가능)"""
        return item

    def window(self, size=None, duration=None) -> "Flux[Flux[T]]":
        """
        윈도우 처리 - 항목들을 시간 또는 개수 기준으로 묶기

        Args:
            size: 윈도우 크기
            duration: 시간 윈도우 (초)
        """

        async def windowed():
            if size is not None:
                window_items = []
                async for item in self.source():
                    window_items = window_items + [item]
                    if len(window_items) >= size:
                        yield Flux.from_iterable(window_items)
                        window_items = []
                if window_items:
                    yield Flux.from_iterable(window_items)
            elif duration is not None:
                window_items = []
                start_time = time.time()
                async for item in self.source():
                    window_items = window_items + [item]
                    if time.time() - start_time >= duration:
                        yield Flux.from_iterable(window_items)
                        window_items = []
                        start_time = time.time()
                if window_items:
                    yield Flux.from_iterable(window_items)
            else:
                all_items = await self.collect_list()
                yield Flux.from_iterable(all_items)

        return Flux(windowed)

    def on_error_continue(
        self, error_handler: Callable[[Exception], None] = None
    ) -> "Flux[T]":
        """
        에러 발생 시 계속 진행

        Args:
            error_handler: 에러 처리 함수
        """

        async def error_continued():
            source_iter = self.source().__aiter__()
            while True:
                try:
                    item = await source_iter.__anext__()
                    yield item
                except StopAsyncIteration:
                    break
                except Exception as e:
                    if error_handler:
                        error_handler(e)
                    continue

        return Flux(error_continued)

    def sample(self, duration: float) -> "Flux[T]":
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
            if has_value:
                yield latest

        return Flux(sampled)

    def throttle(self, elements: int, duration: float) -> "Flux[T]":
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
                if current_time - start_time >= duration:
                    count = 0
                    start_time = current_time
                if count < elements:
                    yield item
                    count = count + 1
                else:
                    wait_time = duration - (current_time - start_time)
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                    count = 0
                    start_time = time.time()
                    yield item
                    count = count + 1

        return Flux(throttled)

    def merge_with(self, *others: "Flux[T]") -> "Flux[T]":
        """
        여러 Flux를 병합 (동시 방출)

        Args:
            *others: 병합할 다른 Flux들
        """

        async def merged():
            tasks = []

            async def collect_from_source(source):
                items = []
                async for item in source():
                    items = items + [item]
                return items

            tasks = tasks + [collect_from_source(self.source)]
            tasks = tasks + list(
                map(lambda other: collect_from_source(other.source), others)
            )
            all_results = await asyncio.gather(*tasks)
            for results in all_results:
                for item in results:
                    yield item

        return Flux(merged)

    def concat_with(self, *others: "Flux[T]") -> "Flux[T]":
        """
        여러 Flux를 연결 (순차 방출)

        Args:
            *others: 연결할 다른 Flux들
        """

        async def concatenated():
            async for item in self.source():
                yield item
            for other in others:
                async for item in other.source():
                    yield item

        return Flux(concatenated)

    def on_error_return(self, default_value: T) -> "Flux[T]":
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

    def retry(self, max_attempts=3) -> "Flux[T]":
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
                    break
                except Exception as e:
                    attempts = attempts + 1
                    if attempts >= max_attempts:
                        raise e
                    await asyncio.sleep(0.1 * attempts)

        return Flux(retried)

    def __aiter__(self):
        """비동기 반복자 지원"""
        return self.source()

    def __repr__(self) -> str:
        return f"Flux({self.__class__.__name__})"
