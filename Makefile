.PHONY: up down test selfcheck bench clean audit puzzle2-eval help

PYTHON ?= python3

help:
	@echo "CFO Copilot - Available Targets:"
	@echo "  make up          - Start local services (stub)"
	@echo "  make down        - Stop local services (stub)"
	@echo "  make test        - Run test suite (unit, integration, security)"
	@echo "  make selfcheck   - Run end-to-end selfcheck against golden set"
	@echo "  make bench       - Run benchmarks (KV cache, latency, concurrency)"
	@echo "  make audit       - Re-run Phase 0 data audit"
	@echo "  make puzzle2-eval- Re-run Phase 0 Puzzle 2 request log diagnosis"

up:
	@echo "[STUB] Starting CFO Copilot services..."
	@echo "Services startup will be wired in Phase 2/Phase 5."

down:
	@echo "[STUB] Stopping CFO Copilot services..."
	@echo "Services shutdown will be wired in Phase 2/Phase 5."

test:
	@echo "Running test suite..."
	$(PYTHON) -m pytest tests/ -v || echo "Tests pending implementation in subsequent phases."

selfcheck:
	@echo "Running one-command self-check against golden question set..."
	@echo "Self-check pipeline will be wired in Phase 5."

bench:
	@echo "Running KV cache and serving latency benchmarks..."
	@echo "Benchmark suite will be wired in Phase 7."

audit:
	$(PYTHON) scripts/audit_data_pack.py

puzzle2-eval:
	$(PYTHON) scripts/analyze_request_log.py
