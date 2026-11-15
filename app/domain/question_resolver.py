"""app/domain/question_resolver.py

Deterministic financial query resolver for CFO Copilot.
Extracts companies, fiscal periods, canonical KPIs, basis, and routes
WITHOUT requiring the LLM to generate database arguments or SQL parameters.
"""

import re
from typing import Any, Dict, List, Optional, Tuple, Union
from app.domain.agent_envelope import ResolvedQuery, RouteType

# Authoritative Entities
COMPANY_ALIASES: Dict[str, str] = {
    "ARG": "ARG",
    "AURORA": "ARG",
    "AURORA RETAIL": "ARG",
    "AURORA RETAIL GROUP": "ARG",
    "CEP": "CEP",
    "COBALT": "CEP",
    "COBALT ENERGY": "CEP",
    "COBALT ENERGY PARTNERS": "CEP",
    "HBS": "HBS",
    "HELIX": "HBS",
    "HELIX BIOSYSTEMS": "HBS",
    "MSI": "MSI",
    "MAINSTAY": "MSI",
    "MAINSTAY SOLUTIONS": "MSI",
    "NWI": "NWI",
    "NORTHWIND": "NWI",
    "NORTHWIND INDUSTRIAL": "NWI",
    "NORTHWIND INDUSTRIAL CORP": "NWI",
    "ZLG": "ZLG",
    "ZEPHYR": "ZLG",
    "ZEPHYR LOGISTICS": "ZLG",
    "ZEPHYR LOGISTICS GROUP": "ZLG",
}

KNOWN_NON_CORPUS_ENTITIES = [
    "TESLA", "APPLE", "MICROSOFT", "AMAZON", "GOOGLE", "ALPHABET", "META", "NVIDIA", "NIMBUS", "NIMBUS CLOUD"
]

# Canonical KPI Synonyms
KPI_SYNONYMS: Dict[str, str] = {
    # 16 Canonical KPIs
    "gross_margin_pct": "gross_margin_pct",
    "gross margin": "gross_margin_pct",
    "gross margin percentage": "gross_margin_pct",
    "gross margin percent": "gross_margin_pct",
    "gp %": "gross_margin_pct",

    "operating_margin_pct": "operating_margin_pct",
    "operating margin": "operating_margin_pct",
    "operating margin percentage": "operating_margin_pct",
    "operating margin percent": "operating_margin_pct",
    "op margin": "operating_margin_pct",

    "net_margin_pct": "net_margin_pct",
    "net margin": "net_margin_pct",
    "net margin percentage": "net_margin_pct",
    "profit margin": "net_margin_pct",

    "ebitda_usd": "ebitda_usd",
    "ebitda": "ebitda_usd",

    "ebitda_margin_pct": "ebitda_margin_pct",
    "ebitda margin": "ebitda_margin_pct",

    "current_ratio_x": "current_ratio_x",
    "current ratio": "current_ratio_x",

    "debt_to_equity_x": "debt_to_equity_x",
    "debt to equity": "debt_to_equity_x",
    "debt-to-equity": "debt_to_equity_x",
    "d/e ratio": "debt_to_equity_x",
    "leverage ratio": "debt_to_equity_x",

    "roe_quarterly_pct": "roe_quarterly_pct",
    "roe": "roe_quarterly_pct",
    "return on equity": "roe_quarterly_pct",

    "free_cash_flow_usd": "free_cash_flow_usd",
    "free cash flow": "free_cash_flow_usd",
    "fcf": "free_cash_flow_usd",

    "fcf_margin_pct": "fcf_margin_pct",
    "fcf margin": "fcf_margin_pct",

    "revenue_yoy_growth_pct": "revenue_yoy_growth_pct",
    "revenue yoy growth": "revenue_yoy_growth_pct",
    "revenue growth": "revenue_yoy_growth_pct",
    "yoy revenue growth": "revenue_yoy_growth_pct",
    "sales growth": "revenue_yoy_growth_pct",

    "opex_ratio_pct": "opex_ratio_pct",
    "opex ratio": "opex_ratio_pct",
    "operating expense ratio": "opex_ratio_pct",

    "interest_coverage_x": "interest_coverage_x",
    "interest coverage": "interest_coverage_x",

    "asset_turnover_x": "asset_turnover_x",
    "asset turnover": "asset_turnover_x",

    "rd_intensity_pct": "rd_intensity_pct",
    "rd intensity": "rd_intensity_pct",
    "r&d intensity": "rd_intensity_pct",
    "research intensity": "rd_intensity_pct",

    "working_capital_usd": "working_capital_usd",
    "working capital": "working_capital_usd",

    # Key Line Items
    "revenue": "revenue",
    "revenues": "revenue",
    "net sales": "revenue",
    "sales": "revenue",
    "gross profit": "gross_profit",
    "operating income": "operating_income",
    "operating profit": "operating_income",
    "net income": "net_income",
    "net earnings": "net_income",
}

HOSTILE_PATTERNS = [
    r"ignore\s+(your\s+)?instructions",
    r"list\s+every\s+table",
    r"database\s+schema",
    r"system\s+prompt",
    r"show\s+me\s+your\s+prompt",
    r"drop\s+table",
    r"select\s+\*\s+from",
    r"union\s+select",
    r"show\s+password",
    r"admin\s+credentials",
    r"developer\s+mode",
    r"jailbreak",
]

CHITCHAT_PATTERNS = [
    r"^hello",
    r"^hi\b",
    r"^good\s+morning",
    r"^good\s+afternoon",
    r"^good\s+evening",
    r"^thanks?",
    r"^thank\s+you",
    r"who\s+(are\s+you|built\s+you|created\s+you)",
    r"what\s+can\s+you\s+do",
    r"what\s+are\s+your\s+capabilities",
]


class QuestionResolver:
    """Deterministically maps natural language CFO queries to structured metadata."""

    @classmethod
    def resolve(cls, query: str, prior_context: Optional[Any] = None) -> ResolvedQuery:
        clean_q = query.strip()
        upper_q = clean_q.upper()

        # Normalize prior_context to string representation for regex scanning
        prior_str = ""
        dict_comp = None
        dict_fy = None
        dict_fq = None
        if isinstance(prior_context, dict):
            dict_comp = prior_context.get("company_id")
            dict_fy = prior_context.get("fiscal_year")
            dict_fq = prior_context.get("fiscal_quarter")
            prior_str = " ".join(str(v) for v in prior_context.values())
        elif isinstance(prior_context, str):
            prior_str = prior_context

        # 0. Check for Hostile / Prompt Injection Attacks in prior_context FIRST
        if prior_str:
            for pat in HOSTILE_PATTERNS:
                if re.search(pat, prior_str, re.IGNORECASE):
                    return ResolvedQuery(
                        question=clean_q,
                        route=RouteType.REFUSAL,
                        refusal_reason="Request rejected: Hostile instruction or injection detected in conversation context."
                    )

        # 1. Check for Hostile / Prompt Injection Attacks in Current Query
        for pat in HOSTILE_PATTERNS:
            if re.search(pat, clean_q, re.IGNORECASE):
                return ResolvedQuery(
                    question=clean_q,
                    route=RouteType.REFUSAL,
                    refusal_reason="Request rejected: Adversarial prompt injection or internal system probe detected."
                )

        # 2. Check for Chitchat / Greetings
        for pat in CHITCHAT_PATTERNS:
            if re.search(pat, clean_q, re.IGNORECASE):
                return ResolvedQuery(
                    question=clean_q,
                    route=RouteType.CHITCHAT
                )

        # 3. Check for Non-Corpus Known Entities in Current Query
        for nce in KNOWN_NON_CORPUS_ENTITIES:
            if re.search(r"\b" + nce + r"\b", upper_q):
                return ResolvedQuery(
                    question=clean_q,
                    route=RouteType.REFUSAL,
                    refusal_reason=f"Entity '{nce.title()}' is not covered in our public company financial corpus."
                )

        # 4. Extract Covered Company Entities (Explicit query takes absolute precedence)
        found_companies = []
        for alias, cid in sorted(COMPANY_ALIASES.items(), key=lambda x: -len(x[0])):
            if re.search(r"\b" + re.escape(alias) + r"\b", upper_q):
                if cid not in found_companies:
                    found_companies.append(cid)

        # Multi-turn slot inheritance: If company missing, inspect safe prior_context
        if not found_companies:
            if dict_comp and dict_comp in COMPANY_ALIASES.values():
                found_companies.append(dict_comp)
            elif prior_str:
                prior_upper = prior_str.upper()
                for alias, cid in sorted(COMPANY_ALIASES.items(), key=lambda x: -len(x[0])):
                    if re.search(r"\b" + re.escape(alias) + r"\b", prior_upper):
                        if cid not in found_companies:
                            found_companies.append(cid)

        # 5. Extract Fiscal Year & Quarter (Explicit query takes absolute precedence)
        fy, fq = cls._extract_period(clean_q)

        # Handle multi-turn follow-ups like "What about the previous quarter?" or "prior quarter"
        is_prior_quarter_request = bool(re.search(r"\b(previous|prior)\s+quarter\b", clean_q, re.IGNORECASE))
        if (fy is None or is_prior_quarter_request) and (prior_str or dict_fy is not None):
            if dict_fy is not None and dict_fq is not None:
                p_fy, p_fq = dict_fy, dict_fq
            else:
                p_fy, p_fq = cls._extract_period(prior_str)

            if is_prior_quarter_request and p_fy is not None and p_fq is not None:
                # Compute arithmetic previous quarter
                if p_fq > 1:
                    fy, fq = p_fy, p_fq - 1
                else:
                    fy, fq = p_fy - 1, 4
            elif fy is None:
                fy = p_fy
                if fq is None:
                    fq = p_fq

        # Check for Out-of-Horizon Time Trap (e.g. FY2026, FY2027)
        if fy is not None and (fy < 2022 or fy > 2024):
            return ResolvedQuery(
                question=clean_q,
                route=RouteType.REFUSAL,
                company_ids=found_companies,
                fiscal_year=fy,
                fiscal_quarter=fq,
                refusal_reason=f"Requested period FY{fy} exceeds available historical filing horizon (FY2022 Q1 - FY2024 Q4)."
            )

        # 6. Extract Basis
        basis = "as_originally_reported" if "originally reported" in clean_q.lower() or "as reported" in clean_q.lower() else "as_restated"

        # 7. Extract KPI Identifier
        found_kpi = cls._extract_kpi(clean_q)
        if not found_kpi and prior_context:
            # Inherit KPI from prior context if current query is asking about a different period for same KPI
            found_kpi = cls._extract_kpi(prior_context)

        # 8. Check for Qualitative / Narrative Elements
        is_qualitative = bool(re.search(r"\b(why|explains?|drove|driver|note\s+\d+|litigation|hedging|risk|discloses?|contract|outage)\b", clean_q, re.IGNORECASE))
        has_kpi = (found_kpi is not None)

        if has_kpi and is_qualitative and (fy is not None):
            route = RouteType.MIXED
        elif is_qualitative:
            route = RouteType.UNSTRUCTURED
        elif has_kpi:
            route = RouteType.STRUCTURED
        else:
            # Check if general filings search
            if "search" in clean_q.lower() or "find" in clean_q.lower() or "patent" in clean_q.lower() or "restatement" in clean_q.lower():
                route = RouteType.UNSTRUCTURED
            elif not found_companies and not fy:
                route = RouteType.REFUSAL
                refusal_reason = "Query is ambiguous or out-of-scope. Please specify a company (ARG, CEP, HBS, MSI, NWI, ZLG) and period."
                return ResolvedQuery(question=clean_q, route=route, refusal_reason=refusal_reason)
            else:
                route = RouteType.UNSTRUCTURED

        return ResolvedQuery(
            question=clean_q,
            route=route,
            company_ids=found_companies,
            fiscal_year=fy,
            fiscal_quarter=fq,
            kpi_id=found_kpi,
            basis=basis,
            is_comparative=len(found_companies) > 1,
            text_search_query=clean_q
        )

    @staticmethod
    def _extract_period(query: str) -> Tuple[Optional[int], Optional[int]]:
        # Match formats:
        # "fiscal 2024 quarter 2"
        # "FY2023 Q3", "FY 2023 Q3"
        # "2023 Q1", "Q4 2023"
        # "fiscal 2023"
        m1 = re.search(r"fiscal\s+(\d{4})\s+quarter\s+([1-4])", query, re.IGNORECASE)
        if m1:
            return int(m1.group(1)), int(m1.group(2))

        m2 = re.search(r"FY\s*(\d{4})\s*Q\s*([1-4])", query, re.IGNORECASE)
        if m2:
            return int(m2.group(1)), int(m2.group(2))

        m3 = re.search(r"Q\s*([1-4])\s*(?:of\s+)?(?:FY\s*)?(\d{4})", query, re.IGNORECASE)
        if m3:
            return int(m3.group(2)), int(m3.group(1))

        m4 = re.search(r"(\d{4})\s*Q\s*([1-4])", query, re.IGNORECASE)
        if m4:
            return int(m4.group(1)), int(m4.group(2))

        m5 = re.search(r"\b(202[0-9])\b", query)
        if m5:
            return int(m5.group(1)), None

        return None, None

    @staticmethod
    def _extract_kpi(query: str) -> Optional[str]:
        q_low = query.lower()
        # Sort by length descending to match multi-word phrases first
        for phrase, canonical in sorted(KPI_SYNONYMS.items(), key=lambda x: -len(x[0])):
            pattern = r"\b" + re.escape(phrase) + r"\b"
            if re.search(pattern, q_low):
                return canonical
        return None
