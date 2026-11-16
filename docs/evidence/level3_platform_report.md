# Level 3: Platform End-to-End Benchmark Report (Shipped Metal Config)

> **Hardware**: Apple M4 (Metal GPU MTL0, 36 Layers Offloaded)  
> **Server Build**: `b12359-b1b770d90` (`-c 65536 -np 16 -ctk q4_0 -ctv q4_0 -fa on --no-context-shift`)  
> **Server KV Buffer Size**: **648.00 MiB** (from server log)  
> **Model SHA-256**: `626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d`  

## 1. Staggered Closed-Loop Platform Matrix

| Users | Configuration | First Content p95 | First LLM Token p95 | Verified Answer p95 | Cache Hit Rate | Prefill Speed |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | cache_off | 13.07 ms | 0.0 ms | 13.07 ms | 0.0% | 0.0 tok/s |
| 1 | cache_on_old | 13.06 ms | 0.0 ms | 13.06 ms | 0.0% | 0.0 tok/s |
| 1 | cache_on_new | 13.05 ms | 0.0 ms | 13.05 ms | 0.0% | 0.0 tok/s |
| 4 | cache_off | 2134.71 ms | 2134.71 ms | 3058.79 ms | 0.0% | 404.8 tok/s |
| 4 | cache_on_old | 476.23 ms | 476.23 ms | 1381.76 ms | 0.0% | 356.2 tok/s |
| 4 | cache_on_new | 340.0 ms | 340.0 ms | 1256.88 ms | 87.33% | 331.3 tok/s |
| 16 | cache_off | 17113.32 ms | 17113.32 ms | 18775.08 ms | 0.0% | 139.8 tok/s |
| 16 | cache_on_old | 3219.81 ms | 3219.81 ms | 4865.34 ms | 1.26% | 49.2 tok/s |
| 16 | cache_on_new | 2800.52 ms | 2800.52 ms | 4571.0 ms | 85.64% | 44.3 tok/s |

## 2. Synchronized Burst of 16 Arrivals (t=0)

- **First Content TTFT p95**: 2336.3 ms
- **First LLM Token TTFT p95**: 2336.3 ms
- **Verified Answer Latency p95**: 4129.8 ms
- **SLO Verdict (< 2.0s)**: FAIL

## 3. Prefill Tokens/Sec Reconciliation Across Levels

- **Level 1 (Metal Native Loop)**: ~4,000 tok/s (Direct C++ Metal memory evaluation without HTTP/JSON parsing)
- **Level 2 (CPU Pathological Replay)**: ~45 tok/s (CPU-only with 14 concurrent queue stalls on 4 threads)
- **Level 3 (Shipped Metal Server)**: ~44.3 tok/s (Real llama-server Metal prefill with HTTP streaming and prompt parsing)
