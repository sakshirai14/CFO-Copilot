# Memory Accounting & 6 GB VRAM Hardware Budget Proof

## 1. Hardware Specification & Usable Budget Definition
- **Target Hardware Envelope**: Single edge GPU with **6.0 GB total VRAM** (e.g. NVIDIA RTX 2060 / 3060 6 GB or equivalent workstation).
- **Mandatory System & Driver Reserve**: **1.5 GB** (reserved for CUDA runtime, OS display compositor, PyTorch/llama.cpp backend scratch buffers).
- **Effective Usable Memory Budget**:
  $$\text{Usable VRAM Budget} = 6.0 \text{ GB} - 1.5 \text{ GB} = \mathbf{4.50 \text{ GB}} \text{ (4,608 MiB)}$$
  *Rule*: Model Weights + Total Concurrent KV Cache $\le 4.50 \text{ GB}$.

---

## 2. Mathematical KV Cache Formulation
For any autoregressive Transformer model:
$$\text{KV Bytes per Token per Slot} = 2 \times \text{layers} \times \text{kv\_heads} \times \text{head\_dim} \times \text{bytes\_per\_num}$$

Where:
- `layers`: Number of Transformer decoder layers.
- `kv_heads`: Number of key-value attention heads (Grouped Query Attention).
- `head_dim`: Dimension of each attention head ($d_{\text{model}} / n_{\text{heads}}$).
- `bytes_per_num`: Precision format (fp16 = 2.0 B, q8_0 = 1.0 B, q4_0 = 0.5 B).

---

## 3. Comprehensive Model Architecture Comparison

| Model | Layers | Attention Heads (Q / KV) | Head Dim | KV Bytes / Token (fp16) | Weights (Q4_K_M) | Weights Memory (GiB) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Qwen2.5-3B-Instruct** | 36 | 16 / **2** | 128 | **36,864 B** | 1,936.4 MiB | **1.89 GB** |
| **Llama-3.2-3B-Instruct** | 28 | 24 / **8** | 128 | **114,688 B** | 2,121.3 MiB | **2.07 GB** |

> **Architectural Takeaway**: Llama-3.2-3B allocates 8 KV heads vs. Qwen2.5-3B's 2 KV heads. As a direct mathematical consequence, Llama-3.2-3B requires **$3.11\times$ more KV cache per token** than Qwen2.5-3B for identical context lengths.

---

## 4. 16 Concurrent Sessions Memory Matrix (4k Context: 65,536 Total Tokens)

Evaluating 16 concurrent chat sessions with $4,096$ tokens of context per slot ($16 \times 4,096 = 65,536$ total tokens):

| Model & Quantization | KV Cache (MiB) | KV Cache (GB) | Model Weights (GB) | Total Footprint (GB) | Usable Budget (4.5 GB) | Margin / Deficit | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Qwen2.5-3B (KV fp16)** | **2,304.0 MiB** | **2.25 GB** | 1.89 GB | **4.14 GB** | 4.50 GB | **+0.36 GB** | ✅ **FITS** |
| **Qwen2.5-3B (KV q8_0)** | **1,152.0 MiB** | **1.13 GB** | 1.89 GB | **3.02 GB** | 4.50 GB | **+1.48 GB** | ✅ **FITS** |
| **Qwen2.5-3B (KV q4_0)** | **576.0 MiB** | **0.56 GB** | 1.89 GB | **2.45 GB** | 4.50 GB | **+2.05 GB** | ✅ **FITS** |
| **Llama-3.2-3B (KV fp16)** | **7,168.0 MiB** | **7.00 GB** | 2.07 GB | **9.07 GB** | 4.50 GB | **-4.57 GB** | ❌ **OOM / EXCEEDS** *(Computed, Not Measured)* |
| **Llama-3.2-3B (KV q8_0)** | **3,584.0 MiB** | **3.50 GB** | 2.07 GB | **5.57 GB** | 4.50 GB | **-1.07 GB** | ❌ **OOM / EXCEEDS** *(Computed, Not Measured)* |
| **Llama-3.2-3B (KV q4_0)** | **1,792.0 MiB** | **1.75 GB** | 2.07 GB | **3.82 GB** | 4.50 GB | **+0.68 GB** | ⚠️ FITS (Degraded Perplexity) |

---

## 5. Hardware Honesty & Measurement Distinction

- **Mac Unified RAM vs. GPU VRAM**:  
  All empirical measurements in this repository were collected on an Apple M-series Mac with 16 GB of unified memory. Because macOS Metal dynamically allocates unified memory from host RAM, running 16 slots of Llama-3.2-3B did not crash the Mac operating system.
- **Labeling of Llama-3.2-3B fp16 (16 slots)**:  
  Because an edge GPU has a hard physical ceiling of 6.0 GB (4.5 GB usable), the Llama-3.2-3B 16-slot fp16 row is labeled strictly as **"COMPUTED, NOT MEASURED"**. On physical 6 GB hardware, loading 2.07 GB weights followed by a 7.00 GB KV allocation would cause an unrecoverable CUDA Out-of-Memory (`cudaErrorMemoryAllocation`) failure during initialization.
- **Qwen2.5-3B Feasibility Proof**:  
  Qwen2.5-3B's total memory requirement under standard fp16 KV cache is **4.14 GB**, fitting comfortably within the 4.50 GB usable envelope with **360 MiB of headroom**.

