# Phase 7.3: KV Cache Memory Sizing Accounting

> **Methodology**: Extracted architectural parameters directly from `models/qwen2.5-3b-instruct-q4_k_m.gguf` binary metadata 
> and `data_pack/CANDIDATE_PACK/puzzle2_data/reference_hardware_and_model.csv`.

## 1. Budget Breakdown (6.0 GB Total Budget)

- **Total Budget**: 6.0 GB
- **Runtime & Activations Reserve**: 1.5 GB
- **Qwen2.5-3B Weights**: 1.96 GB (Leaving **2.54 GB** for KV cache)
- **Reference 3B Model Weights**: 2.00 GB (Leaving **2.50 GB** for KV cache)

## 2. Model Architecture Parameters

- **Qwen2.5-3B**: Layers $L=36$, KV Heads $H_{kv}=2$, Query Heads $H_q=16$, Head Dim $D=128$
- **Reference 3B**: Layers $L=28$, KV Heads $H_{kv}=8$, Head Dim $D=128$

## 3. KV Sizing Comparison Matrix

| Model | KV Quant Type | Bytes / Token | Max Tokens in Budget | Max 4,096 Sessions | VRAM for 16 Sessions (4k ctx) | Fits 16 Sessions? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Qwen2.5-3B** | f16 | 36,864 B | 73,982 | 18.1 | 2.250 GB | **YES** |
| **Qwen2.5-3B** | q8_0 | 18,432 B | 147,965 | 36.1 | 1.125 GB | **YES** |
| **Qwen2.5-3B** | q4_0 | 9,216 B | 295,931 | 72.2 | 0.562 GB | **YES** |
| **Reference 3B** | f16 | 114,688 B | 23,405 | 5.7 | 7.000 GB | **NO** |
| **Reference 3B** | q8_0 | 57,344 B | 46,811 | 11.4 | 3.500 GB | **NO** |
| **Reference 3B** | q4_0 | 28,672 B | 93,622 | 22.9 | 1.750 GB | **YES** |

## 4. Shipped Configuration Justification

- **Selected Quantization**: `q4_0`
- **Allocated Total Context**: 65,536 tokens across 16 parallel slots (4,096 tokens/slot).
- **Total KV Footprint**: 562.5 MB (0.562 GB), consuming only 21.9% of the 2.57 GB KV budget.
- **Headroom**: 2.01 GB safety margin in KV budget; 3.48 GB total headroom under the 6.0 GB ceiling.
