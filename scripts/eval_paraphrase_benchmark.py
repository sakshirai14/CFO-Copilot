#!/usr/bin/env python3
"""scripts/eval_paraphrase_benchmark.py

Fast deterministic evaluation of QuestionResolver across Paraphrase Benchmark:
- Dev Families (2,400 cases)
- Held-Out Families (960 cases)
Reports per-slot and all-slots-correct accuracy with 95% Wilson intervals.
Saves report to docs/evidence/paraphrase_benchmark_report.md.
"""

import json
import math
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.domain.question_resolver import QuestionResolver

DEV_PATH = PROJECT_ROOT / "tests" / "evals" / "paraphrase_dev_families.json"
HELDOUT_PATH = PROJECT_ROOT / "tests" / "evals" / "paraphrase_heldout_families.json"
REPORT_PATH = PROJECT_ROOT / "docs" / "evidence" / "paraphrase_benchmark_report.md"


def wilson_score_interval(successes: int, total: int, confidence: float = 0.95) -> Tuple[float, float, float]:
    if total == 0:
        return 0.0, 0.0, 0.0
    p = successes / total
    z = 1.95996
    denominator = 1.0 + (z**2) / total
    centre_adj = p + (z**2) / (2.0 * total)
    adj_std = math.sqrt((p * (1.0 - p) + (z**2) / (4.0 * total)) / total)
    lower = max(0.0, (centre_adj - z * adj_std) / denominator)
    upper = min(1.0, (centre_adj + z * adj_std) / denominator)
    return p, lower, upper


def evaluate_split(split_name: str, file_path: Path) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    n_total = len(cases)
    comp_ok = 0
    period_ok = 0
    kpi_ok = 0
    basis_ok = 0
    all_ok = 0

    t0 = time.perf_counter()
    for c in cases:
        q = c["question"]
        res = QuestionResolver.resolve(q)

        # Company check
        exp_comp = c["expected_company"]
        c_pass = (exp_comp in res.company_ids)

        # Period check
        exp_fy = c["expected_year"]
        exp_fq = c["expected_quarter"]
        p_pass = (res.fiscal_year == exp_fy and res.fiscal_quarter == exp_fq)

        # KPI check
        exp_kpi = c["expected_kpi"]
        k_pass = (res.kpi_id == exp_kpi)

        # Basis check
        exp_basis = c["expected_basis"]
        b_pass = (res.basis == exp_basis)

        joint_pass = (c_pass and p_pass and k_pass and b_pass)

        if c_pass:
            comp_ok += 1
        if p_pass:
            period_ok += 1
        if k_pass:
            kpi_ok += 1
        if b_pass:
            basis_ok += 1
        if joint_pass:
            all_ok += 1

    dur_sec = time.perf_counter() - t0
    qps = n_total / dur_sec if dur_sec > 0 else 0.0

    return {
        "split": split_name,
        "n": n_total,
        "duration_sec": dur_sec,
        "qps": qps,
        "company": wilson_score_interval(comp_ok, n_total),
        "period": wilson_score_interval(period_ok, n_total),
        "kpi": wilson_score_interval(kpi_ok, n_total),
        "basis": wilson_score_interval(basis_ok, n_total),
        "all_slots": wilson_score_interval(all_ok, n_total),
        "counts": {
            "company": comp_ok,
            "period": period_ok,
            "kpi": kpi_ok,
            "basis": basis_ok,
            "all_slots": all_ok
        }
    }


def main():
    print("========================================================================")
    print(" EVALUATING DETERMINISTIC QUESTION RESOLVER PARAPHRASE BENCHMARK")
    print("========================================================================\n")

    dev_res = evaluate_split("Dev Families (20 template families)", DEV_PATH)
    ho_res = evaluate_split("Held-Out Families (8 template families)", HELDOUT_PATH)

    lines = [
        "# Deterministic Paraphrase Benchmark Evaluation Report",
        "",
        "> **Benchmark**: 28 Template Families across 6 Companies, 10 Canonical KPIs, and Historical Periods  ",
        f"> **Evaluated Date**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  ",
        f"> **Throughput**: ~{dev_res['qps']:.0f} queries/sec (pure regex/grammar, zero LLM calls)  ",
        "",
        "---",
        "",
        "## 1. Split-by-Split Accuracy Comparison (with 95% Wilson Confidence Intervals)",
        "",
        "| Evaluation Slot Field | Dev Families ($n = 2,400$) | 95% Wilson CI (Dev) | Held-Out Families ($n = 960$) | 95% Wilson CI (Held-Out) | Generalization Gap |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
        f"| **Company Resolution** | **{dev_res['company'][0]*100:.1f}%** ({dev_res['counts']['company']}/{dev_res['n']}) | [{dev_res['company'][1]*100:.1f}%, {dev_res['company'][2]*100:.1f}%] | **{ho_res['company'][0]*100:.1f}%** ({ho_res['counts']['company']}/{ho_res['n']}) | [{ho_res['company'][1]*100:.1f}%, {ho_res['company'][2]*100:.1f}%] | {abs(dev_res['company'][0] - ho_res['company'][0])*100:.1f}% |",
        f"| **Period Resolution (FY & FQ)** | **{dev_res['period'][0]*100:.1f}%** ({dev_res['counts']['period']}/{dev_res['n']}) | [{dev_res['period'][1]*100:.1f}%, {dev_res['period'][2]*100:.1f}%] | **{ho_res['period'][0]*100:.1f}%** ({ho_res['counts']['period']}/{ho_res['n']}) | [{ho_res['period'][1]*100:.1f}%, {ho_res['period'][2]*100:.1f}%] | {abs(dev_res['period'][0] - ho_res['period'][0])*100:.1f}% |",
        f"| **KPI Metric Resolution** | **{dev_res['kpi'][0]*100:.1f}%** ({dev_res['counts']['kpi']}/{dev_res['n']}) | [{dev_res['kpi'][1]*100:.1f}%, {dev_res['kpi'][2]*100:.1f}%] | **{ho_res['kpi'][0]*100:.1f}%** ({ho_res['counts']['kpi']}/{ho_res['n']}) | [{ho_res['kpi'][1]*100:.1f}%, {ho_res['kpi'][2]*100:.1f}%] | {abs(dev_res['kpi'][0] - ho_res['kpi'][0])*100:.1f}% |",
        f"| **Basis Resolution** | **{dev_res['basis'][0]*100:.1f}%** ({dev_res['counts']['basis']}/{dev_res['n']}) | [{dev_res['basis'][1]*100:.1f}%, {dev_res['basis'][2]*100:.1f}%] | **{ho_res['basis'][0]*100:.1f}%** ({ho_res['counts']['basis']}/{ho_res['n']}) | [{ho_res['basis'][1]*100:.1f}%, {ho_res['basis'][2]*100:.1f}%] | {abs(dev_res['basis'][0] - ho_res['basis'][0])*100:.1f}% |",
        f"| **All Slots Jointly Correct** | **{dev_res['all_slots'][0]*100:.1f}%** ({dev_res['counts']['all_slots']}/{dev_res['n']}) | [{dev_res['all_slots'][1]*100:.1f}%, {dev_res['all_slots'][2]*100:.1f}%] | **{ho_res['all_slots'][0]*100:.1f}%** ({ho_res['counts']['all_slots']}/{ho_res['n']}) | [{ho_res['all_slots'][1]*100:.1f}%, {ho_res['all_slots'][2]*100:.1f}%] | **{abs(dev_res['all_slots'][0] - ho_res['all_slots'][0])*100:.1f}%** |",
        "",
        "---",
        "",
        "## 2. Analysis of Generalization Gap",
        "",
        "The gap between Dev Families and Held-Out Families measures true semantic generalization to unseen phrasing structures.",
        "Zero LLM inference was used during slot resolution, achieving high throughput with deterministic execution."
    ]

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n✓ Report written to: {REPORT_PATH}")
    print(f">> Dev Families All-Slots: {dev_res['all_slots'][0]*100:.1f}% | Held-Out All-Slots: {ho_res['all_slots'][0]*100:.1f}% (Gap: {abs(dev_res['all_slots'][0] - ho_res['all_slots'][0])*100:.1f}%)")


if __name__ == "__main__":
    main()
