"""
Collection Operations - Swift-inspired and functional collection utilities

Provides higher-order functions for working with collections including
Swift-inspired patterns like first, compactMap, and drop operations.
"""

import itertools
from functools import reduce
from itertools import dropwhile, groupby, islice, takewhile
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
    overload,
)

# RFS Framework imports
from ..core.result import Failure, Result, Success

# Type variables
T = TypeVar("T")
U = TypeVar("U")
K = TypeVar("K")
V = TypeVar("V")


# Swift-inspired functions
def first(
    iterable: Iterable[T], predicate: Optional[Callable[[T], bool]] = None
) -> Optional[T]:
    """
    Returns the first element matching the predicate, or first element if no predicate.
    Swift-inspired: collection.first(where: { $0 > 5 })

    Args:
        iterable: Collection to search
        predicate: Optional condition function

    Returns:
        First matching element or None

    Example:
        >>> first([1, 2, 3, 4, 5], lambda x: x > 3)
        4
        >>> first([1, 2, 3])
        1
        >>> first([], lambda x: x > 0)
        None
    """
    if predicate is None:
        return next(iter(iterable), None)

    for item in iterable:
        if predicate(item):
            return item
    return None


def last(
    iterable: Iterable[T], predicate: Optional[Callable[[T], bool]] = None
) -> Optional[T]:
    """
    Returns the last element matching the predicate.

    Args:
        iterable: Collection to search
        predicate: Optional condition function

    Returns:
        Last matching element or None

    Example:
        >>> last([1, 2, 3, 4, 5], lambda x: x < 4)
        3
        >>> last([1, 2, 3])
        3
    """
    result = None
    if predicate is None:
        for item in iterable:
            result = item
    else:
        for item in iterable:
            if predicate(item):
                result = item
    return result


def compact_map(func: Callable[[T], Optional[U]], iterable: Iterable[T]) -> List[U]:
    """
    Maps and filters None values in one operation.
    Swift-inspired: compactMap { transform($0) }

    Args:
        func: Transform function that may return None
        iterable: Collection to transform

    Returns:
        List of non-None transformed values

    Example:
        >>> compact_map(lambda x: x if x > 2 else None, [1, 2, 3, 4])
        [3, 4]
        >>> compact_map(lambda x: x**2 if x % 2 == 0 else None, [1, 2, 3, 4])
        [4, 16]
    """
    return [result for item in iterable if (result := func(item)) is not None]


def safe_map(func: Callable[[T], U], iterable: Iterable[T]) -> Result[List[U], str]:
    """
    안전한 map 연산 - 예외를 Result로 변환

    모든 요소에 함수를 적용하되, 예외 발생 시 Failure로 래핑합니다.
    PR 문서에서 제안된 API 일관성을 위해 function-first 매개변수 순서를 사용합니다.

    Args:
        func: 변환 함수 (예외 발생 가능)
        iterable: 변환할 컬렉션

    Returns:
        Result[List[U], str]: 성공 시 변환된 리스트, 실패 시 에러 메시지

    Example:
        >>> safe_map(lambda x: x / 2, [2, 4, 6])
        Success([1.0, 2.0, 3.0])

        >>> safe_map(lambda x: 10 // x, [2, 0, 4])  # ZeroDivisionError at index 1
        Failure("Error at index 1: division by zero")

        >>> safe_map(int, ["1", "2", "invalid", "4"])  # ValueError at index 2
        Failure("Error at index 2: invalid literal for int() with base 10: 'invalid'")
    """
    try:
        results = []
        for index, item in enumerate(iterable):
            try:
                result = func(item)
                results.append(result)
            except Exception as e:
                return Failure(f"Error at index {index}: {str(e)}")
        return Success(results)
    except Exception as e:
        return Failure(f"Iteration error: {str(e)}")


def flat_map(func: Callable[[T], Iterable[U]], iterable: Iterable[T]) -> List[U]:
    """
    Maps each element to a collection and flattens the result.
    Swift-inspired: flatMap { transform($0) }

    Args:
        func: Function returning an iterable
        iterable: Collection to transform

    Returns:
        Flattened list of all results

    Example:
        >>> flat_map(lambda x: [x, x*2], [1, 2, 3])
        [1, 2, 2, 4, 3, 6]
        >>> flat_map(lambda x: range(x), [1, 2, 3])
        [0, 0, 1, 0, 1, 2]
    """
    return [item for sublist in map(func, iterable) for item in sublist]


def drop_last(
    iterable: Iterable[T], n=1, predicate: Optional[Callable[[T], bool]] = None
) -> List[T]:
    """
    Drops last n elements or elements matching predicate from the end.
    Swift-inspired: dropLast(while:) and dropLast(n)

    Args:
        iterable: Collection to process
        n: Number of elements to drop from end
        predicate: Optional condition for dropping from end

    Returns:
        List with elements dropped from end

    Example:
        >>> drop_last([1, 2, 3, 4, 5], 2)
        [1, 2, 3]
        >>> drop_last([1, 2, 3, 4, 5], predicate=lambda x: x > 3)
        [1, 2, 3]
    """
    items = list(iterable)

    if predicate:
        # Drop from end while predicate is true
        while items and predicate(items[-1]):
            items.pop()
        return items
    else:
        # Drop last n elements
        return (
            items[:-n] if n > 0 and n < len(items) else [] if n >= len(items) else items
        )


def drop_first(
    iterable: Iterable[T], n=1, predicate: Optional[Callable[[T], bool]] = None
) -> List[T]:
    """
    Drops first n elements or elements matching predicate from start.

    Args:
        iterable: Collection to process
        n: Number of elements to drop from start
        predicate: Optional condition for dropping from start

    Returns:
        List with elements dropped from start

    Example:
        >>> drop_first([1, 2, 3, 4, 5], 2)
        [3, 4, 5]
        >>> drop_first([1, 2, 3, 4, 5], predicate=lambda x: x < 3)
        [3, 4, 5]
    """
    if predicate:
        return list(dropwhile(predicate, iterable))
    else:
        return list(islice(iterable, n, None))


def merging(
    dict1: Dict[K, V], dict2: Dict[K, V], unique_keys_with: Callable[[V, V], V]
) -> Dict[K, V]:
    """
    Merges two dictionaries with a custom resolver for conflicts.
    Swift-inspired: merging(_:uniquingKeysWith:)

    Args:
        dict1: First dictionary
        dict2: Second dictionary
        unique_keys_with: Function to resolve conflicts (old, new) -> resolved

    Returns:
        Merged dictionary

    Example:
        >>> d1 = {'a': 1, 'b': 2}
        >>> d2 = {'b': 3, 'c': 4}
        >>> merging(d1, d2, lambda old, new: old + new)
        {'a': 1, 'b': 5, 'c': 4}
        >>> merging(d1, d2, lambda old, new: new)  # Keep new
        {'a': 1, 'b': 3, 'c': 4}
    """
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result:
            result[key] = unique_keys_with(result[key], value)
        else:
            result[key] = value
    return result


# Standard functional collection operations
def map_indexed(func: Callable[[int, T], U], iterable: Iterable[T]) -> List[U]:
    """
    Maps with index.

    Args:
        func: Function taking (index, item)
        iterable: Collection to map

    Returns:
        List of mapped values

    Example:
        >>> map_indexed(lambda i, x: f"{i}:{x}", ['a', 'b', 'c'])
        ['0:a', '1:b', '2:c']
    """
    return [func(i, item) for i, item in enumerate(iterable)]


def filter_indexed(
    predicate: Callable[[int, T], bool], iterable: Iterable[T]
) -> List[T]:
    """
    Filters with index.

    Args:
        predicate: Function taking (index, item) returning bool
        iterable: Collection to filter

    Returns:
        List of filtered values

    Example:
        >>> filter_indexed(lambda i, x: i % 2 == 0, ['a', 'b', 'c', 'd'])
        ['a', 'c']
    """
    return [item for i, item in enumerate(iterable) if predicate(i, item)]


def reduce_indexed(
    func: Callable[[int, U, T], U], iterable: Iterable[T], initial: U
) -> U:
    """
    Reduces with index.

    Args:
        func: Function taking (index, accumulator, item)
        iterable: Collection to reduce
        initial: Initial value

    Returns:
        Reduced value

    Example:
        >>> reduce_indexed(lambda i, acc, x: acc + i * x, [1, 2, 3], 0)
        8  # 0*1 + 1*2 + 2*3 = 8
    """
    result = initial
    for i, item in enumerate(iterable):
        result = func(i, result, item)
    return result


def fold(func: Callable[[U, T], U], initial: U, iterable: Iterable[T]) -> U:
    """
    Folds (reduces) a collection from left to right.

    Args:
        func: Binary function (accumulator, item)
        initial: Initial value
        iterable: Collection to fold

    Returns:
        Folded value

    Example:
        >>> fold(lambda acc, x: acc + x, 0, [1, 2, 3, 4])
        10
    """
    return reduce(func, iterable, initial)


def fold_left(func: Callable[[U, T], U], initial: U, iterable: Iterable[T]) -> U:
    """
    Left fold (same as fold).
    """
    return fold(func, initial, iterable)


def fold_right(func: Callable[[T, U], U], initial: U, iterable: Iterable[T]) -> U:
    """
    Right fold - processes from right to left.

    Args:
        func: Binary function (item, accumulator)
        initial: Initial value
        iterable: Collection to fold

    Returns:
        Folded value

    Example:
        >>> fold_right(lambda x, acc: f"({x}{acc})", "", ['a', 'b', 'c'])
        '(a(b(c)))'
    """
    items = list(iterable)
    result = initial
    for item in reversed(items):
        result = func(item, result)
    return result


def scan(func: Callable[[U, T], U], initial: U, iterable: Iterable[T]) -> List[U]:
    """
    Like fold but returns all intermediate results.

    Args:
        func: Binary function
        initial: Initial value
        iterable: Collection to scan

    Returns:
        List of all intermediate results

    Example:
        >>> scan(lambda acc, x: acc + x, 0, [1, 2, 3, 4])
        [0, 1, 3, 6, 10]
    """
    results = [initial]
    current = initial
    for item in iterable:
        current = func(current, item)
        results.append(current)
    return results


def partition(
    predicate: Callable[[T], bool], iterable: Iterable[T]
) -> Tuple[List[T], List[T]]:
    """
    Splits collection into two based on predicate.

    Args:
        predicate: Condition function
        iterable: Collection to partition

    Returns:
        Tuple of (matching, non-matching)

    Example:
        >>> partition(lambda x: x % 2 == 0, [1, 2, 3, 4, 5])
        ([2, 4], [1, 3, 5])
    """
    true_items = []
    false_items = []
    for item in iterable:
        if predicate(item):
            true_items.append(item)
        else:
            false_items.append(item)
    return true_items, false_items


def group_by(key_func: Callable[[T], K], iterable: Iterable[T]) -> Dict[K, List[T]]:
    """
    Groups elements by key function.

    Args:
        key_func: Function to generate keys
        iterable: Collection to group

    Returns:
        Dictionary of grouped items

    Example:
        >>> group_by(lambda x: x % 3, [1, 2, 3, 4, 5, 6])
        {1: [1, 4], 2: [2, 5], 0: [3, 6]}
    """
    result = {}
    for item in iterable:
        key = key_func(item)
        if key not in result:
            result[key] = []
        result[key].append(item)
    return result


def chunk(iterable: Iterable[T], size: int) -> List[List[T]]:
    """
    Splits collection into chunks of specified size.

    Args:
        iterable: Collection to chunk
        size: Chunk size

    Returns:
        List of chunks

    Example:
        >>> chunk([1, 2, 3, 4, 5], 2)
        [[1, 2], [3, 4], [5]]
    """
    it = iter(iterable)
    chunks = []
    while True:
        chunk_items = list(islice(it, size))
        if not chunk_items:
            break
        chunks.append(chunk_items)
    return chunks


def flatten(iterable: Iterable[Iterable[T]]) -> List[T]:
    """
    Flattens one level of nesting.

    Args:
        iterable: Nested collection

    Returns:
        Flattened list

    Example:
        >>> flatten([[1, 2], [3, 4], [5]])
        [1, 2, 3, 4, 5]
    """
    return [item for sublist in iterable for item in sublist]


def zip_with(func: Callable[..., U], *iterables: Iterable) -> List[U]:
    """
    Zips collections and applies function to each tuple.

    Args:
        func: Function to apply to zipped elements
        *iterables: Collections to zip

    Returns:
        List of results

    Example:
        >>> zip_with(lambda x, y: x + y, [1, 2, 3], [10, 20, 30])
        [11, 22, 33]
    """
    return [func(*args) for args in zip(*iterables)]


def take(n: int, iterable: Iterable[T]) -> List[T]:
    """
    Takes first n elements.

    Args:
        n: Number of elements
        iterable: Collection

    Returns:
        List of first n elements

    Example:
        >>> take(3, [1, 2, 3, 4, 5])
        [1, 2, 3]
    """
    return list(islice(iterable, n))


def drop(n: int, iterable: Iterable[T]) -> List[T]:
    """
    Drops first n elements.

    Args:
        n: Number of elements to drop
        iterable: Collection

    Returns:
        List without first n elements

    Example:
        >>> drop(2, [1, 2, 3, 4, 5])
        [3, 4, 5]
    """
    return list(islice(iterable, n, None))


def take_while(predicate: Callable[[T], bool], iterable: Iterable[T]) -> List[T]:
    """
    Takes elements while predicate is true.

    Args:
        predicate: Condition function
        iterable: Collection

    Returns:
        List of elements

    Example:
        >>> take_while(lambda x: x < 4, [1, 2, 3, 4, 5])
        [1, 2, 3]
    """
    return list(takewhile(predicate, iterable))


def drop_while(predicate: Callable[[T], bool], iterable: Iterable[T]) -> List[T]:
    """
    Drops elements while predicate is true.

    Args:
        predicate: Condition function
        iterable: Collection

    Returns:
        List of remaining elements

    Example:
        >>> drop_while(lambda x: x < 3, [1, 2, 3, 4, 5])
        [3, 4, 5]
    """
    return list(dropwhile(predicate, iterable))


def forEach(action: Callable[[T], None], iterable: Iterable[T]) -> None:
    """
    Swift-style forEach - 각 요소에 대해 부작용(side effect) 연산을 실행합니다.
    Swift-inspired: collection.forEach { action($0) }

    Args:
        action: 각 요소에 적용할 함수 (반환값 없음)
        iterable: 순회할 컬렉션

    Returns:
        None (부작용만 실행)

    Example:
        >>> result = []
        >>> forEach(lambda x: result.append(x * 2), [1, 2, 3])
        >>> result
        [2, 4, 6]
        
        >>> # 로깅 예시
        >>> forEach(lambda x: print(f"Processing: {x}"), ["a", "b", "c"])
        Processing: a
        Processing: b
        Processing: c
        
        >>> # 딕셔너리 업데이트 예시
        >>> data = {}
        >>> forEach(lambda item: data.update({item['id']: item['value']}), 
        ...         [{'id': 1, 'value': 'A'}, {'id': 2, 'value': 'B'}])
        >>> data
        {1: 'A', 2: 'B'}
    """
    for item in iterable:
        action(item)
