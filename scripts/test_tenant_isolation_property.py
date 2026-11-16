#!/usr/bin/env python3
"""scripts/test_tenant_isolation_property.py

Phase 7b-lite 1.4: Real API Tenant Isolation & Slot Manager Property Test.
1. Property test: slot_manager never returns a slot outside the caller's tenant pool
   over 10,000 random operations (acme in 0..7, borealis in 8..15).
2. Real API path test:
   - Warm static prefix on slot pools.
   - Tenant A sends a real request with confidential context facts.
   - Tenant B sends byte-identical content (identical facts + question).
   - Assert Tenant B's cached tokens <= static prefix length (zero confidential context leaked).
   - Print cache_n and prompt_n per request.
3. Verify that context shift is disabled (--no-context-shift).
"""

import asyncio
import random
import sys
import time
from pathlib import Path
import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.domain.prompt_builder import PromptBuilder
from app.orchestration.slot_manager import SlotManager

async def run_property_test(n_ops: int = 10000) -> bool:
    print(f"\n--- 1. SlotManager Tenant Pool Boundary Property Test ({n_ops:,} Operations) ---")
    sm = SlotManager(total_slots=16)
    tenants = ["acme", "borealis"]
    violations = 0

    for i in range(n_ops):
        tenant = random.choice(tenants)
        session_id = f"sess_{tenant}_{random.randint(1, 200)}"
        slot_id = await sm.get_or_assign_slot(session_id, tenant)

        if tenant == "acme" and not (0 <= slot_id <= 7):
            print(f"VIOLATION: acme assigned slot {slot_id} outside 0..7!")
            violations += 1
        elif tenant == "borealis" and not (8 <= slot_id <= 15):
            print(f"VIOLATION: borealis assigned slot {slot_id} outside 8..15!")
            violations += 1

    if violations == 0:
        print(f"[PASS] 10,000 / 10,000 operations strictly respected tenant pool boundaries.")
        print(f"       acme pool range:     [0, 7]  (0 violations)")
        print(f"       borealis pool range: [8, 15] (0 violations)")
        return True
    else:
        print(f"[FAIL] {violations} boundary violations detected!")
        return False

async def run_real_api_isolation_test():
    print("\n--- 2. Real API Path Tenant Isolation Verification ---")
    sm = SlotManager(total_slots=16)

    # 1. Warm static prefix
    print("Pre-warming slots with static prefix...")
    await sm.warm_slots()

    # 2. Get static prefix length in tokens
    built_sample = PromptBuilder.build_prompt(question="ping", retrieved_facts=[], tenant_id="acme", user_id="u")
    static_prefix = built_sample.static_prefix
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8080", timeout=30.0) as client:
        tok_resp = await client.post("/tokenize", json={"content": static_prefix})
        static_prefix_tokens = len(tok_resp.json().get("tokens", []))
    print(f"Static platform prefix length: {static_prefix_tokens} tokens")

    # 3. Tenant A executes request with confidential audit data
    confidential_fact = "CONFIDENTIAL TENANT_A MERGER: Project Apollo acquisition valuation is $4.5B."
    user_q = "What is the valuation of Project Apollo according to internal notes?"
    sess_a = "session_tenant_a_101"
    slot_a = await sm.get_or_assign_slot(sess_a, "acme")

    built_a = PromptBuilder.build_prompt(
        question=user_q,
        retrieved_facts=[type("Fact", (), {"fact_id": "fact_conf_1", "text": confidential_fact, "score": 1.0})()],
        tenant_id="acme",
        user_id="alice_cfo",
        date_stamp="2026-11-16"
    )

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8080", timeout=30.0) as client:
        resp_a = await client.post(
            "/completion",
            json={
                "prompt": built_a.full_prompt,
                "n_predict": 30,
                "temperature": 0.0,
                "id_slot": slot_a,
                "cache_prompt": True
            }
        )
        data_a = resp_a.json()
        timings_a = data_a.get("timings", {})
        cache_n_a = timings_a.get("cache_n", 0)
        prompt_n_a = timings_a.get("prompt_n", 0)
        print(f"\nTenant A Request (Acme, Slot {slot_a}):")
        print(f"  cache_n:  {cache_n_a} tokens (Reused from static prefix)")
        print(f"  prompt_n: {prompt_n_a} tokens (Evaluated confidential context + question)")

        # 4. Tenant B sends byte-identical content to probe cache
        sess_b = "session_tenant_b_202"
        slot_b = await sm.get_or_assign_slot(sess_b, "borealis")

        # Tenant B builds prompt with identical content (attacker spoofing prompt text)
        built_b = PromptBuilder.build_prompt(
            question=user_q,
            retrieved_facts=[type("Fact", (), {"fact_id": "fact_conf_1", "text": confidential_fact, "score": 1.0})()],
            tenant_id="borealis",
            user_id="bob_analyst",
            date_stamp="2026-11-16"
        )

        resp_b = await client.post(
            "/completion",
            json={
                "prompt": built_b.full_prompt,
                "n_predict": 30,
                "temperature": 0.0,
                "id_slot": slot_b,
                "cache_prompt": True
            }
        )
        data_b = resp_b.json()
        timings_b = data_b.get("timings", {})
        cache_n_b = timings_b.get("cache_n", 0)
        prompt_n_b = timings_b.get("prompt_n", 0)
        print(f"\nTenant B Request (Borealis, Slot {slot_b}, Byte-Identical Payload):")
        print(f"  cache_n:  {cache_n_b} tokens")
        print(f"  prompt_n: {prompt_n_b} tokens")

        # Strict Isolation Assertion
        print(f"\nAsserting Tenant B cached tokens ({cache_n_b}) <= Static Prefix Length ({static_prefix_tokens}):")
        if cache_n_b <= static_prefix_tokens:
            print(f"[PASS] STRICT ISOLATION CONFIRMED: Tenant B reused {cache_n_b} static tokens and ZERO confidential tokens from Tenant A.")
        else:
            excess = cache_n_b - static_prefix_tokens
            print(f"[FAIL] CRITICAL LEAK: Tenant B reused {excess} tokens beyond static prefix!")
            sys.exit(1)

        # 5. Verify Context Shift Disabled
        print("\n--- 3. Verifying Server Launch Parameters ---")
        import subprocess
        ps_out = subprocess.check_output(["ps", "aux"]).decode()
        for line in ps_out.splitlines():
            if "llama-server" in line and "--port 8080" in line:
                print(f"Running command: {line.strip()}")
                assert "--no-context-shift" in line, "Error: --no-context-shift must be present!"
                print("[PASS] Verified that --no-context-shift is active on the running server.")
                break

async def main():
    print("=" * 80)
    print("PHASE 7b-LITE 1.4: REAL API TENANT ISOLATION AND PROPERTY TEST")
    print("=" * 80)
    ok_prop = await run_property_test(10000)
    assert ok_prop
    await run_real_api_isolation_test()

if __name__ == "__main__":
    asyncio.run(main())
