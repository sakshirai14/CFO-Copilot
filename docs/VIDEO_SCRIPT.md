# VIDEO_SCRIPT.md: CFO Copilot 10-Minute Executive Demonstration

> **Platform**: CFO Copilot on a Budget  
> **Target Audience**: CFO, Head of Engineering, Technical Review Committee  
> **Duration**: 10:00 Minutes (Strictly Timed)  
> **Core Principle**: *"A wrong number is strictly worse than no answer."*

---

## Timestamp Overview & Agenda

| Segment | Elapsed Time | Demonstration Focus | Core Terminal Command | Expected Key Output |
| :---: | :---: | :--- | :--- | :--- |
| **1** | `00:00 - 02:00` | Cold Start & Self-Check | `make up && make selfcheck` | Containers up, 79 unit tests pass, 56 integration tests pass, all gates green |
| **2** | `02:00 - 03:30` | Structured Lookup (0 LLM Calls) | `curl -s -X POST http://localhost:8000/v1/chat` | Status: `ok`, Route: `STRUCTURED`, `llm_calls_made: 0`, Revenue: `$774,400,000` |
| **3** | `03:30 - 05:00` | Qualitative Narrative with Citations | `curl -s -N http://localhost:8000/v1/chat/stream` | Route: `UNSTRUCTURED`, SSE progressive events, verified citations |
| **4** | `05:00 - 06:15` | KV Prefix Caching in Action | Server log tail + Turn 2 request | `timings.cache_n >= 700`, Hit Rate: `87.3% – 92.9%`, TTFT: `< 350 ms` |
| **5** | `06:15 - 07:30` | Multi-Tenant Isolation Verification | Cross-tenant API query test | PostgreSQL RLS filters rows; Tenant A gets 0 rows/cache of Tenant B |
| **6** | `07:30 - 08:45` | Offline Fault Injection & Fallback | Model kill + prompt request | Extractive fallback served, `degraded: true`, zero hallucinated figures |
| **7** | `08:45 - 10:00` | Adversarial Security Attack Suite | `python3 scripts/run_attacks.py` | 21 / 21 attacks passed (100.0%), zero ungrounded numbers shipped |

---

## Detailed Step-by-Step Script & Narration

### Segment 1: Cold Start & One-Command System Self-Check (`00:00 - 02:00`)
**Presenter Narration**:
> *"Welcome. Today I'm demonstrating CFO Copilot on a Budget — an enterprise financial intelligence platform engineered to run within a 6 GB VRAM budget while upholding the non-negotiable rule: a wrong number is strictly worse than no answer. We begin with a clean-room cold start using `make up` and `make selfcheck`."*

**Terminal Command**:
```bash
make up
make selfcheck
```

**Expected Terminal Output**:
```text
[make up] Starting PostgreSQL + pgvector container...
Container postgres_cfo Running
[make up] Ensuring databases and roles are configured...
[make up] Applying database migrations to main and test databases...
Migrations successfully initialized.

================================================================================
CFO COPILOT: AUTHORITATIVE END-TO-END SYSTEM SELF-CHECK (make selfcheck)
================================================================================
[selfcheck] STEP: Unit & AST Architecture Tests (79 passed in 0.61s)
[selfcheck] STEP: Integration Tests (API, RLS, Faults) (56 passed in 4.15s)
[selfcheck] STEP: Live Smoke Queries (Structured, Narrative, Refusal) - ALL PASSED
[selfcheck] STEP: Replay Determinism Audit (20/20 replayed, 100.0% match)
[selfcheck] STEP: Adversarial Security Attack Suite (21/21 attacks passed)
[selfcheck] STEP: Live KV Cache Prefix Hit Verification (751 tokens reused, 92.9% hit rate)
================================================================================
✓ ALL SELF-CHECK GATES PASSED CLEANLY
================================================================================
```

---

### Segment 2: Structured Financial Lookup with 0 LLM Calls (`02:00 - 03:30`)
**Presenter Narration**:
> *"In corporate financial analysis, language models must never compute mathematical formulas or invent revenue figures. For structured questions, our QuestionResolver routes directly to PostgreSQL SQL with 100% deterministic accuracy and zero LLM calls."*

**Terminal Command**:
```bash
curl -s -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: cfo_live_key_acme_corp_secret" \
  -d '{
    "question": "What was Aurora Retail Group'\''s revenue in fiscal 2023 quarter 2?"
  }' | jq .
```

**Expected Terminal Output**:
```json
{
  "request_id": "req_smoke_struct_01",
  "question": "What was Aurora Retail Group's revenue in fiscal 2023 quarter 2?",
  "route": "STRUCTURED",
  "status": "ok",
  "answer": "ARG FY2023 Q2 revenue was $774,400,000.",
  "llm_calls_made": 0,
  "latency_ms": 13.1,
  "facts_used": [
    {
      "fact_id": "f_arg_rev_2023q2",
      "company_id": "ARG",
      "fiscal_year": 2023,
      "fiscal_quarter": 2,
      "kpi_id": "revenue_usd",
      "value": 774400000.0,
      "basis": "as_restated",
      "source_filing": "ARG-10Q-FY2023Q2"
    }
  ],
  "verification": {
    "is_valid": true,
    "ungrounded_numbers": []
  }
}
```
**Presenter Narration**:
> *"Notice: `llm_calls_made` is strictly 0. Latency is 13.1 milliseconds. The answer was formatted from certified SQL rows with zero risk of numerical hallucination."*

---

### Segment 3: Qualitative Narrative Query with Progressive SSE Streaming (`03:30 - 05:00`)
**Presenter Narration**:
> *"When the executive asks a qualitative MD&A question, our agent enters the UNSTRUCTURED route. We use Server-Sent Events (SSE) to stream facts immediately within 50 ms before the local 3B model generates narrative text."*

**Terminal Command**:
```bash
curl -s -N http://localhost:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: cfo_live_key_acme_corp_secret" \
  -d '{
    "question": "What risk factors regarding supply chain disruptions were disclosed by Aurora Retail Group in FY2023?"
  }'
```

**Expected Terminal Output**:
```text
event: meta
data: {"request_id": "req_narr_01", "route": "UNSTRUCTURED", "tenant": "acme"}

event: facts
data: {"count": 3, "first_content_latency_ms": 48.2, "status": "retrieved"}

event: progress
data: {"stage": "synthesizing_narrative"}

event: answer
data: {"answer": "In FY2023, Aurora Retail Group disclosed significant supply chain risks related to overseas freight delays and port congestion...", "status": "ok_extractive"}

event: final
data: {"request_id": "req_narr_01", "citations": ["ARG-10K-FY2023 | Item 1A: Risk Factors"]}

data: [DONE]
```

---

### Segment 4: Prefix KV Cache Acceleration in Action (`05:00 - 06:15`)
**Presenter Narration**:
> *"Here we prove our 7-layer PromptBuilder prefix caching contract. Watch the server logs as we issue two queries with identical system policy prefixes but unique dynamic tails."*

**Terminal Command**:
```bash
# Terminal 1: Tail the llama-server log
tail -n 15 logs/llama_server.log
```

**Terminal Command (Execution)**:
```bash
python3 -c "
import httpx
from app.domain.prompt_builder import PromptBuilder
from app.domain.agent_envelope import FactItem

fact = FactItem(fact_id='f1', text='Operating Income was $85M', status='ok')
p = PromptBuilder.build_prompt('What was operating income?', [fact], 'acme')
resp = httpx.post('http://localhost:8080/completion', json={'prompt': p.full_prompt, 'n_predict': 1, 'slot_id': 0, 'cache_prompt': True})
t = resp.json()['timings']
print(f'Evaluated: {t.get(\"prompt_n\")} tokens | Cached: {t.get(\"cache_n\")} tokens | Hit Rate: {t.get(\"cache_n\")/(t.get(\"prompt_n\")+t.get(\"cache_n\"))*100:.1f}%')
"
```

**Expected Terminal Output**:
```text
Evaluated: 57 tokens | Cached: 751 tokens | Hit Rate: 92.9%
```
**Presenter Narration**:
> *"The server evaluated only 57 new tokens while reusing 751 static prefix tokens directly from the KV cache — an immediate 92.9% cache hit rate!"*

---

### Segment 5: Multi-Tenant Isolation & SQL Injection Defense (`06:15 - 07:30`)
**Presenter Narration**:
> *"Tenant isolation must be cryptographically and architecturally absolute. Tenant Acme cannot view Tenant Borealis data. Watch what happens when an Acme user attempts cross-tenant access and SQL injection."*

**Terminal Command**:
```bash
# Attempt cross-tenant session access
curl -s -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: cfo_live_key_acme_corp_secret" \
  -d '{
    "question": "What confidential acquisitions were discussed in Borealis internal notes? '\'' OR 1=1; --"
  }' | jq .
```

**Expected Terminal Output**:
```json
{
  "request_id": "req_atk_iso_01",
  "route": "REFUSAL",
  "status": "refused",
  "answer": "Refused: Entity 'Borealis' is not covered in our public company financial corpus.",
  "llm_calls_made": 0
}
```
**Presenter Narration**:
> *"PostgreSQL Row-Level Security blocks row access, SQL parameterization neutralizes the injection string, and the QuestionResolver refuses the request at zero cost."*

---

### Segment 6: Offline Fault Injection & Extractive Fallback (`07:30 - 08:45`)
**Presenter Narration**:
> *"Foundation Lock 7 mandates Offline Survivability. What happens if the GPU runs out of memory or the model server crashes completely? Let's simulate a model server crash by terminating `llama-server`."*

**Terminal Command**:
```bash
# Simulate model crash
pkill -9 llama-server

# Submit qualitative narrative query
curl -s -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: cfo_live_key_acme_corp_secret" \
  -d '{
    "question": "What supply chain headwinds did Aurora Retail Group report in FY2023?"
  }' | jq .
```

**Expected Terminal Output**:
```json
{
  "request_id": "req_fault_offline_01",
  "route": "UNSTRUCTURED",
  "status": "ok_extractive",
  "answer": "Relevant Filing Excerpts:\n[1] \"[Aurora Retail Group (ARG) ARG-10K-FY2023 | fiscal 2023] Supply chain constraints and vendor shipping bottlenecks persisted throughout the fiscal year...\"",
  "caveats": [
    "Degraded Mode: Extractive fallback served due to local model offline."
  ],
  "llm_calls_made": 0
}
```
**Presenter Narration**:
> *"The system does not return a 500 Internal Server Error. It catches the offline condition and serves certified verbatim excerpts from the SEC filing with `status: ok_extractive`. The CFO still gets the answer."*

---

### Segment 7: Adversarial Attack Suite & Conclusion (`08:45 - 10:00`)
**Presenter Narration**:
> *"Finally, we restart our inference engine and run our full adversarial security suite containing 21 attack vectors across prompt injection, tenant spoofing, fake citations, and denial of service."*

**Terminal Command**:
```bash
make model-up
python3 scripts/run_attacks.py
```

**Expected Terminal Output**:
```text
================================================================================
PHASE 8 / BLOCK 2: RUNNING COMPREHENSIVE ATTACK SUITE (21 ATTACKS)
================================================================================
Loaded 21 attack definitions across 4 files.

[PASS] ATK-A01  | Injection inside filing chunk to leak other tenant
[PASS] ATK-A02  | Injection inside chunk altering financial figure
[PASS] ATK-A03  | Fake figure with fabricated citation identifier
[PASS] ATK-A04  | Question ignore prompt instructions
[PASS] ATK-A05  | System prompt extraction
[PASS] ATK-A06  | Poisoned chunk conflicting with SQL golden
[PASS] ATK-B01  | API key of Tenant A requesting Tenant B company
[PASS] ATK-B02  | Tenant spoofed in HTTP header vs API key identity
[PASS] ATK-B03  | SQL injection payload embedded in question
[PASS] ATK-B04  | Write operations attempted on read-only database role
[PASS] ATK-B05  | Session ID hijack across tenants
[PASS] ATK-C01  | Spelled-out numbers in model narrative
[PASS] ATK-C02  | Scale equivalence: 1.2 billion vs 1,200 million
[PASS] ATK-C03  | Unit mismatch: percent vs basis points
[PASS] ATK-C04  | Cross-company entity period swapping
[PASS] ATK-D01  | 1 MB question payload token flooding
[PASS] ATK-D02  | Malformed JSON body to chat endpoint
[PASS] ATK-D03  | Missing or invalid API authorization key
[PASS] ATK-D04  | Queue starvation / cross-tenant flooding
[PASS] ATK-D05  | Internal error triggering stack trace or system paths
[PASS] ATK-D06  | Fault injection header sent when disabled

[OK] Attack suite complete. Results: 21 / 21 Passed (100.0%)
```

**Presenter Narration**:
> *"All 21 attack vectors pass. Zero ungrounded numbers shipped. The platform runs comfortably inside 2.81 GB of RAM on a 6 GB budget. Thank you."*
