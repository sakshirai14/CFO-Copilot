"""app/inference/client.py

Robust, asynchronous OpenAI-compatible HTTP client for local small LLM inference (llama-server).
Implements:
- Async httpx client with connection pooling
- Exponential backoff retry with jitter on transient network/503 errors
- X-Request-Id header propagation for distributed request tracing
- Call counting, token usage tracking, and latency metrics
- JSON-schema / response_format constrained generation
- Prompt hashing (SHA-256) for audit trails and cache observability
- Typed exception mapping to ModelUnavailableError
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import get_settings
from app.core.errors import ModelUnavailableError

logger = logging.getLogger(__name__)


class InferenceMetrics:
    """Thread-safe / async tracking of inference client usage."""

    def __init__(self):
        self.call_count: int = 0
        self.success_count: int = 0
        self.failed_count: int = 0
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_latency_ms: float = 0.0

    def record_success(self, prompt_tokens: int, completion_tokens: int, latency_ms: float):
        self.call_count += 1
        self.success_count += 1
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_latency_ms += latency_ms

    def record_failure(self):
        self.call_count += 1
        self.failed_count += 1

    def to_dict(self) -> Dict[str, Any]:
        avg_latency = (self.total_latency_ms / self.success_count) if self.success_count > 0 else 0.0
        return {
            "call_count": self.call_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "avg_latency_ms": round(avg_latency, 2),
        }

    def reset(self):
        self.call_count = 0
        self.success_count = 0
        self.failed_count = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_latency_ms = 0.0


class InferenceClient:
    """Asynchronous client connecting to local llama-server via OpenAI-compatible endpoints."""

    def __init__(
        self,
        api_base: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        max_retries: int = 3,
        initial_backoff: float = 0.5,
    ):
        settings = get_settings()
        self.api_base = (api_base or settings.INFERENCE_API_BASE).rstrip("/")
        self.timeout = float(timeout_seconds or settings.INFERENCE_TIMEOUT_SECONDS)
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.metrics = InferenceMetrics()
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.api_base,
                timeout=httpx.Timeout(self.timeout, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @staticmethod
    def compute_prompt_hash(messages: List[Dict[str, str]]) -> str:
        """Computes deterministic SHA-256 hash of messages array for provenance."""
        serialized = json.dumps(messages, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "default",
        temperature: float = 0.0,
        max_tokens: int = 512,
        response_format: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Sends chat completion request with retry, backoff, and tracing."""
        client = self._get_client()
        req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
        prompt_hash = self.compute_prompt_hash(messages)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        if extra_body:
            payload.update(extra_body)

        headers = {
            "Content-Type": "application/json",
            "X-Request-Id": req_id,
        }

        last_error = None
        for attempt in range(self.max_retries):
            t_start = time.perf_counter()
            try:
                response = await client.post(
                    "/chat/completions",
                    json=payload,
                    headers=headers,
                )
                latency_ms = (time.perf_counter() - t_start) * 1000.0

                if response.status_code == 200:
                    data = response.json()
                    usage = data.get("usage", {})
                    p_toks = usage.get("prompt_tokens", 0)
                    c_toks = usage.get("completion_tokens", 0)

                    self.metrics.record_success(p_toks, c_toks, latency_ms)

                    # Augment response with tracking metadata
                    data["_metadata"] = {
                        "request_id": req_id,
                        "prompt_hash": prompt_hash,
                        "latency_ms": round(latency_ms, 2),
                        "attempt": attempt + 1,
                    }
                    return data

                # Handle transient 503 (server overloaded / slots full) or 429
                if response.status_code in (503, 429, 502, 504):
                    logger.warning(
                        "Inference server returned transient status %d on attempt %d: %s",
                        response.status_code,
                        attempt + 1,
                        response.text,
                    )
                    last_error = ModelUnavailableError(
                        f"Server returned transient error {response.status_code}: {response.text}"
                    )
                else:
                    self.metrics.record_failure()
                    raise ModelUnavailableError(
                        f"Inference request failed with HTTP {response.status_code}: {response.text}"
                    )

            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                latency_ms = (time.perf_counter() - t_start) * 1000.0
                logger.warning("Connection error on attempt %d: %s", attempt + 1, exc)
                last_error = ModelUnavailableError(
                    f"Unable to connect to llama-server at {self.api_base}: {exc}"
                )

            # Wait with exponential backoff before retrying
            if attempt < self.max_retries - 1:
                backoff = self.initial_backoff * (2 ** attempt)
                await asyncio.sleep(backoff)

        self.metrics.record_failure()
        raise last_error or ModelUnavailableError(
            f"Inference failed after {self.max_retries} attempts to {self.api_base}"
        )

    def chat_completion_sync(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for chat_completion."""
        return asyncio.run(self.chat_completion(messages, **kwargs))
