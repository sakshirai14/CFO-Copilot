# CFO Copilot Conflict & Reconciliation Policy (v1.0.0)

> **Core Principle**: A wrong number is worse than no answer. Financial figures consumed by the CFO Copilot must come from deterministic SQL, strictly sourced from authoritative SEC filings, with every number traceable to raw rows and every resolution governed by an explicit, auditable rule.

---

## 1. Governance Rules (R1 – R12)

### Rule R1: Source Authority Hierarchy
* **Filing Exclusivity**: Only official SEC filings (`10-K`, `10-Q`, and amended versions `10-K/A`, `10-Q/A`) serve as authoritative inputs for quantitative KPI computation.
* **Non-Filing Documents**: Press releases, earnings transcripts, and analyst research notes in the corpus (`document_type = 'other_document'`) are strictly contextual. They must **never** overwrite, adjust, or supply numeric inputs to financial statements or KPIs. When cited in response to user queries, they must be explicitly labeled as *"unaudited company communication, not an SEC filing"*.

### Rule R2: Restatement & Amendment Precedence
* **Chronological Precedence**: When multiple filings report data for the same company and fiscal period, the filing with the latest filing date (`filing_date`) takes precedence. Specifically, an amended filing (`10-Q/A`, `10-K/A`) supersedes the original filing (`10-Q`, `10-K`).
* **Default Reporting Basis**: The default basis for all KPI calculations is `"as_restated"`, setting `restated = true` and recording the original reported value in provenance/issue logs.
* **As-Originally-Reported Access**: The system preserves the original filing data and supports computing KPIs on an `"as_originally_reported"` basis upon explicit CFO request.

### Rule R3: Comparative Column Reconciliation
* **Corroboration vs. Revision**: SEC filings often present comparative prior-period columns alongside current-period results.
  * If a comparative column value exactly matches the original filing value for that prior period, it serves as independent corroboration.
  * If a comparative column value differs from the original filing value (e.g., retrospective revisions or reclassifications), it is treated as a restatement under **Rule R2**, adopting the newer filing's figure for `"as_restated"` queries while documenting the divergence in `data_quality_issues`.

### Rule R4: Intra-Filing Duplicate Collapse and Discrepancy Gate
* **Identical Duplicates**: If a single filing contains multiple identical rows for the same financial line item (same canonical item, statement, period, and value), the engine collapses them into a single effective line item.
* **Intra-Filing Conflicts**: If a single filing reports conflicting values for the same canonical line item within the same statement and period, neither value is blindly chosen. The effective line item is flagged with status `conflict`, and all dependent KPIs receive status `conflict`.

### Rule R5: Normalization Corrections (Dual-Evidence Standard)
* **Dual-Evidence Requirement**: Raw filing values may contain unit scale errors (e.g., reported in thousands but labeled as whole USD) or sign inversion errors. A normalization correction is applied **only** when supported by at least **two independent checks**:
  1. *Check 1 (Metadata)*: Explicit filing metadata or index conflict (e.g., `filings_index.reporting_unit` differs from raw row unit).
  2. *Check 2 (Magnitude/Cross-Statement)*: Empirical magnitude check against adjacent quarters ($0.001\times$ or $1000\times$ anomaly) or cross-statement reconciliation (e.g., cash on balance sheet matching cash on cash flow statement).
* If fewer than two independent checks support the adjustment, the raw value is preserved unadjusted and flagged as `unverified`.

### Rule R6: Missing Input Handling
* **No Imputation**: If an input required to compute a KPI is missing from the effective financial statements, the system flags the KPI with status `missing_input`.
* **Prohibition of Zero-Filling**: The system must **never** substitute zero or impute values for missing line items, with exactly one domain-specific exception:
  * *Exception (R&D Intensity)*: In accordance with standard financial convention and `kpi_glossary.csv`, if a company (e.g., a pure retailer like ARG) does not perform research and development and reports no R&D line item, R&D expense is treated as $0.00, yielding `rd_intensity_pct = 0.0%`.

### Rule R7: Comparability & Fiscal Calendar Alignment
* **Explicit Period Disclosure**: Every cross-company KPI comparison must explicitly output both the fiscal period label (e.g., `FY2024 Q3`) and the calendar period end date (e.g., `2024-09-30`).
* **Non-Aligned Calendar Flag**: If two companies' period end dates for the same fiscal quarter label differ by more than **15 days** (e.g., ZLG fiscal year ends Sept 30, whereas ARG/CEP/HBS/MSI/NWI fiscal years end Dec 31), the comparison is flagged as `non_aligned`. The assistant must explicitly warn the CFO that the operating periods cover different calendar months.
* **YoY Comparability**: Year-over-Year calculations require comparing the identical fiscal quarter of the prior year under the same reporting basis (`as_restated` vs `as_restated`).

### Rule R8: Mathematical Domain Gates (Zero Denominator & Negative Equity)
* **Zero Denominator**: If the denominator of any ratio or margin is zero, the KPI cannot be evaluated mathematically. The status is set to `denominator_zero`. It must **never** return `NULL`, infinity (`inf`), or `NaN`.
* **Negative or Zero Equity**:
  * For Return on Equity (`roe_quarterly_pct`) and Debt-to-Equity (`debt_to_equity_x`), if `total_equity <= 0`, standard financial analysis deems the ratio economically meaningless. The status is set to `not_meaningful`, accompanied by the explanation: *"Stockholders' equity is negative or zero; ratio is economically non-meaningful"*.

### Rule R9: Formula Canonicalization
* All 16 KPIs must be computed using the exact formulas defined in `kpi_glossary.csv`.
* No ad-hoc formulas, adjusted EBITDA definitions, or alternative conventions are permitted in the calculation engine.

### Rule R10: Storage Precision and Presentation Formatting
* **Database Precision**: In PostgreSQL, all financial line items, monetary values, and calculated KPIs are stored as high-precision `NUMERIC` types (e.g., `NUMERIC(24, 6)` or `NUMERIC(18, 4)`). Never use floating-point types (`FLOAT`, `DOUBLE PRECISION`) for financial amounts.
* **Rounding at Presentation Only**: Rounding occurs strictly at the presentation layer (UI/API/CLI) according to standard conventions:
  * Margins and percentages: 2 decimal places with `%` symbol (e.g., `26.76%`).
  * Ratios and multiples: 2 decimal places with `x` suffix (e.g., `1.40x`).
  * Monetary amounts: Whole US dollars with comma separators, or millions with explicit notation (e.g., `$37,800,000` or `$37.8M`).
* Every metric record must carry its explicit `unit` (`USD`, `percent`, `x`).

### Rule R11: Accounting Integrity Gate
* **Identity Verification**: Every filing is evaluated against primary GAAP accounting identities:
  1. *Balance Sheet Identity*: $\text{Total Assets} = \text{Total Liabilities} + \text{Total Stockholders' Equity}$ (tolerance: $\$1.00$).
  2. *Gross Profit Identity*: $\text{Gross Profit} = \text{Revenue} - \text{Cost of Goods Sold / Cost of Revenue}$ (tolerance: $\$1.00$).
  3. *Operating Income Identity*: $\text{Operating Income} = \text{Gross Profit} - \text{Total Operating Expenses}$ (tolerance: $\$1.00$).
* **Downgrade Gate**: If a filing fails an accounting identity check, the system logs a `CRITICAL` issue in `data_quality_issues`. Any KPI whose formula directly depends on the inconsistent line items is downgraded to status `unverified`, preventing corrupted inputs from generating authoritative output.

### Rule R12: Policy Versioning and Immutable Lineage
* Every effective line item and calculated KPI record must store `policy_version` (currently `v1.0.0`).
* Future adjustments to rules or formulas require incrementing the semantic policy version, ensuring reproducible historic runs and auditability.

---

## 2. KPI Status Reference Table

When the system cannot return an authoritative numeric value with status `ok`, it must output a structured status accompanied by a clear, human-readable CFO explanation:

| Status Code | Description | User-Facing Explanation to CFO |
| :--- | :--- | :--- |
| `ok` | Fully verified, authoritative KPI computed from valid filing rows. | *Value computed deterministically from authoritative SEC filing inputs.* |
| `missing_input` | One or more required financial line items are absent from the filing. | *"Data required to calculate this KPI ({missing_fields}) is not reported in the filing. Value cannot be computed."* |
| `conflict` | Conflicting or unresolvable values reported in the same authoritative filing. | *"Conflicting values were reported within the filing for {item_name}. Cannot determine authoritative figure."* |
| `unverified` | Normalization check failed or underlying accounting identity failed. | *"Underlying filing data failed accounting integrity verification ({reason}). Value withheld to prevent reporting erroneous data."* |
| `not_meaningful` | Economically invalid operation (e.g., negative stockholders' equity in ROE/D2E). | *"Stockholders' equity is negative (${equity_val}); ratio is economically non-meaningful."* |
| `denominator_zero` | Mathematical division by zero (e.g., zero revenue or zero liabilities). | *"Denominator ({denominator_name}) is zero; calculation is mathematically undefined."* |
| `non_aligned` | Cross-company comparison between periods differing by > 15 calendar days. | *"Warning: Company {comp_a} (period ending {date_a}) and {comp_b} (period ending {date_b}) operate on misaligned fiscal calendars (>15 days difference)."* |

---

## 3. Audited Traps $\rightarrow$ Rule $\rightarrow$ Code $\rightarrow$ Test Mapping

| Trap Identified in Data Audit | Governing Rule | Implementation in Code | Automated Verification Test |
| :--- | :--- | :--- | :--- |
| **CEP Form 10-Q/A FY2024 Q2 Restatement**<br>GP restated $81.2M $\rightarrow$ $81.7M, OI restated $41.8M $\rightarrow$ $42.3M. | **R2** (Restatement Precedence) | `app/data/effective.py`<br>Resolves effective line item from newest filing date (`10-Q/A` beats `10-Q`). Sets `basis='as_restated'`, records `restated=True`. | `test_cep_restatement_precedence()` in `tests/integration/test_conflict_policy.py` |
| **NWI Form 10-Q/A FY2024 Q3 Restatement**<br>Net income amended from $38.9M to $34.9M; omitted SG&A and R&D lines. | **R2** (Restatement Precedence) & **R11** (Integrity Gate) | `app/data/effective.py` & `app/data/kpi_calculator.py`<br>Takes amended net income ($34.9M). Flags missing opex as identity failure; downgrades `opex_ratio_pct` to `unverified`. | `test_nwi_amendment_net_income_and_opex_gate()` in `tests/integration/test_conflict_policy.py` |
| **ARG Preliminary Press Release Discrepancy**<br>Press release 2023-06-06 claimed $871M revenue; Form 10-Q filed $777.7M. | **R1** (Source Authority Hierarchy) | `app/data/ingest.py` & `app/data/effective.py`<br>`other_document` rows excluded from `financial_statements` and `effective_line_items`. | `test_press_release_never_overrides_filing()` in `tests/integration/test_conflict_policy.py` |
| **HBS Form 10-Q FY2024 Q2 Unit Anomaly**<br>11 raw rows reported in thousands ($108.4M) but raw string said `USD`. | **R5** (Dual-Evidence Normalization) | `app/data/normalizer.py`<br>Dual-evidence check: (1) `filings_index.reporting_unit` is `USD_thousands`, (2) adjacent quarters are ~$104.3M and ~$111.9M. Multiplies by 1,000. | `test_hbs_unit_dual_evidence_normalization()` in `tests/unit/test_phase1_unit.py` |
| **ARG Form 10-K FY2023 Q4 Duplicate Rows**<br>Row IDs `R000411` and `R001447` both report Operating Income $84.2M. | **R4** (Intra-Filing Duplicate Collapse) | `app/data/normalizer.py` & `app/data/effective.py`<br>Deduplicates identical rows into one effective line item. | `test_arg_duplicate_collapse()` in `tests/integration/test_phase1_integration.py` |
| **NWI Comparative Column Prior-Period Restatement**<br>FY2024 Q3 10-Q comparative column reports FY2023 Q3 Net Income of $34.9M vs originally reported $37.3M. | **R3** (Comparatives) & **R2** (Restatements) | `app/data/effective.py`<br>Recognizes comparative column as later restatement of FY2023 Q3 Net Income under `as_restated`. | `test_comparative_column_restatement_handling()` in `tests/integration/test_conflict_policy.py` |
| **Missing R&D for Aurora Retail Group**<br>ARG is a pure-play retailer reporting no R&D line item. | **R6** (Missing Input Exception) | `app/data/sql/kpis/rd_intensity_pct.sql`<br>`COALESCE(research_and_development, 0.0) / revenue * 100` yielding 0.0% instead of error. | `test_arg_rd_intensity_zero_not_missing()` in `tests/unit/test_kpi_formulas.py` |
| **ZLG Fiscal Year Alignment Misalignment**<br>ZLG fiscal year ends Sept 30; Q1 ends Dec 31, Q2 ends Mar 31, etc. | **R7** (Comparability & Fiscal Alignment) | `app/data/taxonomy.py` & `app/data/effective.py`<br>Maps Sept 30 calendar cleanly; flags comparisons with >15 day period end gaps as `non_aligned`. | `test_zlg_fiscal_calendar()` & `test_non_aligned_period_flag()` |
| **Zero Denominator / Negative Equity Edge Cases**<br>Operating income / 0 interest expense, or negative equity in ROE. | **R8** (Mathematical Domain Gates) | `app/data/sql/kpis/` SQL logic<br>`CASE WHEN total_equity <= 0 THEN 'not_meaningful' ...` and `CASE WHEN revenue = 0 THEN 'denominator_zero' ...`. | `test_kpi_formula_edge_cases()` in `tests/unit/test_kpi_formulas.py` |
| **Missing Q1-Q4 YoY Growth in FY2022**<br>First 4 quarters in dataset have no prior-year data. | **R9** & `kpi_glossary.csv`<br>YoY growth undefined for initial 4 quarters. | `app/data/sql/kpis/revenue_yoy_growth_pct.sql`<br>Outputs `status = 'missing_input'` and reason `"Prior year fiscal quarter not available in dataset"`. | `test_revenue_yoy_first_four_quarters_missing()` in `tests/unit/test_kpi_formulas.py` |
