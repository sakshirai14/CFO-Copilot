"""tests/unit/test_inference_client.py

Unit tests for InferenceClient with mocked HTTP transports.
Verifies retry logic, header propagation, prompt hashing, metrics, and error handling.
"""

import asyncio
import json
import pytest
import httpx

from app.core.errors import ModelUnavailableError
from app.inference.client import InferenceClient


class MockOpenAITransport(httpx.AsyncBaseTransport):
    """Mock HTTP transport returning controlled responses."""

    def __init__(self, responses):
        self.responses = responses
        self.requests = []
        self.idx = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.idx < len(self.responses):
            resp = self.responses[self.idx]
            self.idx += 1
            if isinstance(resp, Exception):
                raise resp
            return resp
        return httpx.Response(500, text="No more mock responses")


def test_client_success_response():
    """Client parses OpenAI-compatible response and tracks metrics."""
    async def _test():
        mock_body = {
            "id": "chatcmpl-test-1",
            "object": "chat.completion",
            "created": 12345678,
            "model": "qwen2.5-3b-instruct",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": '{"status": "ok", "answer": "Test answer"}'},
                    "finish_reason": "stop"
                }
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}
        }

        mock_resp = httpx.Response(200, json=mock_body)
        transport = MockOpenAITransport([mock_resp])

        client = InferenceClient(api_base="http://testserver/v1", timeout_seconds=5)
        client._client = httpx.AsyncClient(transport=transport, base_url="http://testserver/v1")

        messages = [{"role": "user", "content": "Hello"}]
        res = await client.chat_completion(messages, request_id="req_custom_1")

        assert res["choices"][0]["message"]["content"] == '{"status": "ok", "answer": "Test answer"}'
        assert res["_metadata"]["request_id"] == "req_custom_1"
        assert res["_metadata"]["attempt"] == 1
        assert "prompt_hash" in res["_metadata"]

        # Check metrics
        metrics = client.metrics.to_dict()
        assert metrics["call_count"] == 1
        assert metrics["success_count"] == 1
        assert metrics["total_prompt_tokens"] == 50
        assert metrics["total_completion_tokens"] == 20
        assert metrics["total_tokens"] == 70

        # Check request headers
        sent_req = transport.requests[0]
        assert sent_req.headers["X-Request-Id"] == "req_custom_1"
        await client.close()

    asyncio.run(_test())


def test_client_retries_transient_503():
    """Client catches 503, backs off, and succeeds on second attempt."""
    async def _test():
        resp_503 = httpx.Response(503, text="Server slots currently full")
        resp_200 = httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": "Recovered"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}
        })

        transport = MockOpenAITransport([resp_503, resp_200])

        client = InferenceClient(api_base="http://testserver/v1", max_retries=3, initial_backoff=0.01)
        client._client = httpx.AsyncClient(transport=transport, base_url="http://testserver/v1")

        res = await client.chat_completion([{"role": "user", "content": "Retry test"}])
        assert res["choices"][0]["message"]["content"] == "Recovered"
        assert res["_metadata"]["attempt"] == 2
        assert len(transport.requests) == 2
        await client.close()

    asyncio.run(_test())


def test_client_exhausts_retries_and_raises():
    """When retries are exhausted, client raises ModelUnavailableError."""
    async def _test():
        resp_503 = httpx.Response(503, text="Overloaded")
        transport = MockOpenAITransport([resp_503, resp_503, resp_503])

        client = InferenceClient(api_base="http://testserver/v1", max_retries=3, initial_backoff=0.01)
        client._client = httpx.AsyncClient(transport=transport, base_url="http://testserver/v1")

        with pytest.raises(ModelUnavailableError) as exc_info:
            await client.chat_completion([{"role": "user", "content": "Fail test"}])
        assert "transient error 503" in str(exc_info.value)
        assert client.metrics.failed_count == 1
        await client.close()

    asyncio.run(_test())


def test_prompt_hash_determinism():
    """Identical messages produce identical prompt hashes."""
    m1 = [{"role": "system", "content": "Sys"}, {"role": "user", "content": "User"}]
    m2 = [{"role": "system", "content": "Sys"}, {"role": "user", "content": "User"}]
    m3 = [{"role": "system", "content": "Diff"}, {"role": "user", "content": "User"}]

    h1 = InferenceClient.compute_prompt_hash(m1)
    h2 = InferenceClient.compute_prompt_hash(m2)
    h3 = InferenceClient.compute_prompt_hash(m3)

    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64
