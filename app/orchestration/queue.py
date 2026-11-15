"""app/orchestration/queue.py

Bounded Concurrency Queue for LLM-Path Requests.
Enforces Foundation Lock Crowd (Concurrency) and Foundation Lock Fallback (Degradation).
- Max in-flight: 16 (matching llama-server -np 16 slots).
- Max waiting buffer: 16 requests.
- Returns HTTP 429 with Retry-After when buffer is full.
- Degrades into extractive fallback if queue wait timeout is reached.
"""

import asyncio
import time
from typing import Optional
from app.core.config import get_settings


class QueueFullError(Exception):
    """Raised when the LLM request admission queue exceeds max waiting capacity."""
    def __init__(self, message: str = "LLM concurrency queue full. All slots and waiting buffer saturated.", retry_after: int = 5):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class QueueTimeoutError(Exception):
    """Raised when request waits in queue longer than timeout deadline."""
    def __init__(self, message: str = "Request queue wait deadline exceeded.", retry_after: int = 5):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


class BoundedLlmQueue:
    """Bounded semaphore queue sized to measured hardware concurrency."""

    def __init__(
        self,
        max_in_flight: int = 16,
        max_waiting: int = 16,
        wait_timeout_seconds: float = 10.0
    ):
        self.max_in_flight = max_in_flight
        self.max_waiting = max_waiting
        self.wait_timeout = wait_timeout_seconds
        self._semaphore = asyncio.Semaphore(max_in_flight)
        self._waiting_count = 0
        self._active_count = 0
        self._lock = asyncio.Lock()

    @property
    def current_in_flight(self) -> int:
        return self._active_count

    @property
    def current_waiting(self) -> int:
        return self._waiting_count

    async def acquire(self, timeout: Optional[float] = None):
        """Attempts to acquire an execution slot, respecting queue bounds."""
        wait_deadline = timeout or self.wait_timeout

        async with self._lock:
            if self._waiting_count >= self.max_waiting:
                raise QueueFullError(
                    f"LLM concurrency queue saturated: {self._active_count} in-flight, {self._waiting_count} waiting.",
                    retry_after=5
                )
            self._waiting_count += 1

        try:
            t0 = time.perf_counter()
            await asyncio.wait_for(self._semaphore.acquire(), timeout=wait_deadline)
            wait_duration = time.perf_counter() - t0

            async with self._lock:
                self._waiting_count -= 1
                self._active_count += 1

            return wait_duration
        except asyncio.TimeoutError:
            async with self._lock:
                self._waiting_count -= 1
            raise QueueTimeoutError(
                f"Queue wait deadline exceeded ({wait_deadline}s).",
                retry_after=3
            )

    def release(self):
        """Releases the execution slot."""
        self._semaphore.release()
        self._active_count = max(0, self._active_count - 1)


# Global singleton instance
_llm_queue: Optional[BoundedLlmQueue] = None


def get_llm_queue() -> BoundedLlmQueue:
    global _llm_queue
    if _llm_queue is None:
        settings = get_settings()
        _llm_queue = BoundedLlmQueue(
            max_in_flight=settings.MAX_CONCURRENT_SESSIONS,  # 16
            max_waiting=settings.MAX_CONCURRENT_SESSIONS,     # 16
            wait_timeout_seconds=float(settings.REQUEST_QUEUE_TIMEOUT_SECONDS)  # 10s
        )
    return _llm_queue

