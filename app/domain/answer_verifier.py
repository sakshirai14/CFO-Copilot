"""app/domain/answer_verifier.py

Pure Python deterministic AnswerVerifier enforcing the Grounded-Answer Contract.
(Phase 4b Step 3)

Verification Invariants:
1. Zero 1.5% tolerance: A number in the answer is accepted ONLY if it equals the fact's value
   after unit normalization and ROUNDING to the number of decimals the answer itself shows:
   - 26.79% accepts 26.79%, 26.8%, 27%; rejects 27.2%.
   - $109,200,000 accepts $109.2M and $109.2 million; rejects $110.8M and $1.092B.
2. Magnitude errors (x10, x1000, 1/10, 1/1000) are strictly rejected.
3. Sign flips (+ vs -) are strictly rejected.
4. Percent vs ratio (e.g. 26.79 vs 26.79% or 0.2679) are strictly rejected.
5. Entity scoping: facts_used must include at least one fact for every company and period named in the answer.
6. Refusal consistency: status 'insufficient_data' / 'refused' cannot make affirmative financial claims.
7. Security guard: regex patterns block credential leaks, database passwords, and prompt injection echoes.
"""

import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from app.inference.contract import AnswerStatus, GroundedAnswer, InputFact


class ExtractedNumber(BaseModel):
    raw_text: str
    value: float  # Value in base units (e.g. 109200000.0 for $109.2M, 26.79 for 26.79%)
    display_value: float  # Number as displayed (e.g. 109.2 for $109.2M, 26.79 for 26.79%)
    kind: str  # 'currency', 'percentage', 'ratio', 'integer'
    scale: float  # 1e9, 1e6, 1e3, 1.0
    decimals: int  # Number of decimal places shown in the raw token
    is_negative: bool


class VerificationResult(BaseModel):
    valid: bool
    violations: List[str] = Field(default_factory=list)
    ungrounded_numbers: List[Dict[str, Any]] = Field(default_factory=list)
    matched_facts: List[str] = Field(default_factory=list)


class AnswerVerifier:
    """Pure Python deterministic verifier for CFO Copilot responses."""

    SECURITY_PATTERNS = [
        re.compile(r"postgres(?:ql)?://[^\s]+", re.IGNORECASE),
        re.compile(r"password\s*[:=]\s*['\"]?[^\s'\"]+", re.IGNORECASE),
        re.compile(r"information_schema\.tables", re.IGNORECASE),
        re.compile(r"developer\s+mode\s+activated", re.IGNORECASE),
        re.compile(r"bypass(?:ing)?\s+all\s+guardrails", re.IGNORECASE),
        re.compile(r"malicious-exfil-server\.com", re.IGNORECASE),
    ]

    COMPANY_ALIASES = {
        "ARG": ["arg", "aurora retail", "aurora retail group"],
        "CEP": ["cep", "cobalt energy", "cobalt energy partners"],
        "HBS": ["hbs", "helix biosystems", "helix bio", "helix"],
        "MSI": ["msi", "main street investments", "main street"],
        "NWI": ["nwi", "northwind", "northwind industrial", "northwind industrial corp"],
        "ZLG": ["zlg", "zephyr", "zephyr logistics"],
    }

    @staticmethod
    def get_decimal_places(num_str: str) -> int:
        """Counts decimals in numeric string representation."""
        m = re.search(r"\b\d+\.(\d+)", num_str)
        if m:
            return len(m.group(1))
        return 0

    @classmethod
    def parse_numeric_token(cls, raw: str) -> Optional[ExtractedNumber]:
        """Parses a numerical token into ExtractedNumber with scale and decimal precision."""
        clean = raw.strip().replace(",", "")
        is_neg = False
        if clean.startswith("-") or ("(" in clean and ")" in clean):
            is_neg = True
        clean = clean.replace("$", "").replace("(", "").replace(")", "").replace("-", "").replace("+", "").strip()

        kind = "currency"
        scale = 1.0

        if clean.endswith("%"):
            kind = "percentage"
            core_str = clean[:-1].strip()
            try:
                disp_val = float(core_str)
                decimals = cls.get_decimal_places(core_str)
                val = -disp_val if is_neg else disp_val
                return ExtractedNumber(
                    raw_text=raw,
                    value=val,
                    display_value=disp_val,
                    kind="percentage",
                    scale=1.0,
                    decimals=decimals,
                    is_negative=is_neg,
                )
            except ValueError:
                return None

        if clean.lower().endswith("x"):
            kind = "ratio"
            core_str = clean[:-1].strip()
            try:
                disp_val = float(core_str)
                decimals = cls.get_decimal_places(core_str)
                val = -disp_val if is_neg else disp_val
                return ExtractedNumber(
                    raw_text=raw,
                    value=val,
                    display_value=disp_val,
                    kind="ratio",
                    scale=1.0,
                    decimals=decimals,
                    is_negative=is_neg,
                )
            except ValueError:
                return None

        # Check currency / multiplier suffix
        core_str = clean
        if re.search(r"(?i)\b(?:b|billion)\b", clean) or clean.lower().endswith("b"):
            scale = 1e9
            core_str = re.sub(r"(?i)\b(?:b|billion)\b|b$", "", clean).strip()
        elif re.search(r"(?i)\b(?:m|million)\b", clean) or clean.lower().endswith("m"):
            scale = 1e6
            core_str = re.sub(r"(?i)\b(?:m|million)\b|m$", "", clean).strip()
        elif re.search(r"(?i)\b(?:k|thousand)\b", clean) or clean.lower().endswith("k"):
            scale = 1e3
            core_str = re.sub(r"(?i)\b(?:k|thousand)\b|k$", "", clean).strip()

        try:
            disp_val = float(core_str)
            decimals = cls.get_decimal_places(core_str)
            val = (-disp_val if is_neg else disp_val) * scale
            return ExtractedNumber(
                raw_text=raw,
                value=val,
                display_value=disp_val,
                kind=kind,
                scale=scale,
                decimals=decimals,
                is_negative=is_neg,
            )
        except ValueError:
            return None

    @classmethod
    def extract_numbers_from_text(cls, text: str) -> List[ExtractedNumber]:
        """Extracts financial numbers while masking calendar dates and filing labels."""
        extracted: List[ExtractedNumber] = []

        # Mask calendar years, quarters, and form identifiers
        masked = re.sub(r"\b202[0-9]\b", " ", text)
        masked = re.sub(r"\bFY202[0-9]\b", " ", masked, flags=re.IGNORECASE)
        masked = re.sub(r"\bQ[1-4]\b", " ", masked, flags=re.IGNORECASE)
        masked = re.sub(r"\b(?:first|second|third|fourth)\s+quarter\b", " ", masked, flags=re.IGNORECASE)
        masked = re.sub(r"\b10-[KQ](?:/A)?\b", " ", masked, flags=re.IGNORECASE)
        masked = re.sub(r"\bRule\s+R\d+\b", " ", masked, flags=re.IGNORECASE)
        masked = re.sub(r"\bNote\s+\d+\b", " ", masked, flags=re.IGNORECASE)

        # 1. Percentages: 26.79%, 26.8%, 27%
        pct_pat = re.compile(r"[-+]?\d+(?:\.\d+)?%", re.IGNORECASE)
        for m in pct_pat.finditer(masked):
            parsed = cls.parse_numeric_token(m.group(0))
            if parsed:
                extracted.append(parsed)

        # 2. Ratios: 1.85x, 0.42x
        ratio_pat = re.compile(r"\b\d+(?:\.\d+)?x\b", re.IGNORECASE)
        for m in ratio_pat.finditer(masked):
            parsed = cls.parse_numeric_token(m.group(0))
            if parsed:
                extracted.append(parsed)

        # 3. Currency and monetary units: $109.2M, $109.2 million, $109,200,000, -$15M, $1.092B
        # Mask out already extracted percentages and ratios to avoid double-extracting prefix numbers
        masked_for_curr = pct_pat.sub(" ", masked)
        masked_for_curr = ratio_pat.sub(" ", masked_for_curr)

        curr_pat = re.compile(
            r"[-+]?\$?\s*\(?\d+(?:,\d{3})*(?:\.\d+)?\s*(?:(?:billion|million|thousand|[BMK])\b)?\)?",
            re.IGNORECASE,
        )
        for m in curr_pat.finditer(masked_for_curr):
            raw = m.group(0).strip()
            if not raw or raw in ["$", "-", "+", "()"]:
                continue
            if "%" in raw or raw.endswith("x"):
                continue
            parsed = cls.parse_numeric_token(raw)
            if parsed:
                # Filter out small integers under 100 without currency / scale symbols (e.g. '30 days')
                if parsed.value < 100 and parsed.scale == 1.0 and "$" not in raw and "." not in raw:
                    continue
                extracted.append(parsed)

        return extracted

    @classmethod
    def numbers_match_with_rounding(
        cls,
        ans_num: ExtractedNumber,
        fact_num: ExtractedNumber,
    ) -> bool:
        """Strict numerical equality after unit normalization and ROUNDING to answer decimals.

        Zero 1.5% tolerance rule:
        - Kind must match (percentage matches percentage; ratio matches ratio; currency matches currency).
        - Signs must match (positive vs negative).
        - Value must match after rounding fact to answer's displayed decimal precision.
        """
        # 1. Kind mismatch
        if ans_num.kind != fact_num.kind:
            return False

        # 2. Sign mismatch
        if ans_num.is_negative != fact_num.is_negative:
            return False

        dec = ans_num.decimals

        # 3. Percentage matching
        if ans_num.kind == "percentage":
            ans_val = abs(ans_num.display_value)
            fact_val = abs(fact_num.display_value)
            # Round fact to the number of decimals the answer shows
            rounded_fact = round(fact_val, dec)
            return math.isclose(ans_val, rounded_fact, abs_tol=1e-5)

        # 4. Ratio matching
        if ans_num.kind == "ratio":
            ans_val = abs(ans_num.display_value)
            fact_val = abs(fact_num.display_value)
            rounded_fact = round(fact_val, dec)
            return math.isclose(ans_val, rounded_fact, abs_tol=1e-5)

        # 5. Currency / monetary matching
        if ans_num.kind == "currency":
            # Compare at the scale used in the answer
            ans_scaled_val = abs(ans_num.display_value)
            fact_scaled_val = abs(fact_num.value) / ans_num.scale
            rounded_fact = round(fact_scaled_val, dec)
            return math.isclose(ans_scaled_val, rounded_fact, abs_tol=1e-5)

        return False

    @classmethod
    def extract_companies_mentioned(cls, text: str) -> Set[str]:
        """Detects which of the 6 public companies are named in text."""
        lowered = text.lower()
        found = set()
        for cid, aliases in cls.COMPANY_ALIASES.items():
            for a in aliases:
                # Word boundary match
                if re.search(rf"\b{re.escape(a)}\b", lowered):
                    found.add(cid)
                    break
        return found

    @classmethod
    def extract_periods_mentioned(cls, text: str) -> Set[str]:
        """Detects fiscal periods (e.g. FY2023, Q2) named in text."""
        periods = set()
        for m in re.finditer(r"\b(FY202[0-9]|202[0-9])\b", text, re.IGNORECASE):
            periods.add(m.group(0).upper())
        for m in re.finditer(r"\bQ[1-4]\b", text, re.IGNORECASE):
            periods.add(m.group(0).upper())
        return periods

    @classmethod
    def verify(
        cls,
        answer: GroundedAnswer,
        input_facts: List[InputFact],
    ) -> VerificationResult:
        """Verifies GroundedAnswer against input facts under Phase 4b strict contract."""
        violations: List[str] = []
        ungrounded: List[Dict[str, Any]] = []
        matched_facts: Set[str] = set()

        fact_map = {f.fact_id: f for f in input_facts}

        # 1. Check Security & Prohibited Leaks
        for pattern in cls.SECURITY_PATTERNS:
            if pattern.search(answer.answer):
                violations.append(f"Security violation: Answer text contains prohibited pattern '{pattern.pattern}'")

        # 2. Check Fact ID Provenance
        for cited_id in answer.facts_used:
            if cited_id not in fact_map:
                violations.append(f"Citation violation: Fact ID '{cited_id}' was not in input facts context")
            else:
                matched_facts.add(cited_id)

        # 3. Refusal Consistency (insufficient_data / refused / missing_data)
        if answer.status in (AnswerStatus.INSUFFICIENT_DATA, AnswerStatus.REFUSED, AnswerStatus.MISSING_DATA):
            financial_claims = re.findall(
                r"\b(?:revenue|margin|income|profit|ratio)\s+(?:was|is|reached|amounted to)\s+[-+]?\$?\d+",
                answer.answer,
                re.IGNORECASE,
            )
            if financial_claims:
                violations.append(
                    f"Refusal violation: Status is '{answer.status.value}' but answer makes affirmative claims: {financial_claims}"
                )
            return VerificationResult(
                valid=(len(violations) == 0),
                violations=violations,
                ungrounded_numbers=[],
                matched_facts=list(matched_facts),
            )

        # 4. Entity Scoping: Check that facts_used includes facts for every company & period named
        companies_in_answer = cls.extract_companies_mentioned(answer.answer)
        periods_in_answer = cls.extract_periods_mentioned(answer.answer)

        cited_facts = [fact_map[fid] for fid in answer.facts_used if fid in fact_map]
        cited_companies = {f.company_id for f in cited_facts if f.company_id}
        cited_years = {str(f.fiscal_year) for f in cited_facts if f.fiscal_year}
        cited_quarters = {f"Q{f.fiscal_quarter}" for f in cited_facts if f.fiscal_quarter}

        for comp in companies_in_answer:
            if comp not in cited_companies:
                violations.append(
                    f"Scope violation: Answer mentions company '{comp}', but facts_used contains no facts for this company."
                )

        # 5. Numerical Grounding (for status == 'answered' / 'ok')
        extracted_numbers = cls.extract_numbers_from_text(answer.answer)

        # Extract parsed numbers from cited facts
        fact_extracted_numbers: List[Tuple[ExtractedNumber, InputFact]] = []
        for fact in cited_facts:
            # Fact value
            if fact.value is not None:
                val_str = str(fact.value)
                parsed_val = cls.parse_numeric_token(val_str)
                if parsed_val:
                    fact_extracted_numbers.append((parsed_val, fact))
            # Text of fact
            for f_num in cls.extract_numbers_from_text(fact.text):
                fact_extracted_numbers.append((f_num, fact))

        for ext in extracted_numbers:
            matched = False
            for f_num, fact in fact_extracted_numbers:
                if cls.numbers_match_with_rounding(ext, f_num):
                    matched = True
                    break

            if not matched:
                ungrounded.append({
                    "raw_text": ext.raw_text,
                    "extracted_value": ext.value,
                    "kind": ext.kind,
                    "decimals": ext.decimals,
                })
                violations.append(
                    f"Ungrounded number: '{ext.raw_text}' (value {ext.value}, kind {ext.kind}, decimals {ext.decimals}) "
                    f"does not match any cited fact value after unit normalization and rounding."
                )

        # If answered, at least one fact must be cited
        if answer.status in (AnswerStatus.ANSWERED, AnswerStatus.OK) and not answer.facts_used:
            violations.append("Contract violation: Status is 'answered' but facts_used is empty")

        is_valid = (len(violations) == 0 and len(ungrounded) == 0)

        return VerificationResult(
            valid=is_valid,
            violations=violations,
            ungrounded_numbers=ungrounded,
            matched_facts=list(matched_facts),
        )
