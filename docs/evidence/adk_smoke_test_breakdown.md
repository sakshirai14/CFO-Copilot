# Google ADK Smoke Test Detailed Record & Slot Analysis

## 1. Environment & Package Metadata
- **ADK Package**: `google-adk`
- **Installed Version**: `2.14.1` (`.venv/lib/python3.11/site-packages`)
- **Key Modules & Import Paths**:
  - `google.adk.agents`: `BaseAgent`, `LlmAgent`, `SequentialAgent`, `ParallelAgent`
  - `google.adk.tools`: `FunctionTool`, `ToolContext`
  - `google.adk.models`: Integration with standard OpenAI-compatible endpoints (`/v1/chat/completions`)
- **Local Model Endpoint**: `http://127.0.0.1:8080/v1`
- **Model Identifier**: `openai/qwen2.5-3b-instruct`

---

## 2. 4-Tool Smoke Test Results (32 Questions)

| Metric | Result (k/n) | Percentage | 95% Wilson Score Confidence Interval |
| :--- | :---: | :---: | :---: |
| **Tool-Selection Accuracy** | 31 / 32 | **96.9%** | [84.3%, 99.4%] |
| **Argument Accuracy** | 27 / 34 | **79.4%** | [63.2%, 89.7%] |
| **Extra-Call Rate** | 1 / 32 | **3.1%** | [0.6%, 15.7%] |
| **Missing-Call Rate** | 0 / 32 | **0.0%** | [0.0%, 10.7%] |

---

## 3. Detailed Root-Cause Analysis of the 7 Argument-Slot Errors

The model failed argument accuracy on 7 slots across the 32 questions. Every single failure fell into one of three systemic categories:

1. **Taxonomy & Synonym Mismatch (5 cases)**:
   - Case `kpi-01`: Model called `get_kpi_value(company="HBS", kpi="Total revenues")` instead of canonical `kpi="revenue"`.
   - Case `kpi-03`: Model passed `kpi="net_earnings"` instead of canonical `kpi="net_income"`.
   - Case `kpi-04`: Model passed `kpi="gross_margin_dollar"` instead of `kpi="gross_profit"`.
   - Case `kpi-06`: Model passed `kpi="operating_cash_flow"` instead of canonical `kpi="cash_from_operations"`.
   - Case `kpi-07`: Model passed `kpi="fcf"` instead of canonical `kpi="free_cash_flow_usd"`.
2. **Missing Explicit Quarter Extraction (1 case)**:
   - Case `qual-03`: Model searched filings for year 2023 but omitted fiscal quarter filter or passed `None`.
3. **Out-of-Scope Temporal Generation (1 case)**:
   - Case `ambig-04`: Query asked for Northwind in fiscal 2027. Model attempted to call `get_kpi_value(company="NWI", year=2027, quarter=1)` instead of refusing upfront.

---

## 4. Architectural Implication for Phase 5 ("Small Model, Big Agent")
These empirical results prove conclusively that **a 3B parameter open-weight model cannot be trusted to generate typed database arguments or SQL parameters**:
- It reliably determines **routing intent** (96.9% tool selection accuracy).
- But it fails schema-strict argument resolution (79.4% argument accuracy) due to financial synonym variance.

**Phase 5 Architectural Mandate**:
1. Argument resolution must be **deterministic**: `QuestionResolver` uses regex, date math, and `GLOBAL_TAXONOMY` to parse raw questions into strongly-typed `ResolvedQuery` objects.
2. The LLM is **never asked to write database parameters or SQL**.
3. The only agent in the graph with an LLM is `AnswerWriter`, which has **0 tools** and strictly writes executive prose from pre-fetched, validated facts.

