"""app/agents/root_agent.py

CfoCopilotRootAgent implemented on Google Agent Development Kit (ADK).
Root orchestrator coordinating RouterAgent, FactsAgent, AnswerWriter, and VerifierAgent.
Enforces:
- Deterministic routing (SQL for structured, RAG for unstructured, Both for mixed).
- Tight LLM call budget (average <= 2 LLM calls per query).
- Guaranteed 0.0% wrong-number rate via deterministic verification and fallback.
- Strongly-typed AnswerEnvelope ("Show Your Work" contract).
Zero database imports, zero SQL keywords.
"""

import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional
from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event
from app.agents.answer_writer import AnswerWriterAgent
from app.agents.facts_agent import FactsAgent
from app.agents.router_agent import RouterAgent
from app.agents.verifier_agent import VerifierAgent
from app.domain.agent_envelope import (
    AnswerEnvelope,
    AnswerStatus,
    FactItem,
    ResolvedQuery,
    RouteType,
    VerificationResult,
)
from app.domain.answer_composer import AnswerComposer


class CfoCopilotRootAgent(BaseAgent):
    """Root ADK Agent for executive CFO financial intelligence."""

    name: str = "CfoCopilotRootAgent"
    description: str = "Root financial copilot orchestrator. Guarantees deterministic accuracy and verified grounding."

    router: RouterAgent = RouterAgent()
    facts_agent: FactsAgent = FactsAgent()
    answer_writer: AnswerWriterAgent = AnswerWriterAgent()
    verifier: VerifierAgent = VerifierAgent()

    async def answer(
        self,
        question: str,
        tenant: str = "acme",
        prior_context: Optional[str] = None,
        request_id: Optional[str] = None,
        is_test: bool = False,
        force_vector_failure: bool = False
    ) -> AnswerEnvelope:
        """Main entry point: processes query through the ADK agent graph."""
        t_start = time.perf_counter()
        req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
        llm_calls_made = 0
        facts: List[FactItem] = []
        caveats: List[str] = []

        # 1. Step 1: Deterministic Query Resolution & Routing
        query: ResolvedQuery = self.router.resolve(question, prior_context=prior_context)

        # 2. Early-Exit Routes (0 LLM Calls)
        if query.route == RouteType.REFUSAL:
            refusal_text = AnswerComposer.compose_refusal_answer(query)
            latency = (time.perf_counter() - t_start) * 1000.0
            return AnswerEnvelope(
                request_id=req_id,
                question=question,
                route=query.route,
                status=AnswerStatus.REFUSED,
                answer=refusal_text,
                llm_calls_made=0,
                latency_ms=round(latency, 2),
                facts_used=[],
                caveats=[query.refusal_reason] if query.refusal_reason else [],
                verification=VerificationResult(is_valid=True)
            )

        if query.route == RouteType.CHITCHAT:
            chat_text = AnswerComposer.compose_chitchat_answer()
            latency = (time.perf_counter() - t_start) * 1000.0
            return AnswerEnvelope(
                request_id=req_id,
                question=question,
                route=query.route,
                status=AnswerStatus.OK,
                answer=chat_text,
                llm_calls_made=0,
                latency_ms=round(latency, 2),
                facts_used=[],
                caveats=[],
                verification=VerificationResult(is_valid=True)
            )

        # 3. Step 2: Deterministic Data Retrieval (Pure Domain Services)
        facts, caveats = self.facts_agent.fetch_facts(
            query,
            tenant_id=tenant,
            is_test=is_test,
            force_vector_failure=force_vector_failure
        )

        # 4. Step 3: Answer Composition
        # Path A: Pure Structured KPI lookup -> Deterministic SQL Template (0 LLM Calls)
        if query.route == RouteType.STRUCTURED:
            candidate_answer = AnswerComposer.compose_structured_answer(query, facts)
            status = AnswerStatus.OK if facts and any(f.status == "ok" for f in facts) else AnswerStatus.MISSING_DATA
            shipped_answer, ver_res, _ = self.verifier.verify_and_intercept(candidate_answer, facts, query)
            latency = (time.perf_counter() - t_start) * 1000.0
            return AnswerEnvelope(
                request_id=req_id,
                question=question,
                route=query.route,
                status=status,
                answer=shipped_answer,
                llm_calls_made=0,
                latency_ms=round(latency, 2),
                facts_used=facts,
                caveats=caveats,
                verification=ver_res
            )

        # Path B: Unstructured or Mixed -> Language Synthesis via AnswerWriter (1 LLM Call)
        if not facts:
            # Degraded: No facts found for narrative query
            candidate_answer = "Refused: Requested financial disclosures could not be located in SEC filings."
            latency = (time.perf_counter() - t_start) * 1000.0
            return AnswerEnvelope(
                request_id=req_id,
                question=question,
                route=query.route,
                status=AnswerStatus.MISSING_DATA,
                answer=candidate_answer,
                llm_calls_made=0,
                latency_ms=round(latency, 2),
                facts_used=[],
                caveats=caveats,
                verification=VerificationResult(is_valid=True)
            )

        try:
            llm_payload = await self.answer_writer.write_answer(question, facts, caveats)
            llm_calls_made += 1
            candidate_text = llm_payload.get("answer", "")
            status_str = llm_payload.get("status", "ok")
            status_enum = AnswerStatus.OK if status_str == "ok" else AnswerStatus.REFUSED
            extra_caveats = llm_payload.get("caveats", [])
            all_caveats = caveats + extra_caveats
            llm_meta = llm_payload.get("_llm_metadata")
        except Exception as e:
            # Degraded mode fallback on model error/timeout
            candidate_text = AnswerComposer.compose_fallback_answer(facts, query)
            status_enum = AnswerStatus.OK
            all_caveats = caveats + [f"Model inference failed ({str(e)}); served certified template fallback."]
            llm_meta = None

        # 5. Step 4: Strict Verification & Grounding Interception
        shipped_answer, ver_res, fallback_triggered = self.verifier.verify_and_intercept(candidate_text, facts, query)
        if fallback_triggered:
            all_caveats.append("Model output contained ungrounded claims; intercepted and replaced with certified SQL fallback.")

        latency = (time.perf_counter() - t_start) * 1000.0
        return AnswerEnvelope(
            request_id=req_id,
            question=question,
            route=query.route,
            status=status_enum,
            answer=shipped_answer,
            llm_calls_made=llm_calls_made,
            latency_ms=round(latency, 2),
            facts_used=facts,
            caveats=all_caveats,
            verification=ver_res,
            llm_metadata=llm_meta
        )

    async def run_async(self, parent_context: InvocationContext) -> AsyncGenerator[Event, None]:
        """ADK pipeline execution hook."""
        user_msg = getattr(parent_context, "user_content", "") or ""
        env = await self.answer(user_msg)
        yield Event(
            author=self.name,
            content=env.answer
        )


async def answer(
    question: str,
    tenant: str = "acme",
    prior_context: Optional[str] = None,
    request_id: Optional[str] = None
) -> AnswerEnvelope:
    """Module-level entry point matching specified signature."""
    agent = CfoCopilotRootAgent()
    return await agent.answer(
        question=question,
        tenant=tenant,
        prior_context=prior_context,
        request_id=request_id
    )

