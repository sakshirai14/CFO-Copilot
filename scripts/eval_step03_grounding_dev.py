#!/usr/bin/env python3
"""scripts/eval_step03_grounding_dev.py

Step 0.3 verification:
Reruns the 65 grounding DEV cases against the live Qwen2.5-3B-Instruct model
with the updated AnswerVerifier (exact accession masking + financial token extraction).
Reports:
- Shipped wrong numbers
- Hostile injection compliance
- Valid JSON rate
"""

import json
import sys
from pathlib import Path
import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.eval_models import (
    CASES_PATH,
    evaluate_model_on_cases,
    print_metrics_table,
    check_hard_gates,
    ci_str
)

def main():
    print("=" * 90)
    print("STEP 0.3 VERIFIER CHECK: RERUNNING 65 GROUNDING DEV CASES (Qwen2.5-3B-Instruct)")
    print("=" * 90)

    with open(CASES_PATH, "r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    dev_cases = [c for c in cases if c["split"] == "dev"]
    print(f"Loaded {len(dev_cases)} DEV cases (from {CASES_PATH})")

    client = httpx.Client(base_url="http://127.0.0.1:8080", timeout=45.0)

    res = evaluate_model_on_cases(
        client=client,
        cases=dev_cases,
        variant="explicit_rules",
        model_label="Qwen2.5-3B-Instruct (Q4_K_M)"
    )

    print("\n" + "=" * 90)
    print("EVALUATION METRICS SUMMARY (DEV n=65):")
    print("=" * 90)
    print(f"Valid JSON:            {ci_str(res['valid_json_k'], res['valid_json_n'])} ({res['valid_json_k']}/{res['valid_json_n']})")
    print(f"Schema-Valid:          {ci_str(res['schema_valid_k'], res['schema_valid_n'])} ({res['schema_valid_k']}/{res['schema_valid_n']})")
    print(f"Shipped Wrong Numbers: {ci_str(res['shipped_wrong_number_k'], res['shipped_wrong_number_n'])} ({res['shipped_wrong_number_k']}/{res['shipped_wrong_number_n']})")
    print(f"Hostile Compliance:    {ci_str(res['hostile_compliance_k'], res['hostile_compliance_n'])} ({res['hostile_compliance_k']}/{res['hostile_compliance_n']})")
    print(f"Status Accuracy:       {ci_str(res['status_accuracy_k'], res['status_accuracy_n'])} ({res['status_accuracy_k']}/{res['status_accuracy_n']})")
    print(f"Refusal Precision:     {ci_str(res['refusal_precision_k'], res['refusal_precision_n'])}")
    print(f"Refusal Recall:        {ci_str(res['refusal_recall_k'], res['refusal_recall_n'])}")
    print(f"Verifier Rejections:   {res['verifier_rejection_k']}/{res['verifier_rejection_n']}")
    print(f"P50 Latency:           {res['latency_p50_ms']} ms")
    print(f"P95 Latency:           {res['latency_p95_ms']} ms")

    passed, failures = check_hard_gates(res)
    print("\nHARD GATES VERDICT:")
    if passed:
        print("  -> PASSED ALL HARD GATES!")
    else:
        print(f"  -> GATES FAILED: {failures}")

    # Save output to docs/evidence/step03_grounding_dev.json
    out_path = PROJECT_ROOT / "docs" / "evidence" / "step03_grounding_dev.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"\n[OK] Results saved to {out_path}")

if __name__ == "__main__":
    main()

