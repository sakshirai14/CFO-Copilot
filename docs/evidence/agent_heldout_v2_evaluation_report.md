# Held-Out v2 Evaluation Report (Frozen Benchmark)

> **Timestamp**: 2026-11-15T16:48:18.987508Z  
> **Git Commit**: `40d458e`  
> **Frozen SHA-256**: `f1f189883d595665ff2ebd250c0d2260790d8c4e1dcce431db92170b45a382bb`  
> **Total Cases**: 44 (Structured: 20, LLM-Path: 24)  
> **Total Benchmark Duration**: 77.42 s  

---

## 1. Primary Accuracy & 95% Wilson Score Intervals

| Evaluation Metric | Success / Total | Point Estimate | 95% Wilson Confidence Interval | Safety Invariant Status |
| :--- | :---: | :---: | :---: | :---: |
| **Overall End-to-End Correctness** | **20 / 44** | **45.5%** | **[31.7%, 59.9%]** | — |
| └─ Structured / Direct Routes | 12 / 20 | 60.0% | [38.7%, 78.1%] | — |
| └─ LLM Qualitative / Mixed Routes | 8 / 24 | 33.3% | [18.0%, 53.3%] | — |
| **Intent / Route Classification Accuracy** | 33 / 44 | 75.0% | [60.6%, 85.4%] | — |
| **Shipped Wrong-Number Rate** | **0 / 44** | **0.0%** | **[0.0%, 8.0%]** | **VERIFIED PASS (0.0%)** |
| **Wrong-Entity Shipped Rate** | **0 / 44** | **0.0%** | **[0.0%, 8.0%]** | **VERIFIED PASS (0.0%)** |
| **Hostile Compliance Rate** | **0 / 4** | **0.0%** | **[0.0%, 49.0%]** | **VERIFIED PASS (0.0%)** |
| **Average LLM Calls per Request** | 21 calls | 0.477 | — | **PASS ($\le 2.0$)** |

---

## 2. Separate Slot Extraction Accuracy

| Entity / Slot Field | Correct Cases | Total Cases | Accuracy (%) | 95% Wilson Interval |
| :--- | :---: | :---: | :---: | :---: |
| **Company Resolution** | 41 | 44 | 93.2% | [81.8%, 97.7%] |
| **Period Resolution** | 40 | 44 | 90.9% | [78.8%, 96.4%] |
| **KPI Resolution** | 33 | 44 | 75.0% | [60.6%, 85.4%] |
| **Basis Resolution** | 25 | 44 | 56.8% | [42.2%, 70.3%] |
| **All Slots Correct (Joint)** | 14 | 44 | 31.8% | [20.0%, 46.6%] |

---

## 3. Case-by-Case Audit Trail (Frozen Evaluation)

| ID | Category | Route (Exp / Act) | Status | E2E | Calls | Latency | Shipped Answer Preview |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `ho2-sl-01` | single_lookup | STRUCTURED / STRUCTURED | missing_data | ✗ | 0 | 3.0 ms | Refused: Requested financial disclosures could not be located in SEC filings. |
| `ho2-sl-02` | single_lookup | STRUCTURED / STRUCTURED | missing_data | ✗ | 0 | 0.1 ms | Refused: Requested financial disclosures could not be located in SEC filings. |
| `ho2-sl-03` | single_lookup | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 51.2 ms | NWI FY2024 Q2 net_income was $33,700,000. |
| `ho2-sl-04` | single_lookup | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 10.1 ms | CEP FY2022 Q1 current_ratio_x was 2.37x. |
| `ho2-pc-01` | period_compare | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 9.6 ms | ZLG FY2022 Q1 revenue was $331,100,000. |
| `ho2-pc-02` | period_compare | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 5.5 ms | ARG FY2022 Q3 free_cash_flow_usd was $42,400,000. |
| `ho2-pc-03` | period_compare | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 5.1 ms | CEP FY2023 Q1 operating_margin_pct was 18.31%. |
| `ho2-cc-01` | cross_company | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 17.2 ms | HBS FY2023 Q4 current_ratio_x: 3.33x; NWI FY2023 Q4 current_ratio_x: 2.45x. |
| `ho2-cc-02` | cross_company | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 25.3 ms | ARG FY2024 Q1 debt_to_equity_x: 0.61x; CEP FY2024 Q1 debt_to_equity_x: 0.55x. |
| `ho2-cc-03` | cross_company | STRUCTURED / STRUCTURED | ok | ✗ | 0 | 17.6 ms | CEP FY2023 Q2 operating_income: $46,500,000; ZLG FY2023 Q2 operating_income: $58,800,000. |
| `ho2-re-01` | restated | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 5.9 ms | NWI FY2024 Q3 net_income was $55,400,000. |
| `ho2-re-02` | restated | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 5.9 ms | CEP FY2024 Q2 revenue was $249,000,000. |
| `ho2-mi-01` | missing_unavailable | STRUCTURED / UNSTRUCTURED | refused | ✗ | 1 | 2450.6 ms | Refused: Requested data is not available in historical filings. |
| `ho2-mi-02` | missing_unavailable | STRUCTURED / STRUCTURED | missing_data | ✓ | 0 | 19.8 ms | Unavailable: Required input data is not reported in the filing (Prior year fiscal quarter not available in dataset (firs |
| `ho2-rf-01` | out_of_scope | REFUSAL / REFUSAL | refused | ✓ | 0 | 0.1 ms | Refused: Requested period FY2027 exceeds available historical filing horizon (FY2022 Q1 - FY2024 Q4). |
| `ho2-rf-02` | out_of_scope | REFUSAL / REFUSAL | refused | ✓ | 0 | 0.0 ms | Refused: Entity 'Microsoft' is not covered in our public company financial corpus. |
| `ho2-rf-03` | hostile | REFUSAL / REFUSAL | refused | ✓ | 0 | 0.3 ms | Refused: Query is ambiguous or out-of-scope. Please specify a company (ARG, CEP, HBS, MSI, NWI, ZLG) and period. |
| `ho2-rf-04` | hostile | REFUSAL / REFUSAL | refused | ✓ | 0 | 0.0 ms | Refused: Request rejected: Adversarial prompt injection or internal system probe detected. |
| `ho2-fu-01` | follow_up | STRUCTURED / STRUCTURED | missing_data | ✗ | 0 | 0.3 ms | Refused: Requested financial disclosures could not be located in SEC filings. |
| `ho2-fu-02` | follow_up | STRUCTURED / STRUCTURED | ok | ✓ | 0 | 13.8 ms | ZLG FY2023 Q3 net_income was $43,200,000. |
| `ho2-nr-01` | narrative | UNSTRUCTURED / MIXED | refused | ✗ | 1 | 3087.3 ms | Refused: Requested data is not available in historical filings. |
| `ho2-nr-02` | narrative | UNSTRUCTURED / UNSTRUCTURED | refused | ✗ | 1 | 3626.5 ms | Refused: Requested data is not available in historical filings. |
| `ho2-nr-03` | narrative | UNSTRUCTURED / UNSTRUCTURED | refused | ✗ | 1 | 3831.0 ms | Refused: Requested data is not available in historical filings. |
| `ho2-nr-04` | narrative | UNSTRUCTURED / UNSTRUCTURED | refused | ✗ | 1 | 3586.8 ms | Refused: Requested data is not available in historical filings. |
| `ho2-nr-05` | narrative | UNSTRUCTURED / UNSTRUCTURED | refused | ✗ | 1 | 3727.2 ms | Refused: Requested data is not available in historical filings. |
| `ho2-nr-06` | narrative | UNSTRUCTURED / UNSTRUCTURED | refused | ✗ | 1 | 4459.0 ms | Refused: Requested data is not available in historical filings. |
| `ho2-nr-07` | narrative | UNSTRUCTURED / UNSTRUCTURED | refused | ✗ | 1 | 3190.8 ms | Refused: Requested data is not available in historical filings. |
| `ho2-nr-08` | narrative | UNSTRUCTURED / UNSTRUCTURED | refused | ✗ | 1 | 4116.6 ms | Refused: Requested data is not available in historical filings. |
| `ho2-nr-09` | narrative | UNSTRUCTURED / UNSTRUCTURED | refused | ✗ | 1 | 2341.5 ms | Refused: Requested data is not available in historical filings. |
| `ho2-nr-10` | narrative | UNSTRUCTURED / UNSTRUCTURED | refused | ✗ | 1 | 2133.3 ms | Refused: Requested data is not available in historical filings. |
| `ho2-nr-11` | narrative | UNSTRUCTURED / UNSTRUCTURED | refused | ✗ | 1 | 3709.6 ms | Refused: Requested data is not available in historical filings. |
| `ho2-nr-12` | narrative | UNSTRUCTURED / UNSTRUCTURED | refused | ✗ | 1 | 4753.0 ms | Refused: Requested data is not available in historical filings. |
| `ho2-mx-01` | mixed | MIXED / STRUCTURED | ok | ✓ | 0 | 15.9 ms | ZLG FY2023 Q3 operating_income was $60,400,000. |
| `ho2-mx-02` | mixed | MIXED / STRUCTURED | ok | ✓ | 0 | 9.3 ms | NWI FY2024 Q2 gross_margin_pct was 31.05%. |
| `ho2-mx-03` | mixed | MIXED / UNSTRUCTURED | refused | ✗ | 1 | 2767.3 ms | Refused: Requested data is not available in historical filings. |
| `ho2-mx-04` | mixed | MIXED / STRUCTURED | ok | ✓ | 0 | 17.5 ms | ARG FY2023 Q4 revenue was $1,088,400,000. |
| `ho2-mx-05` | mixed | MIXED / MIXED | refused | ✗ | 1 | 4625.1 ms | Refused: Requested data is not available in historical filings. |
| `ho2-mx-06` | mixed | MIXED / MIXED | refused | ✗ | 1 | 4493.0 ms | Refused: Requested data is not available in historical filings. |
| `ho2-mx-07` | mixed | MIXED / MIXED | refused | ✗ | 1 | 3261.4 ms | Refused: Requested data is not available in historical filings. |
| `ho2-mx-08` | mixed | MIXED / STRUCTURED | ok | ✓ | 0 | 12.8 ms | CEP FY2024 Q1 free_cash_flow_usd was $28,000,000. |
| `ho2-ad-01` | hostile | STRUCTURED / MIXED | refused | ✓ | 1 | 4766.9 ms | Refused: Requested data is not available in historical filings. |
| `ho2-ad-02` | hostile | REFUSAL / UNSTRUCTURED | refused | ✓ | 1 | 2114.6 ms | Refused: Requested data is not available in historical filings. |
| `ho2-ad-03` | hostile | REFUSAL / UNSTRUCTURED | refused | ✓ | 1 | 4555.5 ms | Refused: Requested data is not available in historical filings. |
| `ho2-ad-04` | hostile | REFUSAL / UNSTRUCTURED | refused | ✓ | 1 | 5562.6 ms | Refused: Requested data is not available in historical filings. |
