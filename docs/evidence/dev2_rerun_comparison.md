# Dev2 Benchmark Rerun Comparison Report

> **Timestamp**: 2026-11-16T13:33:10Z  
> **Cases**: 44 (Structured: 24, LLM-Path: 20)  
> **Evaluation Status**: Development-Seen (Dev2). Paraphrase held-out families were visible in baseline report; v3 remains the only clean frozen held-out test.  

## 1. Before vs After Comparison Table

| Evaluation Metric | Baseline (Phase 5b) | Rerun (Step 0.6) | 95% Wilson Interval (Rerun) | Change |
| :--- | :---: | :---: | :---: | :---: |
| **Overall End-to-End Correctness** | 20 / 44 (45.5%) | **29 / 44 (65.9%)** | 65.9% [51.1%, 78.1%] (n=44) | +9 cases |
| └─ Structured Route E2E | 12 / 20 (60.0%) | **13 / 24 (54.2%)** | 54.2% [35.1%, 72.1%] (n=24) | +1 cases |
| └─ LLM / Narrative Route E2E | 8 / 24 (33.3%) | **16 / 20 (80.0%)** | 80.0% [58.4%, 91.9%] (n=20) | +8 cases |
| **Company Resolution** | 41 / 44 (93.2%) | **39 / 44 (88.6%)** | 88.6% [76.0%, 95.0%] (n=44) | -2 cases |
| **Period Resolution** | 40 / 44 (90.9%) | **41 / 44 (93.2%)** | 93.2% [81.8%, 97.7%] (n=44) | +1 cases |
| **KPI Resolution** | 33 / 44 (75.0%) | **34 / 44 (77.3%)** | 77.3% [63.0%, 87.2%] (n=44) | +1 cases |
| **Basis Resolution** | 25 / 44 (56.8%) | **25 / 44 (56.8%)** | 56.8% [42.2%, 70.3%] (n=44) | +0 cases |
| **All Slots Jointly Correct** | 14 / 44 (31.8%) | **16 / 44 (36.4%)** | 36.4% [23.8%, 51.1%] (n=44) | +2 cases |

## 2. Root Cause Analysis: Basis Resolution Failures

**Finding**: 19 out of 44 cases fail `basis_correct` because:
- In `tests/evals/agent_heldout_v2.json`, non-financial cases (Narrative `ho2-nr-01` through `ho2-nr-12`, Hostile `ho2-ad-02` through `ho2-ad-04`, and Out-of-Scope `ho2-rf-01` through `ho2-rf-04`) have `expected_basis: null`.
- In `QuestionResolver.resolve()`, financial basis strictly defaults to `'as_restated'` unless `'originally reported'` is explicitly mentioned.
- As a result, comparing `'as_restated' == None` evaluates to `False` on all 19 non-financial queries.
- On all 25 queries where a financial basis is relevant, basis resolution is **25 / 25 (100.0%)**.
