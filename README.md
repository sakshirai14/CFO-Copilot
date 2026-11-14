# CFO Copilot on a Budget

> A private, self-hosted financial assistant for a CFO, designed for strict financial accuracy, prefix-cached local inference on small open-weight LLMs, and multi-tenant isolation.

## Project Status: Phase 0 Complete (Repo Skeleton & Orientation)

This repository implements the 3-day **CFO Copilot on a Budget** platform according to the 11 Foundation Locks and 5 Core Puzzles.

### Core Architectural Pillars
1. **The Wrong Number is Worse Than No Answer**: All financial calculations and KPI evaluations are strictly deterministic (SQL / domain engine). The LLM never hallucinates financial numbers.
2. **Private & Self-Hosted**: 100% local inference using open-weight small models (e.g., Qwen2.5-3B-Instruct) via OpenAI-compatible serving engine with prefix caching. Zero hosted LLM APIs.
3. **KV-Cache Optimization**: Structured prefix cache layout, static-first system prompts, tool schema stabilization, and session hysteresis designed to sustain 16 concurrent users within a 6 GB VRAM budget.
4. **Google ADK Orchestration**: Root and specialized domain sub-agents (Router, KPI/SQL, RAG, Verifier) adhering to an average of $\le 2$ LLM calls per query.
5. **Robust Security & Data Integrity**: Multi-tenant isolation (Tenant A and B), provenance tracking for every reported figure, strict defense-in-depth against prompt injection in filing corpora.

### Repository Layout
```text
.
├── app/                  # Application source code
│   ├── api/              # Typed OpenAPI endpoints, streaming SSE/WebSocket
│   ├── orchestration/    # Request queue, concurrency bounds, retry/backoff
│   ├── agents/           # Google ADK root and specialized sub-agents
│   ├── domain/           # KPI calculators, conflict policies, accounting logic
│   ├── inference/        # Local LLM connector (LiteLLM / OpenAI-compatible client)
│   ├── data/             # Database access, ORM models, vector retrieval
│   └── core/             # Configuration, logging, telemetry, errors
├── benchmarks/           # Benchmark scripts and raw measurement outputs
│   └── results/          # Committed JSON benchmark runs
├── data_pack/            # Vendor data pack (CANDIDATE_PACK and DROP2_RELEASE)
├── docs/                 # Platform blueprints, audit, candidate evaluation
│   ├── evidence/         # Raw command output and execution logs
│   ├── DATA_MAP.md       # Data pack orientation and Drop 1 vs Drop 2 relation
│   ├── DATA_AUDIT.md     # Full empirical audit of financial statements and corpus
│   ├── DIAGNOSIS_PUZZLE2.md # Puzzle 2 prefix-cache log analysis & simulation
│   ├── HARDWARE.md       # Host environment detection and serving strategy
│   ├── MODEL_CANDIDATES.md # GGUF candidate specs and KV memory budgets
│   └── PLAN.md           # 3-day execution roadmap and status table
├── migrations/           # Database schema migrations
├── scripts/              # Audit, log analysis, and ingestion scripts
├── tests/                # Automated test suite (unit, integration, evals, security)
└── ui/                   # Streaming chat interface with "Show Your Work" panel
```

### Reproducibility Commands
- Re-run Data Audit: `make audit` (or `python3 scripts/audit_data_pack.py`)
- Re-run Puzzle 2 Log Diagnosis: `make puzzle2-eval` (or `python3 scripts/analyze_request_log.py`)
