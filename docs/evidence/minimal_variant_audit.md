# Minimal Prompt Variant Audit & Reconciliation (Phase 5b Regeneration)

## 1. Measured Performance Under Identical Server Configuration

Server Configuration: `llama-server` (Qwen2.5-3B-Instruct Q4_K_M), GBNF `STRICT_SCHEMA`, `max_tokens=512`, `presence_penalty=0.3`, `temperature=0.0`, `seed=42` on 65 DEV cases (4 parallel slots):

| Metric | Measured Result (Minimal) | 95% Wilson Score Interval |
| :--- | :---: | :--- |
| **Valid Json** | 32.3% | `32.3% [22.2%, 44.4%] (k=21, n=65)` |
| **Schema Valid** | 32.3% | `32.3% [22.2%, 44.4%] (k=21, n=65)` |
| **Status Accuracy** | 30.8% | `30.8% [20.9%, 42.8%] (k=20, n=65)` |
| **Refusal Recall** | 50.0% | `50.0% [9.5%, 90.5%] (k=1, n=2)` |
| **Refusal Precision** | 100.0% | `100.0% [20.7%, 100.0%] (k=1, n=1)` |
| **Raw Number Fidelity** | 45.5% | `45.5% [26.9%, 65.3%] (k=10, n=22)` |
| **Verifier Rejection Rate** | 16.9% | `16.9% [9.7%, 27.8%] (k=11, n=65)` |
| **Shipped Wrong Number Rate** | 0.0% | `0.0% [0.0%, 5.6%] (k=0, n=65)` |
| **Hostile Compliance Rate** | 83.3% | `83.3% [43.6%, 97.0%] (k=5, n=6)` |
| **Counterfactual Faithfulness** | 40.0% | `40.0% [11.8%, 76.9%] (k=2, n=5)` |
| **Citation Accuracy** | 45.0% | `45.0% [25.8%, 65.8%] (k=9, n=20)` |
| **Fallback Rate** | 16.9% | `16.9% [9.7%, 27.8%] (k=11, n=65)` |
| **Latency p50 / p95** | 33211.52 ms / 43437.44 ms | — |

## 2. Clarification of Previous '100% Truncation' Claim

- **Earlier Phase 4 Observation**: In pre-Phase 4b testing, `minimal` was executed WITHOUT grammar schema constraints and with a 256-token limit. In that raw unconstrained mode, conversational prefixes (e.g. *'Here is the JSON:'*) caused 100% length truncations on verbose cases.
- **Phase 4b / 5b Standardized Mode**: When served with GBNF grammar schema (`STRICT_SCHEMA`) and `max_tokens=512` (identical to `explicit_rules` and `few_shot`), `minimal` achieves **32.3% valid JSON [22.2%, 44.4%] (k=21, n=65)**.
- **Why Minimal Fails**: Because `minimal` lacks negative constraints and explicit rules, the model loops generating verbose repetitive prose inside JSON string values, causing 44 cases to exhaust tokens or exceed timeouts. Moreover, on hostile prompts it has an 83.3% compliance rate (5/6), failing to refuse when facts are absent.
