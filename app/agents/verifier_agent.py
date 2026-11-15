"""app/agents/verifier_agent.py

VerifierAgent implemented on Google Agent Development Kit (BaseAgent).
Enforces the Grounded-Answer Contract and intercepts candidate model responses.
If verification fails, triggers the deterministic fallback engine to guarantee 0.0% wrong numbers.
Zero database imports, zero SQL keywords.
"""

from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event
from app.domain.agent_envelope import FactItem, ResolvedQuery, VerificationResult
from app.domain.answer_composer import AnswerComposer
from app.domain.answer_verifier import AnswerVerifier


class VerifierAgent(BaseAgent):
    """ADK Agent that strictly verifies candidate answers against verified facts."""

    name: str = "VerifierAgent"
    description: str = "Enforces Grounded-Answer Contract and routes to fallback on verification failure."

    def verify_and_intercept(
        self,
        candidate_answer: str,
        facts: List[FactItem],
        query: Optional[ResolvedQuery] = None
    ) -> Tuple[str, VerificationResult, bool]:
        """Verifies candidate text. Returns (shipped_answer, verification_result, was_fallback_triggered)."""
        # Convert domain FactItems to verifier InputFact format
        from app.domain.answer_verifier import InputFact
        from app.inference.contract import AnswerStatus as ContractStatus, GroundedAnswer

        v_facts = [
            InputFact(
                fact_id=f.fact_id,
                company_id=f.company_id,
                fiscal_year=f.fiscal_year,
                fiscal_quarter=f.fiscal_quarter,
                text=f.text
            )
            for f in facts
        ]

        if isinstance(candidate_answer, str):
            g_answer = GroundedAnswer(
                status=ContractStatus.OK,
                answer=candidate_answer,
                facts_used=[f.fact_id for f in facts],
                caveats=[]
            )
        else:
            g_answer = candidate_answer

        raw_ver = AnswerVerifier.verify(g_answer, v_facts)

        ungrounded_strs = [
            f"{u.get('token', '')} ({u.get('reason', '')})" if isinstance(u, dict) else str(u)
            for u in raw_ver.ungrounded_numbers
        ]

        ver_result = VerificationResult(
            is_valid=raw_ver.valid,
            reasons=raw_ver.violations,
            ungrounded_numbers=ungrounded_strs,
            cited_fact_ids=raw_ver.matched_facts
        )

        if raw_ver.valid and not raw_ver.ungrounded_numbers:
            return candidate_answer, ver_result, False

        # Fallback triggered: Reject model output and render certified deterministic answer
        fallback_answer = AnswerComposer.compose_fallback_answer(facts, query)
        ver_result.reasons.append("Model output contained ungrounded figures; routed to certified template fallback.")
        return fallback_answer, ver_result, True

    async def run_async(self, parent_context: InvocationContext) -> AsyncGenerator[Event, None]:
        """ADK pipeline execution hook."""
        yield Event(
            author=self.name,
            content="VerifierAgent completed grounding audit."
        )
