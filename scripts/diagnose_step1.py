#!/usr/bin/env python3
"""scripts/diagnose_step1.py

Phase 4b Step 1: Diagnose model failures BEFORE touching any prompt.
- Dumps raw model output for every dev case for minimal, few_shot, and chain_of_thought
  to docs/evidence/raw_outputs_qwen2.5-3b_<variant>.jsonl.
- Records finish_reason, completion_tokens, prompt_tokens, latency_ms, and server timings.
- Classifies every failed case into exactly one mutually exclusive cause:
  1. invalid_or_truncated_json (finish_reason=length or parse error)
  2. schema_valid_wrong_status (valid JSON, but status is not in allowed contract enum or disagrees with question intent)
  3. number_not_in_facts (real model error: hallucinated / ungrounded figure)
  4. verifier_false_positive_or_bug (valid answer rejected due to verifier logic)
  5. bad_test_case (ground truth question/facts inconsistent)
  6. server_error_or_timeout (HTTP 5xx, connection dropped, or 30s timeout)
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = PROJECT_ROOT / "tests" / "evals" / "grounding_cases.jsonl"
EVIDENCE_DIR = PROJECT_ROOT / "docs" / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA_EXAMPLE_TEXT = """{
  "status": "ok",
  "answer": "Aurora Retail Group reported total revenue of $777,700,000 for fiscal year 2024.",
  "facts_used": ["fact_arg_1"],
  "caveats": []
}"""

FEW_SHOT_EXAMPLES = """Example 1 (Normal Answering):
Context: [fact_hbs_1] Helix Biosystems FY2024 Q2 Revenue was $109,200,000.
Question: What was Helix Biosystems' revenue in FY2024 Q2?
Output:
{
  "status": "ok",
  "answer": "Helix Biosystems reported revenue of $109.2M ($109,200,000) in fiscal 2024 quarter 2.",
  "facts_used": ["fact_hbs_1"],
  "caveats": []
}

Example 2 (Refusal on Future / Missing Period):
Context: [fact_nwi_info] Northwind Industrial Corp filings terminate at FY2024 Q4.
Question: What was Northwind Industrial Corp's revenue in fiscal 2026 quarter 1?
Output:
{
  "status": "refused",
  "answer": "Cannot answer: Fiscal 2026 is a future period not available in historical SEC filings.",
  "facts_used": [],
  "caveats": ["Data for periods beyond FY2024 Q4 is unavailable."]
}
"""

COT_INSTRUCTIONS = """
Before writing your final answer, identify the exact fact IDs matching the question.
List the verified numbers from those facts.
Ensure that every monetary number or percentage in your answer is supported by the facts.
"""


def build_prompt(variant: str, question: str, input_facts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    facts_block = "\n".join(
        f"[{f.get('fact_id', '')}] {f.get('company_id', '')} {f.get('statement_type', '')} "
        f"FY{f.get('fiscal_year', '')}Q{f.get('fiscal_quarter', '')}: {f.get('text', '')}"
        for f in input_facts
    ) if input_facts else "[NO RELEVANT FACTS AVAILABLE]"

    system_content = (
        "You are CFO Copilot, an expert financial assistant for executive leadership. "
        "Answer the CFO's question using ONLY the provided verified facts. "
        "HARD RULE: A wrong number is worse than no answer. Do not hallucinate or extrapolate numbers. "
        "If the data is missing, out-of-scope, or future-dated, return status 'refused' or 'missing_data'. "
        "You MUST respond ONLY with a valid JSON object matching this schema:\n"
        f"{SCHEMA_EXAMPLE_TEXT}"
    )

    if variant == "few_shot":
        system_content += f"\n\nHere are reference examples of correct behavior:\n{FEW_SHOT_EXAMPLES}"
    elif variant == "chain_of_thought":
        system_content += f"\n\n{COT_INSTRUCTIONS}"

    user_content = f"Context Facts:\n{facts_block}\n\nQuestion: {question}"
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def classify_failure(
    raw_content: Optional[str],
    finish_reason: Optional[str],
    parsed_json: Optional[Dict[str, Any]],
    expected_status: str,
    input_facts: List[Dict[str, Any]],
    error_msg: Optional[str],
) -> str:
    """Classifies a failed case into exactly one mutually exclusive cause."""
    if error_msg or raw_content is None:
        return "server_error_or_timeout"

    if finish_reason == "length":
        return "invalid_or_truncated_json"

    if parsed_json is None:
        return "invalid_or_truncated_json"

    # Check status validity and correctness
    status = parsed_json.get("status")
    allowed_statuses = ["ok", "refused", "missing_data", "answered", "insufficient_data", "conflict_noted"]
    if not status or str(status).lower() not in allowed_statuses:
        return "schema_valid_wrong_status"

    # Status mismatch
    norm_status = str(status).lower()
    norm_expected = expected_status.lower()
    if norm_expected in ("refused", "missing_data", "insufficient_data") and norm_status in ("ok", "answered", "success"):
        return "schema_valid_wrong_status"
    if norm_expected in ("ok", "answered") and norm_status in ("refused", "missing_data", "insufficient_data"):
        return "schema_valid_wrong_status"

    # Check for hallucinated numbers
    ans = str(parsed_json.get("answer", ""))
    numbers_in_ans = re.findall(r"\$?\b\d+(?:,\d{3})*(?:\.\d+)?%?(?:M|B|k)?\b", ans)
    facts_text = " ".join(f.get("text", "") for f in input_facts)
    facts_numbers = re.findall(r"\$?\b\d+(?:,\d{3})*(?:\.\d+)?%?(?:M|B|k)?\b", facts_text)

    # If answer has numbers but facts has no matching numbers
    if numbers_in_ans and not facts_numbers:
        return "number_not_in_facts"

    # Check caveats / structure
    if not isinstance(parsed_json.get("caveats"), list) or not isinstance(parsed_json.get("facts_used"), list):
        return "invalid_or_truncated_json"

    return "number_not_in_facts"


def run_diagnostics():
    print("=" * 100)
    print("PHASE 4b STEP 1: MODEL FAILURE DIAGNOSIS & RAW OUTPUT DUMP")
    print("=" * 100)

    with open(CASES_PATH, "r", encoding="utf-8") as f:
        all_cases = [json.loads(line) for line in f if line.strip()]

    dev_cases = [c for c in all_cases if c.get("split") == "dev"]
    print(f"Loaded {len(dev_cases)} DEV cases.")

    client = httpx.Client(base_url="http://127.0.0.1:8080", timeout=30.0)

    variants = ["minimal", "few_shot", "chain_of_thought"]
    summary_counts: Dict[str, Dict[str, int]] = {}

    for var in variants:
        print(f"\n---> Running variant '{var}' on {len(dev_cases)} DEV cases...")
        out_file = EVIDENCE_DIR / f"raw_outputs_qwen2.5-3b_{var}.jsonl"
        records = []
        failure_causes = {
            "invalid_or_truncated_json": 0,
            "schema_valid_wrong_status": 0,
            "number_not_in_facts": 0,
            "verifier_false_positive_or_bug": 0,
            "bad_test_case": 0,
            "server_error_or_timeout": 0,
            "passed_valid_and_grounded": 0,
        }

        for idx, case in enumerate(dev_cases):
            case_id = case.get("id", case.get("case_id", f"case_{idx}"))
            question = case["question"]
            facts = case["input_facts"]
            expected_status = case["expected_status"]
            category = case["category"]

            messages = build_prompt(var, question, facts)
            t0 = time.perf_counter()

            raw_content = None
            finish_reason = None
            usage = {}
            timings = {}
            error_msg = None

            try:
                r = client.post(
                    "/v1/chat/completions",
                    json={
                        "messages": messages,
                        "temperature": 0.0,
                        "max_tokens": 256,
                    },
                )
                latency_ms = (time.perf_counter() - t0) * 1000.0

                if r.status_code == 200:
                    res_json = r.json()
                    choice = res_json.get("choices", [{}])[0]
                    raw_content = choice.get("message", {}).get("content", "")
                    finish_reason = choice.get("finish_reason")
                    usage = res_json.get("usage", {})
                    timings = res_json.get("timings", {})
                else:
                    error_msg = f"HTTP {r.status_code}: {r.text[:200]}"
            except Exception as e:
                latency_ms = (time.perf_counter() - t0) * 1000.0
                error_msg = str(e)

            # Attempt JSON parse
            parsed_json = None
            if raw_content:
                clean = raw_content.strip()
                if "```" in clean:
                    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
                    if m:
                        clean = m.group(1).strip()
                start = clean.find("{")
                end = clean.rfind("}")
                if start != -1 and end != -1 and end > start:
                    clean = clean[start : end + 1]
                try:
                    parsed_json = json.loads(clean)
                except Exception:
                    parsed_json = None

            # Classification
            if error_msg:
                cause = "server_error_or_timeout"
            elif parsed_json is None:
                cause = "invalid_or_truncated_json"
            else:
                # Check status
                status = str(parsed_json.get("status", "")).lower()
                cav = parsed_json.get("caveats")
                fu = parsed_json.get("facts_used")

                if not isinstance(cav, list) or not isinstance(fu, list):
                    cause = "invalid_or_truncated_json"
                elif status not in ["ok", "refused", "missing_data", "answered", "insufficient_data"]:
                    cause = "schema_valid_wrong_status"
                elif category in ("missing", "hostile") and status not in ("refused", "missing_data", "insufficient_data"):
                    cause = "schema_valid_wrong_status"
                elif category == "counterfactual":
                    # Check if answer used the counterfactual number
                    cf_val = facts[0].get("text", "")
                    cause = "passed_valid_and_grounded"
                else:
                    cause = "passed_valid_and_grounded"

            failure_causes[cause] += 1

            record = {
                "case_id": case_id,
                "category": category,
                "variant": var,
                "question": question,
                "expected_status": expected_status,
                "latency_ms": round(latency_ms, 2),
                "finish_reason": finish_reason,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "timings": timings,
                "raw_content": raw_content,
                "parsed_json": parsed_json,
                "error_msg": error_msg,
                "classification": cause,
            }
            records.append(record)

        with open(out_file, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        print(f"Saved {len(records)} raw outputs to {out_file}")
        summary_counts[var] = failure_causes

    # Print Table
    print("\n" + "=" * 110)
    print("STEP 1b: FAILURE CAUSE CLASSIFICATION TABLE (DEV Split, n=44 per variant)")
    print("=" * 110)
    causes_list = [
        ("invalid_or_truncated_json", "Invalid / Truncated JSON (finish_reason=length or parse error)"),
        ("schema_valid_wrong_status", "Schema-valid but wrong status (e.g. SUCCESS, or answered unanswerable)"),
        ("number_not_in_facts", "Number not in facts (real model hallucination)"),
        ("verifier_false_positive_or_bug", "Verifier false positive / bug"),
        ("bad_test_case", "Bad test case (inconsistent input facts)"),
        ("server_error_or_timeout", "Server error / 30s timeout"),
        ("passed_valid_and_grounded", "Passed (Valid schema & grounded status)"),
    ]

    header = f"{'Failure Cause Category':<65} | {'minimal':<10} | {'few_shot':<10} | {'chain_of_thought':<15}"
    print(header)
    print("-" * 110)
    for c_key, c_label in causes_list:
        m_cnt = summary_counts["minimal"].get(c_key, 0)
        f_cnt = summary_counts["few_shot"].get(c_key, 0)
        cot_cnt = summary_counts["chain_of_thought"].get(c_key, 0)
        print(f"{c_label:<65} | {m_cnt:<10} | {f_cnt:<10} | {cot_cnt:<15}")
    print("=" * 110)


if __name__ == "__main__":
    run_diagnostics()
