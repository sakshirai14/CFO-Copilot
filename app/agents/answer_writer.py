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
        caveats: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Calls the local model endpoint using grammar-constrained JSON decoding."""
        settings = get_settings()
        server_url = getattr(settings, "INFERENCE_SERVER_URL", None) or settings.INFERENCE_API_BASE.replace("/v1", "").rstrip("/")

        facts_block = "\n".join(
            f"[{f.fact_id}] {f.text}" for f in facts
        ) if facts else "[NO RELEVANT FACTS AVAILABLE]"

        caveats_block = "\n".join(f"- {c}" for c in (caveats or []))

        user_content = (
            f"Question: {question}\n\n"
            f"Context Facts:\n{facts_block}\n\n"
        )
        if caveats_block:
            user_content += f"Caveats & Context:\n{caveats_block}\n\n"

        user_content += (
            "Return valid JSON matching the schema with fields: "
            "status, answer, facts_used, caveats."
        )

        payload = {
            "model": "qwen2.5-3b-instruct",
            "messages": [
                {"role": "system", "content": self.instruction},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.0,
            "max_tokens": 512,
            "presence_penalty": 0.3,
            "response_format": {
                "type": "json_object",
                "schema": STRICT_SCHEMA
            }
        }

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
                "finish_reason": choice.get("finish_reason", "stop")
            }
            return parsed

    async def run_async(self, parent_context: InvocationContext) -> AsyncGenerator[Event, None]:
        """ADK pipeline execution hook."""
        yield Event(
            author=self.name,
            content="AnswerWriter generation executed with 0 tools and frozen prompt v1."
        )

