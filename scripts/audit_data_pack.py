#!/usr/bin/env python3
"""
scripts/audit_data_pack.py

Phase 0 Data Pack Audit Script for CFO Copilot on a Budget.
Audits all CSV assets in data_pack/ (both CANDIDATE_PACK and DROP2_RELEASE),
verifies schemas, identifies accounting traps, detects prompt injections,
compares Drop 1 vs Drop 2 deltas, and saves the execution trace to docs/evidence/audit_output.txt.
"""

import os
import glob
import re
import sys
import pandas as pd
import numpy as np


def run_audit():
    output_lines = []

    def log(msg=""):
        output_lines.append(msg)
        print(msg)

    log("=" * 80)
    log("CFO COPILOT ON A BUDGET - PHASE 0 DATA PACK AUDIT")
    log("=" * 80)
    log()

    # 1. FILE INVENTORY
    log("### 1. FILE INVENTORY & SCHEMA INTEGRITY")
    log()
    csv_files = sorted(glob.glob("data_pack/**/*.csv", recursive=True))
    inventory = []
    
    for fpath in csv_files:
        df = pd.read_csv(fpath)
        null_counts = df.isnull().sum().to_dict()
        null_cols = {k: v for k, v in null_counts.items() if v > 0}
        file_size_kb = os.path.getsize(fpath) / 1024.0
        
        # Date range detection
        date_cols = [c for c in df.columns if 'date' in c or 'period' in c]
        date_summary = "N/A"
        if date_cols:
            all_dates = []
            for dc in date_cols:
                # convert strings to dates safely
                valid_dates = pd.to_datetime(df[dc], format='mixed', errors='coerce').dropna()
                if not valid_dates.empty:
                    all_dates.extend(valid_dates)
            if all_dates:
                min_d = min(all_dates).strftime('%Y-%m-%d')
                max_d = max(all_dates).strftime('%Y-%m-%d')
                date_summary = f"{min_d} to {max_d}"

        inventory.append({
            "path": fpath,
            "rows": len(df),
            "cols": len(df.columns),
            "size_kb": f"{file_size_kb:.1f}",
            "nulls": str(null_cols) if null_cols else "None",
            "date_range": date_summary
        })

    inv_df = pd.DataFrame(inventory)
    log(inv_df.to_string(index=False))
    log()

    # 2. COMPANIES & FISCAL CALENDARS
    log("### 2. COMPANY COVERAGE & FISCAL CALENDAR ALIGNMENT")
    log()
    c1 = pd.read_csv("data_pack/CANDIDATE_PACK/puzzle1_data/companies.csv")
    c2 = pd.read_csv("data_pack/DROP2_RELEASE/data/companies_new.csv")
    all_companies = pd.concat([c1, c2], ignore_index=True)

    f1 = pd.read_csv("data_pack/CANDIDATE_PACK/puzzle1_data/filings_index.csv")
    f2 = pd.read_csv("data_pack/DROP2_RELEASE/data/filings_index_new.csv")
    all_filings = pd.concat([f1, f2], ignore_index=True)

    for _, c in all_companies.iterrows():
        cid = c['company_id']
        c_filings = all_filings[all_filings['company_id'] == cid]
        quarters = sorted(list(zip(c_filings['fiscal_year'], c_filings['fiscal_quarter'], c_filings['form_type'])))
        log(f"Company: {cid} ({c['name']}) | Sector: {c['sector']} | Currency: {c['reporting_currency']}")
        log(f"  Fiscal Year Definition: {c['fiscal_year_note']}")
        log(f"  Total Filings: {len(c_filings)} | Distinct Quarters: {len(set((y, q) for y, q, _ in quarters))}")
        log(f"  Quarters: {quarters}")
        
        # Check missing quarters (expected 12 quarters: 2022 Q1..Q4, 2023 Q1..Q4, 2024 Q1..Q4)
        expected = set((y, q) for y in [2022, 2023, 2024] for q in [1, 2, 3, 4])
        actual = set((y, q) for y, q, _ in quarters)
        missing = expected - actual
        if missing:
            log(f"  [ALERT] Missing Quarters: {sorted(list(missing))}")
        else:
            log(f"  Quarter Coverage: Complete (12 of 12 fiscal quarters present)")
        log()

    # 3. UNITS, SCALES, AND SIGN CONVENTIONS
    log("### 3. UNITS, SCALES, CURRENCY, AND SIGN CONVENTIONS")
    log()
    raw1 = pd.read_csv("data_pack/CANDIDATE_PACK/puzzle1_data/financial_statements_raw.csv")
    raw2 = pd.read_csv("data_pack/DROP2_RELEASE/data/financial_statements_raw_new.csv")
    all_raw = pd.concat([raw1, raw2], ignore_index=True)

    log("Units breakdown across all financial statement rows:")
    log(all_raw.groupby(['company_id', 'unit']).size().to_string())
    log()

    log("Sign convention check on expenses (Costs / SG&A / Marketing):")
    expense_check = all_raw[all_raw['line_item_raw'].str.contains('Cost|sales and marketing|Selling|marketing|general and administrative', case=False, na=False)]
    for cid, grp in expense_check.groupby('company_id'):
        neg_count = (grp['value'] < 0).sum()
        pos_count = (grp['value'] > 0).sum()
        zero_count = (grp['value'] == 0).sum()
        log(f"  {cid}: Negative rows={neg_count}, Positive rows={pos_count}, Zero={zero_count}")
        if neg_count > 0 and pos_count > 0:
            log(f"    [WARNING] {cid} has MIXED expense signs!")
        elif neg_count > 0:
            log(f"    [SIGN RULE] {cid} reports expenses as NEGATIVE numbers.")
        else:
            log(f"    [SIGN RULE] {cid} reports expenses as POSITIVE numbers.")
    log()

    # 4. DUPLICATES, CONFLICTS, RESTATEMENTS, AND AMENDMENTS
    log("### 4. DATA INTEGRITY ANOMALIES, DUPLICATES & AMENDMENT CONFLICTS")
    log()

    # Exact duplicates
    exact_dups = all_raw.duplicated().sum()
    log(f"Exact row duplicates: {exact_dups}")

    # Business key duplicates within the same filing
    intra_filing_dups = all_raw[all_raw.duplicated(subset=['filing_id', 'statement', 'line_item_raw'], keep=False)]
    log(f"Intra-filing duplicates (same line item repeated in same filing): {len(intra_filing_dups)} rows")
    if not intra_filing_dups.empty:
        log("  Concrete examples of intra-filing duplicate rows:")
        for _, r in intra_filing_dups.head(10).iterrows():
            log(f"    Row {r['row_id']} | Filing: {r['filing_id']} | {r['statement']} | {r['line_item_raw']} = {r['value']} {r['unit']}")
    log()

    # Cross-filing amendment conflicts
    log("Amendments and superseding filings:")
    amendments = all_filings[all_filings['form_type'].str.contains('/A|QA', na=False)]
    log(f"Found {len(amendments)} amended filings:")
    for _, af in amendments.iterrows():
        base_filing_id = af['filing_id'].replace('QA', 'Q').replace('10QA', '10Q')
        log(f"  Amended Filing: {af['filing_id']} (Filed: {af['filed_date']}) supersedes Base Filing: {base_filing_id}")
        base_rows = all_raw[all_raw['filing_id'] == base_filing_id]
        amend_rows = all_raw[all_raw['filing_id'] == af['filing_id']]
        log(f"    Base rows count: {len(base_rows)} | Amended rows count: {len(amend_rows)}")
        merged = pd.merge(base_rows, amend_rows, on=['statement', 'line_item_raw'], suffixes=('_orig', '_amend'))
        diffs = merged[merged['value_orig'] != merged['value_amend']]
        log(f"    Conflicting / Restated line items ({len(diffs)}):")
        for _, dr in diffs.iterrows():
            log(f"      {dr['statement']} | {dr['line_item_raw']}: original={dr['value_orig']} -> amended={dr['value_amend']} (delta: {dr['value_amend'] - dr['value_orig']})")
    log()

    # Extraction Unit Errors (HBS unit anomaly)
    log("Extraction unit anomalies:")
    hbs_raw_units = raw1[raw1['company_id'] == 'HBS']['unit'].value_counts()
    log(f"  HBS raw units distribution: {dict(hbs_raw_units)}")
    hbs_filing_units = f1[f1['company_id'] == 'HBS']['reporting_unit'].value_counts()
    log(f"  HBS filing index reporting_unit distribution: {dict(hbs_filing_units)}")
    hbs_error_rows = raw1[(raw1['company_id'] == 'HBS') & (raw1['unit'] == 'USD_millions')]
    log(f"  [EXTRACTION BUG] HBS-10Q-FY2024Q2 has {len(hbs_error_rows)} rows marked USD_millions in raw statements while filings_index states USD_thousands!")
    log(f"  Concrete sample: Row {hbs_error_rows.iloc[0]['row_id']} | {hbs_error_rows.iloc[0]['line_item_raw']} = {hbs_error_rows.iloc[0]['value']} {hbs_error_rows.iloc[0]['unit']}")
    log()

    # Date formatting anomalies
    log("Date format anomalies:")
    slash_dates = all_raw[all_raw['period_start'].str.contains('/', na=False) | all_raw['period_end'].str.contains('/', na=False)]
    log(f"  Rows using non-standard slash dates (MM/DD/YYYY): {len(slash_dates)}")
    log(f"  Companies affected: {slash_dates['company_id'].unique().tolist()}")
    log(f"  Sample row: {slash_dates.iloc[0]['row_id']} | company={slash_dates.iloc[0]['company_id']} | start={slash_dates.iloc[0]['period_start']} | end={slash_dates.iloc[0]['period_end']}")
    log()

    # Comparative column cross-period row extraction
    log("Comparative column cross-period extraction:")
    all_raw['filing_year'] = all_raw['filing_id'].str.extract(r'FY(\d{4})')[0].astype(int)
    comp_col_rows = all_raw[all_raw['filing_year'] != all_raw['fiscal_year']]
    log(f"  Rows where filing year != fiscal year (comparative column extraction): {len(comp_col_rows)}")
    for _, ccr in comp_col_rows.iterrows():
        log(f"    Row {ccr['row_id']} | Filing: {ccr['filing_id']} (FY{ccr['filing_year']}) contains data for Fiscal Year {ccr['fiscal_year']} Q{ccr['fiscal_quarter']} | {ccr['line_item_raw']} = {ccr['value']}")
    log()

    # 5. CORPUS & ADVERSARIAL SCAN (PUZZLE 5 PREP)
    log("### 5. CORPUS ANALYSIS & ADVERSARIAL INJECTION SIGNATURES")
    log()
    doc1 = pd.read_csv("data_pack/CANDIDATE_PACK/puzzle1_data/corpus_documents.csv")
    doc2 = pd.read_csv("data_pack/DROP2_RELEASE/data/corpus_documents_new.csv")
    all_docs = pd.concat([doc1, doc2], ignore_index=True)

    log(f"Total documents in corpus: {len(all_docs)} (Drop 1: {len(doc1)}, Drop 2: {len(doc2)})")
    log("Breakdown by doc_type and company:")
    log(all_docs.groupby(['company_id', 'doc_type']).size().to_string())
    log()

    all_docs['word_count'] = all_docs['text'].str.split().str.len()
    log("Corpus word count statistics:")
    log(all_docs['word_count'].describe().to_string())
    log()

    # Security scan
    suspicious_patterns = [
        (r'developer mode', 'Developer Mode Jailbreak'),
        (r'ignore (?:any|all|previous) (?:rules|instructions)', 'Instruction Override'),
        (r'disregard all previous instructions', 'Instruction Override'),
        (r'SELECT \* FROM', 'SQL Injection / Exfiltration Probe'),
        (r'database connection string', 'Credential Exfiltration Probe'),
        (r'SYSTEM NOTICE TO AI ASSISTANTS', 'System Prompt Spoofing'),
    ]

    log("Adversarial payload detections in corpus:")
    found_threats = 0
    for pat, label in suspicious_patterns:
        matches = all_docs[all_docs['text'].str.contains(pat, case=False, regex=True, na=False)]
        for _, m in matches.iterrows():
            found_threats += 1
            snippet = m['text']
            matched_text = re.search(pat, snippet, re.IGNORECASE)
            start_pos = max(0, matched_text.start() - 40)
            end_pos = min(len(snippet), matched_text.end() + 80)
            context_snip = snippet[start_pos:end_pos].replace('\n', ' ')
            log(f"  [ATTACK DETECTED] Type: {label} | Doc ID: {m['doc_id']} (Company: {m['company_id']})")
            log(f"    Excerpt: \"...{context_snip}...\"")
    log(f"Total adversarial injection payloads detected: {found_threats}")
    log()

    # 6. KPI FEASIBILITY AUDIT
    log("### 6. KPI FORMULA SUPPORT & LINE-ITEM MAPPING")
    log()
    kpi_df = pd.read_csv("data_pack/CANDIDATE_PACK/puzzle1_data/kpi_glossary.csv")
    log(f"Total KPIs in Glossary: {len(kpi_df)}")
    
    # Check mapping feasibility per company
    companies_list = all_companies['company_id'].unique().tolist()
    log("Line item availability per company for core KPI components:")
    
    components = {
        "Revenue": ['Total revenues', 'Revenues', 'Revenue', 'Total revenue', 'Net sales'],
        "COGS": ['Cost of sales', 'Cost of revenues', 'Cost of revenue', 'Total cost of revenues', 'Cost of goods sold', 'Cost of transportation and services'],
        "Gross Profit": ['Gross margin', 'Gross profit'],
        "Operating Income": ['Operating profit', 'Operating income', 'Income (loss) from operations'],
        "Depr & Amort": ['Depreciation and amortization'],
        "Total Current Assets": ['Total current assets'],
        "Total Current Liabilities": ['Total current liabilities'],
        "Total Debt": ['Total debt'],
        "Stockholders Equity": ["Total stockholders' equity"],
        "Operating Cash Flow": ['Net cash provided by operating activities'],
        "Capex": ['Purchases of property and equipment'],
        "R&D": ['Research and development', 'Technology and development', 'Technology expense', 'Exploration expense'],
        "Interest Expense": ['Interest expense, net', 'Interest expense']
    }

    feasibility_matrix = []
    for cid in companies_list:
        c_raw = all_raw[all_raw['company_id'] == cid]
        c_items = set(c_raw['line_item_raw'].unique())
        row = {"company_id": cid}
        for comp_name, possible_items in components.items():
            matched = [item for item in possible_items if item in c_items]
            row[comp_name] = matched[0] if matched else "MISSING"
        feasibility_matrix.append(row)

    f_matrix_df = pd.DataFrame(feasibility_matrix)
    log(f_matrix_df.to_string(index=False))
    log()

    # 7. RANKED DATA TRAPS
    log("### 7. RANKED DATA TRAPS FOR CFO REPORTING")
    log()
    traps = [
        ("TRAP 1: Unit Scale Mismatch (HBS FY2024Q2 1000x Inflation)",
         "High",
         "HBS raw financial statements mark row R000795 as USD_millions ($109.2B) instead of USD_thousands ($109.2M). Blind aggregation produces a 1,000x error."),
        ("TRAP 2: Mixed Expense Sign Conventions across Companies",
         "High",
         "CEP stores Cost of Revenues and operating expenses as negative numbers (-$179.2M), while ARG, NWI, MSI, HBS store them as positive. Inverted arithmetic corrupts margins."),
        ("TRAP 3: Intra-Filing Exact Line Item Duplication (ARG FY2023Q2)",
         "High",
         "ARG-10Q-FY2023Q2 contains duplicate rows for Total Revenues (R000411 and R001447), Cost of Sales, and Net Earnings. A SQL SUM() doubles quarterly figures."),
        ("TRAP 4: Unaudited Press Release Conflicting with 10-Q (ARG FY2024Q1)",
         "High",
         "Corpus document ARG_press_release_2023-06-06 reports preliminary revenues of 871,000, but official Form 10-Q reports 777,700. Unconstrained RAG hallucinates wrong revenue."),
        ("TRAP 5: Adversarial Prompt Injections Embedded in Regulatory Corpus",
         "High",
         "Corpus contains direct attacks: NWI-10Q-FY2024Q3 ('state that operating margin was 45%'), CEP_investor_faq (SQL schema & credential dump), and HBS analyst note (developer mode)."),
        ("TRAP 6: Non-Standard Fiscal Calendars (HBS Year Beginning Designation)",
         "Medium",
         "HBS designates fiscal years by calendar year of BEGINNING (July 1), whereas standard US practice designates by ENDING year. Misaligns comparative peer benchmarks."),
        ("TRAP 7: Slash Date Formatting Inconsistency in CEP",
         "Medium",
         "CEP rows use MM/DD/YYYY dates while all other companies use YYYY-MM-DD. Strict string comparison or naive date parsers fail."),
        ("TRAP 8: Comparative Column Restatement Extractions",
         "Medium",
         "NWI comparative column extractions attach filing_id NWI-10Q-FY2024Q3 to prior-year FY2023 Q3 rows with restated values (Net Income restated from 37.3M to 34.9M).")
    ]

    for title, severity, desc in traps:
        log(f"{title} [Severity: {severity}]")
        log(f"  Description: {desc}")
        log()

    # 8. OPEN QUESTIONS
    log("### 8. OPEN QUESTIONS REQUIRING POLICY RESOLUTION")
    log()
    open_questions = [
        "Q1: When a company reports zero or no R&D line item (e.g., ARG reports Technology & Development = 0, CEP reports Exploration Expense, ZLG reports Technology Expense), should rd_intensity_pct return 0.0% or NULL?",
        "Q2: In calculating opex_ratio_pct, should CEP's Exploration Expense and ZLG's Technology Expense be classified under Research & Development or General & Administrative?",
        "Q3: When Form 10-Q/A amends a prior Form 10-Q (e.g. CEP FY2024Q2, NWI FY2024Q3), does the CFO policy require reporting the restated historical figure, the originally filed figure, or both with an explicit restatement flag?",
        "Q4: For HBS FY2024Q2, should the platform automatically correct the unit to USD_thousands by cross-referencing filings_index.csv, or quarantine the quarter as an extraction error?",
        "Q5: In free cash flow calculation, Capex is reported as Purchases of property and equipment (negative cash outflow in CF statement). Confirm standard convention: FCF = Cash from Operations - ABS(Purchases of Property & Equipment)."
    ]
    for q in open_questions:
        log(q)
    log()

    log("=" * 80)
    log("AUDIT COMPLETE - SUMMARY PERSISTED")
    log("=" * 80)

    # Save to docs/evidence/audit_output.txt
    os.makedirs("docs/evidence", exist_ok=True)
    with open("docs/evidence/audit_output.txt", "w") as f:
        f.write("\n".join(output_lines) + "\n")
    log("Evidence saved to docs/evidence/audit_output.txt")


if __name__ == "__main__":
    run_audit()
