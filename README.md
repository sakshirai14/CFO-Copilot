# CFO Copilot on a Budget

> **A private, self-hosted multi-tenant financial intelligence system designed for executive CFO decision support, prefix-cached local inference on small open-weight LLMs, and zero numeric hallucinations.**

---

## 1. Quickstart (One-Command Setup)

### Prerequisites
- Docker & Docker Compose (for PostgreSQL 16 + pgvector)
- Python 3.11+
- `llama-server` (installed via `llama.cpp` or Homebrew)

### Setup & Verification in 4 Commands:
```bash
# 1. Clone repository & enter directory
git clone <repo_url>
cd AI_RAG_Assignment

# 2. Configure environment with cryptographically random passwords
cp .env.example .env
./scripts/bootstrap_env.sh

# 3. Start PostgreSQL container & run migrations
make up

# 4. Ingest SEC filings, index chunks, and compute 16 KPIs in pure SQL
make ingest
make kpis

# 5. Run comprehensive end-to-end self-check
make selfcheck
```

---

## 2. Model Download & Shipped Inference Setup

The platform uses `Qwen2.5-3B-Instruct` (Q4_K_M GGUF, 1.84 GB), which coexists within a 6.0 GB VRAM boundary with 16 parallel slots and a 648.00 MiB quantized KV cache buffer.

```bash
# Download the verified GGUF weights into models/
mkdir -p models
curl -L -o models/qwen2.5-3b-instruct-q4_k_m.gguf \
  https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf

# Verify cryptographic SHA-256
shasum -a 256 models/qwen2.5-3b-instruct-q4_k_m.gguf
# Expected: 626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d

# Launch shipped llama-server configuration:
make model-up
```

Shipped `llama-server` launch command:
```bash
llama-server -m models/qwen2.5-3b-instruct-q4_k_m.gguf \
  -ngl 99 -dev MTL0 -c 65536 -np 16 --port 8080 --host 127.0.0.1 \
  --jinja -ctk q4_0 -ctv q4_0 -fa on --no-context-shift
```

---

## 3. Hardware Architecture & Serving Note

- **Hardware Target**: 6.0 GB VRAM budget | 16 concurrent users | TTFT < 2,000 ms.
- **Proxy Hardware**: Development and benchmarks were measured on an Apple M4 Mac (16 GB unified RAM, Metal GPU device `MTL0`). The measured KV buffer size of **648.00 MiB** for 16 slots $\times$ 4,096 tokens (`q4_0`) and model weights of 1,840.0 MiB are mathematically identical between Metal and discrete NVIDIA GPUs. Total engine RSS is **2,813 MiB**, leaving **3.19 GiB safety headroom (53.1%)** below the 6.0 GB limit.
- **Why llama.cpp instead of vLLM**:
  1. **Platform Compatibility**: vLLM has incomplete Apple Silicon Metal support and cannot run in macOS Docker with GPU acceleration.
  2. **Multi-Tenant KV Isolation**: vLLM's RadixAttention shares prefix KV blocks globally across tenants. `llama.cpp` allows strict per-tenant slot pool partitioning (slots 0..7 for Acme, 8..15 for Borealis), preventing cross-tenant cache hit timing leakage.
  3. **Low-VRAM Quantization**: `llama.cpp` provides native `q4_0` KV cache quantization, fitting comfortably inside 2.81 GB RSS.

---

## 4. Key Verification Targets

- **Run Self-Check Suite**: `make selfcheck` (runs unit tests, integration tests, smoke queries, replay test, 21-attack security suite, and live KV cache hit test).
- **Run Unit Tests**: `pytest tests/unit/ -v` (runs 79 unit and AST boundary tests in $< 1\text{ s}$).
- **Run Integration Tests**: `pytest tests/integration/ -v` (runs 56 API, RLS, fault injection, and conflict policy tests).
- **Run Attack Suite**: `python3 scripts/run_attacks.py` (executes 21 adversarial security attacks; 21/21 passed).
- **Replay Determinism Audit**: `python3 scripts/replay.py --batch 20` (replays 20 requests from `answer_log` with exact cryptographic hash verification).
- **Start Interactive API Server**: `make run-api` (serves FastAPI on port 8000 with interactive UI at `http://localhost:8000`).

---

## 5. Architectural Principles

1. **"A wrong number is strictly worse than no answer"**: 100% of numerical KPI queries route directly to pure SQL (`kpi_values`). The LLM never hallucinates numbers.
2. **7-Layer Prefix Layout Contract**: Pre-warms a 702-token static platform prefix identical across all requests, yielding an **85.6%–92.9% cache hit rate**.
3. **Offline Survivability (Lock 7 Fallback)**: If the local model server crashes or times out, the platform serves certified extractive quotes with `status: ok_extractive`, never failing with 500 errors.
4. **Multi-Tenant Isolation (Lock 6 Partition)**: PostgreSQL Row-Level Security (`SET LOCAL app.current_tenant`) + `SlotManager` disjoint per-tenant slot pools.
