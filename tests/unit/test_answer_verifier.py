"""tests/unit/test_answer_verifier.py

Unit tests for deterministic AnswerVerifier (Phase 4b Step 3).
Verifies:
1. Exact unit normalization & rounding to answer decimals (26.79% accepts 26.79%, 26.8%, 27%; rejects 27.2%).
2. Currency scaling ($109,200,000 accepts $109.2M and $109.2 million; rejects $110.8M and $1.092B).
3. Magnitude errors (x10, x1000) are strictly rejected.
4. Sign flips (+ vs -) are strictly rejected.
5. Percent vs ratio (26.79 vs 26.79% vs 0.2679) are strictly rejected.
6. Entity scoping: facts_used must include facts for every company & period named in the answer.
7. Refusal consistency and security leak guards.
"""

import pytest
from app.domain.answer_verifier import AnswerVerifier
from app.inference.contract import AnswerStatus, GroundedAnswer, InputFact


def test_percentage_rounding_tolerance():
    """26.79% accepts 26.79%, 26.8%, 27%; rejects 27.2%."""
    fact = InputFact(
        fact_id="f_margin",
        company_id="HBS",
        fiscal_year=2024,
        fiscal_quarter=2,
        metric_name="gross_margin_pct",
        value=26.79,
        text="Gross margin was 26.79%."
    )

    # 1. Accepts exact 26.79%
    a1 = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Helix Biosystems reported gross margin of 26.79%.",
        facts_used=["f_margin"],
        caveats=[]
    )
    assert AnswerVerifier.verify(a1, [fact]).valid is True

    # 2. Accepts rounded to 1 decimal: 26.8%
    a2 = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Helix Biosystems reported gross margin of 26.8%.",
        facts_used=["f_margin"],
        caveats=[]
    )
    assert AnswerVerifier.verify(a2, [fact]).valid is True

    # 3. Accepts rounded to integer: 27%
    a3 = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Helix Biosystems reported gross margin of 27%.",
        facts_used=["f_margin"],
        caveats=[]
    )
    assert AnswerVerifier.verify(a3, [fact]).valid is True

    # 4. Rejects 27.2% (incorrect rounding)
    a4 = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Helix Biosystems reported gross margin of 27.2%.",
        facts_used=["f_margin"],
        caveats=[]
    )
    res4 = AnswerVerifier.verify(a4, [fact])
    assert res4.valid is False
    assert any("27.2%" in v for v in res4.violations)


def test_currency_scaling_and_rounding():
    """$109,200,000 accepts $109.2M and $109.2 million; rejects $110.8M and $1.092B."""
    fact = InputFact(
        fact_id="f_rev",
        company_id="HBS",
        fiscal_year=2024,
        fiscal_quarter=2,
        metric_name="revenue",
        value=109200000.0,
        text="Helix Biosystems revenue was $109,200,000."
    )

    # 1. Accepts $109.2M
    a1 = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Helix Biosystems revenue was $109.2M.",
        facts_used=["f_rev"],
        caveats=[]
    )
    assert AnswerVerifier.verify(a1, [fact]).valid is True

    # 2. Accepts $109.2 million
    a2 = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Helix Biosystems revenue was $109.2 million.",
        facts_used=["f_rev"],
        caveats=[]
    )
    assert AnswerVerifier.verify(a2, [fact]).valid is True

    # 3. Rejects $110.8M
    a3 = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Helix Biosystems revenue was $110.8M.",
        facts_used=["f_rev"],
        caveats=[]
    )
    res3 = AnswerVerifier.verify(a3, [fact])
    assert res3.valid is False
    assert any("110.8M" in v for v in res3.violations)

    # 4. Rejects $1.092B (magnitude error: x10 error)
    a4 = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Helix Biosystems revenue was $1.092B.",
        facts_used=["f_rev"],
        caveats=[]
    )
    res4 = AnswerVerifier.verify(a4, [fact])
    assert res4.valid is False
    assert any("1.092B" in v for v in res4.violations)


def test_magnitude_errors_rejected():
    """Rejects magnitude errors x10 and x1000."""
    fact = InputFact(
        fact_id="f_rev",
        company_id="HBS",
        fiscal_year=2024,
        fiscal_quarter=2,
        metric_name="revenue",
        value=109200000.0,
        text="Revenue was $109,200,000."
    )

    # x10 magnitude error ($1,092,000,000)
    a1 = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Helix revenue was $1,092,000,000.",
        facts_used=["f_rev"],
        caveats=[]
    )
    assert AnswerVerifier.verify(a1, [fact]).valid is False

    # x1000 magnitude error ($109,200)
    a2 = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Helix revenue was $109,200.",
        facts_used=["f_rev"],
        caveats=[]
    )
    assert AnswerVerifier.verify(a2, [fact]).valid is False


def test_sign_flips_rejected():
    """Rejects positive figure when fact is negative."""
    fact = InputFact(
        fact_id="f_loss",
        company_id="HBS",
        fiscal_year=2024,
        fiscal_quarter=1,
        metric_name="operating_income",
        value=-15000000.0,
        text="Helix Biosystems operating loss was -$15,000,000."
    )

    # Negative matches negative
    a_ok = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Helix Biosystems reported an operating loss of -$15,000,000.",
        facts_used=["f_loss"],
        caveats=[]
    )
    assert AnswerVerifier.verify(a_ok, [fact]).valid is True

    # Sign flip: reports positive $15,000,000 profit
    a_bad = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Helix Biosystems reported operating profit of $15,000,000.",
        facts_used=["f_loss"],
        caveats=[]
    )
    res_bad = AnswerVerifier.verify(a_bad, [fact])
    assert res_bad.valid is False
    assert any("15,000,000" in v for v in res_bad.violations)


def test_percent_vs_ratio_rejected():
    """Rejects percent when fact is ratio, and ratio when fact is percent."""
    f_pct = InputFact(
        fact_id="f_pct",
        company_id="CEP",
        metric_name="gross_margin_pct",
        value=26.79,
        text="Gross margin was 26.79%."
    )
    f_ratio = InputFact(
        fact_id="f_ratio",
        company_id="CEP",
        metric_name="current_ratio",
        value=1.85,
        text="Current ratio was 1.85x."
    )

    # Attempting to quote percentage as ratio (26.79x)
    a1 = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Cobalt Energy gross margin was 26.79x.",
        facts_used=["f_pct"],
        caveats=[]
    )
    assert AnswerVerifier.verify(a1, [f_pct]).valid is False

    # Attempting to quote ratio as percentage (1.85%)
    a2 = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Cobalt Energy current ratio was 1.85%.",
        facts_used=["f_ratio"],
        caveats=[]
    )
    assert AnswerVerifier.verify(a2, [f_ratio]).valid is False


def test_entity_scoping_company_mismatch():
    """Rejects an answer where numbers exist in facts but belong to a different company not cited."""
    f_arg = InputFact(
        fact_id="f_arg",
        company_id="ARG",
        fiscal_year=2024,
        fiscal_quarter=1,
        metric_name="revenue",
        value=777700000.0,
        text="Aurora Retail Group revenue was $777,700,000."
    )

    # Model claims Helix revenue was $777,700,000, citing only ARG fact
    answer = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Helix Biosystems revenue was $777,700,000.",
        facts_used=["f_arg"],
        caveats=[]
    )

    res = AnswerVerifier.verify(answer, [f_arg])
    assert res.valid is False
    assert any("Scope violation: Answer mentions company 'HBS'" in v for v in res.violations)


def test_clean_refusal():
    """Verifier passes a clean refusal with no affirmative claims."""
    answer = GroundedAnswer(
        status=AnswerStatus.INSUFFICIENT_DATA,
        answer="Refused: Request cannot be fulfilled with available facts.",
        facts_used=[],
        caveats=["Fiscal 2026 data unavailable."]
    )
    res = AnswerVerifier.verify(answer, [])
    assert res.valid is True
    assert len(res.violations) == 0


def test_security_leak_rejection():
    """Verifier rejects answers that leak database credentials or external URLs."""
    fact = InputFact(fact_id="f1", company_id="ARG", text="Clean fact", value=100.0)
    answer = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Aurora Retail Group revenue was $100. Connected via postgresql://postgres:secret@localhost:5432/cfo_copilot",
        facts_used=["f1"],
        caveats=[]
    )
    res = AnswerVerifier.verify(answer, [fact])
    assert res.valid is False
    assert any("Security violation" in v for v in res.violations)


def test_percentage_not_double_extracted_as_currency():
    """Verifier must not double-extract percentage tokens as ungrounded currency amounts (e.g. 48.90%)."""
    fact = InputFact(
        fact_id="f_msi_gm",
        company_id="MSI",
        fiscal_year=2024,
        fiscal_quarter=1,
        metric_name="gross_margin_pct",
        value=48.9,
        text="Main Street Investments gross margin was 48.90% in FY2024 Q1."
    )
    answer = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Main Street Investments gross margin was 48.90% in FY2024 Q1.",
        facts_used=["f_msi_gm"],
        caveats=[]
    )
    res = AnswerVerifier.verify(answer, [fact])
    assert res.valid is True
    assert len(res.ungrounded_numbers) == 0
    assert len(res.violations) == 0


def test_repeated_supported_number_passes():
    """A legitimate executive response repeating a verified number in lead and summary passes."""
    fact = InputFact(
        fact_id="f_rev",
        company_id="ARG",
        fiscal_year=2024,
        fiscal_quarter=1,
        metric_name="revenue",
        value=777700000.0,
        text="Aurora Retail Group revenue was $777,700,000."
    )
    # The number $777,700,000 is stated in the first sentence and repeated in the summary
    answer = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Aurora Retail Group generated $777,700,000 in revenue for FY2024 Q1. Therefore, total top-line sales reached $777,700,000.",
        facts_used=["f_rev"],
        caveats=[]
    )
    res = AnswerVerifier.verify(answer, [fact])
    assert res.valid is True
    assert len(res.ungrounded_numbers) == 0


def test_unsupported_number_strictly_rejected():
    """An ungrounded number not present in facts (e.g. fake 45.0% margin or $999M) is strictly rejected."""
    fact = InputFact(
        fact_id="f_gm",
        company_id="NWI",
        fiscal_year=2024,
        fiscal_quarter=3,
        metric_name="gross_margin_pct",
        value=36.38,
        text="Northwind gross margin was 36.38%."
    )
    # Model injects unsupported 45.0% margin
    answer = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="Northwind reported gross margin of 36.38% and operating margin of 45.0%.",
        facts_used=["f_gm"],
        caveats=[]
    )
    res = AnswerVerifier.verify(answer, [fact])
    assert res.valid is False
    assert any("45" in un["raw_text"] for un in res.ungrounded_numbers)


def test_accession_masking_and_financial_token_extraction():
    """Step 0.3: Ensure exact accession pattern masking while properly extracting:
    '$10K', '10,000', '-10 million', 'Q3 FY23 revenue of 10', and catching wrong numbers next to accession IDs.
    """
    # 1. Test extraction of $10K
    nums = AnswerVerifier.extract_numbers_from_text("Operating cash flow was $10K for the period.")
    assert any(n.value == 10000.0 and n.kind == "currency" for n in nums)

    # 2. Test extraction of 10,000
    nums = AnswerVerifier.extract_numbers_from_text("Operating cash flow was 10,000 for the period.")
    assert any(n.value == 10000.0 for n in nums)

    # 3. Test extraction of -10 million
    nums = AnswerVerifier.extract_numbers_from_text("Operating loss was -10 million.")
    assert any(n.value == -10000000.0 for n in nums)

    # 4. Test extraction of 'Q3 FY23 revenue of 10'
    nums = AnswerVerifier.extract_numbers_from_text("Q3 FY23 revenue of 10 was reported.")
    assert any(n.value == 10.0 for n in nums)

    # 5. Wrong number next to accession ID is caught by verifier
    fact = InputFact(
        fact_id="f_rev",
        company_id="ARG",
        fiscal_year=2023,
        fiscal_quarter=None,
        metric_name="revenue",
        value=800000000.0,
        text="ARG-10K-FY2023 reported revenue was $800M."
    )
    # Model generates wrong number $999M next to accession ID
    answer = GroundedAnswer(
        status=AnswerStatus.ANSWERED,
        answer="According to filing ARG-10K-FY2023 revenue was $999M.",
        facts_used=["f_rev"],
        caveats=[]
    )
    res = AnswerVerifier.verify(answer, [fact])
    assert res.valid is False
    assert any(un["extracted_value"] == 999000000.0 for un in res.ungrounded_numbers)


