# ASSUMPTIONS.md: Platform Assumptions & Risk Analysis

> **Platform**: CFO Copilot on a Budget  
> **Phase**: Phase 0 Baseline  
> **Status**: Approved for Phase 0  

This document outlines all core architectural, financial, and operational assumptions for the platform. Each entry is numbered, states the underlying rationale, and documents how the assumption could be invalid or compromised.

---

### 1. Whitespace Tokens as Cache Metric Proxy
- **Assumption**: Prompt token counts and prefix cache block alignments in `request_log.csv` are measured in whitespace-delimited tokens (words) rather than specific BPE subword tokenizer tokens.
- **Reason**: The reference specification in `reference_hardware_and_model.csv` explicitly notes: `"token_counts_in_request_log: whitespace tokens, Approximation, not a model tokenizer"`. Furthermore, our exact reconstruction confirmed that `len(text.split()) == prompt_tokens` with 0 mismatches across all 220 requests.
- **How It Could Be Wrong**: A real serving engine (like `llama.cpp` or `vLLM`) evaluates KV cache blocks over model-specific BPE tokens (e.g. TikToken or Qwen tokenizer). In real inference, 1 whitespace word often maps to $1.2 - 1.4$ BPE tokens, and punctuation splits into separate tokens. Block boundary alignment ($B = 16$) in production may slightly differ from whitespace boundaries.

---

### 2. Hardware Path & Stated CPU Fallback
- **Assumption**: The platform must report reproducible benchmark numbers against a CPU-only fallback, while offering native Apple Silicon Metal acceleration for local interactive CFO demonstrations.
- **Reason**: The host environment is an Apple Silicon M4 Mac (16 GB unified RAM, 10 CPU cores) with no NVIDIA GPU (`nvidia-smi` not found). Furthermore, Docker Desktop on macOS runs within a Linux VM that cannot access Apple Metal GPU acceleration. The assignment explicitly allows a stated CPU-only fallback (`"a CPU-only fallback is allowed but I must state real numbers"`).
- **How It Could Be Wrong**: If the assignment evaluators strictly mandate running on an NVIDIA GPU (e.g., an AWS `g4dn.xlarge` instance with a T4 GPU), CPU-only measurements will report lower generation tokens/s and higher TTFT, failing the $< 2.0\text{ s}$ TTFT SLA under 16 concurrent users unless heavy KV quantization and caching are engaged.

---

### 3. Multi-Tenant Isolation Model (Tenant A and Tenant B)
- **Assumption**: The system serves two completely isolated corporate tenants (e.g., `acme` and `borealis`), sharing the common LLM serving infrastructure and base platform knowledge (KPI glossary, system guardrails, tool schemas), but with strict cryptographic and relational data isolation.
- **Reason**: Foundation Lock 6 mandates: `"two tenants, no cross-tenant cache/context leakage; LLM never holds DB credentials; SQL role read-only"`. The request log demonstrates concurrent traffic from `acme` and `borealis`.
- **How It Could Be Wrong**: If tenants share proprietary financial figures or have custom KPI glossary formulas, a global static prefix cache could inadvertently leak corporate metadata across tenants. We mitigate this by ensuring that the globally cached prefix contains strictly generic financial rules, while all tenant-specific data appears downstream after the tenant barrier.

---

### 4. Drop 1 vs. Drop 2 Authority & Ingestion Event Model
- **Assumption**: Drop 1 (`CANDIDATE_PACK`) serves as the immutable historical baseline (Companies 1–5, FY2022–FY2024), while Drop 2 (`DROP2_RELEASE`) represents a subsequent **data ingestion event** adding Company 6 (`ZLG`) and filing amendment `NWI-10QA-FY2024Q3`. It is not a schema migration; the schema created in Phase 1 structurally supports both drops.
- **Reason**: `README_DROP2.md` states: `"Zephyr Logistics Ltd. (ZLG) joins the CFO's coverage list... Add it through a proper schema migration, not by editing tables by hand... the document NWI-10QA-FY2024Q3... amend[s] a quarter already in your database."` Adding rows to existing tables is an idempotent data ingestion process.
- **How It Could Be Wrong**: If Drop 2 was intended to replace Drop 1 entirely, retaining Drop 1 rows would result in redundant or obsolete tables. Our data audit proved Drop 2 only provides 1 new company and 1 amendment; discarding Drop 1 would destroy 90% of the financial dataset.

---

### 5. Amendment Precedence & Audit Provenance (Puzzle 1 Policy)
- **Assumption**: Form 10-Q/A (`NWI-10QA-FY2024Q3`, `CEP-10QA-FY2024Q2`) legally supersedes original Form 10-Q line items for KPI calculations, but the original rows remain immutably stored in the database with `is_superseded = TRUE` and full audit trails.
- **Reason**: In financial reporting, superseded filings must never be permanently deleted from database tables. An audit trail is mandatory for CFO live defense.
- **How It Could Be Wrong**: A CFO querying `"What did Northwind originally report for Q3 2024 before the distributor shipment restatement?"` requires access to the unamended figures. If the database blindly overwrites the rows, historical forensic questions cannot be answered.

---

### 6. Automated Correction of HBS FY2024Q2 Unit Scale Bug
- **Assumption**: The 11 rows in `HBS-10Q-FY2024Q2` marked `USD_millions` in `financial_statements_raw.csv` are an extraction tool artifact and must be normalized to `USD_thousands` during ingestion, cross-referencing `filings_index.csv`.
- **Reason**: In `filings_index.csv`, `HBS-10Q-FY2024Q2` has `reporting_unit = USD_thousands`. In adjacent quarters, HBS revenue is ~100,000 thousand USD ($100M). Treating this quarter as millions yields $109.2 Billion (a 1,000x error for a mid-size life-sciences company).
- **How It Could Be Wrong**: If the vendor data pack intended for the platform to reject the entire filing or flag it as `LOW_CONFIDENCE` rather than auto-correcting it, modifying the unit without human review could violate strict data integrity rules. We will log a high-severity ingestion adjustment trace whenever a raw unit contradicts the filing index.

---

### 7. Inverted Expense Sign Standardization (CEP Sign Convention)
- **Assumption**: All financial statements must be staged into canonical sign conventions upon database ingestion: Revenues are positive, Expenses/COGS are positive values in storage, and Net Income reflects `Revenues - Expenses`.
- **Reason**: In `financial_statements_raw.csv`, company `CEP` stores expenses as negative numbers (`Cost of revenues = -179,200,000`), while all other companies store expenses as positive numbers. Calculating margins across companies requires an invariant sign convention.
- **How It Could Be Wrong**: If certain lines represent net credit adjustments or negative expense accruals (e.g. warranty accrual roll-offs), forcing `ABS(value)` could accidentally invert a legitimate negative credit into an expense.

---

### 8. Free Cash Flow Capex Outflow Calculation
- **Assumption**: Free Cash Flow is calculated as:
  $$\text{Free Cash Flow} = \text{Cash from Operations} - |\text{Purchases of Property and Equipment}|$$
- **Reason**: In `kpi_glossary.csv`, the formula is `cash_from_operations - capital_expenditures`, accompanied by the explicit note: `"Capex taken as a positive outflow amount"`. In raw cash flow statements, Capex is reported as a negative cash outflow.
- **How It Could Be Wrong**: If a company sells property/plant/equipment during a quarter and reports positive net proceeds under capex, taking the absolute value would incorrectly treat asset sales as capital expenditures.

---

### 9. R&D and Exploration Expense Classification
- **Assumption**: For companies without a dedicated `Research and development` line item:
  - For `ARG` (`Technology and development = 0.0`), `rd_intensity_pct` is `0.0%`.
  - For `CEP` (`Exploration expense`), `rd_intensity_pct` returns `0.0%` by default, but exploration expense is included in operating expenses.
  - For `ZLG` (`Technology expense`), `Technology expense` is mapped to R&D intensity with an explicit provenance note.
- **Reason**: Industry-specific accounting standards treat exploration expenses in energy midstream (CEP) differently from software/pharma R&D.
- **How It Could Be Wrong**: If the assignment golden evaluation set expects `Exploration expense` to be classified as R&D for energy companies, the calculated R&D intensity and Opex ratio would diverge from the test suite.

---

### 10. Non-Standard Fiscal Year Alignment for Peer Benchmarking
- **Assumption**: When a CFO requests comparative cross-company benchmarks (e.g. `"Compare Q3 2023 operating margins across all companies"`), queries must align on fiscal quarter identifiers (`fiscal_year = 2023, fiscal_quarter = 3`), but explicitly disclose the calendar period end date in the answer.
- **Reason**: HBS designates fiscal years by calendar year of beginning (July 1), whereas NWI, CEP, and MSI follow calendar years, and ARG follows a retail calendar.
- **How It Could Be Wrong**: A user asking about calendar Q3 2023 expects operations between July 1 and September 30, 2023. For HBS, fiscal Q1 2023 covers July–September 2023, NOT fiscal Q3. Without date-based reconciliation, peer comparisons compare non-overlapping operational quarters.

---

### 11. Multi-Tenant Engine Isolation via PostgreSQL RLS
- **Assumption**: PostgreSQL Row-Level Security (RLS) with `FORCE ROW LEVEL SECURITY` and `current_setting('app.current_tenant', true)` satisfies Foundation Lock 6's requirement that two tenants cannot see or leak each other's session contexts or chat history.
- **Reason**: Tested and confirmed via `tests/integration/test_phase1_integration.py::TestTenantIsolationRLS`, where an automated canary string written under tenant `acme` is completely invisible to tenant `borealis` (`count == 0`), and cross-tenant insertions are rejected at the database engine level.
- **How It Could Be Wrong**: If an application database connection executes queries without calling `SET app.current_tenant = ...`, or if superuser/owner roles are accidentally used for user queries, RLS policies could be bypassed. To prevent this, all application queries must set tenant context upon acquiring a connection from the pool.

---

### 12. Complete Segregation of Credentials (Lock 6)
- **Assumption**: The LLM agent and tool execution layer can safely execute read-only queries by being permanently restricted to database role `app_ro`.
- **Reason**: Foundation Lock 6 specifies `"LLM never holds DB credentials; SQL role read-only"`. By maintaining three distinct database roles (`cfo_owner`, `app_rw`, `app_ro`), the inference layer only receives an `app_ro` connection string that lacks `INSERT`, `UPDATE`, `DELETE`, or DDL permissions.
- **How It Could Be Wrong**: A read-only role can still be subjected to Denial-of-Service (DoS) queries (e.g. Cartesian joins or recursive CTEs). In Phase 2, statement timeouts (`statement_timeout = '3000ms'`) and result row limits (`LIMIT 50`) will be added to prevent compute exhaustion.



---

### 13. Pure SQL KPI Engine Execution (Foundation Lock 2)
- **Assumption**: All 16 KPIs must be computed in pure, deterministic SQL without Python business logic or LLM arithmetic.
- **Reason**: Foundation Lock 2 mandates strict layering: the agent layer contains NO SQL strings and NO business rules. Precomputing and versioning all 16 KPIs in `kpi_values` guarantees that financial answers are deterministic, reproducible, and immune to prompt injection or model hallucination.
- **How It Could Be Wrong**: If a KPI requires subjective non-GAAP adjustments or bespoke segment allocations not defined in `kpi_glossary.csv`, pure SQL cannot infer analyst judgment. We strictly follow `kpi_glossary.csv` with zero ad-hoc addbacks.

---

### 14. Economic Domain Boundary Gating (Rule R8)
- **Assumption**: If `total_equity <= 0`, Return on Equity and Debt-to-Equity ratios are economically non-meaningful and must output `status = 'not_meaningful'` rather than an arithmetic quotient.
- **Reason**: Negative book equity produces a positive ROE when net income is negative (loss / negative equity = positive percentage), falsely signaling profitability to an executive. In corporate credit analysis, debt-to-negative-equity is undefined.
- **How It Could Be Wrong**: Some quant models report bare negative ratios with footnotes; our conflict policy requires explicit `not_meaningful` status to avoid misleading the CFO.

---

### 15. Comparative Column Prior-Period Restatement Authority (Rule R3)
- **Assumption**: When a newer SEC filing includes comparative prior-period columns whose values diverge from the original filing, the newer comparative value represents an official restatement or reclassification and governs `as_restated`.
- **Reason**: SEC reporting rules mandate that comparative columns incorporate any retrospective adjustments adopted in subsequent periods (e.g. NWI Footnote 2 tax accrual adjustment in FY2024 Q3 restating FY2023 Q3 net income).
- **How It Could Be Wrong**: If comparative columns contain typographical errors by the filer, adopting them without human review could introduce noise. We record all discrepancies in `data_quality_issues`.
