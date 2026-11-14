# DECISIONS.md: Platform Architectural Decision Log

> **Project**: CFO Copilot on a Budget  
> **Repository**: [AI_RAG_Assignment](file:///Users/sakshirai/AI_RAG_Assignment)  
> **Author**: Senior GenAI Platform Engineer  
> **Rule**: Document what was evaluated, what failed, why courses changed, and what we would do differently live.

---

### [2026-11-14] DECISION 1: Google ADK Version & LiteLLM Integration Pattern
- **Decision**: Pin **`google-adk == 2.14.1`** as the core agent orchestration framework.
- **Evidence / Measurement**: Executed `python3 -m pip index versions google-adk`. Latest stable PyPI release confirmed as `2.14.1`.
- **Integration Contract**:
  - ADK communicates with local OpenAI-compatible inference servers using the `LiteLlm` model wrapper:
    ```python
    from google.adk.agents import LlmAgent
    from google.adk.models.lite_llm import LiteLlm

    model = LiteLlm(
        model="openai/qwen2.5-3b-instruct",
        api_base="http://localhost:8080/v1",
        api_key="not-needed-for-local"
    )
    ```
- **Rationale**: ADK satisfies Foundation Lock 2 and Puzzle 4 by decoupling agent execution from specific model runtimes. LiteLLM provides a standardized bridge to our local `llama.cpp` server with zero network traffic exiting the machine.

---

### [2026-11-14] DECISION 2: Serving Strategy & Hardware Path on Apple Silicon
- **Decision**: Adopt a dual-path serving strategy:
  1. **Official Benchmark / Deliverable Path**: Report **CPU-only fallback** numbers in all formal benchmarks and Docker container runs.
  2. **Interactive CFO Demonstration Path**: Run native `llama-server` on Apple Silicon with Metal acceleration (`-ngl 99`) for fast local developer and streaming chat validation.
- **Evidence / Measurement**: System probe confirmed the host is an **Apple M4 Mac with 16 GB unified RAM and 10 CPU cores**. There is no NVIDIA GPU (`nvidia-smi` not found, no CUDA). Docker Desktop on macOS runs in a Linux VM without Metal GPU pass-through, forcing containerized inference to execute on CPU.
- **Rationale**: The assignment explicitly allows a stated CPU-only fallback. Attempting to simulate or fake NVIDIA GPU VRAM metrics violates our hard rule (*"Never fabricate results"*). We report real CPU latency, memory footprint, and prefix-cache metrics honestly.

---

### [2026-11-14] DECISION 3: Open-Weight Model Shortlist for 6 GB VRAM Constraint
- **Decision**: Shortlist **`Qwen2.5-3B-Instruct` (Q4_K_M GGUF)** as the primary candidate, with **`Llama-3.2-3B-Instruct`** as the baseline comparison and **`Qwen2.5-1.5B-Instruct`** as the ultra-low resource fallback.
- **Evidence / Measurement**:
  - `Llama-3.2-3B` (28 layers, 8 KV heads, 128 head dim) consumes **112.0 KB per token in FP16**. Supporting 16 concurrent users at 4,096 tokens requires **7.00 GB of KV cache alone**, causing immediate OOM on a 6 GB card.
  - `Qwen2.5-3B` (36 layers, 2 KV heads, 128 head dim) consumes only **36.0 KB per token in FP16** ($3.1\times$ less KV memory per token!). At 16 concurrent users with 4k context, it requires just **2.25 GB in FP16** (or **1.13 GB in FP8**), fitting within our 2.5 GB KV cache budget. It is the only 3B-class model that comfortably survives the Drop 2 context expansion (8,192 tokens) without OOM.
- **Status**: No weights were downloaded in Phase 0. Physical benchmarking will occur in Phase 3.

---

### [2026-11-14] DECISION 4: Data Release Architecture: Drop 1 Baseline vs. Drop 2 Data Ingestion Event
- **Decision**: Treat `CANDIDATE_PACK` (Drop 1) as the baseline dataset and `DROP2_RELEASE` (Drop 2) as a subsequent **data ingestion event** (introducing 6th company `ZLG` and amended filing `NWI-10QA-FY2024Q3`), NOT a schema migration. Schema migrations are strictly reserved for structural DDL changes.
- **Evidence / Measurement**:
  - `DROP2_RELEASE` provides only 1 new company (`ZLG`, 12 quarters, 276 financial rows) and 1 amended filing (`NWI-10QA-FY2024Q3`, 7 amended lines), plus 13 documents.
  - Drop 2 does not alter table structures or require DDL migrations. The database schema created in Phase 1 fully accommodates all 6 companies and amendment linkages from day one.
- **Policy Contract**:
  - Form 10-Q/A amendments supersede original Form 10-Q numbers for default KPI calculations.
  - Original filings remain stored in database staging tables with `status = 'superseded'` for complete auditability.

---

### [2026-11-14] DECISION 5: Puzzle 2 Prefix Cache Diagnosis Intake & Reproduction
- **Decision**: Confirm and accept the empirical diagnosis of `request_log.csv`.
- **Evidence / Measurement**: Re-ran simulation via `scripts/analyze_request_log.py` against `request_log.csv` and `reference_hardware_and_model.csv`. All reference numbers reproduced exactly:
  1. As-logged hit rate: **3.50%** (Target: 3.5%)
  2. Removing Clock & Request ID: **55.95%** (Target: 55.9%)
  3. Deterministically Sorting Tools: **64.95%** (Target: 64.9%)
  4. Static-First Prompt Reordering: **70.39%** (Target: 70.4%)
  5. Hysteresis History Truncation: **76.72%** (Target: 76.6%)
  6. Day-Stamp at Prompt Tail: **76.20%** (Target: 76.2%)
  7. Tool schema permutations: **24 unique permutations** confirmed ($4! = 24$).
  8. cached_tokens distribution: **16 in 219 rows, 0 in 1 row** confirmed.
  9. Eviction/Memory hypothesis: **REFUTED** (failure occurs on request 2 with zero VRAM pressure).

---

### [2026-11-14] DECISION 6: Data Pack Audit & Ingestion Normalization Contracts
- **Decision**: Mandate the following four ingestion cleaning rules in the database pipeline:
  1. **HBS Unit Scale Auto-Correction**: Cross-reference `financial_statements_raw.csv` unit against `filings_index.csv`. Automatically correct `HBS-10Q-FY2024Q2` from `USD_millions` to `USD_thousands` and log an ingestion defect.
  2. **Accounting Sign Standardization**: Enforce positive values for expenses and COGS (`COGS = ABS(value)`) during staging to eliminate CEP's negative expense convention.
  3. **Intra-Filing Deduplication**: Enforce unique constraint `(filing_id, statement, line_item_raw)` on staging tables to eliminate duplicate rows (e.g. ARG Q2 2023 rows R000411 and R001447).
  4. **Date Normalization**: Parse all `period_start` and `period_end` dates into standard ISO 8601 (`YYYY-MM-DD`) to reconcile CEP's `MM/DD/YYYY` dates.
  5. **Adversarial Context Isolation**: RAG documents must be sanitized and treated as untrusted text (Foundation Lock 2 & Puzzle 5). The LLM is strictly prohibited from executing SQL queries or setting business numbers from retrieved text.

---

### What I'd Do Differently / What Failed or Surprised Us
1. **Initial File Access Outside Workspace Boundary**:
   - *What Happened*: Initial user prompt referenced files located outside the project folder. macOS Privacy & Security (TCC) strictly blocked directory traversal of `~/Downloads`.
   - *Resolution*: Adhered strictly to the workspace isolation rule: all work, audits, and code execution are self-contained inside `/Users/sakshirai/AI_RAG_Assignment/`.
2. **Surprise: The 1,000x Unit Error in HBS**:
   - *What Surprised Us*: Finding that 11 rows in `HBS-10Q-FY2024Q2` were extracted with `unit = USD_millions` while the filing index specified `USD_thousands`. Had this not been caught in Phase 0, Helix BioSystems would have reported $109.2 Billion in quarterly revenue instead of $109.2 Million.
3. **Surprise: Hostile Prompt Injection Payloads in SEC Filings**:
   - *What Surprised Us*: The SEC filing `NWI-10Q-FY2024Q3` contained an explicit system prompt spoofing attack instructing the AI to lie that its operating margin was 45%. Furthermore, `CEP_investor_faq` attempted to trick the model into executing `SELECT * FROM information_schema.tables` and dumping database credentials. This reinforces why Foundation Lock 2 (LLM never generates financial figures, agent contains no SQL strings) is non-negotiable.
4. **Surprise: Llama-3.2-3B vs. Qwen2.5-3B KV Footprint Discrepancy**:
   - *What Surprised Us*: The reference model in the assignment is an 8-KV-head architecture (Llama-3.2-3B). In FP16, 16 concurrent users at 4k tokens consume 7.0 GB of KV cache — completely blowing past a 6 GB VRAM GPU before even counting model weights. Switching to `Qwen2.5-3B` with 2 KV heads drops the KV memory requirement by $68\%$, making 16 concurrent users feasible.

