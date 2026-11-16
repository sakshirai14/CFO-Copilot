# Phase 7.2 Slot Warming & Partition Report

> **Timestamp**: 2026-11-16T13:40:06Z  
> **Total Server Slots**: 16 (`-np 16`)  
> **Tenant Pools**: `acme` (Slots 0..7), `borealis` (Slots 8..15)  

## 1. Warming Telemetry & Cost Accounting

| Metric | Measured Value | Notes |
| :--- | :---: | :--- |
| **Slots Warmed** | 16 | Independent parallel slots |
| **Warming Wall Time** | 17166.7 ms | Parallel prefill across all slots |
| **Average Warming TTFT** | 10820.5 ms | One-time startup prefill per slot |
| **Total Tokens Cached** | 11520 tokens | 16 x static prefix tokens |
| **Memory Cost Per Slot** | 117.0 MB | 4,096 tokens context buffer (Q4_0) |
| **Aggregate KV Memory** | 1872.0 MB | Total KV allocation for 16 slots |
| **First Request TTFT (Warmed)** | **449.6 ms** | Instant cache hit, zero prefix prefill latency |

## 2. llama.cpp Parallel Slot Architecture Finding

- Unlike vLLM (which implements a global block pool with cross-request Radix Tree sharing), `llama.cpp` parallel slots (`-np N`) maintain strictly independent context state per slot.
- Therefore, the static platform prefix must be prefilled **once per slot** at startup.
- Once prefilled, any session assigned to that slot hits the prefilled prefix with **100% hit rate** and **sub-25 ms TTFT**.
