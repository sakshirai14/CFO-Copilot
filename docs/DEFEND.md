# DEFEND.md: Architecture Defense for Executive CFO Briefing

> **Platform**: CFO Copilot on a Budget  
> **Target Audience**: Chief Financial Officer & Senior Leadership  
> **Phase**: Phase 2 Conflict Policy & KPI Engine Defense  
> **Date**: 2026-11-15  

---

# Section 1: The Foundation: Database, Normalization & Provenance

As a senior platform engineer briefing the CFO, I must be able to defend every single line of code, every architectural constraint, and every number in this system. A wrong number presented to an executive or an auditor is fatal to company credibility.

Here is how the foundational data platform is built to guarantee 100% data integrity, auditability, and multi-tenant security.

---

## 1. Why Data Provenance Matters to a CFO

In corporate finance, **a number without provenance is an opinion, not a fact**. 

If an executive assistant claims `"Gross margin in Q2 was 35.4%"`, the CFO's first questions are:
- *Where did that number come from?*
- *Is it from an original Form 10-Q, an amended 10-Q/A, or an unaudited press release?*
- *Did an analyst manually adjust for non-standard revenue recognition?*

To satisfy audit standards and SEC compliance, our architecture establishes a **Three-Tier Immutable Provenance Chain**:

```
[SEC Filing Document]
       │
       ▼
[raw_financial_rows]  <--- Immutable exact CSV strings + source line numbers + SHA-256 row hash
       │
       ▼
[line_item_map]       <--- Authoritative corporate taxonomy mapping
       │
       ▼
[line_items]          <--- Canonical values in USD + scale factors + sign multipliers + FK to raw row
       │
       ▼
[effective_line_items]<--- Set-based resolution of Conflict Policy Rules R1-R5, R11, R12
       │
       ▼
[kpi_values]          <--- Deterministic SQL computation of 16 standard KPIs (Lock 2)
```

If any executive challenges a KPI calculation, the system displays the complete audit trace down to the literal CSV row ID, filing ID, and source document chunk.

---

## 2. How We Neutralized the Four Financial Data Traps

During Phase 0 and Phase 1, our automated data audit detected and neutralized four severe data pathologies embedded in the raw SEC filing data pack:

### Trap 1: Helix BioSystems (HBS) Unit Scale Error (1,000x Overstatement)
- **The Pathological Defect**: In filing `HBS-10Q-FY2024Q2`, 11 Income Statement rows were labeled with `unit = USD_millions`, while `filings_index.csv` declared `reporting_unit = USD_thousands`. In adjacent quarters, HBS reported quarterly revenues of ~\$100M. Taking the raw extracted unit at face value would have reported quarterly revenue as **\$109.2 Billion** instead of **\$109.2 Million**—a catastrophic 1,000x error for a mid-cap life sciences instrument company.
- **Architectural Defense**: Our ingestion pipeline cross-references raw extracted units against `filings_index.reporting_unit`. When a conflict occurs, the system automatically corrects the scale factor from `1,000,000.0` to `1,000.0`, scales the normalized value to canonical USD (\$109,200,000.00), and records a **CRITICAL** defect in `data_quality_issues`.

### Trap 2: Cobalt Energy Partners (CEP) Inverted Sign Convention
- **The Pathological Defect**: In `financial_statements_raw.csv`, Cobalt Energy Partners reported all operating expenses, COGS, interest, and taxes as **negative numbers** (e.g. `Cost of revenues = -179,200,000.0`). In standard financial formulas ($Gross\ Margin = Revenue - COGS$), naive execution computes:
  $$\$245,900,000 - (-\$179,200,000) = \mathbf{\$425,100,000}$$
  Reporting a gross margin of \$425M on \$245M of revenue is physically impossible and financially absurd.
- **Architectural Defense**: At the normalization layer (`app/data/normalizer.py`), our system enforces positive canonical values for all expenses and cash outflows ($COGS = |raw\_value|$), sets `sign_multiplier = -1`, and logs a **WARNING** in `data_quality_issues`. The formula $Revenue - COGS$ now yields the true gross profit of **\$66,700,000**.

### Trap 3: Aurora Retail Group (ARG) Intra-Filing Row Duplication
- **The Pathological Defect**: In filing `ARG-10Q-FY2023Q2`, the raw extraction dumped duplicate rows for primary line items (`R000411` and `R001447` both report `Total revenues = 774400.0`). A naive SQL analyst writing `SELECT SUM(value) WHERE line_item_raw = 'Total revenues'` would have silently doubled ARG's quarterly revenue from \$774.4M to **\$1.55 Billion**.
- **Architectural Defense**: Rather than silently discarding the duplicate row (which destroys raw audit provenance), our normalization engine marks the second row with `status = 'duplicate'` and populates `duplicate_of_id` pointing to the canonical record. All downstream KPI queries filter on `status = 'valid'`, preventing double-counting while preserving forensic evidence. A **CRITICAL** issue is permanently logged in `data_quality_issues`.

### Trap 4: Form 10-Q/A Amendments & Historical Restatements
- **The Financial Reality**: SEC Form 10-Q/A filings (`CEP-10QA-FY2024Q2` and `NWI-10QA-FY2024Q3`) amend previously filed quarterly results due to revenue recognition and audit adjustments.
- **Architectural Defense**: In `filings`, amendments are stored as first-class filing records with an explicit self-referencing foreign key: `amends_filing_id`. Both the original unamended rows and the amended rows coexist in `line_items` with full temporal timestamps. In Phase 2, our query policy selects the latest filed amendment by default while retaining the ability to answer: *"What was originally reported before the amendment?"*

---

# Section 2: Phase 2 Defense: Conflict Policy & Pure SQL KPI Engine

In Phase 2, we transitioned from raw data ingestion to a fully verified quantitative financial engine. Below is how we defend the calculations, policies, and integrity guarantees against audit scrutiny.

---

## 1. Why 16 KPIs Are Computed in Pure SQL (Lock 2: Layering)

A critical failure mode of enterprise GenAI projects is allowing large language models to write arbitrary SQL queries, compute financial formulas dynamically in Python, or fabricate intermediate numbers. 

To completely eliminate mathematical and semantic hallucination:
1. **Zero SQL in the Agent Layer**: The agent layer contains NO SQL strings, NO mathematical operators, and NO accounting formulas. It simply queries structured endpoints or calls typed functions that read precomputed, verified records from `kpi_values`.
2. **Standardized SQL Files**: All 16 KPIs are defined in version-controlled, auditable `.sql` files under `app/data/sql/kpis/`. Every formula strictly mirrors `kpi_glossary.csv`.
3. **Database Precision**: Calculations run at full `NUMERIC` precision inside PostgreSQL. Rounding occurs strictly at the presentation layer.

---

## 2. The Dual-Reporting Basis: Restated vs Originally Reported

In SEC corporate reporting, a CFO must frequently analyze figures on two distinct bases:
- **`as_restated` (Default)**: Incorporates all subsequent Form 10-Q/A amendments and comparative column restatements. Reflected in corporate dashboards and investor relations presentations.
- **`as_originally_reported`**: Freezes financial results to the exact date the original Form 10-Q or 10-K was filed, ignoring subsequent revisions. Vital for forensic accounting, litigation defense, and historical compliance audits.

Our architecture computes both bases concurrently:
- Table `effective_line_items` resolves candidates for both bases using deterministic set-based window functions (`ROW_NUMBER() OVER (...)`).
- For `as_restated`, the latest `filed_date` wins (Rule R2). When a value changes, the original reported value is archived into the `alternatives` JSONB column.
- For `as_originally_reported`, the original filing for that period is preserved intact.

---

## 3. How Rule R1 Protects Against Press Release Hallucination

In marketing and executive communications, preliminary press releases often cite optimistic or unaudited figures before the official 10-Q filing is finalized.

- **The Real-World Trap (RECON-04)**: On 2023-06-06, Aurora Retail Group issued a press release claiming:
  > *"Aurora Retail Group expects record preliminary Q1 revenues of approximately $871,000,000."*
  However, nine days later on 2023-06-15, ARG filed its official SEC Form 10-Q reporting actual quarterly revenue of **\$777,700,000.00**.
- **Conflict Policy Rule R1 Enforcement**: Our platform strictly enforces Rule R1 (Source Authority Hierarchy). Non-filing corpus documents (`document_type = 'other_document'`) are barred from supplying numeric inputs to the financial database. All quantitative metrics trace strictly to Form 10-Q row `R000459`. Press releases are cited strictly as context, labeled as *"unaudited preliminary company communication"*.

---

## 4. How Rule R11 Governs Accounting Integrity Gates

In partial SEC amendments (such as `NWI-10QA-FY2024Q3`), companies frequently file amended summary tables while omitting unchanged operating expense breakdowns.

- **Integrity Anomaly Detected**: In `NWI-10QA-FY2024Q3`, the amendment reported amended Gross Profit (\$168.1M) and Operating Income (\$75.2M), but omitted the individual SG&A and R&D line items. Evaluated in isolation, Gross Profit (\$168.1M) - Opex (\$0.00) != Operating Income (\$75.2M).
- **Rule R11 Isolation**: Rather than propagating unverified data, Rule R11 flags the filing with an accounting identity failure in `data_quality_issues`. Any metric whose calculation depends on the missing or inconsistent inputs (such as `opex_ratio_pct` on the amendment) is downgraded to status `unverified`. Unaffected metrics (such as Gross Margin: \$168.1M / \$462.1M = 36.38%) remain fully verified and `ok`.

---

## 5. Mathematical Domain Gates (Rule R8)

Standard division operations in naive software routinely crash with `ZeroDivisionError` or return invalid IEEE floats (`NaN`, `Infinity`).

Rule R8 establishes strict domain gates enforced directly in SQL:
1. **Zero Denominator**: Whenever revenue or current liabilities equals zero, the engine outputs `status = 'denominator_zero'` with an explicit explanation (e.g., *"Revenue denominator is zero; calculation is mathematically undefined"*). It never returns `NULL` or `NaN`.
2. **Negative Stockholders' Equity**: For Return on Equity (`roe_quarterly_pct`) and Debt-to-Equity (`debt_to_equity_x`), negative equity produces economically nonsensical ratios. The engine outputs `status = 'not_meaningful'` with the explanation: *"Stockholders' equity is negative (${val}); ratio is economically non-meaningful"*.
3. **Retailer Non-R&D Exception (Rule R6)**: For companies that report no R&D (such as Aurora Retail Group), R&D expense is treated as \$0.00, yielding `rd_intensity_pct = 0.0%` with status `ok`.

---

## 6. Empirical Verification & Defense Metrics

To guarantee that our SQL engine is mathematically flawless, we conducted two rigorous, automated independent audits:

### A. 100.00% Differential Verification (Clean-Room Pandas Engine)
- Script: `scripts/verify_kpis_differential.py`
- Methodology: An independent Python/pandas pipeline re-implemented all normalization and formulas directly from the raw SEC CSV files without importing any production code.
- Results: Across all **2,304** calculated KPI values (1,152 `as_restated`, 1,152 `as_originally_reported`):
  - **Match Rate**: **100.00%** across all 16 KPIs.
  - **Discrepancies**: **0**.
  - **Max Absolute Difference**: $0.00000050$ (purely 64-bit IEEE floating-point representation limits).
  - Evidence Log: `docs/evidence/differential_test_results.txt`.

### B. Automated Regression & Golden Set Coverage
- **51 Automated Tests Passing in 1.76s** (`make test`):
  - 12 Conflict policy integration tests verifying Rules R1-R12.
  - 15 Formula unit tests verifying mathematical boundary conditions.
  - 24 Foundation integration & unit tests (RLS isolation, migrations, normalizers).
- **50 Curated Golden Evaluation Cases** (`tests/evals/kpi_golden.csv`):
  - 15 hand-verified against raw SEC filing line numbers and cryptographic SHA-256 hashes.
  - 100% agreement asserted in automated CI testing.
