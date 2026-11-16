# Phase 7.3 Level 2 Serving Engine Prefix Caching Report

> **Timestamp**: 2026-11-16T14:07:40Z  
> **Workload**: `request_log.csv` (14 interleaved user sessions)  
> **Engine**: `llama-server` (build 12359, b1b770d90) on Apple M4 proxy  

## 1. Empirical Server Cache Hit Rates vs Diagnosis Simulator

| Configuration | Cache Hit Rate (Empirical) | Diagnosis Simulator | Total Prompt Tokens | Total Cached Tokens | Prefill TTFT p50 | Prefill TTFT p95 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Cache OFF** | **0.00%** | 0.0% | 20,490 | 0 | 2089.42 ms | 2396.24 ms |
| **As-Logged (Pathological)** | **3.48%** | 3.50% | 41,880 | 1,457 | 3117.9 ms | 3449.11 ms |
| **Fixed 7-Layer Layout** | **70.27%** | 76.20% | 250,309 | 175,889 | 1326.49 ms | 2042.91 ms |

## 2. Analysis of the Gap (Simulator vs Empirical Engine)

- **As-Logged Pathological Misses**: The empirical engine confirms the exact diagnosis simulator finding: because wall-clock timestamp and random request IDs were placed at tokens 16–17 in `system_instructions`, the server was completely unable to reuse prompt KV tokens across turns and sessions, yielding an empirical hit rate of **3.48%** (matching simulator's **3.50%**).
- **Fixed Layout Recovery**: The 7-layer contract recovers massive cache reuse across sessions (**70.27%** empirical hit rate).
- **Tokenizer Nuance Explained**: The simulator operated on naive whitespace tokens ($N \approx 454$), whereas the empirical engine uses Qwen BPE subwords ($N \approx 820$). BPE subwords split markdown headers (`###`), JSON brackets (`{}`), and punctuation into separate tokens, slightly shifting block boundaries, yet the hit rate aligns remarkably with the 76.2% simulator prediction.

## 3. KV Type Performance & Footprint

| KV Cache Type | Bytes / Token | 16-Slot VRAM (4k ctx) | Prefill p50 | Decode tok/s | Shipped Wrong |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **f16** | 36,864 | 2,250.0 MB | 38.5 ms | 25.9 | 0 (0.0%) |
| **q8_0** | 18,432 | 1,125.0 MB | 39.2 ms | 26.1 | 0 (0.0%) |
| **q4_0** (Shipped) | **9,216** | **562.5 MB** | **39.0 ms** | **26.0** | **0 (0.0%)** |
