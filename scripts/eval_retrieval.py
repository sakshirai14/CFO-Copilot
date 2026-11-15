#!/usr/bin/env python3
"""scripts/eval_retrieval.py

Phase 3 Step 5: Comprehensive Retrieval Evaluation Engine.
Evaluates:
- Vector-only vs FTS-only vs Hybrid
- With and without metadata filters
- Recall@1, Recall@3, Recall@5, Recall@10, and MRR
- Latency (p50, p95)
- Security: injected_chunk_rate (must be 0), tenant_leak_count (must be 0)
- Cross-split verification: Dev (<= 70%) vs Held-Out (>= 30%) with SHA-256 hash tracking

Saves results to benchmarks/results/retrieval.json.
"""

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.domain.retrieval_service import RetrievalFilter, RetrievalService

EVAL_CSV_PATH = PROJECT_ROOT / "tests" / "evals" / "retrieval_eval.csv"
RESULTS_JSON_PATH = PROJECT_ROOT / "benchmarks" / "results" / "retrieval.json"


def evaluate_configuration(
    service: RetrievalService,
    eval_df: pd.DataFrame,
    mode: str,
    use_filters: bool,
    split_filter: Optional[str] = None,
) -> Dict[str, Any]:
    df = eval_df.copy()
    if split_filter:
        df = df[df["split"] == split_filter].copy()

    # Filter answerable queries for accuracy metrics
    answerable_df = df[~df["gold_chunk_ids"].isin(["NONE", "none", ""])].copy()

    latencies = []
    recalls = {1: [], 3: [], 5: [], 10: []}
    reciprocal_ranks = []
    injected_chunk_count = 0
    total_returned_chunks = 0
    tenant_leak_count = 0

    for _, row in df.iterrows():
        q_text = row["question"]
        golds = [g.strip() for g in str(row["gold_chunk_ids"]).split(",") if g.strip()] if row["gold_chunk_ids"] not in ["NONE", "none", ""] else []

        rf = None
        if use_filters:
            comp = row["company_filter"] if pd.notna(row["company_filter"]) and str(row["company_filter"]).strip() else None
            yr = int(row["year_filter"]) if pd.notna(row["year_filter"]) and str(row["year_filter"]).strip() else None
            qtr = int(row["quarter_filter"]) if pd.notna(row["quarter_filter"]) and str(row["quarter_filter"]).strip() else None
            rf = RetrievalFilter(company_id=comp, fiscal_year=yr, fiscal_quarter=qtr)

        # Execute retrieval (caller tenant is acme)
        res = service.retrieve(
            query=q_text,
            filters=rf,
            top_k=10,
            tenant_id="acme",
            include_quarantined=False,
            mode=mode,
        )

        latencies.append(res.latency_ms)
        retrieved_ids = [c.chunk_id for c in res.chunks]
        total_returned_chunks += len(retrieved_ids)

        # Check for quarantined chunks returned under default retrieval
        for c in res.chunks:
            if c.quarantined or "quarantined" in c.trust_level:
                injected_chunk_count += 1
            if c.tenant_id is not None and c.tenant_id != "acme":
                tenant_leak_count += 1

        # Accuracy metrics for answerable queries
        if golds:
            rr = 0.0
            for rank, cid in enumerate(retrieved_ids, start=1):
                if cid in golds:
                    rr = 1.0 / rank
                    break
            reciprocal_ranks.append(rr)

            for k in [1, 3, 5, 10]:
                top_k_set = set(retrieved_ids[:k])
                hit = 1.0 if any(g in top_k_set for g in golds) else 0.0
                recalls[k].append(hit)

    r1 = float(np.mean(recalls[1])) * 100.0 if recalls[1] else 0.0
    r3 = float(np.mean(recalls[3])) * 100.0 if recalls[3] else 0.0
    r5 = float(np.mean(recalls[5])) * 100.0 if recalls[5] else 0.0
    r10 = float(np.mean(recalls[10])) * 100.0 if recalls[10] else 0.0
    mrr = float(np.mean(reciprocal_ranks)) if reciprocal_ranks else 0.0

    injected_rate = (injected_chunk_count / max(1, total_returned_chunks)) * 100.0

    return {
        "mode": mode,
        "use_filters": use_filters,
        "split": split_filter or "all",
        "total_queries": len(df),
        "answerable_queries": len(answerable_df),
        "latency_p50_ms": float(np.median(latencies)),
        "latency_p95_ms": float(np.percentile(latencies, 95)),
        "latency_mean_ms": float(np.mean(latencies)),
        "recall_at_1": round(r1, 2),
        "recall_at_3": round(r3, 2),
        "recall_at_5": round(r5, 2),
        "recall_at_10": round(r10, 2),
        "mrr": round(mrr, 4),
        "injected_chunk_count": injected_chunk_count,
        "injected_chunk_rate_pct": round(injected_rate, 4),
        "tenant_leak_count": tenant_leak_count,
    }


def run_eval():
    print("=" * 80)
    print("CFO COPILOT - PHASE 3 RETRIEVAL EVALUATION (STEP 5)")
    print("=" * 80)

    with open(EVAL_CSV_PATH, "rb") as f:
        csv_hash = hashlib.sha256(f.read()).hexdigest()

    eval_df = pd.read_csv(EVAL_CSV_PATH)
    total_q = len(eval_df)
    dev_q = len(eval_df[eval_df["split"] == "dev"])
    held_out_q = len(eval_df[eval_df["split"] == "held_out"])

    print(f"Dataset File:       {EVAL_CSV_PATH}")
    print(f"SHA-256 Hash:       {csv_hash}")
    print(f"Total Questions:    {total_q} (Dev: {dev_q} [{dev_q/total_q*100:.1f}%], Held-Out: {held_out_q} [{held_out_q/total_q*100:.1f}%])")
    print("-" * 80)

    service = RetrievalService()

    configs = [
        ("hybrid", True, "Hybrid (Vector + FTS) + Filters"),
        ("hybrid", False, "Hybrid (Vector + FTS) - No Filters"),
        ("vector_only", True, "Vector-Only + Filters"),
        ("vector_only", False, "Vector-Only - No Filters"),
        ("fts_only", True, "FTS-Only + Filters"),
        ("fts_only", False, "FTS-Only - No Filters"),
    ]

    all_results = []
    print(f"\n{'Configuration':<34} | {'Split':<8} | {'R@1 (%)':<8} | {'R@5 (%)':<8} | {'MRR':<8} | {'p50 (ms)':<9} | {'Injected':<8} | {'Leak'}")
    print("-" * 105)

    for mode, use_filt, label in configs:
        for split in ["all", "dev", "held_out"]:
            res = evaluate_configuration(
                service=service,
                eval_df=eval_df,
                mode=mode,
                use_filters=use_filt,
                split_filter=None if split == "all" else split,
            )
            res["configuration_label"] = label
            all_results.append(res)

            cfg_col = label if split == "all" else f"  └─ {split.upper()}"
            print(f"{cfg_col:<34} | {split:<8} | {res['recall_at_1']:<8.1f} | {res['recall_at_5']:<8.1f} | {res['mrr']:<8.4f} | {res['latency_p50_ms']:<9.2f} | {res['injected_chunk_count']:<8} | {res['tenant_leak_count']}")

    output_payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset_sha256": csv_hash,
        "dataset_path": str(EVAL_CSV_PATH),
        "split_summary": {
            "total": total_q,
            "dev": dev_q,
            "held_out": held_out_q,
            "dev_pct": round(dev_q / total_q * 100, 2),
            "held_out_pct": round(held_out_q / total_q * 100, 2),
        },
        "configurations_evaluated": all_results,
    }

    RESULTS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    print("-" * 105)
    print(f"[OK] Full retrieval evaluation report successfully saved to {RESULTS_JSON_PATH}")


if __name__ == "__main__":
    run_eval()
