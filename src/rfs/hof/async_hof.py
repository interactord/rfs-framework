"""
Async Higher-Order Functions

Async versions of functional programming utilities for working with
coroutines and async iterables.
"""

import asyncio
from functools import reduce, wraps
from typing import (
    Any,
    AsyncIterable,
    Awaitable,
    Callable,
    Coroutine,
    Iterable,
    List,
    Optional,
    TypeVar,
    Union,
)

T = TypeVar("T")
U = TypeVar("U")
R = TypeVar("R")


def async_compose(*functions: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
    """
    Async function composition - right to left.

    Args:
        *functions: Async functions to compose

    Returns:
        Composed async function

    Example:
        >>> async def add_one(x): return x + 1
        >>> async def multiply_two(x): return x * 2
        >>> composed = async_compose(add_one, multiply_two)
        >>> await composed(3)  # (3 * 2) + 1 = 7
        7
    """

    async def composed(*args, **kwargs):
        result = args[0] if len(args) == 1 and not kwargs else (args, kwargs)

        for func in reversed(functions):
            if isinstance(result, tuple) and not kwargs:
                result = await func(*result)
            elif isinstance(result, tuple) and kwargs:
                result = await func(*result[0], **result[1])
            else:
                result = await func(result)

        return result

    return composed


def async_pipe(*functions: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
    """
    Async function composition - left to right.

    Args:
        *functions: Async functions to pipe

    Returns:
        Piped async function

    Example:
        >>> async def add_one(x): return x + 1
        >>> async def multiply_two(x): return x * 2
        >>> piped = async_pipe(add_one, multiply_two)
        >>> await piped(3)  # (3 + 1) * 2 = 8
        8
    """

    async def piped(*args, **kwargs):
        result = args[0] if len(args) == 1 and not kwargs else (args, kwargs)

        for func in functions:
            if isinstance(result, tuple) and not kwargs:
                result = await func(*result)
            elif isinstance(result, tuple) and kwargs:
                result = await func(*result[0], **result[1])
            else:
                result = await func(result)

        return result

    return piped


async def async_map(
    func: Callable[[T], Awaitable[U]], iterable: Iterable[T]
) -> List[U]:
    """
    Async map - applies async function to all items.

    Args:
        func: Async function to apply
        iterable: Items to process

    Returns:
        List of results

    Example:
        >>> async def double(x):
        ...     await asyncio.sleep(0.1)
        ...     return x * 2
        >>> await async_map(double, [1, 2, 3])
        [2, 4, 6]
    """
    tasks = [func(item) for item in iterable]
    return await asyncio.gather(*tasks)


async def async_filter(
    predicate: Callable[[T], Awaitable[bool]], iterable: Iterable[T]
) -> List[T]:
    """
    Async filter - filters items using async predicate.

    Args:
        predicate: Async predicate function
        iterable: Items to filter

    Returns:
        Filtered list

    Example:
        >>> async def is_even(x):
        ...     await asyncio.sleep(0.1)
        ...     return x % 2 == 0
        >>> await async_filter(is_even, [1, 2, 3, 4, 5])
        [2, 4]
    """
    results = []
    for item in iterable:
        if await predicate(item):
            results.append(item)
    return results


async def async_reduce(
    func: Callable[[U, T], Awaitable[U]], iterable: Iterable[T], initial: U
) -> U:
    """
    Async reduce - reduces collection with async function.

    Args:
        func: Async binary function
        iterable: Items to reduce
        initial: Initial value

    Returns:
        Reduced value

    Example:
        >>> async def async_add(x, y):
        ...     await asyncio.sleep(0.1)
        ...     return x + y
        >>> await async_reduce(async_add, [1, 2, 3, 4], 0)
        10
    """
    result = initial
    for item in iterable:
        result = await func(result, item)
    return result


def async_retry(
    max_attempts=3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Async retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier
        exceptions: Exceptions to retry on

    Returns:
        Decorated async function

    Example:
        >>> @async_retry(max_attempts=3, delay=1.0)
        ... async def unreliable_async_call():
        ...     # Might fail sometimes
        ...     pass
    """

    def decorator(func: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff

            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def async_timeout(seconds: float) -> Callable:
    """
    Async timeout decorator.

    Args:
        seconds: Timeout in seconds

    Returns:
        Decorated async function

    Example:
        >>> @async_timeout(5.0)
        ... async def slow_async_function():
        ...     await asyncio.sleep(10)
        >>> await slow_async_function()  # Raises TimeoutError after 5 seconds
    """

    def decorator(func: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)

        return wrapper

    return decorator


async def async_parallel(*coroutines: Coroutine, return_exceptions=False) -> List[Any]:
    """
    Execute coroutines in parallel.

    Args:
        *coroutines: Coroutines to execute
        return_exceptions: Return exceptions instead of raising

    Returns:
        List of results

    Example:
        >>> async def task1(): return 1
        >>> async def task2(): return 2
        >>> await async_parallel(task1(), task2())
        [1, 2]
    """
    return await asyncio.gather(*coroutines, return_exceptions=return_exceptions)


async def async_sequential(
    *coroutines: Union[Coroutine, Callable[[], Coroutine]]
) -> List[Any]:
    """
    Execute coroutines sequentially.

    Args:
        *coroutines: Coroutines or coroutine factories

    Returns:
        List of results in order

    Example:
        >>> async def task1(): return 1
        >>> async def task2(): return 2
        >>> await async_sequential(task1(), task2())
        [1, 2]
    """
    results = []
    for coro in coroutines:
        if callable(coro) and not asyncio.iscoroutine(coro):
            result = await coro()
        else:
            result = await coro
        results.append(result)
    return results


async def async_chunk_process(
    func: Callable[[T], Awaitable[U]], items: Iterable[T], chunk_size=10
) -> List[U]:
    """
    Process items in chunks to limit concurrency.

    Args:
        func: Async function to apply
        items: Items to process
        chunk_size: Size of each chunk

    Returns:
        List of all results

    Example:
        >>> async def process(x):
        ...     await asyncio.sleep(0.1)
        ...     return x * 2
        >>> await async_chunk_process(process, range(100), chunk_size=10)
        # Processes 10 items at a time
    """
    results = []
    items_list = list(items)

    for i in range(0, len(items_list), chunk_size):
        chunk = items_list[i : i + chunk_size]
        chunk_results = await async_map(func, chunk)
        results.extend(chunk_results)

    return results


async def async_race(*coroutines: Coroutine) -> Any:
    """
    Returns the result of the first completed coroutine.

    Args:
        *coroutines: Coroutines to race

    Returns:
        Result of first completed

    Example:
        >>> async def fast():
        ...     await asyncio.sleep(0.1)
        ...     return "fast"
        >>> async def slow():
        ...     await asyncio.sleep(1.0)
        ...     return "slow"
        >>> await async_race(fast(), slow())
        'fast'
    """
    done, pending = await asyncio.wait(coroutines, return_when=asyncio.FIRST_COMPLETED)

    # Cancel pending tasks
    for task in pending:
        task.cancel()

    # Return result of first completed
    return done.pop().result()


async def async_all(predicates: List[Callable[[T], Awaitable[bool]]], value: T) -> bool:
    """
    Check if all async predicates are true.

    Args:
        predicates: List of async predicates
        value: Value to test

    Returns:
        True if all predicates pass

    Example:
        >>> async def is_positive(x): return x > 0
        >>> async def is_even(x): return x % 2 == 0
        >>> await async_all([is_positive, is_even], 4)
        True
    """
    results = await asyncio.gather(*[pred(value) for pred in predicates])
    return all(results)


async def async_any(predicates: List[Callable[[T], Awaitable[bool]]], value: T) -> bool:
    """
    Check if any async predicate is true.

    Args:
        predicates: List of async predicates
        value: Value to test

    Returns:
        True if any predicate passes

    Example:
        >>> async def is_negative(x): return x < 0
        >>> async def is_even(x): return x % 2 == 0
        >>> await async_any([is_negative, is_even], 3)
        False
    """
    results = await asyncio.gather(*[pred(value) for pred in predicates])
    return any(results)


async def async_throttle(
    func: Callable[[T], Awaitable[U]], items: Iterable[T], rate: float, per: float = 1.0
) -> List[U]:
    """
    Process items with rate limiting.

    Args:
        func: Async function to apply
        items: Items to process
        rate: Maximum calls per period
        per: Time period in seconds

    Returns:
        List of results

    Example:
        >>> async def api_call(x):
        ...     return x * 2
        >>> await async_throttle(api_call, range(10), rate=3, per=1.0)
        # Processes max 3 items per second
    """
    interval = per / rate
    results = []

    for item in items:
        start = asyncio.get_event_loop().time()
        result = await func(item)
        results.append(result)

        elapsed = asyncio.get_event_loop().time() - start
        if elapsed < interval:
            await asyncio.sleep(interval - elapsed)

    return results


class AsyncLazy:
    """
    Lazy async evaluation - compute value only when first awaited.

    Example:
        >>> async def expensive_async_data():
        ...     print("Computing...")
        ...     await asyncio.sleep(1)
        ...     return "data"
        >>> lazy = AsyncLazy(expensive_async_data)
        >>> result = await lazy()  # Computes now
        Computing...
        >>> result2 = await lazy()  # Uses cached result
    """

    def __init__(self, func: Callable[[], Awaitable[T]]):
        self.func = func
        self.value = None
        self.computed = False
        self.lock = asyncio.Lock()

    async def __call__(self) -> T:
        async with self.lock:
            if not self.computed:
                self.value = await self.func()
                self.computed = True
        return self.value


async def async_memoize(
    func: Callable[..., Awaitable[T]], maxsize=128
) -> Callable[..., Awaitable[T]]:
    """
    Async memoization decorator.

    Args:
        func: Async function to memoize
        maxsize: Maximum cache size

    Returns:
        Memoized async function

    Example:
        >>> @async_memoize
        ... async def expensive_async_computation(x):
        ...     await asyncio.sleep(1)
        ...     return x ** 2
    """
    import hashlib
    import pickle
    from collections import OrderedDict

    cache: OrderedDict = OrderedDict()
    lock = asyncio.Lock()

    def make_key(*args, **kwargs) -> str:
        key_data = (args, tuple(sorted(kwargs.items())))
        return hashlib.md5(pickle.dumps(key_data)).hexdigest()

    @wraps(func)
    async def wrapper(*args, **kwargs):
        key = make_key(*args, **kwargs)

        async with lock:
            if key in cache:
                cache.move_to_end(key)
                return cache[key]

        result = await func(*args, **kwargs)

        async with lock:
            cache[key] = result
            if len(cache) > maxsize:
                cache.popitem(last=False)

        return result

    wrapper.cache_clear = lambda: cache.clear()
    return wrapper
