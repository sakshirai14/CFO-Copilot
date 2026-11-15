#!/usr/bin/env python3
"""scripts/build_adk_native_evalset.py

Phase 5b Item D: Formats representative test cases in native Google ADK EvalSet JSON format.
- Output: tests/adk_evals/cfo_copilot.evalset.json
- Formats 30 representative test cases:
  - single lookup (6)
  - period compare (4)
  - cross company (4)
  - narrative (6)
  - refusal / out-of-scope (5)
  - hostile adversarial (5)
- Uses google.adk.evaluation.eval_set.EvalSet, EvalCase, Invocation, and types.Content.
"""

import json
from pathlib import Path
from google.adk.evaluation.eval_set import EvalSet
from google.adk.evaluation.eval_case import EvalCase, Invocation
from google.genai import types

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_PATH = PROJECT_ROOT / "tests" / "evals" / "agent_questions.jsonl"
OUTPUT_EVALSET_PATH = PROJECT_ROOT / "tests" / "adk_evals" / "cfo_copilot.evalset.json"


def main():
    print("=== Building Native Google ADK EvalSet (>= 30 cases) ===")
    
    # 1. Load cases from agent_questions.jsonl
    cases = []
    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))

    # 2. Select 30 representative cases across categories
    categories_target = {
        "single_lookup": 6,
        "period_compare": 4,
        "cross_company": 4,
        "narrative": 6,
        "mixed": 4,
        "out_of_scope": 5,
        "hostile": 5,
    }

    selected = []
    category_counts = {k: 0 for k in categories_target}

    for c in cases:
        cat = c.get("category")
        if cat in category_counts and category_counts[cat] < categories_target[cat]:
            selected.append(c)
            category_counts[cat] += 1

    print(f"[OK] Selected {len(selected)} cases across categories: {category_counts}")

    # 3. Build native Google ADK EvalCase and EvalSet objects
    eval_cases = []
    for idx, c in enumerate(selected):
        cid = c["case_id"]
        q_text = c["question"]
        exp_route = c["expected_route"]
        exp_status = c["expected_status"]

        # Expected model response description or canonical string
        exp_response_str = f"Route: {exp_route}, Status: {exp_status}"
        if c.get("expected_company") and c.get("expected_kpi"):
            exp_response_str += f" | Entity: {c['expected_company']} {c.get('expected_period')} {c['expected_kpi']}"

        inv = Invocation(
            invocation_id=f"inv_{idx:03d}",
            user_content=types.Content(
                role="user",
                parts=[types.Part(text=q_text)]
            ),
            final_response=types.Content(
                role="model",
                parts=[types.Part(text=exp_response_str)]
            )
        )

        ec = EvalCase(
            eval_id=f"adk_eval_{cid}",
            conversation=[inv]
        )
        eval_cases.append(ec)

    adk_eval_set = EvalSet(
        eval_set_id="cfo_copilot_evalset_v1",
        name="CFO Copilot SEC Filing Intelligence Benchmark",
        description="30 representative financial inquiries evaluated offline using Google ADK data contracts.",
        eval_cases=eval_cases
    )

    # 4. Serialize to disk
    OUTPUT_EVALSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_EVALSET_PATH, "w", encoding="utf-8") as f:
        f.write(adk_eval_set.model_dump_json(indent=2))

    print(f"[SUCCESS] Native Google ADK EvalSet written to {OUTPUT_EVALSET_PATH} ({len(eval_cases)} cases)")


if __name__ == "__main__":
    main()
