.PHONY: up down ingest kpis test report selfcheck bench clean audit puzzle2-eval help

VENV_PYTHON := ./.venv/bin/python3
PYTHON := $(shell if [ -f $(VENV_PYTHON) ]; then echo $(VENV_PYTHON); else echo python3; fi)

help:
	@echo "CFO Copilot - Available Targets:"
	@echo "  make up          - Start PostgreSQL+pgvector DB, configure roles, and run migrations"
	@echo "  make down        - Stop Docker Compose services"
	@echo "  make ingest      - Ingest Drop 1 and Drop 2 into PostgreSQL and generate report"
	@echo "  make kpis        - Compute 16 KPIs in pure SQL across all companies and periods"
	@echo "  make test        - Run unit and integration tests against isolated test database"
	@echo "  make report      - Re-generate Phase 1 verification report (docs/evidence/phase1_report.txt)"
	@echo "  make selfcheck   - Run end-to-end selfcheck against golden set (Phase 5)"
	@echo "  make bench       - Run benchmarks (Phase 7)"
	@echo "  make audit       - Re-run Phase 0 data audit"
	@echo "  make puzzle2-eval- Re-run Phase 0 Puzzle 2 request log diagnosis"

up:
	@./scripts/bootstrap_env.sh
	@echo "[make up] Starting PostgreSQL + pgvector container..."
	docker compose up -d
	@echo "[make up] Ensuring databases and roles are configured..."
	$(PYTHON) scripts/setup_db_roles.py
	@echo "[make up] Applying database migrations to main and test databases..."
	$(PYTHON) app/data/migrations.py
	$(PYTHON) app/data/migrations.py --test
	@echo "[make up] Database services and migrations successfully initialized."

down:
	@echo "[make down] Stopping Docker Compose services..."
	docker compose down

ingest:
	@echo "[make ingest] Ingesting Drop 1 and Drop 2 datasets..."
	$(PYTHON) scripts/ingest.py
	@echo "[make ingest] Generating Phase 1 verification report..."
	$(PYTHON) scripts/phase1_report.py

kpis:
	@echo "[make kpis] Computing 16 KPIs in pure SQL across all companies and periods..."
	$(PYTHON) scripts/compute_kpis.py

test:
	@echo "[make test] Running test suite against test database..."
	$(PYTHON) -m pytest tests/ -v

report:
	$(PYTHON) scripts/phase1_report.py

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
