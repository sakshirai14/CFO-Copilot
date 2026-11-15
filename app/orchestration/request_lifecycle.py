"""app/orchestration/request_lifecycle.py

Orchestration Layer for Request Lifecycle Management.
Enforces:
- Lock Walls (Layering): Contains ZERO SQL strings, imports nothing from app.data.
- Lock Crowd (Concurrency): Bounded queueing for LLM path; 100% bypass for pure SQL.
- Lock Fallback (Degradation): Extractive fallback on queue timeout, model failure, or fault injection.
- Lock Black Box & Ledger (Provenance & Audit): Persists session messages and immutable answer_log.
- Lock Lantern (Observability): Emits Prometheus metrics and structured log contexts.
"""

import asyncio
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional
from app.agents.root_agent import CfoCopilotRootAgent
from app.core.metrics import metrics
from app.domain.agent_envelope import AnswerEnvelope, AnswerStatus, ResolvedQuery, RouteType, VerificationResult
from app.domain.answer_composer import AnswerComposer
from app.domain.session_service import SessionService
from app.orchestration.queue import QueueFullError, QueueTimeoutError, get_llm_queue


class RequestLifecycleManager:
    """Manages chat execution, queue admission, persistence, streaming, and fallback orchestration."""

    def __init__(self, is_test: bool = False):
        self.is_test = is_test
        self.root_agent = CfoCopilotRootAgent()
        self.session_service = SessionService(is_test=is_test)
        self.queue = get_llm_queue()

    async def execute_request(
        self,
        tenant_id: str,
        question: str,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        fault_inject: Optional[str] = None,
    ) -> AnswerEnvelope:
        """Executes a complete chat interaction turn with session persistence and queue management."""
        t_start = time.perf_counter()
        req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"

        # Fault Injection: Database Down
        if fault_inject == "db_down":
            import psycopg2
            raise psycopg2.OperationalError("Simulated database connection failure (FAULT_DB_DOWN).")

        # 1. Resolve prior context from session history if session_id is active
        prior_context = None
        if session_id:
            prior_context = self.session_service.get_last_resolved_slots(tenant_id, session_id)

        # 2. Pre-resolve query route to determine queue admission
        res_query: ResolvedQuery = self.root_agent.router.resolve(question, prior_context=prior_context)

        # Fault Injection: Queue Saturated
        if fault_inject == "queue_saturated":
            metrics.inc_counter("cfo_copilot_429_total")
            raise QueueFullError("LLM concurrency queue saturated (FAULT_QUEUE_SATURATED): 16 in-flight, 16 waiting.", retry_after=5)

        force_vec_fail = (fault_inject == "vector_fail")

        # 3. Path A: Template / Direct Routes -> 100% Queue Bypass (0 LLM Calls)
        if res_query.route in (RouteType.STRUCTURED, RouteType.REFUSAL, RouteType.CHITCHAT):
            envelope = await self.root_agent.answer(
                question=question,
                tenant=tenant_id,
                prior_context=prior_context,
                request_id=req_id,
                is_test=self.is_test,
                force_vector_failure=force_vec_fail
            )
            # Record metrics
            total_duration = time.perf_counter() - t_start
            metrics.observe("cfo_copilot_request_duration_seconds", total_duration, labels={"route": res_query.route.value})
            metrics.observe("cfo_copilot_ttft_first_content_seconds", total_duration, labels={"route": res_query.route.value})
            metrics.observe("cfo_copilot_ttft_verified_answer_seconds", total_duration, labels={"route": res_query.route.value})
            metrics.inc_counter("cfo_copilot_requests_total", 1.0, labels={"route": res_query.route.value, "status": envelope.status.value})

            # Persist turn
            self._persist_turn_data(tenant_id, session_id, req_id, question, envelope, res_query, t_start)
            return envelope

        # 4. Path B: LLM Path (UNSTRUCTURED / MIXED) -> Requires Bounded Queue Admission
        queue_wait_ms = 0.0
        degraded = False
        degraded_reason = None
        envelope = None

        try:
            # Fault Injection: Model Offline / Timeout
            if fault_inject == "model_offline":
                degraded = True
                degraded_reason = "Model server unreachable / connection refused (FAULT_MODEL_OFFLINE)"
                envelope = self._build_extractive_fallback_envelope(
                    req_id, question, res_query, tenant_id, t_start, degraded_reason
                )
                metrics.inc_counter("cfo_copilot_degraded_total")
                metrics.inc_counter("cfo_copilot_verifier_fallbacks_total")
            elif fault_inject == "model_oom":
                degraded = True
                degraded_reason = "Model server context limit / slot OOM; retry failed (FAULT_MODEL_OOM)"
                envelope = self._build_extractive_fallback_envelope(
                    req_id, question, res_query, tenant_id, t_start, degraded_reason
                )
                metrics.inc_counter("cfo_copilot_degraded_total")
                metrics.inc_counter("cfo_copilot_verifier_fallbacks_total")
            else:
                # Acquire execution slot in bounded queue
                t_queue = time.perf_counter()
                wait_sec = await self.queue.acquire()
                queue_wait_ms = wait_sec * 1000.0
                metrics.observe("cfo_copilot_queue_wait_seconds", wait_sec)
                metrics.set_gauge("cfo_copilot_queue_in_flight", float(self.queue.current_in_flight))
                metrics.set_gauge("cfo_copilot_queue_waiting", float(self.queue.current_waiting))

                try:
                    # Execute agent with generation deadline
                    envelope = await asyncio.wait_for(
                        self.root_agent.answer(
                            question=question,
                            tenant=tenant_id,
                            prior_context=prior_context,
                            request_id=req_id,
                            is_test=self.is_test,
                            force_vector_failure=force_vec_fail
                        ),
                        timeout=25.0
                    )
                finally:
                    self.queue.release()
                    metrics.set_gauge("cfo_copilot_queue_in_flight", float(self.queue.current_in_flight))
                    metrics.set_gauge("cfo_copilot_queue_waiting", float(self.queue.current_waiting))

        except QueueFullError:
            metrics.inc_counter("cfo_copilot_429_total")
            raise
        except (QueueTimeoutError, asyncio.TimeoutError) as e:
            degraded = True
            degraded_reason = f"LLM queue wait/generation deadline exceeded ({str(e)})"
            envelope = self._build_extractive_fallback_envelope(
                req_id, question, res_query, tenant_id, t_start, degraded_reason
            )
            metrics.inc_counter("cfo_copilot_degraded_total")
            metrics.inc_counter("cfo_copilot_verifier_fallbacks_total")
        except Exception as e:
            degraded = True
            degraded_reason = f"Model execution error: {str(e)}"
            envelope = self._build_extractive_fallback_envelope(
                req_id, question, res_query, tenant_id, t_start, degraded_reason
            )
            metrics.inc_counter("cfo_copilot_degraded_total")
            metrics.inc_counter("cfo_copilot_verifier_fallbacks_total")

        # Record metrics
        total_duration = time.perf_counter() - t_start
        metrics.observe("cfo_copilot_request_duration_seconds", total_duration, labels={"route": res_query.route.value})
        metrics.observe("cfo_copilot_ttft_verified_answer_seconds", total_duration, labels={"route": res_query.route.value})
        metrics.inc_counter("cfo_copilot_requests_total", 1.0, labels={"route": res_query.route.value, "status": envelope.status.value})
        metrics.inc_counter("cfo_copilot_llm_calls_total", float(envelope.llm_calls_made))

        # Persist turn
        if envelope:
            self._persist_turn_data(
                tenant_id, session_id, req_id, question, envelope, res_query, t_start,
                degraded=degraded, degraded_reason=degraded_reason, queue_wait_ms=queue_wait_ms
            )

        return envelope

    async def stream_request(
        self,
        tenant_id: str,
        question: str,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        fault_inject: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Progressively streams chat response over SSE in strict contract order:
        meta -> facts (immediate content) -> progress -> answer (verified) -> final -> [DONE].
        Unverified model text NEVER reaches the client.
        """
        t_start = time.perf_counter()
        req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"

        # Fault Injection: Database Down
        if fault_inject == "db_down":
            import psycopg2
            raise psycopg2.OperationalError("Simulated database connection failure (FAULT_DB_DOWN).")

        # 1. Resolve prior context
        prior_context = None
        if session_id:
            prior_context = self.session_service.get_last_resolved_slots(tenant_id, session_id)

        # 2. Pre-resolve query route
        res_query: ResolvedQuery = self.root_agent.router.resolve(question, prior_context=prior_context)

        # Fault Injection: Queue Saturated
        if fault_inject == "queue_saturated":
            metrics.inc_counter("cfo_copilot_429_total")
            raise QueueFullError("LLM concurrency queue saturated (FAULT_QUEUE_SATURATED): 16 in-flight, 16 waiting.", retry_after=5)

        # Step 3 SSE Event 1: meta (route, request_id)
        yield {
            "event": "meta",
            "data": {
                "request_id": req_id,
                "route": res_query.route.value,
                "session_id": session_id
            }
        }

        # Step 3 SSE Event 2: facts (immediate deterministic facts block with citations)
        t_before_facts = time.perf_counter()
        facts, caveats = self.root_agent.facts_agent.fetch_facts(res_query, tenant_id=tenant_id, is_test=self.is_test)
        
        # Fault injection: vector failure -> FTS fallback caveat
        if fault_inject == "vector_fail":
            caveats.append("Degraded mode: pgvector search failed (FAULT_VECTOR_FAIL), falling back to full-text search (BM25) only")

        t_first_content = time.perf_counter()
        ttft_first_content_sec = t_first_content - t_start
        metrics.observe("cfo_copilot_ttft_first_content_seconds", ttft_first_content_sec, labels={"route": res_query.route.value})

        yield {
            "event": "facts",
            "data": {
                "facts": [f.model_dump() for f in facts],
                "caveats": caveats,
                "ttft_first_content_ms": round(ttft_first_content_sec * 1000.0, 2)
            }
        }

        # For narrative and mixed routes: emit immediate deterministic content block
        # (resolved scope + top 3 retrieved passages with citations, marked 'summary pending')
        if res_query.route in (RouteType.UNSTRUCTURED, RouteType.MIXED):
            top_passages = [
                {
                    "citation": f.source_filing or f"passage_{idx}",
                    "authority_label": "SEC Filing",
                    "passage": (f.text[:400] + "...") if f.text and len(f.text) > 400 else (f.text or "")
                }
                for idx, f in enumerate(facts[:3], 1)
            ]
            yield {
                "event": "first_content",
                "data": {
                    "scope": {
                        "companies": res_query.company_ids,
                        "fiscal_year": res_query.fiscal_year,
                        "fiscal_quarter": res_query.fiscal_quarter,
                        "kpi_id": res_query.kpi_id,
                        "topic": res_query.text_search_query
                    },
                    "top_passages": top_passages,
                    "summary_status": "summary pending",
                    "ttft_first_content_ms": round(ttft_first_content_sec * 1000.0, 2)
                }
            }

        # Step 3 SSE Event 3: progress
        yield {
            "event": "progress",
            "data": {
                "stage": "synthesizing",
                "message": "Generating and verifying executive response..."
            }
        }

        # Step 3 SSE Event 4: answer (verified LLM text or deterministic/extractive fallback)
        degraded = False
        degraded_reason = None
        queue_wait_ms = 0.0
        envelope = None

        if res_query.route in (RouteType.STRUCTURED, RouteType.REFUSAL, RouteType.CHITCHAT):
            envelope = await self.root_agent.answer(
                question=question,
                tenant=tenant_id,
                prior_context=prior_context,
                request_id=req_id,
                is_test=self.is_test
            )
        else:
            # LLM path requires queue admission
            try:
                if fault_inject == "model_offline":
                    degraded = True
                    degraded_reason = "Model server unreachable / connection refused (FAULT_MODEL_OFFLINE)"
                    envelope = self._build_extractive_fallback_envelope(
                        req_id, question, res_query, tenant_id, t_start, degraded_reason
                    )
                    metrics.inc_counter("cfo_copilot_degraded_total")
                    metrics.inc_counter("cfo_copilot_verifier_fallbacks_total")
                elif fault_inject == "model_oom":
                    degraded = True
                    degraded_reason = "Model server context limit / slot OOM; retry failed (FAULT_MODEL_OOM)"
                    envelope = self._build_extractive_fallback_envelope(
                        req_id, question, res_query, tenant_id, t_start, degraded_reason
                    )
                    metrics.inc_counter("cfo_copilot_degraded_total")
                    metrics.inc_counter("cfo_copilot_verifier_fallbacks_total")
                else:
                    wait_sec = await self.queue.acquire()
                    queue_wait_ms = wait_sec * 1000.0
                    metrics.observe("cfo_copilot_queue_wait_seconds", wait_sec)
                    try:
                        envelope = await asyncio.wait_for(
                            self.root_agent.answer(
                                question=question,
                                tenant=tenant_id,
                                prior_context=prior_context,
                                request_id=req_id,
                                is_test=self.is_test
                            ),
                            timeout=25.0
                        )
                    finally:
                        self.queue.release()
            except QueueFullError:
                metrics.inc_counter("cfo_copilot_429_total")
                raise
            except (QueueTimeoutError, asyncio.TimeoutError) as e:
                degraded = True
                degraded_reason = f"Queue wait/generation deadline exceeded ({str(e)})"
                envelope = self._build_extractive_fallback_envelope(
                    req_id, question, res_query, tenant_id, t_start, degraded_reason
                )
                metrics.inc_counter("cfo_copilot_degraded_total")
                metrics.inc_counter("cfo_copilot_verifier_fallbacks_total")
            except Exception as e:
                degraded = True
                degraded_reason = f"Model execution error: {str(e)}"
                envelope = self._build_extractive_fallback_envelope(
                    req_id, question, res_query, tenant_id, t_start, degraded_reason
                )
                metrics.inc_counter("cfo_copilot_degraded_total")
                metrics.inc_counter("cfo_copilot_verifier_fallbacks_total")

        # Yield verified answer event
        yield {
            "event": "answer",
            "data": {
                "answer": envelope.answer,
                "status": envelope.status.value,
                "degraded": degraded or any("fallback" in c.lower() for c in envelope.caveats),
                "degraded_reason": degraded_reason
            }
        }

        # Step 3 SSE Event 5: final (full AnswerEnvelope)
        yield {
            "event": "final",
            "data": envelope.model_dump()
        }

        # Step 3 SSE Event 6: [DONE] marker
        yield {
            "event": "done",
            "data": "[DONE]"
        }

        # Record metrics and persist
        total_sec = time.perf_counter() - t_start
        metrics.observe("cfo_copilot_request_duration_seconds", total_sec, labels={"route": res_query.route.value})
        metrics.observe("cfo_copilot_ttft_verified_answer_seconds", total_sec, labels={"route": res_query.route.value})
        metrics.inc_counter("cfo_copilot_requests_total", 1.0, labels={"route": res_query.route.value, "status": envelope.status.value})

        if envelope:
            self._persist_turn_data(
                tenant_id, session_id, req_id, question, envelope, res_query, t_start,
                degraded=degraded, degraded_reason=degraded_reason, queue_wait_ms=queue_wait_ms
            )

    def _build_extractive_fallback_envelope(
        self,
        request_id: str,
        question: str,
        query: ResolvedQuery,
        tenant_id: str,
        t_start: float,
        reason: str,
        force_vector_failure: bool = False
    ) -> AnswerEnvelope:
        """Constructs an extractive fallback envelope when LLM generation fails or times out."""
        facts, caveats = self.root_agent.facts_agent.fetch_facts(
            query,
            tenant_id=tenant_id,
            is_test=self.is_test,
            force_vector_failure=force_vector_failure
        )
        fallback_text = AnswerComposer.compose_fallback_answer(facts, query)
        latency = (time.perf_counter() - t_start) * 1000.0

        return AnswerEnvelope(
            request_id=request_id,
            question=question,
            route=query.route,
            status=AnswerStatus.OK if facts else AnswerStatus.MISSING_DATA,
            answer=fallback_text,
            llm_calls_made=0,
            latency_ms=round(latency, 2),
            facts_used=facts,
            caveats=caveats + [f"Extractive fallback served: {reason}"],
            verification=VerificationResult(
                is_valid=True,
                grounding_score=1.0,
                hallucination_detected=False,
                ungrounded_numbers=[],
                cited_fact_ids=[f.fact_id for f in facts]
            )
        )

    def _persist_turn_data(
        self,
        tenant_id: str,
        session_id: str,
        request_id: str,
        question: str,
        envelope: AnswerEnvelope,
        query: ResolvedQuery,
        t_start: float,
        degraded: bool = False,
        degraded_reason: Optional[str] = None,
        queue_wait_ms: float = 0.0
    ):
        """Helper to save turn records to session_messages and answer_log."""
        total_ms = (time.perf_counter() - t_start) * 1000.0
        slots = {
            "company_id": query.company_ids[0] if query.company_ids else None,
            "fiscal_year": query.fiscal_year,
            "fiscal_quarter": query.fiscal_quarter,
            "kpi_id": query.kpi_id,
            "basis": query.basis
        }
        log_meta = {
            "request_id": request_id,
            "routed_to": envelope.route.value,
            "model_version": "qwen2.5-3b-instruct",
            "prompt_template_hash": "frozen_prompt_v1",
            "ttft_ms": round(envelope.latency_ms, 2),
            "total_time_ms": round(total_ms, 2),
            "llm_calls": envelope.llm_calls_made,
            "policy_version": "v1.2.0",
            "degraded": degraded or any("fallback" in c.lower() for c in envelope.caveats),
            "degraded_reason": degraded_reason,
            "timings": {
                "total_ms": round(total_ms, 2),
                "queue_wait_ms": round(queue_wait_ms, 2),
                "agent_latency_ms": envelope.latency_ms
            },
            "facts": [f.model_dump() for f in envelope.facts_used]
        }
        try:
            self.session_service.save_turn(
                tenant_id=tenant_id,
                session_id=session_id,
                user_message=question,
                assistant_message=envelope.answer,
                resolved_slots=slots,
                envelope_data=envelope.model_dump(),
                log_meta=log_meta
            )
        except Exception:
            # Persistence logging must not crash user response
            pass
