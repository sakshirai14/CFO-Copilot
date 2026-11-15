# Phase 3/4 Comprehensive Retrieval Evaluation & Provenance Summary

**Evaluated**: 2026-11-15T12:29:55Z  
**Dataset**: `/Users/sakshirai/AI_RAG_Assignment/tests/evals/retrieval_eval.csv`  
**SHA-256**: `08a98c7c7a14404da4f423c141dd5ad380a4932b10ae839759a92a01b01810fc`  
**Questions**: Total 49 (DEV: 34 [27 answerable], Held-Out: 15 [11 answerable])

## 1. Retrieval Performance Matrix with 95% Wilson Confidence Intervals

| Configuration | Split | n | Recall@1 [95% CI] | Recall@5 [95% CI] | MRR | Latency p50 (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Hybrid (Vector + FTS) + Gold Filters | all | 38 | 68.4% [52.5% - 80.9%] | 94.7% [82.7% - 98.5%] | 0.8048 | 19.21 |
| &nbsp;&nbsp;↳ *DEV* | dev | 27 | 70.4% [51.5% - 84.1%] | 100.0% [87.5% - 100.0%] | 0.8364 | 10.33 |
| &nbsp;&nbsp;↳ *HELD_OUT* | held_out | 11 | 63.6% [35.4% - 84.8%] | 81.8% [52.3% - 94.9%] | 0.7273 | 11.17 |
| Hybrid (Vector + FTS) + Deterministic Filters | all | 38 | 63.2% [47.3% - 76.6%] | 86.8% [72.7% - 94.2%] | 0.7452 | 10.71 |
| &nbsp;&nbsp;↳ *DEV* | dev | 27 | 66.7% [47.8% - 81.4%] | 96.3% [81.7% - 99.3%] | 0.7994 | 11.09 |
| &nbsp;&nbsp;↳ *HELD_OUT* | held_out | 11 | 54.5% [28.0% - 78.7%] | 63.6% [35.4% - 84.8%] | 0.6124 | 11.59 |
| Hybrid (Vector + FTS) - No Filters | all | 38 | 42.1% [27.9% - 57.8%] | 84.2% [69.6% - 92.6%] | 0.5882 | 13.58 |
| &nbsp;&nbsp;↳ *DEV* | dev | 27 | 44.4% [27.6% - 62.7%] | 92.6% [76.6% - 97.9%] | 0.6352 | 13.71 |
| &nbsp;&nbsp;↳ *HELD_OUT* | held_out | 11 | 36.4% [15.2% - 64.6%] | 63.6% [35.4% - 84.8%] | 0.4727 | 14.73 |
| FTS-Only + Gold Filters | all | 38 | 73.7% [58.0% - 85.0%] | 92.1% [79.2% - 97.3%] | 0.8158 | 5.57 |
| &nbsp;&nbsp;↳ *DEV* | dev | 27 | 77.8% [59.2% - 89.4%] | 96.3% [81.7% - 99.3%] | 0.8580 | 5.76 |
| &nbsp;&nbsp;↳ *HELD_OUT* | held_out | 11 | 63.6% [35.4% - 84.8%] | 81.8% [52.3% - 94.9%] | 0.7121 | 5.79 |
| FTS-Only + Deterministic Filters | all | 38 | 68.4% [52.5% - 80.9%] | 81.6% [66.6% - 90.8%] | 0.7446 | 5.52 |
| &nbsp;&nbsp;↳ *DEV* | dev | 27 | 70.4% [51.5% - 84.1%] | 88.9% [71.9% - 96.1%] | 0.7850 | 5.61 |
| &nbsp;&nbsp;↳ *HELD_OUT* | held_out | 11 | 63.6% [35.4% - 84.8%] | 63.6% [35.4% - 84.8%] | 0.6455 | 6.11 |
| FTS-Only - No Filters | all | 38 | 68.4% [52.5% - 80.9%] | 78.9% [63.7% - 88.9%] | 0.7215 | 6.99 |
| &nbsp;&nbsp;↳ *DEV* | dev | 27 | 70.4% [51.5% - 84.1%] | 85.2% [67.5% - 94.1%] | 0.7562 | 6.67 |
| &nbsp;&nbsp;↳ *HELD_OUT* | held_out | 11 | 63.6% [35.4% - 84.8%] | 63.6% [35.4% - 84.8%] | 0.6364 | 7.42 |
| Vector-Only + Gold Filters | all | 38 | 34.2% [21.2% - 50.1%] | 94.7% [82.7% - 98.5%] | 0.5316 | 5.22 |
| &nbsp;&nbsp;↳ *DEV* | dev | 27 | 33.3% [18.6% - 52.2%] | 100.0% [87.5% - 100.0%] | 0.5321 | 5.17 |
| &nbsp;&nbsp;↳ *HELD_OUT* | held_out | 11 | 36.4% [15.2% - 64.6%] | 81.8% [52.3% - 94.9%] | 0.5303 | 5.23 |
| Vector-Only + Deterministic Filters | all | 38 | 26.3% [15.0% - 42.0%] | 89.5% [75.9% - 95.8%] | 0.4670 | 4.96 |
| &nbsp;&nbsp;↳ *DEV* | dev | 27 | 29.6% [15.9% - 48.5%] | 96.3% [81.7% - 99.3%] | 0.4992 | 5.38 |
| &nbsp;&nbsp;↳ *HELD_OUT* | held_out | 11 | 18.2% [5.1% - 47.7%] | 72.7% [43.4% - 90.3%] | 0.3879 | 5.50 |
| Vector-Only - No Filters | all | 38 | 21.1% [11.1% - 36.3%] | 34.2% [21.2% - 50.1%] | 0.2629 | 6.51 |
| &nbsp;&nbsp;↳ *DEV* | dev | 27 | 22.2% [10.6% - 40.8%] | 37.0% [21.5% - 55.8%] | 0.2788 | 6.75 |
| &nbsp;&nbsp;↳ *HELD_OUT* | held_out | 11 | 18.2% [5.1% - 47.7%] | 27.3% [9.7% - 56.6%] | 0.2237 | 6.23 |

## 2. Gold Rank Distribution (Hybrid + Gold Filters on DEV, n=27)

| Rank Position | Query Count | Percentage |
| :--- | :---: | :---: |
| **Rank 1** | 19 | 70.4% |
| **Rank 2** | 6 | 22.2% |
| **Rank 3** | 1 | 3.7% |
| **Rank 4** | 1 | 3.7% |
| **Rank 5** | 0 | 0.0% |
| **Rank 6-10** | 0 | 0.0% |
| **> Rank 10** | 0 | 0.0% |

## 3. Failure Classification for Queries where Gold is Not Rank 1

| Query ID | Question | Gold Chunks | Gold Rank | Top-1 Chunk Retrieved | Failure Classification |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `dev-03` | What was Cobalt Energy Partners's interest coverage in fiscal 2024 quarter 1? | `CEP_2024Q1_IS#t1` | 4 | `CEP-10Q-FY2024Q1#c1` | `right_company_period_wrong_statement_or_header` |
| `dev-06` | What was Cobalt Energy Partners's operating margin in fiscal 2023 quarter 1? | `CEP_2023Q1_IS#t1` | 2 | `CEP-10Q-FY2023Q1#c2` | `right_company_period_wrong_statement_or_header` |
| `dev-08` | What was Cobalt Energy Partners's gross margin in fiscal 2023 quarter 2? | `CEP_2023Q2_IS#t1` | 2 | `CEP-10Q-FY2023Q2#c2` | `right_company_period_wrong_statement_or_header` |
| `dev-10` | What was Cobalt Energy Partners's gross margin in fiscal 2022 quarter 3? | `CEP_2022Q3_IS#t1` | 2 | `CEP-10Q-FY2022Q3#c2` | `right_company_period_wrong_statement_or_header` |
| `dev-13` | What was Aurora Retail Group's operating margin in fiscal 2024 quarter 1? | `ARG_2024Q1_IS#t1` | 2 | `ARG-10Q-FY2024Q1#c2` | `right_company_period_wrong_statement_or_header` |
| `dev-15` | According to the filings what drove the revenue change at Aurora Retail Group in fiscal 2022 quarter 4? | `ARG-10K-FY2022#c2` | 3 | `ARG-10K-FY2022#c4` | `right_company_period_wrong_statement_or_header` |
| `eval-18` | What was Helix Biosystems's operating income in fiscal 2024 quarter 1? | `HBS_2024Q1_IS#t1` | 2 | `HBS-10Q-FY2024Q1#c2` | `right_company_period_wrong_statement_or_header` |
| `eval-20` | What was MSI's total revenue in fiscal 2022 quarter 4? | `MSI_2022Q4_IS#t1` | 2 | `MSI-10K-FY2022#c2` | `right_company_period_wrong_statement_or_header` |

## 4. Filter Provenance in System Architecture

- **Source**: In Phase 5, metadata filters (`company_id`, `fiscal_year`, `fiscal_quarter`) are deterministically resolved by the upstream Router / Agent layer from the CFO query text.
- **Degradation**: If filter extraction fails or confidence is low, retrieval gracefully degrades to unfiltered Hybrid search (which achieves 92.6% R@5 on DEV and 63.6% on Held-Out).

## 5. Counterfactual Injected Chunk Exposure & Security Limitations

- **Quarantine Active (Default)**: 0 injected chunks in top 5 (0.00% leak rate).
- **Quarantine Inactive (Counterfactual)**: 5 injected chunks appeared in top 5 (1.02% exposure rate).
- **Detector Limitations**: Keyword/regex signature filtering catches known jailbreak markers (e.g. `SYSTEM NOTICE TO AI ASSISTANTS`, `Ignore previous instructions`), but CANNOT detect novel adversarial paraphrases or semantic prompt injections without distinct lexical signatures.
