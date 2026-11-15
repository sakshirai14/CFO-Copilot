"""app/domain/answer_composer.py

Deterministic financial answer composer for CFO Copilot.
Generates CFO-grade presentation answers directly from verified FactItem objects.
Provides sub-millisecond, zero-hallucination responses for structured queries
and serves as the guaranteed fallback engine when candidate answers fail verification.
"""

from typing import List, Optional
from app.domain.agent_envelope import FactItem, RouteType, ResolvedQuery


class AnswerComposer:
    """Renders deterministic CFO-grade answers and safe refusal strings."""

    @classmethod
    def compose_structured_answer(cls, query: ResolvedQuery, facts: List[FactItem]) -> str:
        if not facts:
            if query.refusal_reason:
                return f"Refused: {query.refusal_reason}"
            return "Refused: Requested financial data is not available in historical filings."

        # Filter facts for ok status
        ok_facts = [f for f in facts if f.status == "ok"]
        missing_facts = [f for f in facts if f.status == "missing_input"]
        unverified_facts = [f for f in facts if f.status == "unverified"]

        if missing_facts and not ok_facts:
            reasons = [f.reason for f in missing_facts if f.reason]
            reason_str = f" ({reasons[0]})" if reasons else ""
            return f"Unavailable: Required input data is not reported in the filing{reason_str}. Value cannot be computed."

        if unverified_facts and not ok_facts:
            return "Unavailable: Underlying filing data failed accounting integrity verification (Rule R11). Value withheld."

        if len(ok_facts) == 1:
            fact = ok_facts[0]
            val_str = cls._format_value(fact.value, fact.unit)
            restated_note = " (as restated)" if fact.restated else ""
            return f"{fact.company_id} FY{fact.fiscal_year} Q{fact.fiscal_quarter} {fact.kpi_id} was {val_str}{restated_note}."

        # Multi-company or multi-period comparison
        lines = []
        for fact in ok_facts:
            val_str = cls._format_value(fact.value, fact.unit)
            restated_note = " (as restated)" if fact.restated else ""
            lines.append(f"{fact.company_id} FY{fact.fiscal_year} Q{fact.fiscal_quarter} {fact.kpi_id}: {val_str}{restated_note}")
        return "; ".join(lines) + "."

    @classmethod
    def compose_chitchat_answer(cls) -> str:
        return (
            "Hello! I am CFO Copilot, your private self-hosted executive financial assistant. "
            "I provide certified financial KPI calculations and SEC disclosure intelligence across "
            "our coverage universe (ARG, CEP, HBS, MSI, NWI, ZLG)."
        )

    @classmethod
    def compose_refusal_answer(cls, query: ResolvedQuery) -> str:
        reason = query.refusal_reason or "Requested data is outside system operational boundaries."
        return f"Refused: {reason}"

    @classmethod
    def compose_fallback_answer(cls, facts: List[FactItem], query: Optional[ResolvedQuery] = None) -> str:
        """Invoked when LLM response is rejected by AnswerVerifier or model server is unavailable.
        Provides an extractive fallback: deterministic metrics + verbatim retrieved filing passages with citations.
        """
        if not facts:
            return "Refused: Requested financial disclosures could not be located in SEC filings."

        kpi_facts = [f for f in facts if f.kpi_id is not None]
        text_facts = [f for f in facts if f.kpi_id is None and f.text]

        sections = []

        # 1. Deterministic metric data block (if structured KPIs exist)
        if kpi_facts:
            structured_block = cls.compose_structured_answer(query or ResolvedQuery(question="fallback", route=RouteType.STRUCTURED), kpi_facts)
            sections.append(f"Certified Metric Data:\n{structured_block}")

        # 2. Extractive passages quoted verbatim with citations and authority labels
        if text_facts:
            passage_lines = []
            for idx, tf in enumerate(text_facts[:3], 1):
                # Authority label formatting
                filing_str = (tf.source_filing or "").lower()
                if "press_release" in filing_str or "faq" in filing_str or ("analyst" in filing_str and "note" in filing_str):
                    auth_label = "unaudited, not a filing"
                elif "10-q/a" in filing_str or "10qa" in filing_str:
                    auth_label = "SEC Form 10-Q/A Amendment"
                elif "10-q" in filing_str or "10q" in filing_str or "10-k" in filing_str or "10k" in filing_str:
                    auth_label = "SEC Filing"
                else:
                    auth_label = "Company Disclosure"

                citation = f"Source: {tf.source_filing or tf.fact_id} [{auth_label}]"
                clean_text = tf.text.strip().replace("\n", " ")
                passage_lines.append(f'[{idx}] "{clean_text}" ({citation})')

            sections.append("Relevant Filing Excerpts:\n" + "\n".join(passage_lines))

        if sections:
            return "\n\n".join(sections)

        return cls.compose_structured_answer(query or ResolvedQuery(question="fallback", route=RouteType.STRUCTURED), facts)

    @staticmethod
    def _format_value(value: Optional[float], unit: str) -> str:
        if value is None:
            return "None"
        if unit == "USD":
            return f"${value:,.0f}"
        if unit == "percent":
            return f"{value:.2f}%"
        if unit == "x":
            return f"{value:.2f}x"
        return f"{value}"

