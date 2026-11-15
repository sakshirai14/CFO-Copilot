# Deterministic Paraphrase Benchmark Evaluation Report

> **Benchmark**: 28 Template Families across 6 Companies, 10 Canonical KPIs, and Historical Periods  
> **Evaluated Date**: 2026-11-15 18:58:39 UTC  
> **Throughput**: ~9415 queries/sec (pure regex/grammar, zero LLM calls)  

---

## 1. Split-by-Split Accuracy Comparison (with 95% Wilson Confidence Intervals)

| Evaluation Slot Field | Dev Families ($n = 2,400$) | 95% Wilson CI (Dev) | Held-Out Families ($n = 960$) | 95% Wilson CI (Held-Out) | Generalization Gap |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Company Resolution** | **100.0%** (2400/2400) | [99.8%, 100.0%] | **100.0%** (960/960) | [99.6%, 100.0%] | 0.0% |
| **Period Resolution (FY & FQ)** | **100.0%** (2400/2400) | [99.8%, 100.0%] | **100.0%** (960/960) | [99.6%, 100.0%] | 0.0% |
| **KPI Metric Resolution** | **100.0%** (2400/2400) | [99.8%, 100.0%] | **100.0%** (960/960) | [99.6%, 100.0%] | 0.0% |
| **Basis Resolution** | **100.0%** (2400/2400) | [99.8%, 100.0%] | **87.5%** (840/960) | [85.3%, 89.4%] | 12.5% |
| **All Slots Jointly Correct** | **100.0%** (2400/2400) | [99.8%, 100.0%] | **87.5%** (840/960) | [85.3%, 89.4%] | **12.5%** |

---

## 2. Analysis of Generalization Gap

The gap between Dev Families and Held-Out Families measures true semantic generalization to unseen phrasing structures.
Zero LLM inference was used during slot resolution, achieving high throughput with deterministic execution.
