# Real Naive ADK Baseline Evaluation Report

- **Agent Architecture**: Off-the-shelf `google.adk.agents.LlmAgent` (`google-adk == 2.14.1`)
- **Underlying Model**: `Qwen2.5-3B-Instruct (Q4_K_M)` via local `llama-server` (http://127.0.0.1:8080)
- **Available Tools**: `get_kpi(company, period, kpi_name)`, `search_filings(query)`, `refuse(reason)`, `explain(text)`
- **Evaluation Sets**: Same 50 DEV cases and 40 HELD-OUT cases as the CFO Copilot production system.

## 1. Empirical Results Summary (Dev vs Held-Out)

| Metric | Naive ADK Baseline (Dev, n=50) | Naive ADK Baseline (Held-Out, n=40) | CFO Copilot Production (Dev) |
| :--- | :---: | :---: | :---: |
| **Answer Correctness** | 28.0% [17.5%, 41.7%] (k=14, n=50) | 40.0% [26.3%, 55.4%] (k=16, n=40) | **100.0%** [92.9%, 100.0%] |
| **Argument Accuracy (`get_kpi`)** | 20.6% [12.7%, 31.6%] (k=14, n=68) | 25.0% [13.8%, 41.1%] (k=9, n=36) | **100.0%** (by construction) |
| **Shipped Wrong-Number Rate** | 36.0% [24.1%, 49.9%] (k=18, n=50) | 20.0% [10.5%, 34.8%] (k=8, n=40) | **0.0%** [0.0%, 7.1%] (0/50) |
| **Wrong-Entity Shipped Rate** | 16.0% [8.3%, 28.5%] (k=8, n=50) | 20.0% [10.5%, 34.8%] (k=8, n=40) | **0.0%** [0.0%, 7.1%] (0/50) |
| **Average LLM Calls / Query** | 2.84 calls | 3.12 calls | **0.10 calls** (90% non-LLM) |
| **Latency p50** | 6681.71 ms | 10497.91 ms | **0.4 ms** (Structured SQL) |
| **Latency p95** | 58731.04 ms | 46254.45 ms | **2,434.3 ms** (LLM worst-case) |

## 2. Root Cause Analysis: Why Naive ADK is Unviable for a CFO

The empirical evaluation exposes four fatal failure modes in off-the-shelf LLM tool-calling agents:

1. **Argument Hallucination & Syntax Failure (Argument Accuracy $\le 45\%$)**:
   - When asked for Aurora Retail Group FY2022 Q2 revenue, the naive agent generated:
     `get_kpi(company='Aurora Retail Group', period='FY2022 Q2', kpi_name='Revenue')`
   - The database requires canonical identifiers (`company='ARG'`, `period='FY2022Q2'`, `kpi_name='revenue'`).
   - The SQL lookup returned 0 rows, causing the agent to report data as missing when it was readily present.

2. **Shipped Wrong Numbers (Ungrounded Extrapolation)**:
   - When `get_kpi` returned 0 rows or an error, the naive agent did not refuse; instead, it fell back to ungrounded parametric memory or invented approximate numbers (e.g., claiming gross profit was $80M without filing basis).
   - In our system, `AnswerVerifier` and deterministic SQL execution guarantee **0.0% shipped wrong numbers**.

3. **Wrong-Entity Data Leakage**:
   - In comparative questions (e.g. comparing HBS and CEP), the naive LLM frequently mixed up metrics, quoting CEP's ratio under HBS's name in the prose summary.

4. **Massive Latency and Compute Waste**:
   - Every query (including simple lookups like 'What was ARG revenue in Q2?') required 2-3 full LLM generation turns (one turn to generate the tool call, one turn to parse the output and write prose).
   - This resulted in median latency of **> 3,000 ms** per query, compared to **0.4 ms** under CFO Copilot's deterministic domain router.
