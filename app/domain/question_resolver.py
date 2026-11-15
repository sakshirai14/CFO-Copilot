"""app/domain/question_resolver.py

Deterministic financial query resolver for CFO Copilot.
Extracts companies, fiscal periods, canonical KPIs, basis, and routes
WITHOUT requiring the LLM to generate database arguments or SQL parameters.
Enforces Foundation Lock 6 (The Gate: Deterministic Routing).
"""

import difflib
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from app.domain.agent_envelope import ResolvedQuery, RouteType

# Authoritative Entities
COMPANY_ALIASES: Dict[str, str] = {
    "ARG": "ARG",
    "AURORA": "ARG",
    "AURORA RETAIL": "ARG",
    "AURORA RETAIL GROUP": "ARG",
    "AURORA RETAIL GROUP, INC.": "ARG",
    "CEP": "CEP",
    "COBALT": "CEP",
    "COBALT ENERGY": "CEP",
    "COBALT ENERGY PARTNERS": "CEP",
    "COBALT ENERGY PARTNERS LLC": "CEP",
    "HBS": "HBS",
    "HELIX": "HBS",
    "HELIX BIO": "HBS",
    "HELIX BIOSYSTEMS": "HBS",
    "HELIX BIOSYSTEMS CORPORATION": "HBS",
    "MSI": "MSI",
    "MERIDIAN": "MSI",
    "MERIDIAN SEMI": "MSI",
    "MERIDIAN SEMICONDUCTOR": "MSI",
    "MERIDIAN SEMICONDUCTOR INC.": "MSI",
    "NWI": "NWI",
    "NORTHWIND": "NWI",
    "NORTHWIND INDUSTRIAL": "NWI",
    "NORTHWIND INDUSTRIAL CORP": "NWI",
    "NORTHWIND INDUSTRIAL CORPORATION": "NWI",
    "ZLG": "ZLG",
    "ZEPHYR": "ZLG",
    "ZEPHYR LOG": "ZLG",
    "ZEPHYR LOGISTICS": "ZLG",
    "ZEPHYR LOGISTICS LTD.": "ZLG",
    "ZEPHYR LOGISTICS GROUP": "ZLG",
}

KNOWN_NON_CORPUS_ENTITIES = [
    "TESLA", "APPLE", "MICROSOFT", "AMAZON", "GOOGLE", "ALPHABET", "META", "NVIDIA", "NIMBUS", "NIMBUS CLOUD"
]

# Canonical KPI Synonyms and Acronyms
KPI_SYNONYMS: Dict[str, str] = {
    # 16 Canonical KPIs
    "gross_margin_pct": "gross_margin_pct",
    "gross margin": "gross_margin_pct",
    "gross margin percentage": "gross_margin_pct",
    "gross margin percent": "gross_margin_pct",
    "gross profit margin": "gross_margin_pct",
    "gross profit percentage": "gross_margin_pct",
    "gross margin rate": "gross_margin_pct",
    "gm": "gross_margin_pct",
    "gp %": "gross_margin_pct",

    "operating_margin_pct": "operating_margin_pct",
    "operating margin": "operating_margin_pct",
    "operating margin percentage": "operating_margin_pct",
    "operating margin percent": "operating_margin_pct",
    "operating profit margin": "operating_margin_pct",
    "operating margin rate": "operating_margin_pct",
    "op margin": "operating_margin_pct",
    "om": "operating_margin_pct",

    "net_margin_pct": "net_margin_pct",
    "net margin": "net_margin_pct",
    "net margin percentage": "net_margin_pct",
    "profit margin": "net_margin_pct",

    "ebitda_usd": "ebitda_usd",
    "ebitda": "ebitda_usd",
    "operating cash earnings": "ebitda_usd",
    "earnings before interest": "ebitda_usd",

    "ebitda_margin_pct": "ebitda_margin_pct",
    "ebitda margin": "ebitda_margin_pct",

    "current_ratio_x": "current_ratio_x",
    "current ratio": "current_ratio_x",
    "working capital ratio": "current_ratio_x",
    "liquidity ratio": "current_ratio_x",
    "cr": "current_ratio_x",

    "debt_to_equity_x": "debt_to_equity_x",
    "debt to equity": "debt_to_equity_x",
    "debt-to-equity": "debt_to_equity_x",
    "debt to equity ratio": "debt_to_equity_x",
    "d/e ratio": "debt_to_equity_x",
    "d/e": "debt_to_equity_x",
    "leverage ratio": "debt_to_equity_x",

    "roe_quarterly_pct": "roe_quarterly_pct",
    "roe": "roe_quarterly_pct",
    "return on equity": "roe_quarterly_pct",

    "free_cash_flow_usd": "free_cash_flow_usd",
    "free cash flow": "free_cash_flow_usd",
    "fcf": "free_cash_flow_usd",
    "fcf flow": "free_cash_flow_usd",

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
    "net working capital": "working_capital_usd",
    "operating liquidity": "working_capital_usd",
    "wc": "working_capital_usd",

    # Key Line Items
    "revenue": "revenue",
    "revenues": "revenue",
    "net sales": "revenue",
    "sales": "revenue",
    "total revenues": "revenue",
    "top-line sales": "revenue",
    "rev": "revenue",

    "gross profit": "gross_profit",
    "operating income": "operating_income",
    "operating profit": "operating_income",
    "income from operations": "operating_income",
    "oi": "operating_income",

    "net income": "net_income",
    "net earnings": "net_income",
    "net income (loss)": "net_income",
    "bottom line earnings": "net_income",
    "ni": "net_income",
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
    def _normalize_query(cls, query: str) -> str:
        """Normalizes ordinals, written numbers, and quarter calendar phrases."""
        text = query.strip()
        # Ordinal quarters: 'first quarter' -> 'Q1', 'third quarter' -> 'Q3'
        text = re.sub(r"\b(?:first|1st)\s+quarter\b", "Q1", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(?:second|2nd)\s+quarter\b", "Q2", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(?:third|3rd)\s+quarter\b", "Q3", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(?:fourth|4th)\s+quarter\b", "Q4", text, flags=re.IGNORECASE)

        # Number words: 'quarter one' -> 'Q1'
        text = re.sub(r"\bquarter\s+(?:one|1)\b", "Q1", text, flags=re.IGNORECASE)
        text = re.sub(r"\bquarter\s+(?:two|2)\b", "Q2", text, flags=re.IGNORECASE)
        text = re.sub(r"\bquarter\s+(?:three|3)\b", "Q3", text, flags=re.IGNORECASE)
        text = re.sub(r"\bquarter\s+(?:four|4)\b", "Q4", text, flags=re.IGNORECASE)

        # Quarter ended month: 'quarter ended March' -> 'Q1'
        text = re.sub(r"\b(?:quarter|three\s+months)\s+ended\s+(?:march|mar)\b", "Q1", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(?:quarter|three\s+months)\s+ended\s+(?:june|jun)\b", "Q2", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(?:quarter|three\s+months)\s+ended\s+(?:september|sep|sept)\b", "Q3", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(?:quarter|three\s+months)\s+ended\s+(?:december|dec)\b", "Q4", text, flags=re.IGNORECASE)
        return text

    @classmethod
    def resolve(cls, query: str, prior_context: Optional[Any] = None) -> ResolvedQuery:
        clean_q = query.strip()
        norm_q = cls._normalize_query(clean_q)
        upper_q = norm_q.upper()

        # Normalize prior_context to string representation for regex scanning
        prior_str = ""
        dict_comp = None
        dict_fy = None
        dict_fq = None
        dict_kpi = None
        if isinstance(prior_context, dict):
            dict_comp = prior_context.get("company_id")
            dict_fy = prior_context.get("fiscal_year")
            dict_fq = prior_context.get("fiscal_quarter")
            dict_kpi = prior_context.get("kpi_id")
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

        # 4. Extract Covered Company Entities
        found_companies = []
        for alias, cid in sorted(COMPANY_ALIASES.items(), key=lambda x: -len(x[0])):
            if re.search(r"\b" + re.escape(alias) + r"\b", upper_q):
                if cid not in found_companies:
                    found_companies.append(cid)

        # Fuzzy matching fallback for light typos in company names
        if not found_companies:
            words = re.findall(r"\b[A-Za-z]{3,}\b", clean_q)
            for w in words:
                matches = difflib.get_close_matches(w.upper(), COMPANY_ALIASES.keys(), n=1, cutoff=0.80)
                if matches:
                    cid = COMPANY_ALIASES[matches[0]]
                    if cid not in found_companies:
                        found_companies.append(cid)
                        break

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

        # 5. Extract Fiscal Year & Quarter
        fy, fq = cls._extract_period(norm_q)

        # Handle multi-turn follow-ups like "What about the previous quarter?" or "prior quarter"
        is_prior_quarter_request = bool(re.search(r"\b(previous|prior)\s+quarter\b", clean_q, re.IGNORECASE))
        if (fy is None or is_prior_quarter_request) and (prior_str or dict_fy is not None):
            if dict_fy is not None and dict_fq is not None:
                p_fy, p_fq = dict_fy, dict_fq
            else:
                p_fy, p_fq = cls._extract_period(prior_str)

            if is_prior_quarter_request and p_fy is not None and p_fq is not None:
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

        # 6. Extract Basis (Documented Rule: default 'as_restated'; 'originally reported' -> 'as_originally_reported')
        clean_low = clean_q.lower()
        if any(term in clean_low for term in ("originally reported", "as reported", "original unadjusted")):
            basis = "as_originally_reported"
        else:
            basis = "as_restated"

        # 7. Extract KPI Identifier
        found_kpi = cls._extract_kpi(clean_q)
        if not found_kpi and prior_context:
            if dict_kpi:
                found_kpi = dict_kpi
            elif prior_str:
                found_kpi = cls._extract_kpi(prior_str)

        # 8. Check for Qualitative / Narrative Elements
        is_qualitative = bool(re.search(r"\b(why|explains?|explanation|drove|driver|factors?|note\s+\d+|notes?|litigation|hedging|risk|risks|discloses?|disclosures?|contract|outage|md&a|discussion|headwinds?|commentary|footnotes?|item\s+1a|item\s+2|10-k|10-q)\b", clean_q, re.IGNORECASE))
        has_kpi = (found_kpi is not None)

        if has_kpi and is_qualitative and (fy is not None):
            route = RouteType.MIXED
        elif is_qualitative:
            route = RouteType.UNSTRUCTURED
        elif has_kpi:
            route = RouteType.STRUCTURED
        else:
            if "search" in clean_low or "find" in clean_low or "patent" in clean_low or "restatement" in clean_low:
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

    @classmethod
    def _extract_period(cls, query: str) -> Tuple[Optional[int], Optional[int]]:
        """Comprehensive grammar parser for fiscal year and quarter representations."""
        # 1. FY2023 Q3 / FY2023-Q3 / FY23 Q3
        m1 = re.search(r"FY\s*(\d{2,4})[\s\-_]*Q\s*([1-4])", query, re.IGNORECASE)
        if m1:
            raw_y = int(m1.group(1))
            fy = raw_y if raw_y > 100 else 2000 + raw_y
            return fy, int(m1.group(2))

        # 2. Q3 of fiscal 2023 / Q3 of 2023 / Q1 FY2024 / Q2 in 2022
        m2 = re.search(r"Q\s*([1-4])\s*(?:of|in)?\s*(?:fiscal(?:\s+year)?)?\s*(?:FY\s*)?(\d{2,4})", query, re.IGNORECASE)
        if m2:
            raw_y = int(m2.group(2))
            fy = raw_y if raw_y > 100 else 2000 + raw_y
            return fy, int(m2.group(1))

        # 3. fiscal year 2022 quarter 1 / fiscal 2024 quarter 2
        m3 = re.search(r"fiscal(?:\s+year)?\s+(\d{4})\s+(?:quarter|Q)\s+([1-4])", query, re.IGNORECASE)
        if m3:
            return int(m3.group(1)), int(m3.group(2))

        # 4. 2023 Q1
        m4 = re.search(r"\b(\d{4})\s*Q\s*([1-4])\b", query, re.IGNORECASE)
        if m4:
            return int(m4.group(1)), int(m4.group(2))

        # 5. Q1 2023
        m5 = re.search(r"\bQ\s*([1-4])\s+(\d{4})\b", query, re.IGNORECASE)
        if m5:
            return int(m5.group(2)), int(m5.group(1))

        # 6. Combined year + normalized Q token anywhere in string
        m_year = re.search(r"\b(202[0-9])\b", query)
        m_q = re.search(r"\bQ([1-4])\b", query)
        if m_year and m_q:
            return int(m_year.group(1)), int(m_q.group(1))

        # 7. Form 10-K with year implies Q4 annual filing in SEC chunk corpus
        m_10k = re.search(r"\b(?:FY\s*)?(\d{4})\b.*?\b10-?K\b", query, re.IGNORECASE)
        if m_10k:
            return int(m_10k.group(1)), 4

        # 8. Year-only
        if m_year:
            return int(m_year.group(1)), None

        return None, None

    @classmethod
    def _extract_kpi(cls, query: str) -> Optional[str]:
        q_low = query.lower()
        upper_q = query.upper()

        # 1. Exact phrase matching (sorted by length descending for greedy match)
        for phrase, canonical in sorted(KPI_SYNONYMS.items(), key=lambda x: -len(x[0])):
            pattern = r"\b" + re.escape(phrase) + r"\b"
            if re.search(pattern, q_low):
                return canonical

        # 2. Acronym exact word boundary check
        acronyms = {
            "GM": "gross_margin_pct",
            "OM": "operating_margin_pct",
            "OI": "operating_income",
            "NI": "net_income",
            "FCF": "free_cash_flow_usd",
            "CR": "current_ratio_x",
            "WC": "working_capital_usd",
            "REV": "revenue",
            "EBITDA": "ebitda_usd",
            "ROE": "roe_quarterly_pct",
            "D/E": "debt_to_equity_x"
        }
        for acr, canon in acronyms.items():
            if re.search(r"\b" + re.escape(acr) + r"\b", upper_q):
                return canon

        # 3. Token-level fuzzy match fallback
        words = re.findall(r"\b[A-Za-z]{3,}\b", q_low)
        for w in words:
            matches = difflib.get_close_matches(w, KPI_SYNONYMS.keys(), n=1, cutoff=0.82)
            if matches:
                return KPI_SYNONYMS[matches[0]]

        return None
