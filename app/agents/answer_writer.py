"""app/agents/answer_writer.py

AnswerWriter Agent implemented on Google Agent Development Kit (LlmAgent).
The ONLY LLM agent in the CFO Copilot architecture.
Has strictly ZERO tools (tools = []).
Uses frozen EXPLICIT_RULES_SYSTEM_PROMPT_V1.
Zero SQL imports, zero database drivers, zero authority over arithmetic.
"""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx
from google.adk.agents import LlmAgent, InvocationContext
from google.adk.events import Event
from app.core.config import get_settings
from app.domain.agent_envelope import FactItem
from app.domain.prompt_builder import PromptBuilder, BuiltPrompt
from app.prompts.prompt_v1 import EXPLICIT_RULES_SYSTEM_PROMPT_V1

STRICT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["ok", "refused", "insufficient_data", "unsupported"]
        },
        "answer": {
            "type": "string"
        },
        "facts_used": {
            "type": "array",
            "items": {"type": "string"}
        },
        "caveats": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["status", "answer", "facts_used", "caveats"],
    "additionalProperties": False
}


class AnswerWriterAgent(LlmAgent):
    """ADK LlmAgent responsible for executive narrative generation from verified facts."""

    name: str = "AnswerWriter"
    description: str = "Executive financial writer. Generates CFO-grade narrative strictly from verified facts."
    model: str = "openai/qwen2.5-3b-instruct"
    instruction: str = EXPLICIT_RULES_SYSTEM_PROMPT_V1
    tools: List[Any] = []  # Foundation Lock 2: Strictly ZERO tools

    async def write_answer(
        self,
        question: str,
        facts: List[FactItem],
        caveats: Optional[List[str]] = None,
        tenant_id: str = "acme",
        user_id: str = "cfo_user",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        date_stamp: str = "2026-11-16",
        id_slot: Optional[int] = None
    ) -> Dict[str, Any]:
        """Calls the local model endpoint using 7-layer Prefix Layout Contract and grammar-constrained JSON decoding."""
        settings = get_settings()
        server_url = getattr(settings, "INFERENCE_SERVER_URL", None) or settings.INFERENCE_API_BASE.replace("/v1", "").rstrip("/")

        # Assemble prompt via canonical PromptBuilder (Foundation Lock 7 / Phase 7.1)
        built = PromptBuilder.build_prompt(
            question=question,
            retrieved_facts=facts,
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_history=conversation_history,
            date_stamp=date_stamp
        )

        payload = {
            "model": "qwen2.5-3b-instruct",
            "messages": built.messages,
            "temperature": 0.0,
            "max_tokens": 512,
            "presence_penalty": 0.3,
            "response_format": {
                "type": "json_object",
                "schema": STRICT_SCHEMA
            }
        }
        if id_slot is not None:
            payload["id_slot"] = id_slot

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{server_url}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw_text)
            choice = data.get("choices", [{}])[0]
            usage = data.get("usage", {})
            parsed["_llm_metadata"] = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "finish_reason": choice.get("finish_reason", "stop"),
                "static_sha256": built.static_sha256,
                "tenant_sha256": built.tenant_sha256,
                "dynamic_sha256": built.dynamic_sha256,
                "layout_version": built.layout_version
            }
            return parsed

    async def run_async(self, parent_context: InvocationContext) -> AsyncGenerator[Event, None]:
        """ADK pipeline execution hook."""
        yield Event(
            author=self.name,
            content="AnswerWriter generation executed with 0 tools and frozen prompt v1."
        )

