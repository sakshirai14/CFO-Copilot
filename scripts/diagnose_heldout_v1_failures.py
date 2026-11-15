#!/usr/bin/env python3
"""scripts/diagnose_heldout_v1_failures.py
Diagnose the 40 Held-Out v1 cases: classify failures, analyze unexpected refusals.
"""

import asyncio
from app.agents.root_agent import CfoCopilotRootAgent
from app.domain.agent_envelope import AnswerStatus, RouteType
from scripts.build_agent_evalset import HELD_OUT_CASES

async def main():
    root = CfoCopilotRootAgent()
    print(f"Diagnosing {len(HELD_OUT_CASES)} Held-Out v1 cases...")

    failures = []
    unexpected_refusals = []
    route_breakdown = {"STRUCTURED": {"total": 0, "correct": 0}, "LLM_PATH": {"total": 0, "correct": 0, "verified_llm": 0, "fallback_extractive": 0, "refused": 0}}

    for case in HELD_OUT_CASES:
        cid = case["id"]
        q = case["question"]
        exp_route = case.get("expected_route", "STRUCTURED")
        exp_status = case.get("expected_status", "ok")
        exp_comp = case.get("expected_company")
        exp_period = case.get("expected_period")
        exp_kpi = case.get("expected_kpi")
        is_llm = exp_route in ("UNSTRUCTURED", "MIXED")

        env = await root.answer(q, is_test=False)

        # Correctness check
        is_route_ok = (env.route.value == exp_route)
        is_stat_ok = (env.status.value == exp_status) or (exp_status == "ok" and env.status.value in ("ok", "missing_data", "missing_input"))
        is_correct = is_route_ok and is_stat_ok

        # Track route breakdown
        if not is_llm:
            route_breakdown["STRUCTURED"]["total"] += 1
            if is_correct:
                route_breakdown["STRUCTURED"]["correct"] += 1
        else:
            route_breakdown["LLM_PATH"]["total"] += 1
            if is_correct:
                route_breakdown["LLM_PATH"]["correct"] += 1
            if env.status == AnswerStatus.REFUSED:
                route_breakdown["LLM_PATH"]["refused"] += 1
            elif any("fallback" in c.lower() for c in env.caveats):
                route_breakdown["LLM_PATH"]["fallback_extractive"] += 1
            elif env.llm_calls_made > 0:
                route_breakdown["LLM_PATH"]["verified_llm"] += 1

        # Track unexpected refusal
        if exp_route != "REFUSAL" and (env.route == RouteType.REFUSAL or env.status == AnswerStatus.REFUSED):
            unexpected_refusals.append({
                "id": cid,
                "question": q,
                "expected_route": exp_route,
                "actual_route": env.route.value,
                "actual_status": env.status.value,
                "refusal_reason": env.caveats[0] if env.caveats else env.answer
            })

        # Failure cause classification
        if not is_correct:
            # Classify cause
            cause = "unknown"
            if exp_route in ("UNSTRUCTURED", "MIXED") and env.route == RouteType.REFUSAL:
                cause = "router (misclassified qualitative query as refusal or entity out of scope)"
            elif exp_route != env.route.value:
                cause = "router (route selection mismatch)"
            elif exp_status != env.status.value:
                if env.status == AnswerStatus.REFUSED:
                    cause = "resolver (false refusal trigger)"
                elif "fallback" in str(env.caveats).lower():
                    cause = "verifier (intercepted model output)"
                else:
                    cause = "template / status mismatch"
            failures.append({
                "id": cid,
                "question": q,
                "exp_route": exp_route,
                "act_route": env.route.value,
                "exp_status": exp_status,
                "act_status": env.status.value,
                "cause": cause,
                "answer": env.answer[:100]
            })

    print(f"\n--- ROUTE BREAKDOWN ---")
    print(f"Structured: {route_breakdown['STRUCTURED']}")
    print(f"LLM Path: {route_breakdown['LLM_PATH']}")

    print(f"\n--- UNEXPECTED REFUSALS ({len(unexpected_refusals)}) ---")
    for ur in unexpected_refusals:
        print(f"[{ur['id']}] Q: {ur['question']}")
        print(f"  Reason: {ur['refusal_reason']}")

    print(f"\n--- TOTAL FAILURES ({len(failures)}) ---")
    for f in failures:
        print(f"[{f['id']}] Cause: {f['cause']} | Exp: {f['exp_route']}/{f['exp_status']} | Act: {f['act_route']}/{f['act_status']}")

if __name__ == "__main__":
    asyncio.run(main())

