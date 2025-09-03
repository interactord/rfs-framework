"""
RFS Readable HOF Processing System

배치 데이터 처리 및 변환 시스템을 구현합니다.
복잡한 중첩 루프를 읽기 쉬운 체이닝 패턴으로 변환하여
데이터 파이프라인을 구성할 수 있게 합니다.

사용 예:
    results = (extract_from(batch_results)
               .flatten_batches()
               .successful_only()
               .extract_content()
               .filter_by(lambda x: len(x.strip()) > min_length)
               .transform_to(create_item)
               .collect())
"""

from typing import Any, Awaitable, Callable, Iterable, List, Optional, TypeVar, Union
from dataclasses import dataclass
from functools import reduce

from .base import FluentBase, ChainableResult, success, failure
from .types import ProcessorFunction, PredicateFunction, TransformFunction, T, U

class DataExtractor(FluentBase[Any]):
    """
    데이터 추출을 위한 플루언트 인터페이스
    
    복잡한 데이터 구조로부터 필요한 정보를 체이닝 방식으로 추출합니다.
    """
    
    def flatten_batches(self) -> 'DataProcessor[List[Any]]':
        """
        배치들을 평면화합니다.
        
        Returns:
            평면화된 데이터를 가진 DataProcessor
        """
        try:
            if not hasattr(self._value, '__iter__'):
                return DataProcessor([])
            
            flattened = []
            for batch in self._value:
                if hasattr(batch, 'results'):
                    # batch.results가 있는 경우
                    flattened.extend(batch.results)
                elif hasattr(batch, '__iter__') and not isinstance(batch, str):
                    # 이터러블인 경우
                    flattened.extend(batch)
                else:
                    # 단일 아이템인 경우
                    flattened.append(batch)
            
            return DataProcessor(flattened)
        except Exception as e:
            # 오류 발생 시 빈 리스트로 처리
            return DataProcessor([])
    
    def flatten_items(self) -> 'DataProcessor[List[Any]]':
        """
        중첩된 아이템들을 평면화합니다.
        
        Returns:
            평면화된 아이템들을 가진 DataProcessor
        """
        try:
            flattened = []
            
            def flatten_recursive(items):
                for item in items:
                    if hasattr(item, '__iter__') and not isinstance(item, (str, bytes, dict)):
                        flatten_recursive(item)
                    else:
                        flattened.append(item)
            
            if hasattr(self._value, '__iter__'):
                flatten_recursive(self._value)
            else:
                flattened.append(self._value)
            
            return DataProcessor(flattened)
        except Exception:
            return DataProcessor([])
    
    def extract_field(self, field_name: str) -> 'DataProcessor[List[Any]]':
        """
        특정 필드를 추출합니다.
        
        Args:
            field_name: 추출할 필드명
            
        Returns:
            추출된 필드값들을 가진 DataProcessor
        """
        extracted = []
        
        try:
            if hasattr(self._value, '__iter__') and not isinstance(self._value, str):
                for item in self._value:
                    if hasattr(item, field_name):
                        value = getattr(item, field_name)
                        extracted.append(value)
                    elif isinstance(item, dict) and field_name in item:
                        extracted.append(item[field_name])
        except Exception:
            pass
        
        return DataProcessor(extracted)
    
    def extract_nested_field(self, field_path: str, separator: str = '.') -> 'DataProcessor[List[Any]]':
        """
        중첩된 필드를 추출합니다 (예: "user.profile.name").
        
        Args:
            field_path: 점으로 구분된 필드 경로
            separator: 필드 구분자 (기본값: '.')
            
        Returns:
            추출된 값들을 가진 DataProcessor
        """
        field_parts = field_path.split(separator)
        extracted = []
        
        try:
            if hasattr(self._value, '__iter__') and not isinstance(self._value, str):
                for item in self._value:
                    current = item
                    
                    # 필드 경로를 따라 탐색
                    for field_part in field_parts:
                        if hasattr(current, field_part):
                            current = getattr(current, field_part)
                        elif isinstance(current, dict) and field_part in current:
                            current = current[field_part]
                        else:
                            current = None
                            break
                    
                    if current is not None:
                        extracted.append(current)
        except Exception:
            pass
        
        return DataProcessor(extracted)

@dataclass
class DataProcessor(FluentBase[List[T]]):
    """
    데이터 처리를 위한 플루언트 인터페이스
    
    데이터 리스트에 대해 필터링, 변환, 그룹화 등의 작업을 체이닝으로 수행합니다.
    """
    
    def successful_only(self) -> 'DataProcessor[List[T]]':
        """
        성공한 결과만 필터링합니다.
        
        Returns:
            성공한 결과들만 가진 DataProcessor
        """
        filtered = []
        
        for item in self._value:
            # is_success 메서드가 있는 경우
            if hasattr(item, 'is_success') and callable(item.is_success):
                if item.is_success():
                    filtered.append(item)
            # success 필드가 있는 경우
            elif hasattr(item, 'success') and item.success:
                filtered.append(item)
            # 딕셔너리에서 success 키가 있는 경우
            elif isinstance(item, dict) and item.get('success', False):
                filtered.append(item)
            # error나 실패 표시가 없는 경우
            elif not self._is_error_item(item):
                filtered.append(item)
        
        return DataProcessor(filtered)
    
    def failed_only(self) -> 'DataProcessor[List[T]]':
        """
        실패한 결과만 필터링합니다.
        
        Returns:
            실패한 결과들만 가진 DataProcessor
        """
        filtered = []
        
        for item in self._value:
            # is_failure 메서드가 있는 경우
            if hasattr(item, 'is_failure') and callable(item.is_failure):
                if item.is_failure():
                    filtered.append(item)
            # is_success가 있지만 실패인 경우
            elif hasattr(item, 'is_success') and callable(item.is_success):
                if not item.is_success():
                    filtered.append(item)
            # error 표시가 있는 경우
            elif self._is_error_item(item):
                filtered.append(item)
        
        return DataProcessor(filtered)
    
    def extract_content(self) -> 'DataProcessor[List[Any]]':
        """
        컨텐츠를 추출합니다.
        
        Returns:
            추출된 컨텐츠들을 가진 DataProcessor
        """
        contents = []
        
        for item in self._value:
            content = None
            
            # content 필드 확인
            if hasattr(item, 'content'):
                content = item.content
            elif isinstance(item, dict) and 'content' in item:
                content = item['content']
            # data 필드 확인
            elif hasattr(item, 'data'):
                content = item.data
            elif isinstance(item, dict) and 'data' in item:
                content = item['data']
            # value 필드 확인
            elif hasattr(item, 'value'):
                content = item.value
            elif isinstance(item, dict) and 'value' in item:
                content = item['value']
            else:
                content = item
            
            if content is not None:
                contents.append(content)
        
        return DataProcessor(contents)
    
    def flatten_text_chunks(self) -> 'DataProcessor[List[str]]':
        """
        텍스트 청크들을 평면화합니다.
        
        Returns:
            평면화된 텍스트 청크들을 가진 DataProcessor
        """
        chunks = []
        
        for item in self._value:
            if isinstance(item, str):
                chunks.append(item)
            elif hasattr(item, 'content') and hasattr(item.content, '__iter__'):
                # content가 이터러블인 경우
                for chunk in item.content:
                    if isinstance(chunk, str):
                        chunks.append(chunk)
                    else:
                        chunks.append(str(chunk))
            elif hasattr(item, '__iter__') and not isinstance(item, (str, dict)):
                # 아이템 자체가 이터러블인 경우
                for chunk in item:
                    if isinstance(chunk, str):
                        chunks.append(chunk)
                    else:
                        chunks.append(str(chunk))
            else:
                chunks.append(str(item))
        
        return DataProcessor(chunks)
    
    def filter_by(self, predicate: PredicateFunction) -> 'DataProcessor[List[T]]':
        """
        조건에 따라 필터링합니다.
        
        Args:
            predicate: 필터링 조건 함수
            
        Returns:
            필터링된 데이터를 가진 DataProcessor
        """
        try:
            filtered = [item for item in self._value if predicate(item)]
            return DataProcessor(filtered)
        except Exception:
            # 필터링 중 오류 발생 시 빈 리스트 반환
            return DataProcessor([])
    
    def filter_not_empty(self) -> 'DataProcessor[List[T]]':
        """
        비어있지 않은 항목들만 필터링합니다.
        
        Returns:
            비어있지 않은 항목들을 가진 DataProcessor
        """
        def not_empty(item):
            if item is None:
                return False
            if isinstance(item, str):
                return len(item.strip()) > 0
            if hasattr(item, '__len__'):
                return len(item) > 0
            return True
        
        return self.filter_by(not_empty)
    
    def filter_by_length(self, min_length: Optional[int] = None, max_length: Optional[int] = None) -> 'DataProcessor[List[T]]':
        """
        길이에 따라 필터링합니다.
        
        Args:
            min_length: 최소 길이
            max_length: 최대 길이
            
        Returns:
            길이 조건을 만족하는 항목들을 가진 DataProcessor
        """
        def length_check(item):
            try:
                length = len(item)
                if min_length is not None and length < min_length:
                    return False
                if max_length is not None and length > max_length:
                    return False
                return True
            except TypeError:
                return False
        
        return self.filter_by(length_check)
    
    def transform_to(self, transformer: TransformFunction) -> 'DataProcessor[List[U]]':
        """
        각 항목을 변환합니다.
        
        Args:
            transformer: 변환 함수
            
        Returns:
            변환된 데이터를 가진 DataProcessor
        """
        try:
            transformed = []
            for item in self._value:
                try:
                    result = transformer(item)
                    if result is not None:
                        transformed.append(result)
                except Exception:
                    # 개별 변환 실패는 건너뛰고 계속 진행
                    continue
            
            return DataProcessor(transformed)
        except Exception:
            return DataProcessor([])
    
    def group_by(self, key_func: Callable[[T], Any]) -> 'DataProcessor[dict]':
        """
        키 함수에 따라 그룹화합니다.
        
        Args:
            key_func: 그룹화 키를 생성하는 함수
            
        Returns:
            그룹화된 딕셔너리를 가진 DataProcessor
        """
        try:
            groups = {}
            for item in self._value:
                try:
                    key = key_func(item)
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(item)
                except Exception:
                    # 키 생성 실패 시 'unknown' 그룹에 추가
                    if 'unknown' not in groups:
                        groups['unknown'] = []
                    groups['unknown'].append(item)
            
            return DataProcessor(groups)
        except Exception:
            return DataProcessor({})
    
    def sort_by(self, key_func: Optional[Callable[[T], Any]] = None, reverse: bool = False) -> 'DataProcessor[List[T]]':
        """
        정렬합니다.
        
        Args:
            key_func: 정렬 키 함수 (None이면 기본 정렬)
            reverse: True이면 내림차순
            
        Returns:
            정렬된 데이터를 가진 DataProcessor
        """
        try:
            if key_func:
                sorted_items = sorted(self._value, key=key_func, reverse=reverse)
            else:
                sorted_items = sorted(self._value, reverse=reverse)
            return DataProcessor(sorted_items)
        except Exception:
            # 정렬 실패 시 원본 데이터 반환
            return DataProcessor(self._value)
    
    def take(self, n: int) -> 'DataProcessor[List[T]]':
        """
        처음 n개 항목을 가져옵니다.
        
        Args:
            n: 가져올 개수
            
        Returns:
            처음 n개 항목을 가진 DataProcessor
        """
        return DataProcessor(self._value[:n])
    
    def skip(self, n: int) -> 'DataProcessor[List[T]]':
        """
        처음 n개 항목을 건너뜁니다.
        
        Args:
            n: 건너뛸 개수
            
        Returns:
            n개 이후 항목들을 가진 DataProcessor
        """
        return DataProcessor(self._value[n:])
    
    def distinct(self) -> 'DataProcessor[List[T]]':
        """
        중복을 제거합니다.
        
        Returns:
            중복이 제거된 항목들을 가진 DataProcessor
        """
        seen = set()
        unique_items = []
        
        for item in self._value:
            # 해시 가능한 항목인지 확인
            try:
                if item not in seen:
                    seen.add(item)
                    unique_items.append(item)
            except TypeError:
                # 해시 불가능한 항목은 매번 추가 (완전 중복 제거 불가)
                unique_items.append(item)
        
        return DataProcessor(unique_items)
    
    def count(self) -> int:
        """항목 개수를 반환합니다."""
        return len(self._value)
    
    def is_empty(self) -> bool:
        """비어있는지 확인합니다."""
        return len(self._value) == 0
    
    def collect(self) -> List[T]:
        """
        최종 결과를 리스트로 수집합니다.
        
        Returns:
            처리된 데이터의 리스트
        """
        return self._value
    
    def collect_first(self) -> Optional[T]:
        """
        첫 번째 항목을 반환합니다.
        
        Returns:
            첫 번째 항목 또는 None
        """
        return self._value[0] if self._value else None
    
    def to_chainable_result(self) -> ChainableResult[List[T]]:
        """
        ChainableResult로 변환합니다.
        
        Returns:
            데이터를 담은 ChainableResult
        """
        return success(self._value)
    
    def _is_error_item(self, item: Any) -> bool:
        """항목이 에러인지 확인합니다."""
        if hasattr(item, 'error') or hasattr(item, 'exception'):
            return True
        if isinstance(item, dict) and ('error' in item or 'exception' in item):
            return True
        if hasattr(item, 'is_failure') and callable(item.is_failure):
            try:
                return item.is_failure()
            except Exception:
                return False
        return False

# 메인 진입점 함수
def extract_from(data: Any) -> DataExtractor:
    """
    데이터로부터 정보를 추출하기 위한 시작점입니다.
    
    Args:
        data: 추출할 데이터
        
    Returns:
        DataExtractor 인스턴스
        
    Example:
        >>> results = (extract_from(batch_results)
        ...            .flatten_batches()
        ...            .successful_only()
        ...            .extract_content()
        ...            .filter_by(lambda x: len(x.strip()) > 10)
        ...            .collect())
    """
    return DataExtractor(data)

# 편의 함수들
def process_batch(items: List[T], processor: TransformFunction) -> List[U]:
    """
    배치 항목들을 처리합니다.
    
    Args:
        items: 처리할 항목들
        processor: 변환 함수
        
    Returns:
        처리된 결과 리스트
    """
    return DataProcessor(items).transform_to(processor).collect()

def filter_and_transform(items: List[T], predicate: PredicateFunction, transformer: TransformFunction) -> List[U]:
    """
    필터링과 변환을 함께 수행합니다.
    
    Args:
        items: 처리할 항목들
        predicate: 필터링 조건
        transformer: 변환 함수
        
    Returns:
        필터링되고 변환된 결과 리스트
    """
    return (DataProcessor(items)
            .filter_by(predicate)
            .transform_to(transformer)
            .collect())


# 병렬 처리 기능 추가
import asyncio
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import partial


class ParallelDataProcessor(FluentBase[List[T]]):
    """
    병렬 처리를 지원하는 DataProcessor 확장
    
    ThreadPoolExecutor와 ProcessPoolExecutor를 사용하여
    멀티스레딩/멀티프로세싱 병렬 처리를 제공합니다.
    """
    
    def parallel_transform(
        self, 
        transformer: TransformFunction,
        max_workers: Optional[int] = None,
        use_processes: bool = False
    ) -> 'ParallelDataProcessor[List[U]]':
        """
        병렬로 각 항목을 변환합니다.
        
        Args:
            transformer: 변환 함수
            max_workers: 최대 워커 수 (None이면 자동)
            use_processes: True면 프로세스 풀, False면 스레드 풀 사용
            
        Returns:
            병렬로 변환된 데이터를 가진 ParallelDataProcessor
        """
        try:
            executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
            
            with executor_class(max_workers=max_workers) as executor:
                # 각 항목을 병렬로 처리
                futures = [executor.submit(transformer, item) for item in self._value]
                
                results = []
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        if result is not None:
                            results.append(result)
                    except Exception:
                        # 개별 변환 실패는 건너뛰고 계속 진행
                        continue
                
                # 원래 순서 유지를 위해 다시 정렬
                ordered_results = []
                completed_futures = [executor.submit(transformer, item) for item in self._value]
                for future in completed_futures:
                    try:
                        result = future.result()
                        if result is not None:
                            ordered_results.append(result)
                    except Exception:
                        continue
                
                return ParallelDataProcessor(ordered_results)
                
        except Exception:
            # 병렬 처리 실패 시 순차 처리로 폴백
            return ParallelDataProcessor(self.transform_to(transformer).value)
    
    def parallel_filter_and_transform(
        self,
        predicate: PredicateFunction,
        transformer: TransformFunction,
        max_workers: Optional[int] = None,
        use_processes: bool = False
    ) -> 'ParallelDataProcessor[List[U]]':
        """
        병렬로 필터링과 변환을 함께 수행합니다.
        
        Args:
            predicate: 필터링 조건
            transformer: 변환 함수
            max_workers: 최대 워커 수
            use_processes: 프로세스 풀 사용 여부
            
        Returns:
            병렬로 처리된 데이터를 가진 ParallelDataProcessor
        """
        def filter_and_transform_item(item):
            if predicate(item):
                return transformer(item)
            return None
        
        return self.parallel_transform(filter_and_transform_item, max_workers, use_processes)
    
    def parallel_batch_process(
        self,
        transformer: TransformFunction,
        batch_size: int = 10,
        max_workers: Optional[int] = None,
        use_processes: bool = False
    ) -> 'ParallelDataProcessor[List[U]]':
        """
        데이터를 배치로 나누어 병렬 처리합니다.
        
        Args:
            transformer: 변환 함수
            batch_size: 배치 크기
            max_workers: 최대 워커 수
            use_processes: 프로세스 풀 사용 여부
            
        Returns:
            배치별로 병렬 처리된 결과를 가진 ParallelDataProcessor
        """
        # 데이터를 배치로 분할
        batches = []
        items = list(self._value)
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batches.append(batch)
        
        def process_batch_func(batch):
            return [transformer(item) for item in batch if transformer(item) is not None]
        
        try:
            executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
            
            with executor_class(max_workers=max_workers) as executor:
                batch_futures = [executor.submit(process_batch_func, batch) for batch in batches]
                
                all_results = []
                for future in concurrent.futures.as_completed(batch_futures):
                    try:
                        batch_results = future.result()
                        all_results.extend(batch_results)
                    except Exception:
                        continue
                
                return ParallelDataProcessor(all_results)
                
        except Exception:
            # 병렬 처리 실패 시 순차 처리로 폴백
            sequential_results = []
            for batch in batches:
                batch_results = process_batch_func(batch)
                sequential_results.extend(batch_results)
            return ParallelDataProcessor(sequential_results)
    
    def collect(self) -> List[T]:
        """
        처리된 결과를 리스트로 반환합니다.
        
        Returns:
            처리된 데이터 리스트
        """
        return self._value


def extract_from_parallel(data: Any, max_workers: Optional[int] = None) -> ParallelDataProcessor:
    """
    병렬 처리를 지원하는 데이터 추출기를 생성합니다.
    
    Args:
        data: 추출할 데이터
        max_workers: 최대 워커 수
        
    Returns:
        병렬 처리가 가능한 DataProcessor
        
    Example:
        >>> results = (extract_from_parallel(batch_data)
        ...           .parallel_transform(expensive_function, max_workers=4)
        ...           .collect())
    """
    # 데이터를 리스트로 변환
    if isinstance(data, list):
        processed_data = data
    elif hasattr(data, '__iter__') and not isinstance(data, str):
        processed_data = list(data)
    else:
        processed_data = [data]
    
    return ParallelDataProcessor(processed_data)


async def async_extract_from(data: Any) -> 'AsyncDataProcessor':
    """
    비동기 데이터 추출기를 생성합니다.
    
    Args:
        data: 추출할 데이터
        
    Returns:
        비동기 처리가 가능한 DataProcessor
    """
    processor = DataProcessor(data).flatten_batches().successful_only()
    return AsyncDataProcessor(processor.value)


class AsyncDataProcessor(DataProcessor[List[T]]):
    """
    비동기 처리를 지원하는 DataProcessor 확장
    """
    
    async def async_transform(self, transformer: Callable[[T], Awaitable[U]]) -> 'AsyncDataProcessor[List[U]]':
        """
        비동기로 각 항목을 변환합니다.
        
        Args:
            transformer: 비동기 변환 함수
            
        Returns:
            비동기로 변환된 데이터를 가진 AsyncDataProcessor
        """
        from ..async_hof import async_map
        
        try:
            results = await async_map(transformer, self._value)
            return AsyncDataProcessor([r for r in results if r is not None])
        except Exception:
            # 비동기 처리 실패 시 빈 결과 반환
            return AsyncDataProcessor([])
    
    async def async_filter_and_transform(
        self,
        predicate: Callable[[T], Awaitable[bool]],
        transformer: Callable[[T], Awaitable[U]]
    ) -> 'AsyncDataProcessor[List[U]]':
        """
        비동기로 필터링과 변환을 함께 수행합니다.
        
        Args:
            predicate: 비동기 필터링 조건
            transformer: 비동기 변환 함수
            
        Returns:
            비동기로 처리된 데이터를 가진 AsyncDataProcessor
        """
        from ..async_hof import async_filter
        
        try:
            # 먼저 필터링
            filtered_items = await async_filter(predicate, self._value)
            # 그 다음 변환
            return await AsyncDataProcessor(filtered_items).async_transform(transformer)
        except Exception:
            return AsyncDataProcessor([])
    
    async def async_chunk_process(
        self,
        transformer: Callable[[T], Awaitable[U]],
        chunk_size: int = 10
    ) -> 'AsyncDataProcessor[List[U]]':
        """
        청크 단위로 비동기 처리합니다.
        
        Args:
            transformer: 비동기 변환 함수
            chunk_size: 청크 크기
            
        Returns:
            청크별로 비동기 처리된 결과를 가진 AsyncDataProcessor
        """
        from ..async_hof import async_chunk_process
        
        try:
            results = await async_chunk_process(transformer, self._value, chunk_size)
            return AsyncDataProcessor([r for r in results if r is not None])
        except Exception:
            return AsyncDataProcessor([])


# 편의 함수들
def quick_parallel_process(
    data: Any, 
    transformer: TransformFunction,
    max_workers: Optional[int] = None,
    batch_size: Optional[int] = None
) -> List[Any]:
    """
    데이터를 빠르게 병렬 처리합니다.
    
    Args:
        data: 처리할 데이터
        transformer: 변환 함수
        max_workers: 최대 워커 수
        batch_size: 배치 크기 (None이면 단일 항목 처리)
        
    Returns:
        병렬 처리된 결과 리스트
    """
    processor = extract_from_parallel(data, max_workers)
    
    if batch_size:
        return processor.parallel_batch_process(transformer, batch_size, max_workers).collect()
    else:
        return processor.parallel_transform(transformer, max_workers).collect()


async def quick_async_process(
    data: Any,
    transformer: Callable[[Any], Awaitable[Any]],
    chunk_size: int = 10
) -> List[Any]:
    """
    데이터를 빠르게 비동기 처리합니다.
    
    Args:
        data: 처리할 데이터
        transformer: 비동기 변환 함수
        chunk_size: 청크 크기
        
    Returns:
        비동기 처리된 결과 리스트
    """
    processor = await async_extract_from(data)
    result_processor = await processor.async_chunk_process(transformer, chunk_size)
    return result_processor.collect()