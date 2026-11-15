# Audit of Minimal Prompt Variant Discrepancy (Step 1b vs Step 5)

## Summary of Observation
In early Phase 4b reporting, two tables presented seemingly contradictory results for the `minimal` prompt variant:
- **Step 1b Diagnosis (`scripts/diagnose_step1.py`)**: Reported 15 JSON syntax errors / truncations (`finish_reason = length`), 0% valid JSON under standard sampling.
- **Step 5 Full Benchmark (`scripts/eval_models.py`)**: Reported 100.0% valid JSON, 0 unparsed completions, but 3 ungrounded numbers.

## Root Cause Analysis & Server Parameter Reconciliation

The divergence stems entirely from the runtime inference parameters and grammar enforcement applied during each evaluation step:

| Parameter / Configuration | Step 1b Diagnosis (`diagnose_step1.py`) | Step 5 Benchmark (`eval_models.py`) | Reason for Difference |
| :--- | :--- | :--- | :--- |
| **Grammar Enforcement** | `None` (Raw unconstrained generation) | `response_format` with GBNF JSON Schema (`STRICT_SCHEMA`) | Step 1b tested unguided LLM capability; Step 5 enforced grammar at tokenizer level. |
| **`max_tokens`** | 256 tokens | 512 tokens | 256 tokens was too short for multi-fact JSON, causing truncation on verbose answers. |
| **`presence_penalty`** | `0.0` | `0.3` | Prevented token oscillation loops on repetitive JSON keys. |
| **`temperature`** | `0.0` (greedy) | `0.0` (greedy) | Identical deterministic sampling. |
| **`seed`** | 42 | 42 | Identical pseudo-random seed. |

## Detailed Breakdown of Outcomes

1. **Why Step 1b Failed JSON Syntax**:
   - Without a grammar compiler constraint, Qwen2.5-3B under `minimal` generated introductory conversational prose (e.g. *"Here is the financial data in JSON format:"*) followed by multi-line JSON.
   - Combined with the 256-token ceiling, the closing brackets `}` were clipped, resulting in `finish_reason = "length"` and syntax parse errors.

2. **Why Step 5 Passed JSON Syntax but Failed Grounding**:
   - In Step 5, the server enforced the strict GBNF grammar with `max_tokens = 512`. The model was structurally forced to output 100% syntactically valid JSON matching `AnswerEnvelope`.
   - However, because the `minimal` prompt text contained **no negative constraints** (no instruction to refuse when data is missing, no rule against hallucinating unstated periods), the model outputted valid JSON containing hallucinated values (e.g. dev-04 hallucinated $109.2B; dev-12 hallucinated 15.4% YoY growth).

## Architectural Conclusion
Grammar enforcement guarantees syntactic validity (100% valid JSON), but **cannot guarantee semantic truth**. Grounding and refusal discipline require the combination of:
1. `explicit_rules` prompt architecture (teaching the model when to refuse).
2. Deterministic `AnswerVerifier` (rejecting any hallucinated number).
3. Deterministic template fallback (replacing rejected answers with verified SQL numbers).
