"""tests/unit/test_answer_verifier.py

Unit tests for deterministic AnswerVerifier.
Verifies numerical grounding, unit scaling tolerance, fact ID checking, refusal integrity, and security filtering.
"""

import pytest
from app.domain.answer_verifier import AnswerVerifier
from app.inference.contract import AnswerStatus, GroundedAnswer, InputFact


def test_valid_grounded_answer_with_scaling():
    """Verifier accepts scaled monetary numbers ($109.2M matching 109,200,000)."""
    facts = [
        InputFact(
            fact_id="fact_hbs_rev",
            company_id="HBS",
            fiscal_year=2024,
            fiscal_quarter=2,
            metric_name="revenue",
            value=109200000.0,
            text="Revenue was $109,200,000 for Helix Biosystems in fiscal 2024 quarter 2"
        ),
        InputFact(
            fact_id="fact_hbs_margin",
            company_id="HBS",
            fiscal_year=2024,
            fiscal_quarter=2,
            metric_name="gross_margin_pct",
            value=26.79,
            text="Gross margin was 26.79% (or 0.2679)"
        )
    ]

    answer = GroundedAnswer(
        status=AnswerStatus.OK,
        answer="In fiscal 2024 quarter 2, Helix Biosystems generated $109.2M in revenue with a gross margin of 26.8%.",
        facts_used=["fact_hbs_rev", "fact_hbs_margin"],
        caveats=[]
    )

    res = AnswerVerifier.verify(answer, facts)
    assert res.valid is True
    assert len(res.violations) == 0
    assert len(res.ungrounded_numbers) == 0
    assert "fact_hbs_rev" in res.matched_facts
    assert "fact_hbs_margin" in res.matched_facts


def test_ungrounded_number_rejection():
    """Verifier rejects an answer that hallucinates a number not in facts."""
    facts = [
        InputFact(
            fact_id="fact_arg_rev",
            company_id="ARG",
            fiscal_year=2024,
            fiscal_quarter=1,
            metric_name="revenue",
            value=777700000.0,
            text="Revenue was $777.7M"
        )
    ]

    # Model hallucinates operating profit of $45.0M
    answer = GroundedAnswer(
        status=AnswerStatus.OK,
        answer="Aurora Retail Group reported revenue of $777.7M and operating profit of $45.0M.",
        facts_used=["fact_arg_rev"],
        caveats=[]
    )

    res = AnswerVerifier.verify(answer, facts)
    assert res.valid is False
    assert any("45" in v for v in res.violations)
    assert len(res.ungrounded_numbers) == 1
    assert res.ungrounded_numbers[0]["raw_text"] == "$45.0M"


def test_uncited_or_fake_fact_id_rejection():
    """Verifier rejects an answer that cites a fact ID that was not provided in input facts."""
    facts = [
        InputFact(
            fact_id="fact_legit_1",
            text="Legitimate fact"
        )
    ]

    answer = GroundedAnswer(
        status=AnswerStatus.OK,
        answer="The company performed well.",
        facts_used=["fact_legit_1", "fact_hallucinated_999"],
        caveats=[]
    )

    res = AnswerVerifier.verify(answer, facts)
    assert res.valid is False
    assert any("fact_hallucinated_999" in v for v in res.violations)


def test_refusal_with_fabricated_claims_rejection():
    """Verifier rejects a response marked 'refused' that nonetheless asserts financial figures."""
    facts = []

    answer = GroundedAnswer(
        status=AnswerStatus.REFUSED,
        answer="I refuse to answer, but revenue was $500M in fiscal 2026.",
        facts_used=[],
        caveats=[]
    )

    res = AnswerVerifier.verify(answer, facts)
    assert res.valid is False
    assert any("Refusal violation" in v for v in res.violations)


def test_legitimate_clean_refusal():
    """Verifier passes a clean refusal without fabricated figures."""
    facts = []

    answer = GroundedAnswer(
        status=AnswerStatus.REFUSED,
        answer="Cannot answer: Fiscal 2026 is a future period not covered by available SEC filings.",
        facts_used=[],
        caveats=["Data for future fiscal years is unavailable."]
    )

    res = AnswerVerifier.verify(answer, facts)
    assert res.valid is True
    assert len(res.violations) == 0


def test_security_leak_rejection():
    """Verifier rejects answers that leak database credentials or external URLs."""
    facts = [InputFact(fact_id="f1", text="Clean fact", value=100.0)]

    answer = GroundedAnswer(
        status=AnswerStatus.OK,
        answer="Revenue was $100. Connected via postgresql://postgres:secret@localhost:5432/cfo_copilot",
        facts_used=["f1"],
        caveats=[]
    )

    res = AnswerVerifier.verify(answer, facts)
    assert res.valid is False
    assert any("Security violation" in v for v in res.violations)
