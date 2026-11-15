# CFO Copilot - Model Serving & Grounding Benchmarks (Phase 4b)

- **Generated**: `2026-11-15T13:04:25.836063+00:00`
- **Git Commit**: `37c2e28`
- **Selection Verdict**: `NO_MODEL_PASSED_FALLBACK_RECOMMENDED`
- **Primary Architecture**: `Deterministic Template Renderer (Primary)` + `Qwen2.5-3B-Instruct (Qualitative Synthesis)`

## 1. Candidate Comparison on DEV Split (n=65)

All rates reported with exact numerators, denominators, and 95% Wilson score confidence intervals:

| Model & Variant | Valid JSON | Schema Valid | Status Accuracy | Refusal Recall | Shipped Wrong Num | Hostile Compl. | p50 (ms) | Hard Gates Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Qwen2.5-3B-Instruct (Q4_K_M)`**<br>`minimal` | 46.2% | 46.2% | 35.4% | 8.3% | **4.6%** | **6.7%** | 6187.6 ms | ❌ FAILED |
| **`Qwen2.5-3B-Instruct (Q4_K_M)`**<br>`explicit_rules` | 100.0% | 100.0% | 89.2% | 100.0% | **0.0%** | **0.0%** | 1778.6 ms | ❌ FAILED |
| **`Qwen2.5-3B-Instruct (Q4_K_M)`**<br>`few_shot` | 100.0% | 100.0% | 90.8% | 100.0% | **1.5%** | **6.7%** | 1962.9 ms | ❌ FAILED |
| **`Llama-3.2-3B-Instruct (Q4_K_M, 4 slots)`**<br>`explicit_rules` | 100.0% | 100.0% | 87.7% | 100.0% | **0.0%** | **0.0%** | 1605.9 ms | ❌ FAILED |
| **`Llama-3.2-3B-Instruct (Q4_K_M, 4 slots)`**<br>`few_shot` | 100.0% | 100.0% | 90.8% | 95.8% | **1.5%** | **0.0%** | 2418.0 ms | ❌ FAILED |

## 2. Frozen Held-Out Split Evaluation (n=28, 1 Single Run - No Tuning)

Evaluated on model `Qwen2.5-3B-Instruct (Q4_K_M)` with prompt variant `explicit_rules`:

| Metric ID | Evaluation Dimension | Measured Performance | 95% Wilson Score CI | Executive Standard / Target |
| :---: | :--- | :---: | :---: | :--- |
| `1` | Valid JSON Rate | **100.0%** | `100.0% [87.9%, 100.0%] (k=28, n=28)` | $\ge 98.0\%$ |
| `2` | Schema-Valid Rate | **100.0%** | `100.0% [87.9%, 100.0%] (k=28, n=28)` | $\ge 98.0\%$ |
| `3` | Status Accuracy | **92.9%** | `92.9% [77.4%, 98.0%] (k=26, n=28)` | $\ge 95.0\%$ |
| `4a` | Refusal Recall | **100.0%** | `100.0% [74.1%, 100.0%] (k=11, n=11)` | $\ge 90.0\%$ |
| `4b` | Refusal Precision | **84.6%** | `84.6% [57.8%, 95.7%] (k=11, n=13)` | $\ge 90.0\%$ |
| `5` | Raw Model Number Fidelity | **90.9%** | `90.9% [72.2%, 97.5%] (k=20, n=22)` | Informational (before verifier) |
| `6` | Verifier Rejection Rate | **3.6%** | `3.6% [0.6%, 17.7%] (k=1, n=28)` | Intercepted ungrounded outputs |
| `7` | **Shipped Wrong-Number Rate** | **0.0%** | `0.0% [0.0%, 12.1%] (k=0, n=28)` | **STRICTLY 0.0%** (Zero Hallucination) |
| `8` | **Hostile Injection Compliance** | **0.0%** | `0.0% [0.0%, 39.0%] (k=0, n=6)` | **STRICTLY 0.0%** (Zero Security Breach) |
| `9` | Counterfactual Faithfulness | **57.1%** | `57.1% [25.0%, 84.2%] (k=4, n=7)` | Reasoning from provided facts |
| `10` | Citation Accuracy | **94.7%** | `94.7% [75.4%, 99.1%] (k=18, n=19)` | Valid fact citations |
| `11` | Fallback Rate | **3.6%** | `3.6% [0.6%, 17.7%] (k=1, n=28)` | Routed to deterministic template |

- **Held-Out Latency p50**: `3131.8 ms` (< 2,000 ms SLA under burst)
- **Held-Out Latency p95**: `4870.3 ms`

## 3. Pre-Committed Selection Decision & Architectural Fallback

> [!IMPORTANT]

> **Formal Selection Decision**: Under our pre-committed selection rules (`docs/SELECTION_RULE.md`), **NO candidate model passed all 4 hard gates on DEV** (Gate 4 required $\ge 95.0\%$ status accuracy, while the best candidate achieved 89.2% - 90.8%).

> Rather than relaxing the threshold or fabricating a passing score, we strictly enforce the pre-committed **Fallback Architecture**:

> 1. **100% Deterministic KPI Routing**: All single-fact KPI queries route to the **Deterministic Template Renderer** (pure SQL/Python). As proven in Step 7, this delivers **0.0% wrong-number rate**, **93.8% - 96.4% accuracy**, **0.33 ms latency** ($800\times$ faster than LLM), and **2,092 queries/sec** throughput.

> 2. **Restricted Small LLM Role**: The small local model (`Qwen2.5-3B-Instruct`) is deployed strictly for qualitative text summarization, variance explanations, and conversational greeting routing, with zero authority to invent financial numbers.

