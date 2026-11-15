"""tests/unit/test_agents.py

Unit tests for ADK Agents (RouterAgent, FactsAgent, AnswerComposer, VerifierAgent, CfoCopilotRootAgent).
Verifies deterministic execution, call budget, and AnswerEnvelope contracts.
"""

import pytest
from app.agents.router_agent import RouterAgent
from app.agents.facts_agent import FactsAgent
from app.agents.verifier_agent import VerifierAgent
from app.agents.root_agent import CfoCopilotRootAgent
from app.domain.agent_envelope import AnswerStatus, FactItem, RouteType
from app.domain.answer_composer import AnswerComposer


@pytest.mark.anyio
async def test_router_agent_deterministic_dispatch():
    router = RouterAgent()
    r1 = router.resolve("What was HBS revenue in fiscal 2024 quarter 2?")
    assert r1.route == RouteType.STRUCTURED
    assert r1.company_ids == ["HBS"]
    assert r1.kpi_id == "revenue"

    r2 = router.resolve("What is Tesla's gross margin?")
    assert r2.route == RouteType.REFUSAL

    r3 = router.resolve("Good morning assistant!")
    assert r3.route == RouteType.CHITCHAT


def test_answer_composer_formats():
    fact = FactItem(
        fact_id="fact_test_1",
        company_id="HBS",
        fiscal_year=2024,
        fiscal_quarter=2,
        kpi_id="revenue",
        value=109200000.0,
        unit="USD",
        status="ok",
        text="HBS FY2024 Q2 revenue was $109,200,000."
    )
    from app.domain.agent_envelope import ResolvedQuery
    q = ResolvedQuery(question="test", route=RouteType.STRUCTURED)
    ans = AnswerComposer.compose_structured_answer(q, [fact])
    assert "$109,200,000" in ans
    assert "HBS" in ans


def test_verifier_agent_intercepts_ungrounded():
    verifier = VerifierAgent()
    fact = FactItem(
        fact_id="fact_test_1",
        company_id="HBS",
        fiscal_year=2024,
        fiscal_quarter=2,
        kpi_id="revenue",
        value=109200000.0,
        unit="USD",
        status="ok",
        text="HBS FY2024 Q2 revenue was $109,200,000."
    )

    # Valid grounded answer
    cand_valid = "Helix Biosystems revenue was $109.2M in FY2024 Q2."
    shipped, v_res, triggered = verifier.verify_and_intercept(cand_valid, [fact])
    assert not triggered
    assert v_res.is_valid

    # Hallucinated wrong number ($999M)
    cand_fake = "Helix Biosystems revenue was $999M in FY2024 Q2."
    shipped_fallback, v_res_fake, triggered_fallback = verifier.verify_and_intercept(cand_fake, [fact])
    assert triggered_fallback
    assert "$109,200,000" in shipped_fallback
    assert "$999M" not in shipped_fallback


@pytest.mark.anyio
async def test_root_agent_structured_zero_llm_calls():
    root = CfoCopilotRootAgent()
    env = await root.answer("What was Helix Biosystems's revenue in fiscal 2024 quarter 2?", is_test=True)
    assert env.status == AnswerStatus.OK
    assert env.llm_calls_made == 0  # Foundation Lock 2: 0 LLM calls for structured lookup!
    assert "$109,200,000" in env.answer
    assert env.verification.is_valid


@pytest.mark.anyio
async def test_root_agent_refusal_zero_llm_calls():
    root = CfoCopilotRootAgent()
    env = await root.answer("What was Northwind's revenue in fiscal 2026 quarter 1?")
    assert env.status == AnswerStatus.REFUSED
    assert env.llm_calls_made == 0
    assert "Refused:" in env.answer
