# MODEL_CANDIDATES.md: Small Open-Weight Model Sizing & KV Cache Budget Evaluation

> **Target Constraints**: 6.0 GB Total VRAM, 1.5 GB Runtime Reserve, $\le 2.0 - 2.5\text{ GB}$ 4-bit Weights, Available KV Cache Budget $\approx 2.0 - 2.5\text{ GB}$  
> **Concurrency Target**: 16 concurrent chat sessions  
> **Context Target**: 4,096 tokens (Phase 1–5), rising to 8,192 tokens (Drop 2)  
> **Rule**: DO NOT DOWNLOAD ANY MODEL IN PHASE 0. Spec evaluation only.

---

## 1. Mathematical Formulas for Model Sizing

For any transformer model with Grouped-Query Attention (GQA):
- **Layers ($L$)**: Number of decoder transformer blocks.
- **KV Heads ($H_{kv}$)**: Number of Key and Value projection heads.
- **Head Dimension ($D$)**: Dimension per attention head ($\text{hidden\_size} / \text{num\_query\_heads}$).
- **Bytes per element ($b$)**: 2.0 for FP16, 1.0 for FP8, 0.5 for Q4.

$$\text{KV Bytes Per Token} = 2 \times L \times H_{kv} \times D \times b$$

$$\text{KV Cache Size (Total)} = (\text{Concurrent Sessions} \times \text{Tokens Per Session}) \times \text{KV Bytes Per Token}$$

---

## 2. Candidate Architecture Comparison Table

| Candidate Model | Parameters | Layers ($L$) | KV Heads ($H_{kv}$) | Head Dim ($D$) | 4-bit Weights (Q4_K_M) | KV Bytes/Tok (FP16) | KV Bytes/Tok (FP8) | KV Bytes/Tok (Q4) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Qwen2.5-3B-Instruct** | 3.09 B | 36 | 2 | 128 | **1.95 GB** | **36,864 B** (36.0 KB) | **18,432 B** (18.0 KB) | **9,216 B** (9.0 KB) |
| **Llama-3.2-3B-Instruct** *(Reference Model)* | 3.21 B | 28 | 8 | 128 | **2.02 GB** | **114,688 B** (112.0 KB) | **57,344 B** (56.0 KB) | **28,672 B** (28.0 KB) |
| **Phi-4-mini-instruct** | 3.82 B | 32 | 8 | 128 | **2.40 GB** | **131,072 B** (128.0 KB) | **65,536 B** (64.0 KB) | **32,768 B** (32.0 KB) |
| **Gemma-3-4B-IT** | 4.20 B | 34 | 4 | 256 | **2.65 GB** | **139,264 B** (136.0 KB) | **69,632 B** (68.0 KB) | **34,816 B** (34.0 KB) |
| **Qwen2.5-1.5B-Instruct** *(Ultra-Light)* | 1.54 B | 28 | 2 | 128 | **1.05 GB** | **28,672 B** (28.0 KB) | **14,336 B** (14.0 KB) | **7,168 B** (7.0 KB) |

---

## 3. Concurrency Memory Footprint Analysis (16 Sessions)

### Scenario A: Baseline 4,096 Context Length ($16 \times 4,096 = 65,536\text{ tokens}$ in flight)
Budget Available for KV Cache: **$2.50\text{ GB}$** ($2,684,354,560\text{ bytes}$)

| Candidate Model | KV Footprint (FP16) | KV Footprint (FP8) | KV Footprint (Q4) | Fits in 2.5 GB Budget? | Recommendation |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Qwen2.5-3B-Instruct** | **2.25 GB** | **1.13 GB** | **0.56 GB** | **YES (Even in FP16!)** | **Top Recommendation** |
| **Llama-3.2-3B-Instruct** | 7.00 GB | 3.50 GB | **1.75 GB** | **YES (Q4 only)** | Strong Contender (with Q4 KV) |
| **Phi-4-mini-instruct** | 8.00 GB | 4.00 GB | **2.00 GB** | **YES (Q4 only)** | Heavy weight, tight budget |
| **Gemma-3-4B-IT** | 8.50 GB | 4.25 GB | 2.13 GB | **NO (Weights exceed budget)** | Disqualified (weights = 2.65 GB) |
| **Qwen2.5-1.5B-Instruct** | **1.75 GB** | **0.88 GB** | **0.44 GB** | **YES (All precisions)** | Backup for extreme CPU limits |

### Scenario B: Drop 2 Twist Context Length 8,192 ($16 \times 8,192 = 131,072\text{ tokens}$ in flight)
Budget Available for KV Cache: **$2.50\text{ GB}$**

| Candidate Model | KV Footprint (FP16) | KV Footprint (FP8) | KV Footprint (Q4) | Fits 8k Context Target? |
| :--- | :---: | :---: | :---: | :--- |
| **Qwen2.5-3B-Instruct** | 4.50 GB | **2.25 GB** | **1.13 GB** | **YES (Fits comfortably in FP8 or Q4)** |
| **Llama-3.2-3B-Instruct** | 14.00 GB | 7.00 GB | 3.50 GB | **NO** (Exceeds budget unless prefix shared $\ge 50\%$) |
| **Phi-4-mini-instruct** | 16.00 GB | 8.00 GB | 4.00 GB | **NO** (OOM at 8k concurrency) |
| **Gemma-3-4B-IT** | 17.00 GB | 8.50 GB | 4.25 GB | **NO** (OOM at 8k concurrency) |
| **Qwen2.5-1.5B-Instruct** | 3.50 GB | **1.75 GB** | **0.88 GB** | **YES (Fits in FP8 or Q4)** |

---

## 4. Key Takeaways & Model Shortlist for Phase 3

1. **Why Qwen2.5-3B-Instruct is the Optimal Architecture**:
   - Qwen2.5-3B uses Grouped-Query Attention with only **2 KV heads** (16 query heads : 2 KV heads, an 8:1 compression ratio).
   - In contrast, Llama-3.2-3B uses **8 KV heads** (24 query heads : 8 KV heads, a 3:1 ratio).
   - As a direct result, **Qwen2.5-3B requires only 36.0 KB per token in FP16**, compared to **112.0 KB per token for Llama-3.2-3B** ($3.1\times$ less KV memory per token!).
   - At 16 concurrent users with 4,096 tokens, Qwen2.5-3B consumes just **2.25 GB in native FP16** (or **1.13 GB in FP8**), making it uniquely capable of sustaining 16 users on 6 GB VRAM and surviving the 8k Drop 2 context expansion without OOM.
2. **Shortlist for Puzzle 3 Evaluation**:
   - **Primary Model**: `Qwen2.5-3B-Instruct` (Q4_K_M GGUF)
   - **Baseline Comparison Model**: `Llama-3.2-3B-Instruct` (Q4_K_M GGUF, reference specification)
   - **Fallback Lightweight Model**: `Qwen2.5-1.5B-Instruct` (Q4_K_M GGUF)
3. **No Model Downloaded**: In adherence to Phase 0 constraints, no model binaries have been downloaded. Model selection and benchmark evaluation will occur in Phase 3.
