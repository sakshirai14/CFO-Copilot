#!/usr/bin/env python3
"""scripts/selfcheck.py

Unified One-Command End-to-End Self-Check Suite.
Runs:
1. Unit Tests (including AST boundary tests)
2. Integration Tests (API, RLS, conflict policy, fault injection)
3. Smoke Queries (Structured, Narrative, Refusal)
4. Replay Determinism Verification (scripts/replay.py)
5. Adversarial Security Attack Suite (scripts/run_attacks.py)
6. Live Prefix KV Cache Hit Verification
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agents.root_agent import CfoCopilotRootAgent
from app.domain.agent_envelope import AnswerStatus, RouteType, FactItem
from app.domain.prompt_builder import PromptBuilder
import httpx


def run_cmd(cmd: list[str], desc: str) -> None:
    print(f"\n========================================================")
    print(f"[selfcheck] STEP: {desc}")
    print(f"Command: {' '.join(cmd)}")
    print(f"========================================================")
    t0 = time.perf_counter()
    res = subprocess.run(cmd, cwd=PROJECT_ROOT)
    elapsed = time.perf_counter() - t0
    if res.returncode != 0:
        print(f"[selfcheck] FAILED: {desc} (exit code: {res.returncode}, elapsed: {elapsed:.2f}s)", file=sys.stderr)
        sys.exit(res.returncode)
    print(f"[selfcheck] PASSED: {desc} ({elapsed:.2f}s)")


async def run_smoke_queries():
    print(f"\n========================================================")
    print(f"[selfcheck] STEP: Live Smoke Queries (Structured, Narrative, Refusal)")
    print(f"========================================================")
    root = CfoCopilotRootAgent()

    # 1. Structured query
    q1 = "What was Aurora Retail Group's revenue in fiscal 2023 quarter 2?"
    t0 = time.perf_counter()
    env1 = await root.answer(q1, tenant="acme", request_id="selfcheck_smoke_struct", is_test=False)
    e1 = time.perf_counter() - t0
    print(f"  [1/3] Structured: '{q1}'")
    print(f"        Status: {env1.status.value} | Route: {env1.route.value} | LLM calls: {env1.llm_calls_made} | Time: {e1*1000:.1f}ms")
    assert env1.status == AnswerStatus.OK, f"Expected OK, got {env1.status}"
    assert env1.route == RouteType.STRUCTURED, f"Expected STRUCTURED route, got {env1.route}"
    assert env1.llm_calls_made == 0, f"Structured query must make 0 LLM calls, got {env1.llm_calls_made}"
    assert "$774,400,000" in env1.answer or "774,400,000" in env1.answer, f"Answer missing revenue fact: {env1.answer}"
    print(f"        Answer excerpt: {env1.answer[:80]}...")

    # 2. Narrative query
    q2 = "What risk factors regarding supply chain disruptions were disclosed by Aurora Retail Group in FY2023?"
    t0 = time.perf_counter()
    env2 = await root.answer(q2, tenant="acme", request_id="selfcheck_smoke_narrative", is_test=False)
    e2 = time.perf_counter() - t0
    print(f"  [2/3] Narrative: '{q2}'")
    print(f"        Status: {env2.status.value} | Route: {env2.route.value} | LLM calls: {env2.llm_calls_made} | Time: {e2*1000:.1f}ms")
    assert env2.status in (AnswerStatus.OK, AnswerStatus.OK_EXTRACTIVE), f"Expected OK/OK_EXTRACTIVE, got {env2.status}"
    assert len(env2.provenance_traces) > 0 or len(env2.facts_used) > 0, "Narrative answer must have provenance/facts"
    print(f"        Provenance records: {len(env2.provenance_traces)} | Answer excerpt: {env2.answer[:80]}...")

    # 3. Refusal query
    q3 = "What was Apple's iPhone revenue in fiscal 2023?"
    t0 = time.perf_counter()
    env3 = await root.answer(q3, tenant="acme", request_id="selfcheck_smoke_refusal", is_test=False)
    e3 = time.perf_counter() - t0
    print(f"  [3/3] Refusal: '{q3}'")
    print(f"        Status: {env3.status.value} | Route: {env3.route.value} | LLM calls: {env3.llm_calls_made} | Time: {e3*1000:.1f}ms")
    assert env3.status in (AnswerStatus.REFUSED, AnswerStatus.MISSING_DATA), f"Expected REFUSED/MISSING_DATA, got {env3.status}"
    assert "refused" in env3.answer.lower() or "not available" in env3.answer.lower() or "not covered" in env3.answer.lower(), f"Unexpected refusal text: {env3.answer}"
    print(f"        Refusal excerpt: {env3.answer[:80]}...")

    print(f"[selfcheck] PASSED: All 3 Smoke Queries Verified")


def run_cache_hit_check():
    print(f"\n========================================================")
    print(f"[selfcheck] STEP: Live KV Cache Prefix Hit Verification")
    print(f"========================================================")
    fact1 = FactItem(
        fact_id="f_selfcheck_01",
        text="ARG FY2023 Q2 revenue was $774,400,000.",
        status="ok"
    )
    prompt_obj = PromptBuilder.build_prompt(
        question="What was ARG's revenue in Q2 2023?",
        retrieved_facts=[fact1],
        tenant_id="acme"
    )

    url = "http://127.0.0.1:8080/completion"
    payload1 = {
        "prompt": prompt_obj.full_prompt,
        "n_predict": 1,
        "temperature": 0.0,
        "slot_id": 0,
        "cache_prompt": True
    }
    
    with httpx.Client(timeout=30.0) as client:
        # Request 1 (Warming turn)
        t0 = time.perf_counter()
        resp1 = client.post(url, json=payload1)
        lat1 = (time.perf_counter() - t0) * 1000.0
        assert resp1.status_code == 200, f"Server error: {resp1.status_code} {resp1.text}"
        data1 = resp1.json()
        timings1 = data1.get("timings", {})
        prompt_n1 = timings1.get("prompt_n", 0)
        cache_n1 = timings1.get("cache_n", 0)
        print(f"  [Turn 1] Prefill: {prompt_n1} tok | Cached: {cache_n1} tok | Latency: {lat1:.1f}ms")

        # Request 2 (Identical prefix, unique tail)
        fact2 = FactItem(
            fact_id="f_selfcheck_02",
            text="ARG FY2023 Q2 operating income was $85,000,000.",
            status="ok"
        )
        prompt_obj2 = PromptBuilder.build_prompt(
            question="What was ARG's operating income in Q2 2023?",
            retrieved_facts=[fact2],
            tenant_id="acme"
        )
        payload2 = {
            "prompt": prompt_obj2.full_prompt,
            "n_predict": 1,
            "temperature": 0.0,
            "slot_id": 0,
            "cache_prompt": True
        }
        t0 = time.perf_counter()
        resp2 = client.post(url, json=payload2)
        lat2 = (time.perf_counter() - t0) * 1000.0
        assert resp2.status_code == 200, f"Server error: {resp2.status_code} {resp2.text}"
        data2 = resp2.json()
        timings2 = data2.get("timings", {})
        prompt_n2 = timings2.get("prompt_n", 0)
        cache_n2 = timings2.get("cache_n", 0)
        hit_rate = (cache_n2 / (prompt_n2 + cache_n2)) * 100.0 if (prompt_n2 + cache_n2) > 0 else 0.0
        print(f"  [Turn 2] Prefill: {prompt_n2} tok | Cached: {cache_n2} tok | Hit Rate: {hit_rate:.1f}% | Latency: {lat2:.1f}ms")
        assert cache_n2 >= 650, f"Expected at least 650 cached tokens from static prefix, got {cache_n2}"
        assert hit_rate >= 80.0, f"Expected cache hit rate >= 80%, got {hit_rate:.1f}%"
        print(f"[selfcheck] PASSED: Prefix KV Cache Hit Verified ({cache_n2} tokens reused, {hit_rate:.1f}% hit rate)")


def ensure_database_ready():
    print(f"\n========================================================")
    print(f"[selfcheck] STEP: Database Readiness & Ingestion Check")
    print(f"========================================================")
    import psycopg2
    from app.core.config import get_settings
    settings = get_settings()
    try:
        conn = psycopg2.connect(**settings.get_connection_params(role="ro"))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM kpi_values;")
        count = cur.fetchone()[0]
        conn.close()
        if count == 0:
            print("[selfcheck] Database not populated. Running ingestion and KPI computation...")
            py = sys.executable
            run_cmd([py, "scripts/ingest.py"], "Ingest Filings")
            run_cmd([py, "scripts/index_chunks.py"], "Index Chunks")
            run_cmd([py, "scripts/compute_kpis.py"], "Compute 16 KPIs")
        else:
            print(f"[selfcheck] Database ready ({count} computed KPI rows found).")
    except Exception as e:
        print(f"[selfcheck] Database readiness notice: {e}")


def main():
    print("================================================================================")
    print("CFO COPILOT: AUTHORITATIVE END-TO-END SYSTEM SELF-CHECK (make selfcheck)")
    print("================================================================================")
    py = sys.executable

    # 0. Ensure Database Populated
    ensure_database_ready()

    # 1. Unit Tests
    run_cmd([py, "-m", "pytest", "tests/unit/", "-q"], "Unit & AST Architecture Tests")

    # 2. Integration Tests
    run_cmd([py, "-m", "pytest", "tests/integration/", "-q"], "Integration Tests (API, RLS, Faults)")

    # 3. Live Smoke Queries
    asyncio.run(run_smoke_queries())

    # 4. Replay Test
    run_cmd([py, "scripts/replay.py", "--batch", "20"], "Replay Determinism Audit")

    # 5. Adversarial Security Attack Suite
    run_cmd([py, "scripts/run_attacks.py"], "Adversarial Security Attack Suite (21 attacks)")

    # 6. Prefix KV Cache Hit Verification
    run_cache_hit_check()

    print("\n================================================================================")
    print("✓ ALL SELF-CHECK GATES PASSED CLEANLY (Unit, Integration, Smoke, Replay, Attacks, Cache)")
    print("================================================================================\n")


if __name__ == "__main__":
    main()
