#!/usr/bin/env python3
"""scripts/seed_live_requests.py

Generates 24 live requests through RequestLifecycleManager with the new cryptographic
hashes (prompt_template_hash=dd4a4ded..., model_version=qwen2.5-3b-instruct-q4_k_m:626b4a66...)
into answer_log for tenant 'acme'.
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.orchestration.request_lifecycle import RequestLifecycleManager

QUESTIONS = [
    # Structured (12)
    "What was Aurora Retail Group's revenue in fiscal 2023 quarter 2?",
    "What was Cobalt Energy Partners's operating income in fiscal 2024 quarter 1?",
    "Report the gross margin of Helix BioSystems in fiscal 2022 quarter 4.",
    "What was Meridian Software's free cash flow in fiscal 2023 quarter 3?",
    "What was Northwind Industrial's debt to equity in fiscal 2024 quarter 3?",
    "State the current ratio of Zephyr Logistics in fiscal 2023 quarter 3.",
    "What was Aurora Retail Group's net profit margin in fiscal 2024 quarter 1?",
    "What was Cobalt Energy Partners's EBITDA in fiscal 2023 quarter 2?",
    "What was Helix BioSystems's R&D expense in fiscal 2023 quarter 1?",
    "What was Meridian Software's revenue in fiscal 2022 quarter 3?",
    "What was Northwind Industrial's as-restated net margin in fiscal 2023 quarter 3?",
    "What was Zephyr Logistics's operating margin in fiscal 2024 quarter 1?",
    # Narrative (6)
    "What risk factors regarding supply chain disruptions were disclosed by Aurora Retail Group in FY2023?",
    "What explanation did Cobalt Energy Partners provide regarding commodity price fluctuations in fiscal 2023?",
    "Summarize clinical trial and regulatory milestones disclosed by Helix BioSystems in FY2024.",
    "What software licensing and renewal trends did Meridian Software cite in fiscal 2023 MD&A?",
    "What manufacturing headwinds did Northwind Industrial disclose in fiscal 2024 quarter 1?",
    "What fuel cost and capacity constraints did Zephyr Logistics highlight in fiscal 2024 MD&A?",
    # Mixed (6)
    "What was Aurora Retail Group's revenue in fiscal 2023 quarter 3 and what factors explained that performance in MD&A?",
    "Report Cobalt Energy Partners's operating margin in fiscal 2023 quarter 4 and what drivers were cited?",
    "State Helix BioSystems's R&D intensity in fiscal 2024 quarter 2 and summarize the clinical pipeline commentary.",
    "What was Meridian Software's net income in fiscal 2023 quarter 1 and what operating drivers were highlighted?",
    "What was Northwind Industrial's gross profit in fiscal 2024 quarter 1 and what raw material factors affected margins?",
    "What was Zephyr Logistics's free cash flow in fiscal 2023 quarter 4 and how did management explain capital spending?"
]


async def main():
    mgr = RequestLifecycleManager()
    print(f"Seeding {len(QUESTIONS)} live requests with new cryptographic hashes...")
    for idx, q in enumerate(QUESTIONS, 1):
        env = await mgr.execute_request(
            question=q,
            tenant_id="acme",
            session_id=f"sess_seed_{idx:02d}",
            request_id=f"req_blackbox_{idx:02d}"
        )
        print(f"[{idx:02d}/{len(QUESTIONS)}] {env.request_id} ({env.route.value}): Status={env.status.value}")

    print("✓ Seeding complete.")


if __name__ == "__main__":
    asyncio.run(main())
