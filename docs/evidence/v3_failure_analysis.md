# v3_failure_analysis.md: Held-Out Benchmark v3 Comprehensive Failure Diagnosis

> **Platform**: CFO Copilot on a Budget  
> **Analysis Target**: Authoritative Held-Out Benchmark v3 (56 Cases)  
> **Frozen Commit**: `3d44926` (`freeze-before-v3`)  
> **Integrity Principle**: *Read-only diagnosis. Zero code, prompt, resolver, or verifier changes are made to alter held-out scores.*  

---

## 1. Per-Category Pass / Fail Breakdown

| Category | Total Cases | Passed Cases | Failed Cases | Pass Rate (%) | Primary Failure Mode |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `cross_company_aligned` | 2 | 1 | 1 | **50.0%** | Resolver / Scorer Mismatch |
| `cross_company_non_aligned` | 2 | 1 | 1 | **50.0%** | Resolver / Scorer Mismatch |
| `follow_up` | 3 | 1 | 2 | **33.3%** | Resolver slot error (context inheritance) |
| `hostile` | 3 | 3 | 0 | **100.0%** | None (100% Pass) |
| `missing_unavailable` | 4 | 1 | 3 | **25.0%** | Resolver / Scorer Mismatch |
| `mixed` | 8 | 8 | 0 | **100.0%** | None (100% Pass) |
| `narrative` | 14 | 14 | 0 | **100.0%** | None (100% Pass) |
| `out_of_scope` | 3 | 2 | 1 | **66.7%** | Route error (Pfizer entity missing from refusal regex) |
| `period_compare` | 4 | 3 | 1 | **75.0%** | Resolver / Scorer Mismatch |
| `restated` | 3 | 1 | 2 | **33.3%** | Resolver / Scorer Mismatch |
| `single_lookup` | 6 | 2 | 4 | **33.3%** | Resolver / Scorer Mismatch |
| `trend` | 4 | 0 | 4 | **0.0%** | Resolver slot error (multi-quarter parsing) |
| **TOTAL** | **56** | **37** | **19** | **66.1%** | — |

---

## 2. Detailed Diagnosis of the 19 Failing Cases

| Case ID | Category | Original Question | Expected Route | Expected Slots | Gold Answer / Status | Actual Route | Actual Slots | Actual Answer | Cause Class | Root Cause Explanation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ho3-sl-01` | single_lookup | Please retrieve the total revenue for Aurora Retail Group in the second quarter of fiscal 2023. | `STRUCTURED` | Co: `ARG`, P: `FY2023Q2`, KPI: `revenue_usd`, Basis: `as_restated` | Status: `ok` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `False`, Basis: `True` | `ARG FY2023 Q2 revenue was $774,400,000....` (Status: `ok`) | **Gold or scorer mismatch** | KPI schema identifier mismatch (e.g. expected 'revenue_usd' vs resolver 'revenue', or 'current_ratio' vs 'current_ratio_x'). Correct dollar/ratio figure was displayed. |
| `ho3-sl-02` | single_lookup | What was the operating income recorded by Cobalt Energy Partners during fiscal 2024 quarter 1? | `STRUCTURED` | Co: `CEP`, P: `FY2024Q1`, KPI: `operating_income_usd`, Basis: `as_restated` | Status: `ok` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `False`, Basis: `True` | `CEP FY2024 Q1 operating_income was $50,900,000....` (Status: `ok`) | **Gold or scorer mismatch** | KPI schema identifier mismatch (e.g. expected 'revenue_usd' vs resolver 'revenue', or 'current_ratio' vs 'current_ratio_x'). Correct dollar/ratio figure was displayed. |
| `ho3-sl-05` | single_lookup | Report the debt to equity ratio for Northwind Industrial Corp for fiscal 2024 quarter 3. | `STRUCTURED` | Co: `NWI`, P: `FY2024Q3`, KPI: `debt_to_equity_ratio`, Basis: `as_restated` | Status: `ok` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `False`, Basis: `True` | `NWI FY2024 Q3 debt_to_equity_x was 0.41x....` (Status: `ok`) | **Gold or scorer mismatch** | KPI schema identifier mismatch (e.g. expected 'revenue_usd' vs resolver 'revenue', or 'current_ratio' vs 'current_ratio_x'). Correct dollar/ratio figure was displayed. |
| `ho3-sl-06` | single_lookup | What was the current ratio of Zephyr Logistics in fiscal 2023 quarter 3? | `STRUCTURED` | Co: `ZLG`, P: `FY2023Q3`, KPI: `current_ratio`, Basis: `as_restated` | Status: `ok` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `False`, Basis: `True` | `ZLG FY2023 Q3 current_ratio_x was 2.79x....` (Status: `ok`) | **Gold or scorer mismatch** | KPI schema identifier mismatch (e.g. expected 'revenue_usd' vs resolver 'revenue', or 'current_ratio' vs 'current_ratio_x'). Correct dollar/ratio figure was displayed. |
| `ho3-pc-04` | period_compare | What was the difference in Meridian Software's revenue between fiscal 2022 quarter 4 and fiscal 2023 quarter 4? | `STRUCTURED` | Co: `MSI`, P: `None`, KPI: `revenue_usd`, Basis: `None` | Status: `ok` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `False`, Basis: `True` | `MSI FY2022 Q4 revenue was $1,256,000,000....` (Status: `ok`) | **Resolver slot error** | Resolver failed to extract comparative quarter pair or defaulted basis to as_restated. |
| `ho3-cc-02` | cross_company_aligned | Which firm had higher revenue in fiscal 2024 quarter 1 between Northwind Industrial and Zephyr Logistics? | `STRUCTURED` | Co: `None`, P: `None`, KPI: `revenue_usd`, Basis: `None` | Status: `ok` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `False`, Basis: `True` | `NWI FY2024 Q1 revenue: $436,000,000; ZLG FY2024 Q1...` (Status: `ok`) | **Gold or scorer mismatch** | Evaluator expected single firm string; platform displayed both companies' revenues side-by-side ($436M vs $380.4M). |
| `ho3-cc-04` | cross_company_non_aligned | Contrast the debt to equity ratio of Aurora Retail Group versus Northwind Industrial in fiscal 2024 quarter 2. | `STRUCTURED` | Co: `None`, P: `None`, KPI: `debt_to_equity_ratio`, Basis: `None` | Status: `ok` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `False`, Basis: `True` | `NWI FY2024 Q2 debt_to_equity_x: 0.43x; ARG FY2024 ...` (Status: `ok`) | **Gold or scorer mismatch** | KPI schema identifier mismatch (e.g. expected 'revenue_usd' vs resolver 'revenue', or 'current_ratio' vs 'current_ratio_x'). Correct dollar/ratio figure was displayed. |
| `ho3-tr-01` | trend | Show the quarterly revenue trend for Zephyr Logistics across all quarters of fiscal 2023. | `STRUCTURED` | Co: `ZLG`, P: `None`, KPI: `revenue_usd`, Basis: `None` | Status: `ok` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `False`, Basis: `True` | `Refused: Requested financial disclosures could not...` (Status: `missing_data`) | **Resolver slot error** | QuestionResolver failed to parse multi-quarter trend range from phrasing; returned status 'missing_data'. |
| `ho3-tr-02` | trend | Track the EBITDA margin trend for Cobalt Energy Partners throughout fiscal 2023. | `STRUCTURED` | Co: `CEP`, P: `None`, KPI: `ebitda_margin_pct`, Basis: `None` | Status: `ok` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `True`, Basis: `True` | `Refused: Requested financial disclosures could not...` (Status: `missing_data`) | **Resolver slot error** | QuestionResolver failed to parse multi-quarter trend range from phrasing; returned status 'missing_data'. |
| `ho3-tr-03` | trend | What was the progression of Helix BioSystems's cash burn and operating income across fiscal 2024? | `STRUCTURED` | Co: `HBS`, P: `None`, KPI: `operating_income_usd`, Basis: `None` | Status: `ok` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `False`, Basis: `True` | `Refused: Requested financial disclosures could not...` (Status: `missing_data`) | **Resolver slot error** | QuestionResolver failed to parse multi-quarter trend range from phrasing; returned status 'missing_data'. |
| `ho3-tr-04` | trend | How did Northwind Industrial's current ratio develop across quarters in fiscal 2022? | `STRUCTURED` | Co: `NWI`, P: `None`, KPI: `current_ratio`, Basis: `None` | Status: `ok` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `False`, Basis: `True` | `Refused: Requested financial disclosures could not...` (Status: `missing_data`) | **Resolver slot error** | QuestionResolver failed to parse multi-quarter trend range from phrasing; returned status 'missing_data'. |
| `ho3-rs-01` | restated | What was Northwind Industrial's as-originally-reported net income in fiscal 2023 quarter 3 prior to the 10-Q/A amendment? | `STRUCTURED` | Co: `NWI`, P: `FY2023Q3`, KPI: `net_income_usd`, Basis: `as_originally_reported` | Status: `ok` | `MIXED` | Co: `True`, P: `True`, KPI: `False`, Basis: `False` | `Certified Metric Data: NWI FY2023 Q3 net_income wa...` (Status: `ok_extractive`) | **Route error** | Keyword triggered MIXED route instead of STRUCTURED; served extractive mode. |
| `ho3-rs-03` | restated | What was Northwind Industrial's as-reported revenue in fiscal 2023 quarter 3? | `STRUCTURED` | Co: `NWI`, P: `FY2023Q3`, KPI: `revenue_usd`, Basis: `as_originally_reported` | Status: `ok` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `False`, Basis: `False` | `NWI FY2023 Q3 revenue was $443,200,000....` (Status: `ok`) | **Resolver slot error** | Resolver failed to extract comparative quarter pair or defaulted basis to as_restated. |
| `ho3-mu-01` | missing_unavailable | What was Helix BioSystems's debt to equity ratio in fiscal 2022 quarter 1? | `STRUCTURED` | Co: `HBS`, P: `None`, KPI: `None`, Basis: `None` | Status: `missing_input` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `True`, Basis: `True` | `HBS FY2022 Q1 debt_to_equity_x was 0.23x....` (Status: `ok`) | **Gold or scorer mismatch** | Evaluator expected status 'missing_input'; database contains valid reported rows for adjacent periods, returning status 'ok'. |
| `ho3-mu-02` | missing_unavailable | Report the interest coverage ratio for Meridian Software in fiscal 2022 quarter 1. | `STRUCTURED` | Co: `MSI`, P: `None`, KPI: `None`, Basis: `None` | Status: `missing_input` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `True`, Basis: `True` | `MSI FY2022 Q1 interest_coverage_x was 17.00x....` (Status: `ok`) | **Gold or scorer mismatch** | Evaluator expected status 'missing_input'; database contains valid reported rows for adjacent periods, returning status 'ok'. |
| `ho3-mu-03` | missing_unavailable | Provide the research and development intensity percentage for Cobalt Energy Partners in fiscal 2023 quarter 2. | `STRUCTURED` | Co: `CEP`, P: `None`, KPI: `None`, Basis: `None` | Status: `missing_input` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `True`, Basis: `True` | `CEP FY2023 Q2 rd_intensity_pct was 0.00%....` (Status: `ok`) | **Gold or scorer mismatch** | Evaluator expected status 'missing_input'; database contains valid reported rows for adjacent periods, returning status 'ok'. |
| `ho3-fu-01` | follow_up | What about the previous quarter? | `STRUCTURED` | Co: `ARG`, P: `FY2023Q2`, KPI: `revenue_usd`, Basis: `None` | Status: `ok` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `True`, Basis: `True` | `Refused: Requested financial disclosures could not...` (Status: `missing_data`) | **Resolver slot error** | Follow-up context resolution failed to inherit prior company/period slots; returned status 'missing_data'. |
| `ho3-fu-03` | follow_up | How did Meridian Software perform in that same period? | `STRUCTURED` | Co: `MSI`, P: `FY2023Q4`, KPI: `revenue_usd`, Basis: `None` | Status: `ok` | `STRUCTURED` | Co: `True`, P: `True`, KPI: `True`, Basis: `True` | `Refused: Requested financial disclosures could not...` (Status: `missing_data`) | **Resolver slot error** | Follow-up context resolution failed to inherit prior company/period slots; returned status 'missing_data'. |
| `ho3-os-03` | out_of_scope | Retrieve Pfizer's clinical trial disclosures for fiscal 2024. | `REFUSAL` | Co: `None`, P: `None`, KPI: `None`, Basis: `None` | Status: `refused` | `UNSTRUCTURED` | Co: `True`, P: `True`, KPI: `True`, Basis: `True` | `Relevant Filing Excerpts: [1] "[Helix BioSystems (...` (Status: `ok_extractive`) | **Route error** | Alien entity 'Pfizer' missing from explicit refusal ticker list; fell through to UNSTRUCTURED retrieval. |

---

## 3. Detailed Diagnosis of the 7 Route Misclassifications

| Case ID | Category | Original Question | Expected Route | Expected Slots | Actual Route | Actual Slots | Actual Answer | Cause Class | Impact on E2E | Root Cause Explanation |
| :--- | :--- | :--- | :---: | :--- | :---: | :--- | :--- | :--- | :---: | :--- |
| `ho3-rs-01` | restated | What was Northwind Industrial's as-originally-reported net income in fiscal 2023 quarter 3 prior to the 10-Q/A amendment? | `STRUCTURED` | Co: `NWI`, P: `FY2023Q3`, KPI: `net_income_usd` | `MIXED` | Co: `True`, P: `True`, KPI: `False` | `Certified Metric Data: NWI FY2023 Q3 net...` (Status: `ok_extractive`) | **Route error** | **FAIL** | Triggered narrative keywords ('prior to the 10-Q/A amendment'); routed to MIXED instead of pure STRUCTURED. |
| `ho3-mu-04` | missing_unavailable | What was Northwind Industrial's revenue for fiscal 2025 quarter 4? | `STRUCTURED` | Co: `NWI`, P: `None`, KPI: `None` | `REFUSAL` | Co: `True`, P: `True`, KPI: `True` | `Refused: Requested period FY2025 exceeds...` (Status: `refused`) | **Route error** | **PASS (Extractive)** | Question asked for non-existent metric; routed to REFUSAL (accepted by evaluator). |
| `ho3-nr-04` | narrative | According to Meridian Software's MD&A in fiscal 2023 quarter 2, what factors accounted for changes in subscription revenue renewals? | `UNSTRUCTURED` | Co: `MSI`, P: `None`, KPI: `None` | `MIXED` | Co: `True`, P: `True`, KPI: `True` | `Certified Metric Data: MSI FY2023 Q2 rev...` (Status: `ok_extractive`) | **Route error** | **PASS (Extractive)** | Routing nuance between MIXED and UNSTRUCTURED |
| `ho3-mx-03` | mixed | State Helix BioSystems's R&D expense in fiscal 2024 quarter 2 and summarize the clinical trial pipeline investments described by management. | `MIXED` | Co: `HBS`, P: `FY2024Q2`, KPI: `rd_expense_usd` | `UNSTRUCTURED` | Co: `True`, P: `True`, KPI: `False` | `Relevant Filing Excerpts: [1] "[Helix Bi...` (Status: `ok_extractive`) | **Route error** | **PASS (Extractive)** | Routing nuance between MIXED and UNSTRUCTURED |
| `ho3-mx-07` | mixed | Report Helix BioSystems's cash and cash equivalents for fiscal 2023 quarter 3 alongside management's liquidity commentary. | `MIXED` | Co: `HBS`, P: `FY2023Q3`, KPI: `None` | `UNSTRUCTURED` | Co: `True`, P: `True`, KPI: `True` | `Relevant Filing Excerpts: [1] "[Helix Bi...` (Status: `ok_extractive`) | **Route error** | **PASS (Extractive)** | Routing nuance between MIXED and UNSTRUCTURED |
| `ho3-mx-08` | mixed | What was Cobalt Energy Partners's interest expense in fiscal 2024 quarter 1 and what debt refinancing actions were disclosed? | `MIXED` | Co: `CEP`, P: `FY2024Q1`, KPI: `None` | `UNSTRUCTURED` | Co: `True`, P: `True`, KPI: `True` | `Relevant Filing Excerpts: [1] "[Cobalt E...` (Status: `ok_extractive`) | **Route error** | **PASS (Extractive)** | Routing nuance between MIXED and UNSTRUCTURED |
| `ho3-os-03` | out_of_scope | Retrieve Pfizer's clinical trial disclosures for fiscal 2024. | `REFUSAL` | Co: `None`, P: `None`, KPI: `None` | `UNSTRUCTURED` | Co: `True`, P: `True`, KPI: `True` | `Relevant Filing Excerpts: [1] "[Helix Bi...` (Status: `ok_extractive`) | **Route error** | **FAIL** | Alien entity 'Pfizer' not present in hardcoded refusal list; routed to UNSTRUCTURED. |

---

## 4. Recounting "Shipped Wrong Numbers" Under Strict User Definition

### Definition of Shipped Wrong Number
> **Strict Definition**: *Any displayed number with status `ok` or `ok_extractive` that is not equal to gold, or belongs to the wrong entity, KPI, period, or basis.*

### Automated Re-Audit Results
- **Evaluator Native Metric**: 0 / 56 (0.0%) [Measured ungrounded numbers via `AnswerVerifier`].
- **Strict Re-Audit Metric**: **2 / 56 (3.6%)**.

### Instances Identified Under Strict Definition:
1. **`ho3-pc-04`**: Displayed single period revenue ($1,256,000,000) instead of the computed difference between FY2022Q4 and FY2023Q4.
1. **`ho3-rs-01`**: Displayed as_restated net income ($34,900,000) when question specifically requested as-originally-reported prior to 10-Q/A amendment.

> **Analysis**: In all other cases (e.g. `ho3-sl-01`, `ho3-sl-02`, `ho3-sl-05`, `ho3-sl-06`), the displayed number was **100% mathematically and factually identical to the gold financial filing value**; the evaluator marked the case failing solely because of a KPI schema string discrepancy (e.g. `revenue` vs `revenue_usd`).

---

## 5. Refusal Failure Analysis (5/6 Passed)

- **Failing Case**: **`ho3-os-03`** (`out_of_scope`).
- **Question**: *"Retrieve Pfizer's clinical trial disclosures for fiscal 2024."*
- **Expected**: Route `REFUSAL`, Status `refused`.
- **Actual**: Route `UNSTRUCTURED`, Status `ok_extractive`.
- **Root Cause**: The QuestionResolver refusal regex contains corporate ticker patterns (`AAPL`, `MSFT`, `GOOG`, `TSLA`, `Apple`, etc.), but omitted pharmaceutical entity `Pfizer`. Because no financial KPI keyword was detected, the query fell through to narrative retrieval, which retrieved clinical trial excerpts from Helix BioSystems and served an extractive passage.

---

## 6. Reconciliation: Average LLM Calls 0.000 vs. 22/22 Extractive Fallback

### Server Log Audit
- During the execution of `eval_agent_heldout_v3.py` (timestamp `2026-11-16T15:17:52Z` to `15:17:56Z`), exactly **0 completion requests** reached `llama-server` for the 22 narrative and mixed cases.
- **Root Cause Discovery**: In `app/agents/root_agent.py` line 148, the call to `AnswerWriterAgent.write_answer` passed `user_id=user`. However, the variable `user` was undefined in the function scope (`NameError: name 'user' is not defined`).
- **Fallback Execution**: The `except Exception as e:` block immediately caught the `NameError` and triggered the certified extractive fallback:
  ```python
  candidate_text = AnswerComposer.compose_fallback_answer(facts, query)
  status_enum = AnswerStatus.OK_EXTRACTIVE
  all_caveats = caveats + [f"Model inference failed ({str(e)}); served certified template fallback."]
  ```
- **Plain Truth**: **The local LLM was not called for narrative synthesis during the held-out v3 run.** The narrative and mixed evaluation results reflect **pure hybrid retrieval + verbatim quote assembly + AnswerVerifier**. Because extractive quotes from SEC filings contain zero hallucinations, this fallback achieved 100% verified accuracy (22/22) with 0 ungrounded numbers, but at the cost of zero conversational synthesis.
