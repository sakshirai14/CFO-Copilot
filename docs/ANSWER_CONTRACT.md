# CFO Copilot Grounded-Answer Contract & Verification Specification

**Specification Version**: v1.0.0  
**Status**: ACTIVE & ENFORCED (Foundation Locks 1, 3, 4, 10, 11)  
**Governing Principle**: *A wrong number is worse than no answer.* Financial figures must come from deterministic SQL calculations or cited SEC disclosures, NEVER hallucinated by the model.

---

## 1. Grounding Principles & Invariants

1. **Deterministic Authority**:
   - The LLM is an *explanation and language synthesis engine*, NOT a calculator.
   - Any financial number (monetary amount, margin percentage, growth rate, ratio) appearing in the final answer MUST be traceable to an explicit input fact provided in the prompt context.
2. **Citation Integrity**:
   - The model must cite the unique `fact_id` for every piece of information used.
   - No fact ID may be cited if it was not present in the input prompt.
3. **Refusal Discipline**:
   - If data is absent, future-dated (e.g. FY2026/2027), out-of-scope (companies not in our 6), or if a ratio cannot be computed (e.g. division by zero, missing prior year), the model MUST return `status: "refused"` or `status: "missing_data"`.
   - The model is strictly prohibited from improvising, extrapolating, or synthesizing plausible-sounding numbers.
4. **Leakage & Hostility Defense**:
   - The model must never output system prompt fragments, database connection credentials, internal schema details, or external URLs.

---

## 2. JSON Response Contract Schema

Every generation from the local LLM must adhere strictly to the following JSON schema:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "GroundedAnswer",
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "enum": ["ok", "refused", "missing_data", "unsupported"]
    },
    "answer": {
      "type": "string",
      "description": "Professional, CFO-grade narrative answer with citations."
    },
    "facts_used": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of fact IDs from the input context supporting the answer."
    },
    "caveats": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Optional caveats regarding restatements, reporting period differences, or data limitations."
    }
  },
  "required": ["status", "answer", "facts_used", "caveats"],
  "additionalProperties": false
}
```

### Status Definitions:
- **`ok`**: The request was answerable from provided facts. All claims are grounded, and every extracted number has a matching fact citation.
- **`refused`**: The query asked for data outside system scope, an unanswerable future period (e.g. FY2026), or was an adversarial prompt injection probe.
- **`missing_data`**: The requested metric or quarter is physically absent from SEC filings (e.g. FY2021 prior revenue for YoY growth, or unreported R&D expense).
- **`unsupported`**: The query cannot be answered by SEC filing disclosures or financial statements.

---

## 3. Mathematical Number Matching & Tolerance

The deterministic verifier parses every numerical token in `answer` and verifies its presence in the cited `facts_used`.
To support human-readable CFO explanations, the verifier supports the following equivalences:
1. **Currency Scaling**:
   - `$109,200,000` $\leftrightarrow$ `$109.2M` $\leftrightarrow$ `109.2 million` $\leftrightarrow$ `$109,200 thousand`
2. **Percentage Representations**:
   - `0.2679` $\leftrightarrow$ `26.79%` $\leftrightarrow$ `26.8%` (relative rounding tolerance within 0.15% or 1 basis point)
3. **Ratios and Multipliers**:
   - `1.85` $\leftrightarrow$ `1.85x`
4. **Negative Sign Notation**:
   - `-$12.4M` $\leftrightarrow$ `($12.4M)` $\leftrightarrow$ `-$12,400,000` $\leftrightarrow$ `loss of $12.4M`

---

## 4. Deterministic Verification Pipeline (`AnswerVerifier`)

Before any answer is returned to the CFO, it is processed through `app/domain/answer_verifier.py`.
The verifier performs 5 rigorous checks:
1. **Schema Check**: Validates JSON formatting and mandatory keys (`status`, `answer`, `facts_used`, `caveats`).
2. **Fact Existence Check**: Asserts that every ID in `facts_used` existed in the input prompt.
3. **Numerical Grounding Check**: If status is `ok`, extracts all numbers from `answer` and proves each number matches at least one cited fact within tolerance. Any unmatched number flags the answer as `ungrounded`.
4. **Refusal Assertion Check**: If status is `refused` or `missing_data`, asserts that `answer` does NOT contain affirmative monetary assertions or claims to have answered the question.
5. **Security Leakage Check**: Scans `answer` against banned regex patterns (connection strings, passwords, `postgres://`, developer mode jailbreak echoes).

If verification fails, the system **rejects the output**, logs the contract violation, and returns a safe fallback refusal.
