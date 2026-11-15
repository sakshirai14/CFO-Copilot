"""app/agents/router_agent.py

RouterAgent implemented on Google Agent Development Kit (ADK).
Deterministically resolves natural language user queries into structured routing metadata.
No LLM calls, zero database imports, zero SQL keywords.
"""

from typing import Any, AsyncGenerator, Optional
from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event
from app.domain.agent_envelope import ResolvedQuery, RouteType
from app.domain.question_resolver import QuestionResolver


class RouterAgent(BaseAgent):
    """ADK Agent for deterministic query resolution and route classification."""

    name: str = "RouterAgent"
    description: str = "Classifies user inquiries into STRUCTURED, UNSTRUCTURED, MIXED, REFUSAL, or CHITCHAT."

    def resolve(self, question: str) -> ResolvedQuery:
        """Synchronously resolves query into typed ResolvedQuery object."""
        return QuestionResolver.resolve(question)

    async def run_async(self, parent_context: InvocationContext) -> AsyncGenerator[Event, None]:
        """ADK pipeline execution hook."""
        user_msg = getattr(parent_context, "user_content", "") or ""
        resolved = self.resolve(user_msg)
        yield Event(
            author=self.name,
            content=f"Route classified as {resolved.route.value} (entities: {resolved.company_ids}, period: {resolved.fiscal_year}Q{resolved.fiscal_quarter})"
        )
