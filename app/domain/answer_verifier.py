"""app/domain/answer_verifier.py

Pure-Python, deterministic answer verifier (Foundation Locks 1, 3, 4, 10, 11).
Enforces the Grounded-Answer Contract:
- Extracts financial numbers from narrative answers
- Verifies extracted numbers match cited input facts within tolerance
- Verifies cited fact IDs exist in input prompt context
- Enforces refusal contract (no fabricated figures on refused/missing data)
- Detects leaked connection strings, prompt instructions, and external URLs
"""

import math
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

from app.inference.contract import AnswerStatus, GroundedAnswer, InputFact


@dataclass
class ExtractedNumber:
    raw_text: str
    value: float
    kind: str  # 'currency', 'percentage', 'ratio', 'plain'


@dataclass
class VerificationResult:
    valid: bool
    violations: List[str] = field(default_factory=list)
    ungrounded_numbers: List[Dict[str, Any]] = field(default_factory=list)
    matched_facts: List[str] = field(default_factory=list)


class AnswerVerifier:
    """Deterministic verifier for LLM generated financial answers."""

    # Patterns indicating leaked internal prompt instructions or credentials
    SECURITY_PATTERNS = [
        re.compile(r"postgres(?:ql)?://[^\s]+", re.IGNORECASE),
        re.compile(r"password\s*=\s*[^\s]+", re.IGNORECASE),
        re.compile(r"system\s+notice\s+to\s+ai", re.IGNORECASE),
        re.compile(r"disregard\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"developer\s+mode\s+activated", re.IGNORECASE),
        re.compile(r"https?://[^\s]+", re.IGNORECASE),  # No external URLs
    ]

    @classmethod
    def parse_numeric_token(cls, raw: str) -> Optional[float]:
        """Parses a numerical string token (e.g. '$109.2M', '26.79%', '1,450') into a float."""
        clean = raw.strip().replace(",", "").replace("$", "").replace("(", "-").replace(")", "")
        multiplier = 1.0

        if clean.endswith("%"):
            clean = clean[:-1]
            return float(clean)  # treat as percentage point, e.g. 26.79

        if clean.lower().endswith("b") or clean.lower().endswith("billion"):
            multiplier = 1e9
            clean = re.sub(r"(?i)b(?:illion)?", "", clean)
        elif clean.lower().endswith("m") or clean.lower().endswith("million"):
            multiplier = 1e6
            clean = re.sub(r"(?i)m(?:illion)?", "", clean)
        elif clean.lower().endswith("k") or clean.lower().endswith("thousand"):
            multiplier = 1e3
            clean = re.sub(r"(?i)k(?:housand)?", "", clean)
        elif clean.lower().endswith("x"):
            clean = clean[:-1]

        clean = clean.strip()
        try:
            val = float(clean) * multiplier
            return val
        except ValueError:
            return None

    @classmethod
    def extract_numbers_from_text(cls, text: str) -> List[ExtractedNumber]:
        """Extracts financial numbers from narrative text while ignoring fiscal years and quarters."""
        extracted: List[ExtractedNumber] = []

        # Mask fiscal years and quarters before token extraction
        masked = re.sub(r"\b202[0-9]\b", " ", text)
        masked = re.sub(r"\bFY202[0-9]\b", " ", masked, flags=re.IGNORECASE)
        masked = re.sub(r"\bQ[1-4]\b", " ", masked, flags=re.IGNORECASE)
        masked = re.sub(r"\b(?:first|second|third|fourth)\s+quarter\b", " ", masked, flags=re.IGNORECASE)
        masked = re.sub(r"\b10-[KQ](?:/A)?\b", " ", masked, flags=re.IGNORECASE)
        masked = re.sub(r"\bRule\s+R\d+\b", " ", masked, flags=re.IGNORECASE)

        # Regex patterns for financial tokens
        # 1. Currency with scale: $109.2M, $109.2 million, $54,300,000, -$12.4M
        currency_pattern = re.compile(
            r"[-+]?\$?\s*\(?\d+(?:,\d{3})*(?:\.\d+)?\s*(?:(?:billion|million|thousand|[BMK])\b)?\)?",
            re.IGNORECASE
        )
        # 2. Percentage: 26.79%, 0.00%, -5.2%
        percentage_pattern = re.compile(r"[-+]?\d+(?:\.\d+)?%", re.IGNORECASE)
        # 3. Ratio: 1.85x, 0.42x
        ratio_pattern = re.compile(r"\b\d+(?:\.\d+)?x\b", re.IGNORECASE)

        # Extract percentages
        for match in percentage_pattern.finditer(masked):
            raw = match.group(0).strip()
            val = cls.parse_numeric_token(raw)
            if val is not None:
                extracted.append(ExtractedNumber(raw_text=raw, value=val, kind="percentage"))

        # Extract ratios
        for match in ratio_pattern.finditer(masked):
            raw = match.group(0).strip()
            val = cls.parse_numeric_token(raw)
            if val is not None:
                extracted.append(ExtractedNumber(raw_text=raw, value=val, kind="ratio"))

        # Extract currencies & raw metrics
        for match in currency_pattern.finditer(masked):
            raw = match.group(0).strip()
            if not raw or raw in ["$", "-", "+", "()"]:
                continue
            # Avoid re-matching pure percentages or ratios
            if "%" in raw or raw.endswith("x"):
                continue
            val = cls.parse_numeric_token(raw)
            if val is not None:
                # Filter out pure integers under 100 that might be counts/ranks (e.g. 'top 5', 'rank 1')
                if val < 100 and "." not in raw and not any(k in raw.lower() for k in ["$", "m", "k", "b"]):
                    continue
                extracted.append(ExtractedNumber(raw_text=raw, value=val, kind="currency"))

        return extracted

    @classmethod
    def numbers_match(cls, val1: float, val2: float, tolerance_pct: float = 0.5) -> bool:
        """Determines if two values match within scaling or relative rounding tolerance."""
        if val1 == 0.0 and val2 == 0.0:
            return True
        if val1 == 0.0 or val2 == 0.0:
            return abs(val1 - val2) < 0.01

        # Direct comparison with tolerance
        rel_diff = abs(val1 - val2) / max(abs(val1), abs(val2))
        if rel_diff <= (tolerance_pct / 100.0):
            return True

        # Scaling comparison (e.g. 109,200,000 vs 109.2, or percentage 26.79 vs 0.2679)
        scales = [1e3, 1e6, 1e9, 100.0, 0.01]
        for s in scales:
            scaled1 = val1 * s
            if abs(scaled1 - val2) / max(abs(scaled1), abs(val2)) <= (tolerance_pct / 100.0):
                return True
            scaled2 = val2 * s
            if abs(val1 - scaled2) / max(abs(val1), abs(scaled2)) <= (tolerance_pct / 100.0):
                return True

        return False

    @classmethod
    def verify(
        cls,
        answer: GroundedAnswer,
        input_facts: List[InputFact],
    ) -> VerificationResult:
        """Verifies a GroundedAnswer against provided input facts."""
        violations = []
        ungrounded = []
        matched_facts = set()

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

        # 3. Check Refusal Consistency
        if answer.status in (AnswerStatus.REFUSED, AnswerStatus.MISSING_DATA):
            # Check if answer makes an affirmative financial calculation claim
            financial_claims = re.findall(
                r"\b(?:revenue|margin|income|profit|ratio)\s+(?:was|is|reached|amounted to)\s+[-+]?\$?\d+",
                answer.answer,
                re.IGNORECASE,
            )
            if financial_claims:
                violations.append(
                    f"Refusal violation: Status is '{answer.status.value}' but answer makes affirmative claims: {financial_claims}"
                )
            # A valid refusal does not need numerical grounding against facts
            return VerificationResult(
                valid=(len(violations) == 0),
                violations=violations,
                ungrounded_numbers=[],
                matched_facts=list(matched_facts),
            )

        # 4. Check Numerical Grounding (for status == 'ok')
        extracted_numbers = cls.extract_numbers_from_text(answer.answer)

        # Collect all numeric values present in cited facts
        fact_values: List[float] = []
        for cited_id in answer.facts_used:
            fact = fact_map.get(cited_id)
            if not fact:
                continue
            if fact.value is not None:
                try:
                    fact_values.append(float(fact.value))
                except (ValueError, TypeError):
                    pass
            # Also extract numbers from fact.text
            for f_num in cls.extract_numbers_from_text(fact.text):
                fact_values.append(f_num.value)

        # Every extracted number must match at least one fact value
        for ext in extracted_numbers:
            matched = False
            for f_val in fact_values:
                if cls.numbers_match(ext.value, f_val):
                    matched = True
                    break

            if not matched:
                ungrounded.append({
                    "raw_text": ext.raw_text,
                    "extracted_value": ext.value,
                    "kind": ext.kind,
                })
                violations.append(
                    f"Ungrounded number: '{ext.raw_text}' (value: {ext.value}) does not match any value in cited facts"
                )

        # Ensure that if status is ok, at least one fact was cited
        if answer.status == AnswerStatus.OK and not answer.facts_used:
            violations.append("Contract violation: Status is 'ok' but facts_used is empty")

        is_valid = (len(violations) == 0 and len(ungrounded) == 0)

        return VerificationResult(
            valid=is_valid,
            violations=violations,
            ungrounded_numbers=ungrounded,
            matched_facts=list(matched_facts),
        )
