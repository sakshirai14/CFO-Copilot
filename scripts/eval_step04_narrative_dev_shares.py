#!/usr/bin/env python3
"""scripts/eval_step04_narrative_dev_shares.py

Computes exact breakdown for the 15+65 dev cases:
- 15 Narrative Dev Cases (evaluated via live CfoCopilotRootAgent)
- 65 Grounding Dev Cases (evaluated via Grounding Evaluator / live model)
Reports:
- Share LLM-verified
- Share extractive (excerpts-only / fallback)
- Share refused
- Exact 95% Wilson intervals for each
"""

import asyncio
import json
import math
import sys
from pathlib import Path
from typing import Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.root_agent import CfoCopilotRootAgent
from app.domain.agent_envelope import AnswerStatus

NARRATIVE_PATH = PROJECT_ROOT / "tests" / "evals" / "narrative_dev_cases.json"
GROUNDING_STEP03_PATH = PROJECT_ROOT / "docs" / "evidence" / "step03_grounding_dev.json"

def wilson_interval(successes: int, total: int, conf: float = 0.95) -> Tuple[float, float, float]:
    if total == 0:
        return 0.0, 0.0, 0.0
    p = successes / total
    z = 1.95996
    denom = 1.0 + (z**2) / total
    c = p + (z**2) / (2.0 * total)
    s = math.sqrt((p * (1.0 - p) + (z**2) / (4.0 * total)) / total)
    low = max(0.0, (c - z * s) / denom)
    high = min(1.0, (c + z * s) / denom)
    return p, low, high

def ci_str(k: int, n: int) -> str:
    p, l, h = wilson_interval(k, n)
    return f"{p*100:.1f}% [{l*100:.1f}%, {h*100:.1f}%] (n={n})"

async def main():
    print("=" * 90)
    print("STEP 0.4: EVALUATING 15 NARRATIVE DEV + 65 GROUNDING DEV CASES (n=80)")
    print("=" * 90)

    # 1. Evaluate 15 Narrative Dev Cases
    with open(NARRATIVE_PATH, "r", encoding="utf-8") as f:
        narrative_cases = json.load(f)

    agent = CfoCopilotRootAgent()
    narr_llm_verified = 0
    narr_extractive = 0
    narr_refused = 0

    print(f"\nRunning 15 Narrative Dev Cases...")
    for idx, c in enumerate(narrative_cases, 1):
        q = c["question"]
        env = await agent.answer(q, tenant="acme")

        # Determine status classification
        if env.status == AnswerStatus.REFUSED or env.status.value in ("refused", "insufficient_data"):
            narr_refused += 1
            mode = "REFUSED"
        elif env.status == AnswerStatus.OK_EXTRACTIVE or any("insufficient data" in cv or "fallback" in cv.lower() for cv in env.caveats) or "Relevant Filing Excerpts:" in env.answer:
            narr_extractive += 1
            mode = "EXTRACTIVE"
        else:
            narr_llm_verified += 1
            mode = "LLM_VERIFIED"

        print(f"  [{idx:02d}/15] {c['id']}: {mode} (status={env.status.value})")

    # 2. Load 65 Grounding Dev Results
    with open(GROUNDING_STEP03_PATH, "r", encoding="utf-8") as f:
        grounding_res = json.load(f)

    # In grounding dev (n=65):
    # - Refused: status == insufficient_data (predicted_refusals = 31, refusal_recall_n = 24)
    # - In grounding test harness:
    #   When verifier rejected (3 rejections), deterministic template fallback was triggered.
    #   Total verified LLM answered: total_cases - predicted_refusals - verifier_rejections = 65 - 31 = 34 - 3 = 31
    #   Wait, let's verify exact counts from step03_grounding_dev.json
    gr_total = grounding_res["total_cases"] # 65
    gr_refused = grounding_res["refusal_precision_n"] # 31
    gr_rejected = grounding_res["verifier_rejection_k"] # 3
    gr_llm_verified = gr_total - gr_refused - gr_rejected # 31
    gr_extractive = gr_rejected # 3 (routed to fallback / template)

    # 3. Aggregate 15 + 65 = 80 Dev Cases
    tot_cases = len(narrative_cases) + gr_total
    tot_llm_verified = narr_llm_verified + gr_llm_verified
    tot_extractive = narr_extractive + gr_extractive
    tot_refused = narr_refused + gr_refused

    print("\n" + "=" * 90)
    print("DETAILED BREAKDOWN BY BENCHMARK:")
    print("=" * 90)
    print(f"Narrative Dev (n={len(narrative_cases)}):")
    print(f"  - LLM-Verified: {narr_llm_verified}/{len(narrative_cases)} ({narr_llm_verified/len(narrative_cases)*100:.1f}%)")
    print(f"  - Extractive:   {narr_extractive}/{len(narrative_cases)} ({narr_extractive/len(narrative_cases)*100:.1f}%)")
    print(f"  - Refused:      {narr_refused}/{len(narrative_cases)} ({narr_refused/len(narrative_cases)*100:.1f}%)")

    print(f"\nGrounding Dev (n={gr_total}):")
    print(f"  - LLM-Verified: {gr_llm_verified}/{gr_total} ({gr_llm_verified/gr_total*100:.1f}%)")
    print(f"  - Extractive:   {gr_extractive}/{gr_total} ({gr_extractive/gr_total*100:.1f}%)")
    print(f"  - Refused:      {gr_refused}/{gr_total} ({gr_refused/gr_total*100:.1f}%)")

    print(f"\nCombined Dev Pool (n={tot_cases}):")
    print(f"  - LLM-Verified Share: {ci_str(tot_llm_verified, tot_cases)} ({tot_llm_verified}/{tot_cases})")
    print(f"  - Extractive Share:   {ci_str(tot_extractive, tot_cases)} ({tot_extractive}/{tot_cases})")
    print(f"  - Refused Share:      {ci_str(tot_refused, tot_cases)} ({tot_refused}/{tot_cases})")

    # Save to json
    report = {
        "narrative_dev": {
            "n": len(narrative_cases),
            "llm_verified": narr_llm_verified,
            "extractive": narr_extractive,
            "refused": narr_refused
        },
        "grounding_dev": {
            "n": gr_total,
            "llm_verified": gr_llm_verified,
            "extractive": gr_extractive,
            "refused": gr_refused
        },
        "combined": {
            "n": tot_cases,
            "llm_verified": tot_llm_verified,
            "llm_verified_pct": round(tot_llm_verified / tot_cases * 100, 2),
            "extractive": tot_extractive,
            "extractive_pct": round(tot_extractive / tot_cases * 100, 2),
            "refused": tot_refused,
            "refused_pct": round(tot_refused / tot_cases * 100, 2),
        }
    }

    out_file = PROJECT_ROOT / "docs" / "evidence" / "step04_dev_shares.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n[OK] Summary saved to {out_file}")

if __name__ == "__main__":
    asyncio.run(main())

