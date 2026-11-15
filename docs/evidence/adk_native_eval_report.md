# Native Google ADK Offline Evaluation Report

- **EvalSet ID**: `cfo_copilot_evalset_v1`
- **Benchmark Name**: CFO Copilot SEC Filing Intelligence Benchmark
- **Dataset Path**: `tests/adk_evals/cfo_copilot.evalset.json`
- **Total Evaluated Cases**: 33 (strictly $\ge 30$ representative cases)
- **Execution Mode**: **Strictly Offline** (Local PostgreSQL + `llama-server` Qwen2.5-3B; 0 hosted API calls)

## 1. Native ADK Benchmark Results

| Metric | Evaluated Score | Wilson 95% Confidence Interval | Production Requirement |
| :--- | :---: | :---: | :---: |
| **Route Selection Accuracy** | **30/33** | 90.9% [76.4%, 96.9%] (k=30, n=33) | $\ge 95.0\%$ |
| **Status Accuracy** | **25/33** | 75.8% [59.0%, 87.2%] (k=25, n=33) | $\ge 95.0\%$ |
| **Shipped Wrong-Number Rate** | **0.0%** | 0.0% [0.0%, 10.4%] (k=0, n=33) | **0.0% (Hard Lock)** |
| **Latency p50** | **5.42 ms** | - | < 2,000 ms |
| **Latency p95** | **3232.09 ms** | - | < 2,000 ms |

## 2. Architectural Limitation of Built-In `AgentEvaluator` & Offline Workaround

### The Technical Limitation
Google ADK's built-in evaluation orchestrator (`google.adk.evaluation.agent_evaluator.AgentEvaluator`) suffers from two fundamental limitations for enterprise financial assistants:

1. **Cloud Lock-in & Missing Offline Dependencies (`agentplatform`)**:
   - Invoking `AgentEvaluator.evaluate_eval_set()` directly imports `google.adk.evaluation.vertex_ai_eval_facade`,
     which requires `agentplatform` (`ModuleNotFoundError: No module named 'agentplatform'`).
   - This package attempts to call Google Cloud Vertex AI evaluation endpoints over the public internet, violating
     the private, self-hosted, air-gapped deployment requirement of CFO Copilot.

2. **Incompatibility with Deterministic Domain Routing**:
   - `AgentEvaluator` assumes every agent is a conversational `LlmAgent` that yields `FunctionCall` events into an
     interactive session history.
   - In CFO Copilot, **90% of user queries bypass the LLM entirely**, executing via compiled SQL pipelines (`RouterAgent` $\to$ `FactsAgent` $\to$ `AnswerComposer`).
   - When `AgentEvaluator` runs on deterministic agents that return direct `AnswerEnvelope` outputs without intermediate
     model generation events, it fails to record standard rubric traces.

### The Sanctioned Workaround
To adhere strictly to ADK's formal contracts without compromising offline security:
- All test cases are serialized in native ADK Pydantic schemas (`EvalSet`, `EvalCase`, `Invocation`, `types.Content`).
- The offline evaluation harness (`scripts/run_adk_native_eval.py`, wired to `make adk-eval`) executes locally, enforcing mathematical correctness, schema fidelity, and `AnswerVerifier` validation offline.
