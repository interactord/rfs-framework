"""
Function Decorators - Memoization, throttling, debouncing, and more

Provides decorators for caching, rate limiting, and other cross-cutting concerns.
"""

import asyncio
import hashlib
import logging
import pickle
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from functools import wraps
from threading import Lock, Timer
from typing import Any, Callable, Dict, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class MemoizeCache:
    """LRU cache for memoization."""

    def __init__(self, maxsize: int = 128) -> None:
        self.cache: OrderedDict = OrderedDict()
        self.maxsize = maxsize
        self.lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                return self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        with self.lock:
            if key in self.cache:
                # Update and move to end
                self.cache.move_to_end(key)
            self.cache[key] = value
            # Remove oldest if over capacity
            if len(self.cache) > self.maxsize:
                self.cache.popitem(last=False)

    def clear(self) -> None:
        with self.lock:
            self.cache.clear()


def memoize(
    maxsize=128,
    ttl=None,
    key_func: Optional[Callable[..., str]] = None,
) -> Callable:
    """
    Memoization decorator with LRU cache and optional TTL.

    Args:
        maxsize: Maximum cache size
        ttl: Time to live for cached values
        key_func: Custom function to generate cache keys

    Returns:
        Memoized function

    Example:
        >>> @memoize(maxsize=100, ttl=timedelta(minutes=5))
        ... def expensive_computation(x, y):
        ...     time.sleep(1)  # Simulate expensive operation
        ...     return x ** y
        >>> expensive_computation(2, 10)  # Takes 1 second
        1024
        >>> expensive_computation(2, 10)  # Returns immediately
        1024
    """

    def decorator(func: Callable) -> Callable:
        cache = MemoizeCache(maxsize)
        cache_times: Dict[str, datetime] = {}

        def make_key(*args, **kwargs) -> str:
            if key_func:
                return key_func(*args, **kwargs)
            # Default key generation
            key_data = (args, tuple(sorted(kwargs.items())))
            return hashlib.md5(pickle.dumps(key_data)).hexdigest()

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            key = make_key(*args, **kwargs)

            # Check if cached value exists and is valid
            cached = cache.get(key)
            if cached is not None:
                if ttl is None:
                    return cached
                # Check TTL
                cache_time = cache_times.get(key)
                if cache_time and datetime.now() - cache_time < ttl:
                    return cached

            # Compute and cache result
            result = func(*args, **kwargs)
            cache.set(key, result)
            if ttl:
                cache_times[key] = datetime.now()

            return result

        wrapper.cache_clear = cache.clear
        wrapper.cache = cache
        return wrapper

    return decorator


def throttle(rate: float, per: float = 1.0, burst=1) -> Callable:
    """
    Throttle function calls to a maximum rate.

    Args:
        rate: Maximum number of calls
        per: Time period in seconds
        burst: Allow burst of calls

    Returns:
        Throttled function

    Example:
        >>> @throttle(rate=3, per=1.0)  # Max 3 calls per second
        ... def api_call():
        ...     print(f"Called at {time.time()}")
        >>> for _ in range(5):
        ...     api_call()  # Only 3 will execute immediately
    """

    def decorator(func: Callable) -> Callable:
        min_interval = per / rate
        last_called = [0.0]
        burst_count = [0]
        lock = Lock()

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            with lock:
                now = time.time()
                time_since_last = now - last_called[0]

                if time_since_last >= min_interval:
                    # Enough time has passed
                    last_called[0] = now
                    burst_count[0] = 1
                    return func(*args, **kwargs)
                elif burst_count[0] < burst:
                    # Use burst allowance
                    burst_count[0] += 1
                    return func(*args, **kwargs)
                else:
                    # Need to wait
                    sleep_time = min_interval - time_since_last
                    time.sleep(sleep_time)
                    last_called[0] = time.time()
                    burst_count[0] = 1
                    return func(*args, **kwargs)

        return wrapper

    return decorator


def debounce(wait: float, immediate=False) -> Callable:
    """
    Debounce function calls - only execute after wait period of no calls.

    Args:
        wait: Wait time in seconds
        immediate: Execute on leading edge instead of trailing

    Returns:
        Debounced function

    Example:
        >>> @debounce(wait=0.5)
        ... def save_document():
        ...     print("Document saved")
        >>> # Rapid calls will only trigger once after 0.5s of inactivity
    """

    def decorator(func: Callable) -> Callable:
        timer = [None]
        lock = Lock()

        @wraps(func)
        def wrapper(*args, **kwargs):
            def call_func():
                timer[0] = None
                if not immediate:
                    func(*args, **kwargs)

            with lock:
                if timer[0] is not None:
                    timer[0].cancel()

                if immediate and timer[0] is None:
                    func(*args, **kwargs)

                timer[0] = Timer(wait, call_func)
                timer[0].start()

        wrapper.cancel = lambda: timer[0].cancel() if timer[0] else None
        return wrapper

    return decorator


def retry(
    max_attempts=3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    on_failure: Optional[Callable[[Exception, int], None]] = None,
) -> Callable:
    """
    Retry function on failure with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier
        exceptions: Exceptions to catch and retry
        on_failure: Callback on each failure

    Returns:
        Function with retry logic

    Example:
        >>> @retry(max_attempts=3, delay=1.0, backoff=2.0)
        ... def unreliable_network_call():
        ...     # Might fail sometimes
        ...     pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if on_failure:
                        on_failure(e, attempt + 1)

                    if attempt < max_attempts - 1:
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.warning(
                            f"Function {func.__name__} failed after {max_attempts} attempts"
                        )

            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def timeout(seconds: float, error_message="Function call timed out") -> Callable:
    """
    Timeout decorator for functions (works with threads).

    Args:
        seconds: Timeout in seconds
        error_message: Error message on timeout

    Returns:
        Function with timeout

    Example:
        >>> @timeout(seconds=5.0)
        ... def slow_function():
        ...     time.sleep(10)
        >>> slow_function()  # Raises TimeoutError after 5 seconds
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            import queue
            import threading

            result_queue = queue.Queue()
            exception_queue = queue.Queue()

            def target():
                try:
                    result = func(*args, **kwargs)
                    result_queue.put(result)
                except Exception as e:
                    exception_queue.put(e)

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=seconds)

            if thread.is_alive():
                raise TimeoutError(error_message)

            if not exception_queue.empty():
                raise exception_queue.get()

            return result_queue.get()

        return wrapper

    return decorator


def rate_limit(calls: int, period: timedelta, scope="global") -> Callable:
    """
    Rate limiting decorator with configurable scope.

    Args:
        calls: Number of allowed calls
        period: Time period
        scope: Rate limit scope ('global', 'user', 'ip')

    Returns:
        Rate limited function

    Example:
        >>> @rate_limit(calls=100, period=timedelta(hours=1))
        ... def api_endpoint():
        ...     return "response"
    """

    def decorator(func: Callable) -> Callable:
        call_times = {}
        lock = Lock()

        def get_scope_key(*args, **kwargs) -> str:
            if scope == "global":
                return "global"
            elif scope == "user" and "user" in kwargs:
                return f"user:{kwargs['user']}"
            elif scope == "ip" and "ip" in kwargs:
                return f"ip:{kwargs['ip']}"
            else:
                return "global"

        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                scope_key = get_scope_key(*args, **kwargs)
                now = datetime.now()

                if scope_key not in call_times:
                    call_times[scope_key] = []

                # Remove old calls outside the period
                call_times[scope_key] = [
                    call_time
                    for call_time in call_times[scope_key]
                    if now - call_time < period
                ]

                if len(call_times[scope_key]) >= calls:
                    raise Exception(f"Rate limit exceeded: {calls} calls per {period}")

                call_times[scope_key].append(now)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def circuit_breaker(
    failure_threshold=5,
    recovery_timeout: float = 60.0,
    expected_exception: type = Exception,
) -> Callable:
    """
    Circuit breaker pattern to prevent cascading failures.

    Args:
        failure_threshold: Failures before opening circuit
        recovery_timeout: Time before attempting recovery
        expected_exception: Exception type to track

    Returns:
        Function with circuit breaker

    Example:
        >>> @circuit_breaker(failure_threshold=3, recovery_timeout=30)
        ... def external_service_call():
        ...     # Might fail and trigger circuit breaker
        ...     pass
    """

    def decorator(func: Callable) -> Callable:
        failure_count = [0]
        last_failure_time = [None]
        state = ["closed"]  # closed, open, half-open
        lock = Lock()

        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                now = time.time()

                # Check if circuit should be reset
                if state[0] == "open":
                    if (
                        last_failure_time[0]
                        and now - last_failure_time[0] > recovery_timeout
                    ):
                        state[0] = "half-open"
                        failure_count[0] = 0
                    else:
                        raise Exception("Circuit breaker is open")

                try:
                    result = func(*args, **kwargs)
                    # Success - reset failure count
                    if state[0] == "half-open":
                        state[0] = "closed"
                    failure_count[0] = 0
                    return result

                except expected_exception as e:
                    failure_count[0] += 1
                    last_failure_time[0] = now

                    if failure_count[0] >= failure_threshold:
                        state[0] = "open"
                        logger.warning(f"Circuit breaker opened for {func.__name__}")

                    raise e

        wrapper.state = lambda: state[0]
        wrapper.reset = lambda: (
            failure_count.__setitem__(0, 0),
            state.__setitem__(0, "closed"),
        )

        return wrapper

    return decorator


def lazy(func: Callable[[], T]) -> Callable[[], T]:
    """
    Lazy evaluation - compute value only when first accessed.

    Args:
        func: Function to evaluate lazily

    Returns:
        Lazy function

    Example:
        >>> @lazy
        ... def expensive_data():
        ...     print("Computing...")
        ...     return [i ** 2 for i in range(1000000)]
        >>> # Not computed yet
        >>> result = expensive_data()  # Now computed
        Computing...
        >>> result2 = expensive_data()  # Uses cached result
    """
    cache: List[Any] = []
    lock = Lock()

    @wraps(func)
    def wrapper():
        with lock:
            if not cache:
                cache.append(func())
        return cache[0]

    return wrapper


def once(func: Callable) -> Callable:
    """
    Ensure function is called only once.

    Args:
        func: Function to call once

    Returns:
        Function that executes only once

    Example:
        >>> @once
        ... def initialize():
        ...     print("Initializing...")
        ...     return "initialized"
        >>> initialize()  # Prints and returns
        Initializing...
        'initialized'
        >>> initialize()  # Returns cached result
        'initialized'
    """
    called = [False]
    result = [None]
    lock = Lock()

    @wraps(func)
    def wrapper(*args, **kwargs):
        with lock:
            if not called[0]:
                result[0] = func(*args, **kwargs)
                called[0] = True
        return result[0]

    return wrapper
