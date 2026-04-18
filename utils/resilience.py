"""Resilience utilities: Retries and simple Circuit Breaker."""

from __future__ import annotations
import time
import functools
import logging
from typing import Callable, Any, TypeVar

T = TypeVar("T")
_log = logging.getLogger(__name__)

def retry(
    max_attempts: int = 3, 
    base_delay: float = 1.0, 
    exceptions: tuple = (Exception,)
) -> Callable:
    """Decorator for exponential backoff retries."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    if attempts == max_attempts:
                        _log.error(f"Final attempt failed for {func.__name__}: {e}")
                        raise
                    delay = base_delay * (2 ** (attempts - 1))
                    _log.warning(f"Attempt {attempts} failed for {func.__name__}. Retrying in {delay:.2f}s... Error: {e}")
                    time.sleep(delay)
            return func(*args, **kwargs) # Should not be reachable
        return wrapper
    return decorator

class CircuitBreaker:
    """Very simple circuit breaker state machine."""
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED" # "CLOSED", "OPEN", "HALF-OPEN"

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "HALF-OPEN"
                else:
                    raise RuntimeWarning(f"Circuit {func.__name__} is OPEN. Failing fast.")

            try:
                result = func(*args, **kwargs)
                if self.state == "HALF-OPEN":
                    self.state = "CLOSED"
                    self.failures = 0
                return result
            except Exception as e:
                self.failures += 1
                self.last_failure_time = time.time()
                if self.failures >= self.failure_threshold:
                    self.state = "OPEN"
                    _log.error(f"Circuit breaker for {func.__name__} TRIPPED to OPEN state.")
                raise e
        return wrapper
