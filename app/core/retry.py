"""app/core/retry.py

Robust retry mechanism with exponential backoff and jitter.
Implements Foundation Lock 4 (Idempotency & Retries).
Does not require external libraries.
"""

import functools
import logging
import random
import time
from typing import Callable, Tuple, Type, Any

logger = logging.getLogger(__name__)


def retry_with_backoff(
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    max_retries: int = 4,
    base_delay: float = 0.05,
    max_delay: float = 2.0,
    jitter: bool = True,
) -> Callable:
    """Decorator that retries a function with exponential backoff and optional jitter."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_err = None
            delay = base_delay

            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_err = e
                    if attempt == max_retries:
                        logger.error(
                            f"[retry] Function '{func.__name__}' failed on final attempt {attempt}/{max_retries}: {e}"
                        )
                        raise

                    sleep_time = delay * (1 + (random.random() if jitter else 0.0))
                    sleep_time = min(sleep_time, max_delay)
                    logger.warning(
                        f"[retry] Attempt {attempt}/{max_retries} of '{func.__name__}' failed with {e.__class__.__name__}: {e}. "
                        f"Retrying in {sleep_time:.3f}s..."
                    )
                    time.sleep(sleep_time)
                    delay *= 2

            if last_err:
                raise last_err

        return wrapper
    return decorator
