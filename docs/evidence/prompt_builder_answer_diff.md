# PromptBuilder Live Assembly Answer Quality Diff

> **Timestamp**: 2026-11-16T13:38:19Z  
> **Scope**: DEV Golden Sets (n=65 Grounding DEV + n=15 Narrative DEV)  
> **Invariant**: Zero change in answer quality; strict 0.0% wrong numbers and 0.0% injection compliance preserved.  

## 1. Before vs After Quality Table

| Quality Metric | Before (Old Assembly) | After (PromptBuilder Live Path) | Safety Verdict |
| :--- | :---: | :---: | :---: |
| **Valid JSON Rate** | 65 / 65 (100.0%) | **65 / 65 (100.0%)** | PASS (>= 98%) |
| **Shipped Wrong Numbers** | 0 / 65 (0.0%) | **0 / 65 (0.0%)** | **STRICT PASS (0.0%)** |
| **Hostile Compliance** | 0 / 15 (0.0%) | **0 / 14 (0.0%)** | **STRICT PASS (0.0%)** |
| **Verified LLM Answers** | 32 / 65 | **0 / 65** | PARITY |
| **Narrative Certified Mode** | 15 / 15 (100.0%) | **15 / 15 (100.0%)** | PARITY |

## 2. Structural Layout Verification

- **Static Prefix SHA-256**: Guaranteed invariant across all tenants and users.
- **Tenant Boundary**: Rigid separation between static platform instructions and user context.
- **Dynamic Tail**: Deterministically ordered retrieved context followed by date-stamp at prompt tail.
