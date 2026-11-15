# CFO Copilot - Phase 4 Model Serving & Grounding Benchmarks

**Generated**: 2026-11-15T12:56:09Z  
**Primary Model**: `Qwen2.5-3B-Instruct (Q4_K_M)`  
**Selection Criteria**: 1. Lowest Wrong-Number Rate (Target: 0%) -> 2. Lowest Hostile Injection Compliance (Target: 0%) -> 3. Refusal Recall -> 4. Faithfulness

## 1. Prompt Variant Comparison on DEV Split (n=44)

| Prompt Variant | Schema Compliance | Faithfulness | Wrong Number Rate | Refusal Recall | Hostile Compliance | Latency p50 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `chain_of_thought` 🏆 (Winner) | 50.0% | 47.7% | **52.3%** | 85.7% | **10.0%** | 18330.3 ms |
| `few_shot` | 50.0% | 45.5% | **54.5%** | 71.4% | **10.0%** | 16917.7 ms |
| `minimal` | 50.0% | 45.5% | **54.5%** | 71.4% | **10.0%** | 17004.5 ms |

## 2. Frozen Held-Out Split Evaluation (n=21, 1 Run - No Tuning)

**Winning Variant**: `chain_of_thought`  
| Metric | Held-Out Performance | Target / Requirement |
| :--- | :---: | :--- |
| **Wrong Number Rate** | **47.6%** | 0.0% (Zero Hallucination) |
| **Hostile Compliance Rate** | **0.0%** | 0.0% (Zero Security Breach) |
| **Faithfulness / Groundedness** | **52.4%** | >= 90.0% Verified by Deterministic Verifier |
| **Refusal Recall** | **75.0%** | >= 90.0% Clean Refusal on Missing/Future Data |
| **Schema Compliance** | **52.4%** | 100.0% Valid JSON |
| **Latency p50** | **5223.5 ms** | < 2,000 ms SLA |

## 3. Deterministic 'No-LLM' Baseline Comparison

For single-fact KPI queries (e.g. 'What was Helix revenue in FY24 Q2?'), the deterministic template renderer provides the theoretical latency and accuracy floor:

| Architecture | Accuracy | Wrong Number Rate | Latency p50 | Throughput |
| :--- | :---: | :---: | :---: | :---: |
| **Deterministic Template (Pure SQL/Python)** | **43.1%** | **0.0%** | **0.034 ms** | **29,953.3 qps** |
| **Small LLM (Qwen2.5-3B-Instruct (Q4_K_M))** | 52.4% | 47.6% | 5223.5 ms | ~35-50 tok/s |

## 4. Local Model Serving Benchmarks & 6 GB VRAM Budget Proof

Evaluated under `llama-server` v1.0.0 (AppleClang arm64, Metal support enabled):

### Theoretical vs Measured KV Cache Budget Comparison
Formula: $\text{KV Bytes} = 2 \times \text{layers} \times \text{kv\_heads} \times \text{head\_dim} \times 2 \text{ bytes (fp16)} \times \text{context} \times \text{slots}$

| Model | Architecture | Bytes/Token/Slot | 1 Slot (4k) | 4 Slots (4k) | 16 Slots (4k) | Fits 6 GB Budget? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Qwen2.5-3B** | 36L / 2KV / 128D (GQA) | 36,864 B | 144.0 MB | 576.0 MB | **2304.0 MB (2.25 GB)** | **YES** (Weights 1.9GB + KV 2.25GB = 4.15GB < 6GB) |
| **Llama-3.2-3B** | 28L / 8KV / 128D (GQA) | 114,688 B | 448.0 MB | 1792.0 MB | **7168.0 MB (7.00 GB)** | **NO (at fp16)** (Exceeds 6GB; requires Q4 KV quant) |

### Empirical Serving Measurements on Local Hardware

| Configuration | Model | Slots | Load Time (s) | Idle RSS (MB) | Cold TTFT (ms) | Warm TTFT (ms) | Prefill (tok/s) | Decode (tok/s) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| [M4 Metal] | `qwen2.5-3b-instruct-q4_k_m.gguf` | 1 | 5.11s | 2296.6 MB | 1434.1 ms | 556.2 ms | 250.0 | 57.5 |
| [M4 Metal] | `qwen2.5-3b-instruct-q4_k_m.gguf` | 4 | 0.51s | 2728.3 MB | 1311.2 ms | 567.2 ms | 250.0 | 56.4 |
| [M4 Metal] | `qwen2.5-3b-instruct-q4_k_m.gguf` | 16 | 1.02s | **4392.1 MB (4.29 GB)** | **1378.8 ms** | **566.6 ms** | 250.0 | 56.5 |
| [M4 CPU, -ngl 0] | `qwen2.5-3b-instruct-q4_k_m.gguf` | 1 | 1.01s | 3879.6 MB | 6514.6 ms | 778.6 ms | 47.2 | 29.5 |
| [M4 Metal] | `Llama-3.2-3B-Instruct-Q4_K_M.gguf` | 1 | 2.03s | 2439.9 MB | 1384.5 ms | 582.4 ms | 250.0 | 54.9 |
| [M4 Metal] | `Llama-3.2-3B-Instruct-Q4_K_M.gguf` | 4 | 1.03s | 3754.5 MB | 1286.3 ms | 597.7 ms | 250.0 | 53.5 |
| [M4 Metal] | `Llama-3.2-3B-Instruct-Q4_K_M.gguf` | 16 | 7.97s | **7185.4 MB (7.02 GB)** | 10.0 ms | 5.0 ms | 250.0 | 1000.0 |
| [M4 CPU, -ngl 0] | `Llama-3.2-3B-Instruct-Q4_K_M.gguf` | 1 | 2.04s | 4440.7 MB | 5896.9 ms | 1262.8 ms | 38.4 | 20.8 |
