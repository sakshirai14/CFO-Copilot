.PHONY: up down ingest kpis index retrieval-eval test report selfcheck bench clean audit puzzle2-eval model-up model-down eval-models help

MODEL_FILE ?= models/qwen2.5-3b-instruct-q4_k_m.gguf
MODEL_PORT ?= 8080
MODEL_SLOTS ?= 16
MODEL_CTX ?= 65536

VENV_PYTHON := ./.venv/bin/python3
PYTHON := $(shell if [ -f $(VENV_PYTHON) ]; then echo $(VENV_PYTHON); else echo python3; fi)

help:
	@echo "CFO Copilot - Available Targets:"
	@echo "  make up          - Start PostgreSQL+pgvector DB, configure roles, and run migrations"
	@echo "  make down        - Stop Docker Compose services"
	@echo "  make ingest      - Ingest Drop 1 and Drop 2 into PostgreSQL and generate report"
	@echo "  make kpis        - Compute 16 KPIs in pure SQL across all companies and periods"
	@echo "  make index       - Run deterministic chunking and vector embedding pipeline"
	@echo "  make retrieval-eval - Run retrieval benchmark against retrieval_eval.csv"
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

index:
	@echo "[make index] Running deterministic chunking and vector embedding pipeline..."
	$(PYTHON) scripts/index_chunks.py

retrieval-eval:
	@echo "[make retrieval-eval] Running retrieval benchmark against retrieval_eval.csv..."
	$(PYTHON) scripts/eval_retrieval.py

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

model-up:
	@echo "[make model-up] Starting llama-server with $(MODEL_FILE) on port $(MODEL_PORT)..."
	@mkdir -p logs
	@llama-server -m $(MODEL_FILE) -c $(MODEL_CTX) -np $(MODEL_SLOTS) --port $(MODEL_PORT) --host 127.0.0.1 --jinja > logs/llama_server.log 2>&1 & echo $$! > logs/llama_server.pid
	@echo "[make model-up] Waiting for llama-server to be ready on port $(MODEL_PORT)..."
	@for i in $$(seq 1 45); do \
		if curl -s http://127.0.0.1:$(MODEL_PORT)/health | grep -q 'ok'; then \
			echo "[make model-up] llama-server ready on http://127.0.0.1:$(MODEL_PORT) (PID: $$(cat logs/llama_server.pid))"; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "[ERROR] llama-server failed to start! Check logs/llama_server.log"; exit 1

model-down:
	@echo "[make model-down] Stopping llama-server..."
	@if [ -f logs/llama_server.pid ]; then \
		kill -9 $$(cat logs/llama_server.pid) 2>/dev/null || true; \
		rm -f logs/llama_server.pid; \
		echo "[make model-down] llama-server stopped."; \
	else \
		pkill -9 llama-server 2>/dev/null || true; \
		echo "[make model-down] llama-server stopped via pkill."; \
	fi

eval-models:
	@echo "[make eval-models] Running model comparison and grounding evaluation..."
	$(PYTHON) scripts/eval_models.py

agent-eval:
	@echo "[make agent-eval] Running ADK agent evaluation against agent_questions.jsonl..."
	$(PYTHON) scripts/eval_adk_agents.py

adk-eval:
	@echo "[make adk-eval] Running Google ADK agent test suite..."
	$(PYTHON) scripts/eval_adk_agents.py
