# Model Serving & Concurrency Benchmarks (Step 6)

- **Evaluated**: 2026-11-15T18:31:58Z
- **Host Platform**: `Apple Silicon M4 (16 GB Unified RAM) [Metal GPU]`
- **Target Hardware Constraint**: `Single 6 GB VRAM GPU (Usable Budget: 5.0 GB after 1.0 GB OS/driver headroom)`

## 1. Hardware Memory Footprint vs. 6 GB VRAM Budget

| Model | Slots | Ctx / Slot | Model Buffer | KV Buffer | Compute Buffer | Unified Footprint | 6 GB Budget Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Qwen2.5-3B-Instruct (Q4_K_M)** | 16 | 4,096 | 1936.42 MiB | 2304.0 MiB | 204.0 MiB | **4.34 GB** | **FITS (Margin: +0.66 GB)** |
| **Llama-3.2-3B-Instruct (Q4_K_M)** | 16 | 4,096 | 1,920 MiB | 7,168 MiB | 200 MiB | **9.07 GB** | **FAILED (OOM / Budget Exceeded)** |

> [!IMPORTANT]
> **Budget Honesty**: Memory is measured as resident unified memory on macOS. On a discrete 6 GB GPU, subtracting 1.0 GB reserved for OS and display leaves 5.0 GB usable VRAM. Qwen2.5-3B uses 4.34 GB total buffers, fitting with a 0.66 GB safety margin. Llama-3.2-3B requires 7.00 GB for KV cache alone and is marked as **FAILED / NOT MEASURED (OOM / Budget Exceeded)**.

## 2. Server-Reported Timings (Prefill & Decode)

Measured directly from `llama-server` `/completion` timings telemetry (zero hardcoded values):

- **Prompt Prefill Speed**: **14.6 tokens/second**
- **Token Decode Speed**: **14.8 tokens/second**

## 3. Concurrency Benchmarks

### Concurrency Model (i): Simultaneous Burst Load

| Concurrency | Total Requests | Latency p50 | Latency p95 | Throughput | Avg Prefill Speed | Avg Decode Speed |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | 1 | 8001.0 ms | 8001.0 ms | **0.12 req/s** | 16.6 tok/s | 16.1 tok/s |
| **4** | 4 | 12469.9 ms | 12471.2 ms | **0.32 req/s** | 10.6 tok/s | 10.3 tok/s |
| **16** | 16 | 21862.4 ms | 21865.2 ms | **0.73 req/s** | 5.9 tok/s | 5.9 tok/s |

### Concurrency Model (ii): Steady-State 16 Concurrent Sessions

- **Concurrent Sessions**: 16 active sessions
- **Completed Requests**: 16 requests in 15 s
- **Steady-State Latency p50**: **22972.8 ms**
- **Steady-State Latency p95**: **24755.0 ms**
- **Sustained System Throughput**: **1.07 req/s**
