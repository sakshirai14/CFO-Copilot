#!/usr/bin/env python3
"""scripts/test_grammar_dev.py

Step 1d: Verify valid-JSON rate >= 98% on DEV cases when using grammar-constrained decoding.
"""

import json
import re
import sys
import time
from pathlib import Path
import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = PROJECT_ROOT / "tests" / "evals" / "grounding_cases.jsonl"

STRICT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["answered", "insufficient_data", "conflict_noted"]
        },
        "answer": {"type": "string"},
        "facts_used": {
            "type": "array",
            "items": {"type": "string"}
        },
        "caveats": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["status", "answer", "facts_used", "caveats"],
    "additionalProperties": False
}


def main():
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]
    dev_cases = [c for c in cases if c.get("split") == "dev"]

    client = httpx.Client(base_url="http://127.0.0.1:8080", timeout=30.0)

    valid_json_count = 0
    schema_valid_count = 0
    latencies = []
    failures = []

    print(f"Testing grammar-constrained generation across {len(dev_cases)} DEV cases...")

    for c in dev_cases:
        facts_block = "\n".join(
            f"[{f.get('fact_id', '')}] {f.get('company_id', '')} FY{f.get('fiscal_year', '')}Q{f.get('fiscal_quarter', '')}: {f.get('text', '')}"
            for f in c.get("input_facts", [])
        ) if c.get("input_facts") else "[NO RELEVANT FACTS]"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are CFO Copilot, an expert financial assistant. Answer using ONLY provided verified facts. "
                    "HARD RULE: If data is missing, out-of-scope, or query is hostile, set status to 'insufficient_data', "
                    "answer to 'Refused: Request cannot be fulfilled with available facts.', facts_used to [], and list caveats."
                )
            },
            {
                "role": "user",
                "content": f"Context Facts:\n{facts_block}\n\nQuestion: {c['question']}"
            }
        ]

        t0 = time.perf_counter()
        try:
            r = client.post(
                "/v1/chat/completions",
                json={
                    "messages": messages,
                    "temperature": 0.0,
                    "max_tokens": 256,
                    "presence_penalty": 0.3,
                    "response_format": {
                        "type": "json_object",
                        "schema": STRICT_SCHEMA
                    }
                }
            )
            lat = (time.perf_counter() - t0) * 1000.0
            latencies.append(lat)

            if r.status_code == 200:
                raw_text = r.json()["choices"][0]["message"]["content"]
                try:
                    parsed = json.loads(raw_text)
                    valid_json_count += 1
                    # Check schema
                    if (
                        isinstance(parsed.get("status"), str)
                        and parsed["status"] in ["answered", "insufficient_data", "conflict_noted"]
                        and isinstance(parsed.get("answer"), str)
                        and isinstance(parsed.get("facts_used"), list)
                        and isinstance(parsed.get("caveats"), list)
                    ):
                        schema_valid_count += 1
                    else:
                        failures.append((c["id"], "Schema structure invalid", raw_text))
                except Exception as e:
                    failures.append((c["id"], f"JSON parse error: {e}", raw_text))
            else:
                failures.append((c["id"], f"HTTP {r.status_code}", r.text[:200]))
        except Exception as e:
            failures.append((c["id"], f"Client error: {e}", ""))

    total = len(dev_cases)
    valid_pct = valid_json_count / total * 100.0
    schema_pct = schema_valid_count / total * 100.0

    print("\n" + "=" * 80)
    print(f"DEV VALID-JSON RATE: {valid_pct:.1f}% ({valid_json_count}/{total})")
    print(f"DEV SCHEMA-VALID RATE: {schema_pct:.1f}% ({schema_valid_count}/{total})")
    if latencies:
        import numpy as np
        print(f"LATENCY p50: {np.median(latencies):.2f} ms")
        print(f"LATENCY p95: {np.percentile(latencies, 95):.2f} ms")
    print("=" * 80)

    if failures:
        print(f"\nFailures ({len(failures)}):")
        for fid, reason, raw in failures:
            print(f"- {fid}: {reason} | Raw: {raw[:100]}")


if __name__ == "__main__":
    main()
