# Narrative Dev Benchmark Evaluation Report (n = 15)

> **Evaluated Date**: 2026-11-15 19:00:19 UTC  
> **Model**: Qwen2.5-3B-Instruct (Q4_K_M) + Verified Extractive Fallback Engine  

---

## 1. Summary Metrics & 95% Wilson Confidence Intervals

| Metric | Result ($n=15$) | Percentage | 95% Wilson Interval |
| :--- | :---: | :---: | :---: |
| **Retrieval Recall@5** | 15/15 | **100.0%** | [79.6%, 100.0%] |
| **Answers LLM-Verified Synthesized** | 0/15 | **0.0%** | [0.0%, 20.4%] |
| **Preserved Extractive Fallbacks** | 15/15 | **100.0%** | [79.6%, 100.0%] |
| **Zero Ungrounded Numbers Rate** | 15/15 | **100.0%** | [79.6%, 100.0%] |
| **End-to-End Correctness** | 15/15 | **100.0%** | [79.6%, 100.0%] |

---

## 2. Per-Case Diagnostic Breakdown

| Case ID | Co | Period | Gold Chunk | Recall | Delivery Mode | Status | Grounded | E2E | Latency |
| :--- | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `ndev-01` | **ARG** | FY2023Q4 | `ARG-10K-FY2023#c2` | ✓ | Extractive | ok | ✓ | **✓** | 5816 ms |
| `ndev-02` | **ARG** | FY2023Q2 | `ARG-10Q-FY2023Q2#c3` | ✓ | Extractive | ok | ✓ | **✓** | 2648 ms |
| `ndev-03` | **ARG** | FY2024Q1 | `ARG-10Q-FY2024Q1#c2` | ✓ | Extractive | ok | ✓ | **✓** | 1924 ms |
| `ndev-04` | **CEP** | FY2022Q4 | `CEP-10K-FY2022#c2` | ✓ | Extractive | ok | ✓ | **✓** | 3895 ms |
| `ndev-05` | **CEP** | FY2023Q2 | `CEP-10Q-FY2023Q2#c3` | ✓ | Extractive | ok | ✓ | **✓** | 1852 ms |
| `ndev-06` | **CEP** | FY2024Q1 | `CEP-10Q-FY2024Q1#c4` | ✓ | Extractive | ok | ✓ | **✓** | 2194 ms |
| `ndev-07` | **HBS** | FY2023Q3 | `HBS-10Q-FY2023Q3#c2` | ✓ | Extractive | ok | ✓ | **✓** | 2836 ms |
| `ndev-08` | **HBS** | FY2024Q4 | `HBS-10K-FY2024#c3` | ✓ | Extractive | ok | ✓ | **✓** | 3394 ms |
| `ndev-09` | **HBS** | FY2022Q2 | `HBS-10Q-FY2022Q2#c2` | ✓ | Extractive | ok | ✓ | **✓** | 3414 ms |
| `ndev-10` | **MSI** | FY2023Q1 | `MSI-10Q-FY2023Q1#c2` | ✓ | Extractive | ok | ✓ | **✓** | 4040 ms |
| `ndev-11` | **MSI** | FY2024Q2 | `MSI-10Q-FY2024Q2#c3` | ✓ | Extractive | ok | ✓ | **✓** | 1868 ms |
| `ndev-12` | **NWI** | FY2023Q3 | `NWI-10Q-FY2023Q3#c2` | ✓ | Extractive | ok | ✓ | **✓** | 4529 ms |
| `ndev-13` | **NWI** | FY2024Q1 | `NWI-10Q-FY2024Q1#c3` | ✓ | Extractive | ok | ✓ | **✓** | 2883 ms |
| `ndev-14` | **ZLG** | FY2023Q4 | `ZLG-10K-FY2023#c2` | ✓ | Extractive | ok | ✓ | **✓** | 4000 ms |
| `ndev-15` | **ZLG** | FY2024Q2 | `ZLG-10Q-FY2024Q2#c3` | ✓ | Extractive | ok | ✓ | **✓** | 2232 ms |
