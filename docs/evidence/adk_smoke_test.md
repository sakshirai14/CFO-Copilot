# Google ADK / LiteLLM Tool-Calling Smoke Test Report

- **Evaluated**: 2026-11-15 18:33:32Z
- **Model**: `openai/qwen2.5-3b-instruct` via `llama-server` (port 8080)
- **Total Test Queries**: 32 (6 functional categories)
- **Tools Registered**: `get_kpi_value`, `search_filings`, `get_kpi_definition`, `calculator`

## 1. Overall Performance Metrics (with Wilson 95% CIs)

| Metric | Performance Rate | 95% Wilson CI | Target |
| :--- | :---: | :---: | :--- |
| **Tool-Selection Accuracy** | **96.9%** | `96.9% [84.3%, 99.4%] (k=31, n=32)` | $\ge 90.0\%$ |
| **Argument Accuracy** | **79.4%** | `79.4% [63.2%, 89.7%] (k=27, n=34)` | $\ge 90.0\%$ |
| **Extra-Call Rate** | **3.1%** | `3.1% [0.6%, 15.7%] (k=1, n=32)` | $\le 10.0\%$ |
| **Missing-Call Rate** | **0.0%** | `0.0% [0.0%, 10.7%] (k=0, n=32)` | $\le 10.0\%$ |

## 2. Category-by-Category Results

| ID | Category | Query | Expected Tools | Actual Tools Called | Tool Match | Args Match | Latency |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `kpi-01` | direct_kpi | What was Helix Biosystems's revenue in fiscal 2024 quarter 2? | `['get_kpi_value']` | `['get_kpi_value']` | ✅ | ❌ | 14297 ms |
| `kpi-02` | direct_kpi | Get the operating margin for Cobalt Energy Partners in fiscal 2023 quarter 1. | `['get_kpi_value']` | `['get_kpi_value']` | ✅ | ✅ | 18646 ms |
| `kpi-03` | direct_kpi | What was Aurora Retail Group net income in FY2024 Q1? | `['get_kpi_value']` | `['get_kpi_value']` | ✅ | ❌ | 2764 ms |
| `kpi-04` | direct_kpi | Can you check Northwind's gross profit in fiscal 2024 quarter 3? | `['get_kpi_value']` | `['get_kpi_value']` | ✅ | ❌ | 2590 ms |
| `kpi-05` | direct_kpi | Look up MSI current ratio for FY2022 Q4. | `['get_kpi_value']` | `['get_kpi_value']` | ✅ | ✅ | 3009 ms |
| `kpi-06` | direct_kpi | What was Zephyr Logistics operating cash flow in FY2023 Q2? | `['get_kpi_value']` | `['get_kpi_value']` | ✅ | ❌ | 2890 ms |
| `kpi-07` | direct_kpi | Find HBS free cash flow in fiscal 2024 quarter 1. | `['get_kpi_value']` | `['get_kpi_value']` | ✅ | ❌ | 2816 ms |
| `kpi-08` | direct_kpi | What was CEP debt to equity in FY2023 Q3? | `['get_kpi_value']` | `['get_kpi_value']` | ✅ | ✅ | 2962 ms |
| `qual-01` | qualitative | What did Northwind disclose in Note 7 about revenue recognition accounting changes? | `['search_filings']` | `['search_filings']` | ✅ | ✅ | 2281 ms |
| `qual-02` | qualitative | Search the filings for any mention of pending litigation against Aurora Retail Group. | `['search_filings']` | `['search_filings']` | ✅ | ✅ | 1796 ms |
| `qual-03` | qualitative | Find the MD&A explanation for why Cobalt Energy's gross margin dropped in 2023. | `['search_filings']` | `['search_filings']` | ✅ | ❌ | 2218 ms |
| `qual-04` | qualitative | Did Helix Biosystems mention any patent expiration risks in their latest 10-K? | `['search_filings']` | `['search_filings']` | ✅ | ✅ | 2308 ms |
| `qual-05` | qualitative | Search filings for Zephyr Logistics diesel fuel hedging contracts in 2023. | `['search_filings']` | `['search_filings']` | ✅ | ✅ | 2611 ms |
| `qual-06` | qualitative | Find disclosures regarding restatement of prior period financial statements for NWI. | `['search_filings']` | `['search_filings']` | ✅ | ❌ | 2137 ms |
| `def-01` | definition | How is operating margin percentage calculated under our conflict policy? | `['get_kpi_definition']` | `['get_kpi_definition']` | ✅ | ✅ | 1385 ms |
| `def-02` | definition | What is the official definition and formula for current_ratio? | `['get_kpi_definition']` | `['get_kpi_definition']` | ✅ | ✅ | 1592 ms |
| `def-03` | definition | Explain the policy for EBITDA when depreciation and amortization is not reported. | `['get_kpi_definition']` | `['get_kpi_definition']` | ✅ | ✅ | 4398 ms |
| `def-04` | definition | Show me the definition and formula for free_cash_flow. | `['get_kpi_definition']` | `['get_kpi_definition']` | ✅ | ✅ | 1628 ms |
| `def-05` | definition | What components are required to compute debt_to_equity ratio? | `['get_kpi_definition']` | `['get_kpi_definition']` | ✅ | ✅ | 1590 ms |
| `comp-01` | compound | Calculate the revenue growth percentage for HBS between FY2023 Q2 and FY2024 Q2. | `['get_kpi_value', 'calculator']` | `['get_kpi_value', 'get_kpi_value', 'calculator']` | ✅ | ✅ | 7220 ms |
| `comp-02` | compound | Compare the operating margin of CEP and ARG for fiscal 2023 quarter 3. | `['get_kpi_value']` | `['get_kpi_value', 'get_kpi_value']` | ✅ | ✅ | 5302 ms |
| `comp-03` | compound | What was the difference in net income between NWI and MSI in FY2024 Q1? | `['get_kpi_value']` | `['get_kpi_value', 'get_kpi_value', 'calculator', 'get_kpi_value']` | ✅ | ✅ | 7603 ms |
| `comp-04` | compound | Compute the sum of operating cash flow for all quarters of FY2023 for ZLG. | `['get_kpi_value', 'calculator']` | `['get_kpi_value', 'get_kpi_value', 'get_kpi_value']` | ✅ | ✅ | 7237 ms |
| `comp-05` | compound | Get HBS revenue for FY2024 Q2 and multiply it by 1.15 to project next quarter. | `['get_kpi_value', 'calculator']` | `['get_kpi_value', 'calculator']` | ✅ | ✅ | 4011 ms |
| `ambig-01` | ambiguous | What will happen to the stock price of Tesla next month? | `[]` | `[]` | ✅ | ✅ | 5333 ms |
| `ambig-02` | ambiguous | Can you give me the Q3 earnings for that company? | `[]` | `[]` | ✅ | ✅ | 1974 ms |
| `ambig-03` | ambiguous | Write a python script to download SEC filings from Edgar. | `[]` | `[]` | ✅ | ✅ | 7030 ms |
| `ambig-04` | ambiguous | What is the revenue for Northwind in fiscal 2027? | `[]` | `['get_kpi_value']` | ❌ | ✅ | 2660 ms |
| `chat-01` | chitchat | Good morning CFO Copilot, how are you today? | `[]` | `[]` | ✅ | ✅ | 1400 ms |
| `chat-02` | chitchat | Hello! What are your capabilities as a financial assistant? | `[]` | `[]` | ✅ | ✅ | 2450 ms |
| `chat-03` | chitchat | Thanks, that was very helpful information. | `[]` | `[]` | ✅ | ✅ | 760 ms |
| `chat-04` | chitchat | Who built you and what model are you running? | `[]` | `[]` | ✅ | ✅ | 1645 ms |
