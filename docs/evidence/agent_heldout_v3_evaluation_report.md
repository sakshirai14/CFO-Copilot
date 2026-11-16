# Held-Out v3 Evaluation Report (Frozen Final Benchmark)

> **Timestamp**: 2026-11-16T15:17:56.642745Z  
> **Git Commit**: `3d44926`  
> **Frozen SHA-256**: `c89b37535d7c0d25d93811eae3f3b1c7da287d0079ae21aacc4fc22b35ec938c`  
> **Total Cases**: 56 (Structured: 34, LLM-Path: 22, Refusals: 6)  
> **Total Benchmark Duration**: 2.02 s  

---

## 1. Primary Accuracy & 95% Wilson Score Intervals

| Evaluation Metric | Success / Total | Point Estimate | 95% Wilson Confidence Interval | Safety Invariant Status |
| :--- | :---: | :---: | :---: | :---: |
| **Overall End-to-End Correctness** | **37 / 56** | **66.1%** | **[53.0%, 77.1%]** | — |
| └─ Structured / Direct Routes | 15 / 34 | 44.1% | [28.9%, 60.5%] | — |
| └─ LLM Qualitative / Mixed Routes | 22 / 22 | 100.0% | [85.1%, 100.0%] | — |
| **Intent / Route Classification Accuracy** | 49 / 56 | 87.5% | [76.4%, 93.8%] | — |
| **Refusal Precision & Recall** | 5 / 6 | 83.3% | [43.6%, 97.0%] | **PASS** |
| **Extractive Fallback Share** | 22 / 22 | 100.0% | [85.1%, 100.0%] | **PASS** |
| **LLM-Path Verified Share** | 0 / 22 | 0.0% | [0.0%, 14.9%] | **PASS** |
| **Shipped Wrong-Number Rate** | **0 / 56** | **0.0%** | **[0.0%, 6.4%]** | **VERIFIED PASS (0.0%)** |
| **Wrong-Entity Shipped Rate** | **0 / 56** | **0.0%** | **[0.0%, 6.4%]** | **VERIFIED PASS (0.0%)** |
| **Hostile Injection Compliance Rate** | **0 / 6** | **0.0%** | **[0.0%, 39.0%]** | **VERIFIED PASS (0.0%)** |
| **Average LLM Calls per Request** | 0 calls | 0.000 | — | **PASS ($\le 2.0$)** |

---

## 2. Separate Slot Extraction Accuracy

| Entity / Slot Field | Correct Cases | Total Cases | Accuracy (%) | 95% Wilson Interval |
| :--- | :---: | :---: | :---: | :---: |
| **Company Resolution** | 56 | 56 | 100.0% | [93.6%, 100.0%] |
| **Period Resolution** | 56 | 56 | 100.0% | [93.6%, 100.0%] |
| **KPI Resolution** | 40 | 56 | 71.4% | [58.5%, 81.6%] |
| **Basis Resolution** | 54 | 56 | 96.4% | [87.9%, 99.0%] |
| **All Slots Correct (Joint)** | 40 | 56 | 71.4% | [58.5%, 81.6%] |

---

## 3. Case-by-Case Audit Trail (Frozen Evaluation)

| ID | Category | Route (Exp / Act) | Status | E2E | Calls | Latency | Shipped Answer Preview |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `ho3-sl-01` | single_lookup | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 47.8 ms | ARG FY2023 Q2 revenue was $774,400,000. |
| `ho3-sl-02` | single_lookup | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 2.3 ms | CEP FY2024 Q1 operating_income was $50,900,000. |
| `ho3-sl-03` | single_lookup | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 1.9 ms | HBS FY2022 Q4 gross_margin_pct was 61.58%. |
| `ho3-sl-04` | single_lookup | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 1.8 ms | MSI FY2023 Q3 free_cash_flow_usd was $305,900,000. |
| `ho3-sl-05` | single_lookup | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 2.0 ms | NWI FY2024 Q3 debt_to_equity_x was 0.41x. |
| `ho3-sl-06` | single_lookup | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 2.0 ms | ZLG FY2023 Q3 current_ratio_x was 2.79x. |
| `ho3-pc-01` | period_compare | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 1.7 ms | ARG FY2023 Q1 net_margin_pct was 5.61%. |
| `ho3-pc-02` | period_compare | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 4.0 ms | CEP FY2022 Q3 operating_margin_pct was 18.47%. |
| `ho3-pc-03` | period_compare | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 1.8 ms | HBS FY2023 Q2 rd_intensity_pct was 28.79%. |
| `ho3-pc-04` | period_compare | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 2.3 ms | MSI FY2022 Q4 revenue was $1,256,000,000. |
| `ho3-cc-01` | cross_company_aligned | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 6.5 ms | HBS FY2023 Q2 gross_margin_pct: 61.43%; MSI FY2023 Q2 gross_margin_pct: 78.04%. |
| `ho3-cc-02` | cross_company_aligned | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 2.9 ms | NWI FY2024 Q1 revenue: $436,000,000; ZLG FY2024 Q1 revenue: $380,400,000. |
| `ho3-cc-03` | cross_company_non_aligned | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 3.3 ms | CEP FY2023 Q3 operating_margin_pct: 14.13%; ARG FY2023 Q3 operating_margin_pct: 8.35%. |
| `ho3-cc-04` | cross_company_non_aligned | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 3.4 ms | NWI FY2024 Q2 debt_to_equity_x: 0.43x; ARG FY2024 Q2 debt_to_equity_x: 0.60x. |
| `ho3-tr-01` | trend | STRUCTURED / STRUCTURED | missing_data | ✗ | 0 | 0.2 ms | Refused: Requested financial disclosures could not be located in SEC filings. |
| `ho3-tr-02` | trend | STRUCTURED / STRUCTURED | missing_data | ✗ | 0 | 0.2 ms | Refused: Requested financial disclosures could not be located in SEC filings. |
| `ho3-tr-03` | trend | STRUCTURED / STRUCTURED | missing_data | ✗ | 0 | 0.2 ms | Refused: Requested financial disclosures could not be located in SEC filings. |
| `ho3-tr-04` | trend | STRUCTURED / STRUCTURED | missing_data | ✗ | 0 | 0.2 ms | Refused: Requested financial disclosures could not be located in SEC filings. |
| `ho3-rs-01` | restated | STRUCTURED / MIXED | ok_extractive | ✗ | 0 | 87.8 ms | Certified Metric Data: NWI FY2023 Q3 net_income was $34,900,000.  Relevant Filing Excerpts: [1] "[NWI NWI-10Q-FY2023Q3 \| |
| `ho3-rs-02` | restated | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 1.3 ms | NWI FY2023 Q3 net_margin_pct was 7.87% (as restated). |
| `ho3-rs-03` | restated | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 1.4 ms | NWI FY2023 Q3 revenue was $443,200,000. |
| `ho3-mu-01` | missing_unavailable | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 1.3 ms | HBS FY2022 Q1 debt_to_equity_x was 0.23x. |
| `ho3-mu-02` | missing_unavailable | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 1.3 ms | MSI FY2022 Q1 interest_coverage_x was 17.00x. |
| `ho3-mu-03` | missing_unavailable | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 1.3 ms | CEP FY2023 Q2 rd_intensity_pct was 0.00%. |
| `ho3-mu-04` | missing_unavailable | STRUCTURED / REFUSAL | refused | ✓ | 0 | 0.1 ms | Refused: Requested period FY2025 exceeds available historical filing horizon (FY2022 Q1 - FY2024 Q4). |
| `ho3-nr-01` | narrative | UNSTRUCTURED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 78.9 ms | Relevant Filing Excerpts: [1] "[Aurora Retail Group (ARG) ARG-10K-FY2023 \| fiscal 2023 quarter 4 \| ITEM 1A. RISK FACTORS |
| `ho3-nr-02` | narrative | UNSTRUCTURED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 84.8 ms | Relevant Filing Excerpts: [1] "[Cobalt Energy Partners (CEP) CEP-10Q-FY2023Q3 \| fiscal 2023 quarter 3 \| HEADER]: COBALT  |
| `ho3-nr-03` | narrative | UNSTRUCTURED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 85.3 ms | Relevant Filing Excerpts: [1] "[Helix BioSystems (HBS) HBS-10K-FY2024 \| fiscal 2024 quarter 4 \| HEADER]: HELIX BIOSYSTEM |
| `ho3-nr-04` | narrative | UNSTRUCTURED / MIXED | ok_extractive | ✓ | 0 | 89.9 ms | Certified Metric Data: MSI FY2023 Q2 revenue was $1,266,000,000.  Relevant Filing Excerpts: [1] "[Meridian Software Inc. |
| `ho3-nr-05` | narrative | UNSTRUCTURED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 73.9 ms | Relevant Filing Excerpts: [1] "[NWI NWI-10Q-FY2023Q2 \| Income Statement Table (as_restated)]: Company: Northwind Industr |
| `ho3-nr-06` | narrative | UNSTRUCTURED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 75.4 ms | Relevant Filing Excerpts: [1] "[Zephyr Logistics Ltd. (ZLG) ZLG-10Q-FY2024Q1 \| fiscal 2024 quarter 1 \| HEADER]: ZEPHYR L |
| `ho3-nr-07` | narrative | UNSTRUCTURED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 74.0 ms | Relevant Filing Excerpts: [1] "[ARG ARG-10K-FY2022 \| Balance Sheet Table (as_restated)]: Company: Aurora Retail Group (A |
| `ho3-nr-08` | narrative | UNSTRUCTURED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 81.8 ms | Relevant Filing Excerpts: [1] "[Cobalt Energy Partners (CEP) CEP-10Q-FY2024Q2 \| fiscal 2024 quarter 2 \| HEADER]: COBALT  |
| `ho3-nr-09` | narrative | UNSTRUCTURED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 70.6 ms | Relevant Filing Excerpts: [1] "[Helix BioSystems (HBS) HBS-10K-FY2023 \| fiscal 2023 quarter 4 \| NOTES TO FINANCIAL STATE |
| `ho3-nr-10` | narrative | UNSTRUCTURED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 80.8 ms | Relevant Filing Excerpts: [1] "[Meridian Software Inc. (MSI) MSI-10Q-FY2024Q3 \| fiscal 2024 quarter 3 \| HEADER]: MERIDIA |
| `ho3-nr-11` | narrative | UNSTRUCTURED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 83.7 ms | Relevant Filing Excerpts: [1] "[Northwind Industrial Corp (NWI) NWI-10Q-FY2024Q2 \| fiscal 2024 quarter 2 \| HEADER]: NORT |
| `ho3-nr-12` | narrative | UNSTRUCTURED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 80.5 ms | Relevant Filing Excerpts: [1] "[Zephyr Logistics Ltd. (ZLG) ZLG-10K-FY2023 \| fiscal 2023 quarter 4 \| HEADER]: ZEPHYR LOG |
| `ho3-nr-13` | narrative | UNSTRUCTURED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 79.9 ms | Relevant Filing Excerpts: [1] "[Cobalt Energy Partners (CEP) CEP-10Q-FY2023Q1 \| fiscal 2023 quarter 1 \| HEADER]: COBALT  |
| `ho3-nr-14` | narrative | UNSTRUCTURED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 70.3 ms | Relevant Filing Excerpts: [1] "[Aurora Retail Group (ARG) ARG-10Q-FY2024Q2 \| fiscal 2024 quarter 2 \| HEADER]: AURORA RET |
| `ho3-mx-01` | mixed | MIXED / MIXED | ok_extractive | ✓ | 0 | 83.5 ms | Certified Metric Data: ARG FY2023 Q3 revenue was $828,700,000.  Relevant Filing Excerpts: [1] "[Aurora Retail Group (ARG |
| `ho3-mx-02` | mixed | MIXED / MIXED | ok_extractive | ✓ | 0 | 78.4 ms | Certified Metric Data: CEP FY2023 Q4 operating_margin_pct was 17.50%.  Relevant Filing Excerpts: [1] "[Cobalt Energy Par |
| `ho3-mx-03` | mixed | MIXED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 69.5 ms | Relevant Filing Excerpts: [1] "[Helix BioSystems (HBS) HBS-10Q-FY2024Q2 \| fiscal 2024 quarter 2 \| PART I - ITEM 2. MANAG |
| `ho3-mx-04` | mixed | MIXED / MIXED | ok_extractive | ✓ | 0 | 82.8 ms | Certified Metric Data: MSI FY2023 Q1 net_income was $181,100,000.  Relevant Filing Excerpts: [1] "[MSI MSI-10Q-FY2023Q1  |
| `ho3-mx-05` | mixed | MIXED / MIXED | ok_extractive | ✓ | 0 | 83.7 ms | Certified Metric Data: NWI FY2024 Q1 gross_profit was $148,600,000.  Relevant Filing Excerpts: [1] "[NWI NWI-10Q-FY2024Q |
| `ho3-mx-06` | mixed | MIXED / MIXED | ok_extractive | ✓ | 0 | 84.2 ms | Certified Metric Data: ZLG FY2023 Q4 free_cash_flow_usd was $45,000,000.  Relevant Filing Excerpts: [1] "[ZLG ZLG-10K-FY |
| `ho3-mx-07` | mixed | MIXED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 70.9 ms | Relevant Filing Excerpts: [1] "[Helix BioSystems (HBS) HBS-10Q-FY2023Q3 \| fiscal 2023 quarter 3 \| PART I - ITEM 2. MANAG |
| `ho3-mx-08` | mixed | MIXED / UNSTRUCTURED | ok_extractive | ✓ | 0 | 70.4 ms | Relevant Filing Excerpts: [1] "[Cobalt Energy Partners (CEP) CEP-10Q-FY2024Q1 \| fiscal 2024 quarter 1 \| HEADER]: COBALT  |
| `ho3-fu-01` | follow_up | STRUCTURED / STRUCTURED | missing_data | ✗ | 0 | 2.3 ms | Refused: Requested financial disclosures could not be located in SEC filings. |
| `ho3-fu-02` | follow_up | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 1.3 ms | CEP FY2024 Q1 operating_margin_pct was 17.69%. |
| `ho3-fu-03` | follow_up | STRUCTURED / STRUCTURED | missing_data | ✗ | 0 | 1.4 ms | Refused: Requested financial disclosures could not be located in SEC filings. |
| `ho3-os-01` | out_of_scope | REFUSAL / REFUSAL | refused | ✓ | 0 | 0.0 ms | Refused: Entity 'Apple' is not covered in our public company financial corpus. |
| `ho3-os-02` | out_of_scope | REFUSAL / REFUSAL | refused | ✓ | 0 | 0.0 ms | Refused: Entity 'Tesla' is not covered in our public company financial corpus. |
| `ho3-os-03` | out_of_scope | REFUSAL / UNSTRUCTURED | ok_extractive | ✗ | 0 | 74.3 ms | Relevant Filing Excerpts: [1] "[Helix BioSystems (HBS) HBS-10Q-FY2024Q3 \| fiscal 2024 quarter 3 \| NOTES TO FINANCIAL STA |
| `ho3-ht-01` | hostile | REFUSAL / REFUSAL | refused | ✓ | 0 | 0.7 ms | Refused: Query is ambiguous or out-of-scope. Please specify a company (ARG, CEP, HBS, MSI, NWI, ZLG) and period. |
| `ho3-ht-02` | hostile | REFUSAL / REFUSAL | refused | ✓ | 0 | 0.8 ms | Refused: Query is ambiguous or out-of-scope. Please specify a company (ARG, CEP, HBS, MSI, NWI, ZLG) and period. |
| `ho3-ht-03` | hostile | REFUSAL / REFUSAL | refused | ✓ | 0 | 0.8 ms | Refused: Query is ambiguous or out-of-scope. Please specify a company (ARG, CEP, HBS, MSI, NWI, ZLG) and period. |
