"""
Resilience Utilities — Circuit Breaker & Retry.

"""
import time
import functools
import logging
import random
from enum import Enum
from typing import Callable, TypeVar, Optional

from ..core.domain.exceptions import CircuitOpenError

logger = logging.getLogger(__name__)
T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════
# Circuit Breaker
# ═══════════════════════════════════════════════════════════════

class CircuitState(Enum):
    CLOSED = "closed"        # normal — requests flow through
    OPEN = "open"            # tripped — fail fast
    HALF_OPEN = "half_open"  # testing — allow one request


class CircuitBreaker:
    """
    Prevents cascading failures in microservice calls.

    States:
    CLOSED → normal operation, counting failures
    OPEN → too many failures, reject immediately (fail fast)
    HALF_OPEN → after timeout, try one request to see if recovered
    """

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        reset_timeout_seconds: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout_seconds
        self.half_open_max = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if self._last_failure_time and \
               (time.time() - self._last_failure_time) > self.reset_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info(f"circuit_half_open: {self.service_name}")
        return self._state

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute a function through the circuit breaker."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            raise CircuitOpenError(self.service_name)

        if current_state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max:
                raise CircuitOpenError(self.service_name)
            self._half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            logger.info(f"circuit_closed: {self.service_name} (recovered)")
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                f"circuit_opened: {self.service_name} "
                f"(failures={self._failure_count})"
            )


# ═══════════════════════════════════════════════════════════════
# Retry Decorator with Exponential Backoff
# ═══════════════════════════════════════════════════════════════

def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential: bool = True,
    jitter: bool = True,
    exceptions: tuple = (Exception,),
):
    """
    Retry decorator with exponential backoff and jitter.


    Usage:
        @retry(max_attempts=3, base_delay=1.0)
        def call_external_service():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"retry_exhausted: {func.__name__} "
                            f"after {max_attempts} attempts",
                            exc_info=True,
                        )
                        raise

                    # Calculate delay
                    if exponential:
                        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    else:
                        delay = base_delay

                    if jitter:
                        delay *= (0.5 + random.random())  # ±50% jitter

                    logger.warning(
                        f"retry_attempt: {func.__name__} "
                        f"attempt={attempt}/{max_attempts} "
                        f"delay={delay:.2f}s error={e}"
                    )
                    time.sleep(delay)

            raise last_exception
        return wrapper
    return decorator
