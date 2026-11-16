# DEFEND.md: Architecture Defense & Technical Interview Guide

> **Platform**: CFO Copilot on a Budget  
> **Target Audience**: Technical Interviewer, System Architect, Executive Review Committee  
> **Authoritative Commit**: `freeze-before-v3` (`3d44926`)  
> **Core Principle**: *"A wrong number is strictly worse than no answer."*

---

# Technical Reviewer & Interview Defense: 15 Critical System Questions

---

### Q1: Why do you route structured queries to SQL instead of letting the LLM query the database or write SQL?
- **The Honest Answer**: Small 3B open-weight models have an unacceptable SQL syntax error rate (> 25%) and frequently invent table names, hallucinate aggregate functions, or calculate ratios using wrong arithmetic formulas. Furthermore, granting an LLM database credentials or SQL generation capabilities creates massive SQL injection and prompt injection vulnerabilities. By routing structured queries to certified SQL templates in `kpi_values`, we achieve **0.0% wrong numbers**, **0 LLM calls**, and **sub-15ms latency**.
- **File & Line Number Proof**: [`app/agents/root_agent.py`](file:///Users/sakshirai/AI_RAG_Assignment/app/agents/root_agent.py#L88-L105) (Zero LLM calls for structured route) and [`tests/unit/test_architecture.py`](file:///Users/sakshirai/AI_RAG_Assignment/tests/unit/test_architecture.py#L20-L46) (AST checks verifying zero SQL in agent modules).
- **The Trade-Off Made**: The system cannot answer open-ended or arbitrary unstructured SQL questions outside the 16 canonical KPIs and financial statements without schema updates.
- **What to Do Differently in Production**: Build a text-to-SQL semantic layer using typed AST builders (e.g. Cube.js or PRQL) rather than raw text generation, backed by read-only query sandboxing with strict timeout limits.

---

### Q2: How do you prove that Tenant A cannot access Tenant B's data or KV cache?
- **The Honest Answer**: We enforce isolation at two independent architectural boundaries:
  1. **Database Layer**: PostgreSQL Row-Level Security (`FORCE ROW LEVEL SECURITY`) with connection-scoped `SET LOCAL app.current_tenant = %s`.
  2. **Inference Layer**: `SlotManager` strictly partitions the 16 server slots into disjoint pools: slots 0..7 for `acme` and slots 8..15 for `borealis`. A slot allocated to Acme is never assigned to Borealis.
  3. **Empirical Property Test**: Across 10,000 random operations, `SlotManager` had zero cross-tenant slot assignments. When Tenant B sent a prompt identical to Tenant A's private text, `llama-server` reported `cache_n = 0`.
- **File & Line Number Proof**: [`app/orchestration/slot_manager.py`](file:///Users/sakshirai/AI_RAG_Assignment/app/orchestration/slot_manager.py#L35-L65) and [`scripts/test_tenant_isolation_property.py`](file:///Users/sakshirai/AI_RAG_Assignment/scripts/test_tenant_isolation_property.py#L40-L95).
- **The Trade-Off Made**: Static 8/8 partitioning reduces per-tenant burst capacity (max 8 concurrent slots per tenant instead of 16).
- **What to Do Differently in Production**: Deploy isolated per-tenant model sidecars or an elastic slot controller with runtime `--slot-save-path` state wiping (`POST /slots/{id}?action=erase`).

---

### Q3: How do you prevent LLMs from hallucinating numbers in qualitative narrative answers?
- **The Honest Answer**: All LLM narrative generations are intercepted by `AnswerVerifier` before being returned to the user. `AnswerVerifier` extracts every numerical token from the candidate answer, normalizes scales (e.g. "1.2 billion" $\to 1,200,000,000$), canonicalizes units (e.g. "500 bps" $\to 5.0\%$), and checks them against the certified set of numbers in retrieved filing facts. If any ungrounded number is found, the generation is rejected and replaced with certified extractive quotes.
- **File & Line Number Proof**: [`app/domain/answer_verifier.py`](file:///Users/sakshirai/AI_RAG_Assignment/app/domain/answer_verifier.py#L45-L115) and [`tests/unit/test_answer_verifier.py`](file:///Users/sakshirai/AI_RAG_Assignment/tests/unit/test_answer_verifier.py#L20-L55).
- **The Trade-Off Made**: Narrative answers that perform valid unstated estimations or rounding approximations are intercepted and degraded to verbatim quotes.
- **What to Do Differently in Production**: Implement token-level constrained decoding (logits processors) that restrict generation to vocabulary tokens matching retrieved facts when generating quantities.

---

### Q4: How do you guarantee the system fits inside a 6.0 GB VRAM budget while serving 16 concurrent users?
- **The Honest Answer**: Through architectural model selection and quantized KV caching:
  1. `Qwen2.5-3B-Instruct` has only 2 KV heads (Grouped Query Attention), consuming $36.0\text{ KB/token}$ in FP16 ($3.1\times$ less than Llama-3.2-3B).
  2. In `q4_0` quantized KV cache (`-ctk q4_0 -ctv q4_0`), 16 parallel slots $\times$ 4,096 tokens consume exactly **648.00 MiB** (as reported in `llama-server` MTL0 startup logs).
  3. Weights occupy 1,840.0 MiB in Q4_K_M.
  4. Total process RSS is **2,813.0 MiB** (2.75 GiB), leaving **3.19 GiB of safety headroom (53.1%)** on a 6.0 GB budget.
- **File & Line Number Proof**: [`docs/KV_CACHE.md`](file:///Users/sakshirai/AI_RAG_Assignment/docs/KV_CACHE.md#L45-L75) and [`benchmarks/results/kv_level3_platform.json`](file:///Users/sakshirai/AI_RAG_Assignment/benchmarks/results/kv_level3_platform.json#L5-L10).
- **The Trade-Off Made**: `q4_0` KV quantization introduces slight perplexity degradation on very long sequences ($> 4\text{k tokens}$).
- **What to Do Differently in Production**: Use `q8_0` KV cache (1,224.0 MiB) on modern 8 GB or 16 GB GPUs for near-lossless precision.

---

### Q5: Why did you choose Qwen2.5-3B-Instruct over Llama-3.2-3B-Instruct?
- **The Honest Answer**: Llama-3.2-3B has 8 KV heads, requiring **7.00 GB of KV cache alone** for 16 slots at 4,096 tokens in FP16 (immediate OOM on 6 GB). `Qwen2.5-3B` has 2 KV heads, requiring only 2.25 GB in FP16 and 648.00 MiB in `q4_0`. Furthermore, Qwen2.5-3B has a 32,768 native context window, allowing it to survive Drop 2's context expansion to 8,192 tokens without truncation.
- **File & Line Number Proof**: [`docs/MODEL_CANDIDATES.md`](file:///Users/sakshirai/AI_RAG_Assignment/docs/MODEL_CANDIDATES.md#L30-L55) and [`DECISIONS.md`](file:///Users/sakshirai/AI_RAG_Assignment/DECISIONS.md#L38-L46) (Decision 3).
- **The Trade-Off Made**: Qwen's BPE tokenizer has a slightly larger vocabulary (152k tokens) which increases embedding table size in RAM.
- **What to Do Differently in Production**: Test DeepSeek-R1-Distill-Qwen-1.5B/7B for quantitative reasoning once GGUF quantization stabilizes.

---

### Q6: How do you achieve an 85%+ prefix cache hit rate on a local inference server?
- **The Honest Answer**: Standard dynamic prompts destroy prefix caching because timestamps, request IDs, or tenant names are placed near the beginning of the prompt. We implemented a **7-Layer Layout Contract** in `PromptBuilder`. Layers 1–3 contain static role instructions, JSON schemas, and tool definitions (702 tokens) which are identical across 100% of requests and pre-warmed at startup. Request IDs, timestamps, and user queries are placed strictly in Layer 7 at the bottom.
- **File & Line Number Proof**: [`app/domain/prompt_builder.py`](file:///Users/sakshirai/AI_RAG_Assignment/app/domain/prompt_builder.py#L30-L85) and [`tests/unit/test_prompt_builder.py`](file:///Users/sakshirai/AI_RAG_Assignment/tests/unit/test_prompt_builder.py#L19-L45).
- **The Trade-Off Made**: System instructions must remain frozen; adding dynamic in-context examples requires updating the static prefix contract and flushing slot cache.
- **What to Do Differently in Production**: Implement chunk-level prefix tree caching (Radix tree) with content-defined chunk hashing.

---

### Q7: What happens if the local LLM server crashes, OOMs, or times out?
- **The Honest Answer**: Foundation Lock 7 (Fallback) mandates that the platform must survive total model server failure. If `llama-server` is killed or times out:
  1. The connection error is caught by `RequestLifecycleManager`.
  2. The system switches to **Degraded Extractive Mode**.
  3. Certified SQL KPIs and verbatim filing passages are formatted directly into an answer with `status: ok_extractive` and caveat `"Degraded Mode: Model offline"`.
  4. The user receives certified facts in $< 100\text{ ms}$ with zero 500 errors.
- **File & Line Number Proof**: [`app/orchestration/request_lifecycle.py`](file:///Users/sakshirai/AI_RAG_Assignment/app/orchestration/request_lifecycle.py#L110-L145) and [`tests/integration/test_fault_injection.py`](file:///Users/sakshirai/AI_RAG_Assignment/tests/integration/test_fault_injection.py#L30-L65).
- **The Trade-Off Made**: The response lacks conversational polish and narrative synthesis; it is an extractive summary of filing quotes.
- **What to Do Differently in Production**: Maintain a secondary warm standby inference worker or cold fallback endpoint on a shared CPU cluster.

---

### Q8: How does the system handle Form 10-Q/A amendments and restated financial disclosures?
- **The Honest Answer**: We enforce Rule R2 from `docs/CONFLICT_POLICY.md`. When Form 10-Q/A amendments are ingested (e.g. `CEP-10QA-FY2023Q3` and `NWI-10QA-FY2024Q3`), the original filing rows are not deleted (preserving audit trail). Instead, an amended filing relation is established in `effective_line_items`. When querying `as_restated` basis, the amendment supersedes original numbers; when querying `as_originally_reported`, original values are returned.
- **File & Line Number Proof**: [`app/data/migrations.py`](file:///Users/sakshirai/AI_RAG_Assignment/app/data/migrations.py#L30-L75) and [`tests/integration/test_conflict_policy.py`](file:///Users/sakshirai/AI_RAG_Assignment/tests/integration/test_conflict_policy.py#L30-L60).
- **The Trade-Off Made**: Requires storing multiple versions of the same line item, slightly increasing database row count.
- **What to Do Differently in Production**: Implement temporal bitemporal tables (valid time vs transaction time) per SQL:2011 standards.

---

### Q9: Why is zero never used as a default fill for missing financial line items?
- **The Honest Answer**: In accounting, **zero is a valid number, not missing data**. Treating missing R&D as \$0 for a biotech company like Helix BioSystems would distort EBITDA and operating margins. Per Rule R6, missing inputs explicitly result in `status = 'missing_data'` and `kpi_value = missing_input`. The only exception is ARG and ZLG where explicit SEC disclosures state that no research activities exist.
- **File & Line Number Proof**: [`app/data/normalizer.py`](file:///Users/sakshirai/AI_RAG_Assignment/app/data/normalizer.py#L40-L85) and [`tests/integration/test_conflict_policy.py`](file:///Users/sakshirai/AI_RAG_Assignment/tests/integration/test_conflict_policy.py#L110-L135).
- **The Trade-Off Made**: Downstream ratios (like Interest Coverage or OpEx Ratio) cannot be computed when any required input is absent.
- **What to Do Differently in Production**: Support customizable tenant accounting policies where financial controllers can explicitly declare default imputation rules per entity.

---

### Q10: Why did you use hybrid retrieval (dense vectors + BM25) instead of pure vector search?
- **The Honest Answer**: Pure dense retrieval with `BAAI/bge-small-en-v1.5` achieved only **10.5% Recall@1** on financial filing queries because dense vectors struggle with exact corporate codes (e.g. "ARG-10K", "FY2023Q2") and financial keywords. By combining PostgreSQL BM25 Full-Text Search with dense embeddings via Reciprocal Rank Fusion ($k=60$), Recall@5 jumped to **94.7%**.
- **File & Line Number Proof**: [`app/domain/retrieval_service.py`](file:///Users/sakshirai/AI_RAG_Assignment/app/domain/retrieval_service.py#L40-L95) and [`benchmarks/results/retrieval.json`](file:///Users/sakshirai/AI_RAG_Assignment/benchmarks/results/retrieval.json).
- **The Trade-Off Made**: Running two queries (pgvector cosine + ts_rank) doubles database IO operations during search.
- **What to Do Differently in Production**: Pre-filter by metadata (company ID, fiscal year, filing type) in SQL before executing dense vector dot products.

---

### Q11: How do you handle non-aligned fiscal calendars across companies (e.g. ARG vs CEP)?
- **The Honest Answer**: Rule R7 checks entity fiscal year-ends before performing cross-company comparisons. Aurora Retail Group (ARG) operates on a 4-4-5 retail calendar ending January 31, while Cobalt Energy Partners (CEP) operates on a standard calendar ending December 31. Direct period matching (e.g. Q1 to Q1) represents mismatched calendar months. The QuestionResolver detects this and emits an explicit calendar non-alignment caveat.
- **File & Line Number Proof**: [`app/domain/question_resolver.py`](file:///Users/sakshirai/AI_RAG_Assignment/app/domain/question_resolver.py#L140-L180) and [`tests/integration/test_conflict_policy.py`](file:///Users/sakshirai/AI_RAG_Assignment/tests/integration/test_conflict_policy.py#L145-L165).
- **The Trade-Off Made**: Queries comparing ARG and CEP require extra explanation and cannot be reduced to a single unqualified percentage delta.
- **What to Do Differently in Production**: Map all quarterly filing periods to continuous calendar date intervals (e.g. start_date to end_date) and allow time-weighted prorated comparisons.

---

### Q12: Why did you use llama.cpp instead of vLLM or Ollama?
- **The Honest Answer**: vLLM has incomplete support for Apple Silicon Metal and cannot run containerized GPU workloads under macOS Docker without an NVIDIA GPU. Furthermore, vLLM's RadixAttention shares prefix KV blocks across all requests globally, risking cross-tenant cache hit timing leakage. `llama.cpp` provides deterministic per-slot memory allocation (`--no-context-shift`), explicit per-tenant slot assignment (`slot_id=N`), and native quantized KV cache (`q4_0`), operating stably in under 3 GB of RAM.
- **File & Line Number Proof**: [`DECISIONS.md`](file:///Users/sakshirai/AI_RAG_Assignment/DECISIONS.md#L550-L570) and [`docs/BLUEPRINT.md`](file:///Users/sakshirai/AI_RAG_Assignment/docs/BLUEPRINT.md#L150-L175).
- **The Trade-Off Made**: `llama.cpp` does not have dynamic PagedAttention memory defragmentation across arbitrary variable batch sizes.
- **What to Do Differently in Production**: On Linux clusters with NVIDIA A10G/L4 GPUs, deploy vLLM with custom tenant salt hashing or run dedicated per-tenant TensorRT-LLM container instances.

---

### Q13: Why did TTFT exceed 2,000 ms under 16 concurrent LLM prefill requests?
- **The Honest Answer**: Under 16 concurrent users running simultaneous narrative prefills on local Apple M4 hardware (4 CPU compute threads allocated to inference), GPU prefill compute is shared across slots, causing thread contention. Prefill throughput degrades from 331 tok/s (at 4 users) to 44.3 tok/s (at 16 users), pushing p95 TTFT to 2,800.5 ms. However, structured queries bypass the queue entirely (13.1 ms), and capping LLM queue concurrency to 4 in-flight requests achieves a 340.0 ms TTFT.
- **File & Line Number Proof**: [`benchmarks/results/kv_level3_platform.json`](file:///Users/sakshirai/AI_RAG_Assignment/benchmarks/results/kv_level3_platform.json) and [`DECISIONS.md`](file:///Users/sakshirai/AI_RAG_Assignment/DECISIONS.md#L570-L585).
- **The Trade-Off Made**: Bounding LLM concurrency to 4 in-flight requests causes excess narrative requests to wait briefly in the queue or receive 429 backpressure.
- **What to Do Differently in Production**: Deploy dual GPU instances separating prefill workers (high compute) from decode workers (memory bandwidth bound) via disaggregated serving.

---

### Q14: How is request replayability guaranteed for compliance audits (Black Box)?
- **The Honest Answer**: Every user query and generated response is logged to `answer_log` with cryptographic fingerprints:
  1. `prompt_template_hash`: SHA-256 of the exact rendered prompt template.
  2. `model_version`: SHA-256 of the GGUF model weights file.
  3. `retrieval_snapshot`: IDs and hashes of all retrieved filing chunks.
  4. `scripts/replay.py` re-executes the pipeline using logged facts. If prompt hash or model hash differs, replay halts with `HASH_MISMATCH`. Across 20 live requests, we measured a **100% exact match replay rate**.
- **File & Line Number Proof**: [`app/domain/prompt_builder.py`](file:///Users/sakshirai/AI_RAG_Assignment/app/domain/prompt_builder.py#L90-L125) and [`scripts/replay.py`](file:///Users/sakshirai/AI_RAG_Assignment/scripts/replay.py#L80-L120).
- **The Trade-Off Made**: Adds ~4 ms write latency to log full cryptographic fingerprints and chunk snapshot IDs on every turn.
- **What to Do Differently in Production**: Ship audit logs to an append-only WORM (Write Once, Read Many) cloud bucket (e.g. AWS S3 Object Lock) for immutable regulatory archiving.

---

### Q15: What happens if a third corporate tenant attempts to onboard dynamically?
- **The Honest Answer**: In the current implementation, `SlotManager` has a static dual-tenant partitioning contract (`acme` $\to$ slots 0..7, `borealis` $\to$ slots 8..15). If a tenant `charlie` attempts to query the system without administrative reconfiguration, `SlotManager.get_tenant_slots("charlie")` raises `ValueError`, resulting in an immediate 401/422 refusal. This fail-closed design strictly prevents unpartitioned tenants from invading another tenant's KV cache.
- **File & Line Number Proof**: [`app/orchestration/slot_manager.py`](file:///Users/sakshirai/AI_RAG_Assignment/app/orchestration/slot_manager.py#L40-L55) and [`DECISIONS.md`](file:///Users/sakshirai/AI_RAG_Assignment/DECISIONS.md#L535-L545).
- **The Trade-Off Made**: Onboarding a third tenant requires updating configuration and rebooting `llama-server` to allocate additional slots.
- **What to Do Differently in Production**: Implement dynamic tenant registration where a Tenant Management Service dynamically provisions slot quotas ($N_{slots} / N_{active\_tenants}$) and assigns ephemeral slot leases with runtime memory sanitization.
