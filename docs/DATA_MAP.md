# DATA_MAP.md: Workspace Data Inventory and Release Analysis

This document provides a comprehensive mapping of all data assets present in `data_pack/`, defines their puzzle mapping, quotes authoritative statements from vendor READMEs, and analyzes the structural and semantic relationship between `CANDIDATE_PACK` (Drop 1) and `DROP2_RELEASE` (Drop 2).

---

## 1. Directory Tree & File Inventory

```text
data_pack/
├── CANDIDATE_PACK/
│   ├── README.md                      # Overview of initial candidate pack and rules
│   ├── data_dictionary.csv            # Detailed schema definitions for all columns
│   ├── puzzle1_data/
│   │   ├── companies.csv              # Reference master of the initial 5 companies
│   │   ├── corpus_documents.csv       # 64 filing text documents and other corporate docs
│   │   ├── filings_index.csv          # Metadata for 61 filings (10-K, 10-Q)
│   │   ├── financial_statements_raw.csv # 1,449 extracted financial line items
│   │   └── kpi_glossary.csv           # 16 authoritative KPI formulas and computation rules
│   ├── puzzle2_data/
│   │   ├── reference_hardware_and_model.csv # GPU hardware budget & reference 3.1B GQA specs
│   │   └── request_log.csv            # 220 chat requests logged by existing platform
│   ├── puzzle3_data/
│   │   └── starter_test_cases.csv     # 12 test cases (normal, conflict, missing data)
│   └── puzzle4_data/
│       └── dev_questions.csv          # 21 development questions with routes and gold answers
└── DROP2_RELEASE/
    ├── README_DROP2.md                # Specifications for Drop 2 requirements & changes
    └── data/
        ├── companies_new.csv          # 1 row: 6th company (Zephyr Logistics Ltd. / ZLG)
        ├── corpus_documents_new.csv   # 13 docs: 12 ZLG filings + 1 NWI 10-Q/A amendment
        ├── filings_index_new.csv      # 13 filings: 12 ZLG filings + 1 NWI 10-Q/A filing
        └── financial_statements_raw_new.csv # 283 rows: 261 ZLG rows + 22 NWI 10-Q/A rows
```

---

## 2. File-by-File Specification & Puzzle Mapping

| Relative Path | Primary Puzzle | Secondary Puzzle | Description & Format |
| :--- | :--- | :--- | :--- |
| `CANDIDATE_PACK/README.md` | All | Foundations | Overview, vendor notices, and guidelines. |
| `CANDIDATE_PACK/data_dictionary.csv` | All | Foundation 5 | 66 rows defining every file, column name, and business meaning. |
| `puzzle1_data/companies.csv` | Puzzle 1 | Puzzle 4 | 5 companies: ticker, company name, industry sector, reporting currency, fiscal year convention note. |
| `puzzle1_data/filings_index.csv` | Puzzle 1 | Puzzle 4 | 61 filings: filing ID, company ID, form type (10-K, 10-Q), fiscal year, quarter, period end, filing date, doc_id, reporting unit. |
| `puzzle1_data/financial_statements_raw.csv` | Puzzle 1 | Puzzle 4 | 1,449 rows: raw extracted line items across Income Statement (IS), Balance Sheet (BS), and Cash Flow (CF) statements. |
| `puzzle1_data/kpi_glossary.csv` | Puzzle 1 | Puzzle 4 | 16 authoritative KPI definitions, explicit formulas, target units (percent, ratio, USD), and accounting notes. |
| `puzzle1_data/corpus_documents.csv` | RAG / P5 | P3, P4 | 64 full-text documents (filings and disclosures) with markdown tables, used for semantic retrieval and adversarial analysis. |
| `puzzle2_data/reference_hardware_and_model.csv` | Puzzle 2 | Architecture | 14 parameters defining deployment targets: 6 GB VRAM, 1.5 GB runtime, 3.1B parameter GQA model, 16 concurrent users. |
| `puzzle2_data/request_log.csv` | Puzzle 2 | Foundations | 220 logged chat requests with decomposed prompt segments, token counts, cached token counts, and TTFT metrics. |
| `puzzle3_data/starter_test_cases.csv` | Puzzle 3 | Foundation 10 | 12 starter test cases evaluating model behavior on normal queries, real-world fact conflicts, and required data absence (refusals). |
| `puzzle4_data/dev_questions.csv` | Puzzle 4 | P3, P5 | 21 development questions with expected classification routes (`sql`, `rag`, `both`, `none`), answers, and tolerances. |
| `DROP2_RELEASE/README_DROP2.md` | P1, P2, P4 | Foundations | The Day 2 assignment twist specifying company 6 (ZLG), amendment (NWI 10-Q/A), 8k context window, and confidence scores. |
| `DROP2_RELEASE/data/companies_new.csv` | Puzzle 1 | Foundation 5 | Master record for Zephyr Logistics Ltd. (ZLG). |
| `DROP2_RELEASE/data/filings_index_new.csv` | Puzzle 1 | Foundation 4, 5 | 12 filings for ZLG (FY2022 Q1..Q4 through FY2024 Q1..Q4) + 1 filing for NWI (`NWI-10QA-FY2024Q3`). |
| `DROP2_RELEASE/data/corpus_documents_new.csv` | RAG / P5 | P1, P3, P4 | 12 full-text filings for ZLG + 1 full-text amended filing for NWI (`NWI-10QA-FY2024Q3`). |
| `DROP2_RELEASE/data/financial_statements_raw_new.csv` | Puzzle 1 | P1, P4 | 283 raw financial rows (261 rows for ZLG across 12 periods, 22 rows for NWI FY2024 Q3 amended line items). |

---

## 3. Relationship Between CANDIDATE_PACK and DROP2_RELEASE

### Does Drop 2 Replace, Extend, Correct, or Conflict?
Drop 2 exhibits a dual relationship:
1. **Extends (Additive)**: It extends the enterprise universe by introducing a 6th company (`ZLG` - Zephyr Logistics Ltd.) with 12 quarters of complete filing history (FY2022 Q1 through FY2024 Q4).
2. **Corrects & Conflicts (Amendatory)**: It amends an existing quarter for company `NWI` (`FY2024Q3`). It does not replace earlier files wholesale. Instead, `NWI-10QA-FY2024Q3` introduces restated numbers that directly conflict with the original `NWI-10Q-FY2024Q3` filing in `CANDIDATE_PACK`.
3. **Does NOT Replace**: Drop 2 is an incremental patch/delta, not a standalone replacement. Drop 1 files must remain in place as the initial baseline.

### Authoritative Vendor Quotes
From `data_pack/CANDIDATE_PACK/README.md`:
> *"All companies, filings and figures are FICTIONAL and were produced for this exercise. The data comes from an automated extraction process and has NOT been cleaned for you. Treat it the way you would treat data from an outside vendor."* (Lines 7-8)
>
> *"- Sign conventions, labels, units and date formats are as extracted. Documenting and handling them is part of your job.*
> *- The `kpi_glossary.csv` formulas are authoritative for this project.*
> *- The hidden evaluation set is larger than the development set and is not in this pack.*
> *- Reference hardware figures are for budgeting only."* (Lines 24-27)

From `data_pack/DROP2_RELEASE/README_DROP2.md`:
> *"Four things changed. Adapt your system, then hand in a short diff note.*
> *## 1. A sixth company*
> *Zephyr Logistics Ltd. (ZLG) joins the CFO's coverage list. See the files in `data/`. It has its own fiscal calendar. Add it through a proper schema migration, not by editing tables by hand.*
> *## 2. A filing amendment*
> *the document `NWI-10QA-FY2024Q3` in `data/corpus_documents_new.csv` and the matching rows in `data/financial_statements_raw_new.csv` amend a quarter already in your database. Decide how your policy handles it, and show that earlier answers change (or do not change) for the reason your policy says.*
> *## 3. Longer contexts*
> *The CFO now wants whole filings in context. Your maximum context length rises from **4,096 to 8,192 tokens**. GPU (6 GB), concurrency target and p95 TTFT target are unchanged. Show what you gave up to stay inside the budget.*
> *## 4. A new product requirement: confidence*
> *Every answer must now carry a `confidence` level (`high`, `medium`, `low`) and a short `confidence_basis`, **derived from evidence in your pipeline**..."* (Lines 1-20)

---

## 4. Open Questions Unresolved by the READMEs

1. **Ingestion Timing of Drop 2**: Should Drop 2 data be loaded into the initial database during Day 1 development, or held back and applied strictly via an ingestion command simulating the Day 2 live event?
   - *Assumption*: Drop 2 is an additive and amendatory **data ingestion event**, not a schema migration (the database schema supports all 6 companies and amendments from the initial DDL migration). Our ingestion script supports loading Drop 1 independently, and then loading Drop 2, demonstrating idempotency across multi-phase releases.
2. **Original Filing Retention upon Amendment**: When `NWI-10QA-FY2024Q3` amends `NWI-10Q-FY2024Q3`, should the database overwrite existing raw rows, mark them as superseded via an `is_superseded` flag / effective dating, or store both under distinct filing IDs and resolve during KPI aggregation?
   - *Assumption*: In financial systems, financial statement line items must preserve immutable audit trails. Both filings will be stored with full provenance, but KPI resolution views will select amended figures by default based on filing date / form type hierarchy (`10-Q/A` supersedes `10-Q`), with an explicit policy flag.
3. **ZLG Reporting Currency and Unit Scale**: Does ZLG share the same reporting scale (`thousands` or `millions`) and currency as the initial 5 companies, or does it introduce novel unit labels? (Addressed empirically in `docs/DATA_AUDIT.md`).

