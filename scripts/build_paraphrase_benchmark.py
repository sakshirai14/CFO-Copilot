#!/usr/bin/env python3
"""scripts/build_paraphrase_benchmark.py

Generates a large-scale deterministic paraphrase benchmark (thousands of cases, fast)
for all (company, KPI, period) tuples across 28 distinct template FAMILIES.
Splits by template FAMILIES:
- Dev Families: 20 families
- Held-Out Families: 8 families

Freezes held-out families with SHA-256 in docs/evidence/paraphrase_heldout_hash.txt
BEFORE any modifications to question_resolver.py.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEV_OUTPUT = PROJECT_ROOT / "tests" / "evals" / "paraphrase_dev_families.json"
HELDOUT_OUTPUT = PROJECT_ROOT / "tests" / "evals" / "paraphrase_heldout_families.json"
HASH_FILE = PROJECT_ROOT / "docs" / "evidence" / "paraphrase_heldout_hash.txt"

COMPANIES = {
    "ARG": {
        "ticker": "ARG",
        "legal": "Aurora Retail Group, Inc.",
        "common": "Aurora Retail Group",
        "alias": "Aurora Retail",
        "typo": "Auror Retail"
    },
    "CEP": {
        "ticker": "CEP",
        "legal": "Cobalt Energy Partners LLC",
        "common": "Cobalt Energy Partners",
        "alias": "Cobalt Energy",
        "typo": "Coblat Energy"
    },
    "HBS": {
        "ticker": "HBS",
        "legal": "Helix BioSystems Corporation",
        "common": "Helix Biosystems",
        "alias": "Helix Bio",
        "typo": "Helx Biosystems"
    },
    "MSI": {
        "ticker": "MSI",
        "legal": "Meridian Semiconductor Inc.",
        "common": "Meridian Semiconductor",
        "alias": "Meridian Semi",
        "typo": "Meridan Semiconductor"
    },
    "NWI": {
        "ticker": "NWI",
        "legal": "Northwind Industrial Corporation",
        "common": "Northwind Industrial Corp",
        "alias": "Northwind Industrial",
        "typo": "Northwnd Industrial"
    },
    "ZLG": {
        "ticker": "ZLG",
        "legal": "Zephyr Logistics Ltd.",
        "common": "Zephyr Logistics",
        "alias": "Zephyr Log",
        "typo": "Zephyr Logistcs"
    }
}

KPIS = {
    "revenue": {
        "canonical": "revenue",
        "common": "revenue",
        "acronym": "REV",
        "casual": "top-line sales",
        "short": "sales",
        "formal": "Total Revenues"
    },
    "gross_margin_pct": {
        "canonical": "gross_margin_pct",
        "common": "gross margin",
        "acronym": "GM",
        "casual": "gross profit percentage",
        "short": "gross margin rate",
        "formal": "Gross Profit Margin"
    },
    "operating_income": {
        "canonical": "operating_income",
        "common": "operating income",
        "acronym": "OI",
        "casual": "operating profit",
        "short": "operating income",
        "formal": "Income from Operations"
    },
    "net_income": {
        "canonical": "net_income",
        "common": "net income",
        "acronym": "NI",
        "casual": "bottom line earnings",
        "short": "net earnings",
        "formal": "Net Income (Loss)"
    },
    "operating_margin_pct": {
        "canonical": "operating_margin_pct",
        "common": "operating margin",
        "acronym": "OM",
        "casual": "operating profit margin",
        "short": "operating margin rate",
        "formal": "Operating Margin Percentage"
    },
    "free_cash_flow_usd": {
        "canonical": "free_cash_flow_usd",
        "common": "free cash flow",
        "acronym": "FCF",
        "casual": "free cash flow",
        "short": "FCF flow",
        "formal": "Free Cash Flow"
    },
    "debt_to_equity_x": {
        "canonical": "debt_to_equity_x",
        "common": "debt to equity",
        "acronym": "D/E",
        "casual": "leverage ratio",
        "short": "debt to equity ratio",
        "formal": "Debt to Equity Ratio"
    },
    "current_ratio_x": {
        "canonical": "current_ratio_x",
        "common": "current ratio",
        "acronym": "CR",
        "casual": "liquidity ratio",
        "short": "working capital ratio",
        "formal": "Current Ratio"
    },
    "ebitda_usd": {
        "canonical": "ebitda_usd",
        "common": "EBITDA",
        "acronym": "EBITDA",
        "casual": "operating cash earnings",
        "short": "EBITDA",
        "formal": "Earnings Before Interest, Taxes, Depreciation and Amortization"
    },
    "working_capital_usd": {
        "canonical": "working_capital_usd",
        "common": "working capital",
        "acronym": "WC",
        "casual": "operating liquidity",
        "short": "working capital",
        "formal": "Net Working Capital"
    }
}

PERIODS = [
    (2022, 1), (2022, 2), (2022, 3), (2022, 4),
    (2023, 1), (2023, 2), (2023, 3), (2023, 4),
    (2024, 1), (2024, 2), (2024, 3)
]

ORDINALS = {1: "first", 2: "second", 3: "third", 4: "fourth"}
WORDS = {1: "one", 2: "two", 3: "three", 4: "four"}
MONTHS = {1: "March", 2: "June", 3: "September", 4: "December"}

# 28 Template Families
# Dev Families: 0 to 19 (20 families)
# Held-Out Families: 20 to 27 (8 families)

DEV_FAMILIES = [
    # Period phrasings
    "fam_01_std_fy_q",
    "fam_02_q_of_fiscal_year",
    "fam_03_ordinal_quarter_fy",
    "fam_04_quarter_word_year",
    "fam_05_fiscal_year_quarter_num",
    "fam_06_ended_month_year",
    "fam_07_trailing_dash_tag",
    "fam_08_quarter_first_fy",
    # KPI synonyms & acronyms
    "fam_09_acronym_metric",
    "fam_10_casual_metric_name",
    "fam_11_formal_disclosure_title",
    "fam_12_short_metric_rate",
    # Company naming & typos
    "fam_13_full_legal_name",
    "fam_14_ticker_symbol",
    "fam_15_informal_alias",
    "fam_16_light_typo_company",
    # Basis phrasings
    "fam_17_as_originally_reported",
    "fam_18_restated_explicit",
    "fam_19_restatement_adjusted",
    "fam_20_original_unadjusted"
]

HELDOUT_FAMILIES = [
    # Unseen syntactic & conversational structures
    "fam_21_conversational_polite",
    "fam_22_executive_brief_pipe",
    "fam_23_interrogative_inverted",
    "fam_24_passive_voice_reported",
    "fam_25_calendar_three_months_ended",
    "fam_26_imperative_extract_metric",
    "fam_27_structured_field_colon",
    "fam_28_inquisitive_what_did_report"
]


def render_family(family_id: str, comp_id: str, kpi_id: str, fy: int, fq: int) -> Dict[str, Any]:
    c_meta = COMPANIES[comp_id]
    k_meta = KPIS[kpi_id]
    ord_str = ORDINALS[fq]
    word_str = WORDS[fq]
    month_str = MONTHS[fq]
    fy_short = str(fy)[2:]

    # Default basis
    expected_basis = "as_restated"
    q_text = ""

    if family_id == "fam_01_std_fy_q":
        q_text = f"What was {c_meta['common']}'s {k_meta['common']} in FY{fy} Q{fq}?"
    elif family_id == "fam_02_q_of_fiscal_year":
        q_text = f"Can you report the {k_meta['common']} of {c_meta['common']} for Q{fq} of fiscal {fy}?"
    elif family_id == "fam_03_ordinal_quarter_fy":
        q_text = f"State {c_meta['common']}'s {k_meta['common']} in the {ord_str} quarter of FY{fy}."
    elif family_id == "fam_04_quarter_word_year":
        q_text = f"What was {c_meta['common']} {k_meta['common']} in quarter {word_str} of {fy}?"
    elif family_id == "fam_05_fiscal_year_quarter_num":
        q_text = f"Give me {c_meta['common']}'s {k_meta['common']} in fiscal year {fy} quarter {fq}."
    elif family_id == "fam_06_ended_month_year":
        q_text = f"What was the {k_meta['common']} for {c_meta['common']} for the quarter ended {month_str} {fy}?"
    elif family_id == "fam_07_trailing_dash_tag":
        q_text = f"{c_meta['common']} {k_meta['common']} (FY{fy}-Q{fq})."
    elif family_id == "fam_08_quarter_first_fy":
        q_text = f"In Q{fq} {fy}, what was {c_meta['common']}'s {k_meta['common']}?"
    elif family_id == "fam_09_acronym_metric":
        q_text = f"Show {c_meta['common']} {k_meta['acronym']} for FY{fy} Q{fq}."
    elif family_id == "fam_10_casual_metric_name":
        q_text = f"How much {k_meta['casual']} did {c_meta['common']} generate in FY{fy} Q{fq}?"
    elif family_id == "fam_11_formal_disclosure_title":
        q_text = f"Disclose {c_meta['common']}'s {k_meta['formal']} for FY{fy} Q{fq}."
    elif family_id == "fam_12_short_metric_rate":
        q_text = f"What was {c_meta['common']}'s {k_meta['short']} in FY{fy} Q{fq}?"
    elif family_id == "fam_13_full_legal_name":
        q_text = f"What was {c_meta['legal']} {k_meta['common']} in FY{fy} Q{fq}?"
    elif family_id == "fam_14_ticker_symbol":
        q_text = f"Report {c_meta['ticker']} {k_meta['common']} in FY{fy} Q{fq}."
    elif family_id == "fam_15_informal_alias":
        q_text = f"What was {c_meta['alias']} {k_meta['common']} in FY{fy} Q{fq}?"
    elif family_id == "fam_16_light_typo_company":
        q_text = f"What was {c_meta['typo']} {k_meta['common']} in FY{fy} Q{fq}?"
    elif family_id == "fam_17_as_originally_reported":
        q_text = f"What was {c_meta['common']}'s {k_meta['common']} in FY{fy} Q{fq} as originally reported?"
        expected_basis = "as_originally_reported"
    elif family_id == "fam_18_restated_explicit":
        q_text = f"What was {c_meta['common']}'s {k_meta['common']} in FY{fy} Q{fq} (as restated)?"
        expected_basis = "as_restated"
    elif family_id == "fam_19_restatement_adjusted":
        q_text = f"Show restatement-adjusted {k_meta['common']} for {c_meta['common']} in FY{fy} Q{fq}."
        expected_basis = "as_restated"
    elif family_id == "fam_20_original_unadjusted":
        q_text = f"Report original unadjusted {k_meta['common']} of {c_meta['common']} in FY{fy} Q{fq}."
        expected_basis = "as_originally_reported"
    # Held-Out Families
    elif family_id == "fam_21_conversational_polite":
        q_text = f"Could you please tell me {c_meta['common']}'s {k_meta['common']} during FY{fy} Q{fq}?"
    elif family_id == "fam_22_executive_brief_pipe":
        q_text = f"{c_meta['ticker']} | {k_meta['common']} | FY{fy} Q{fq}"
    elif family_id == "fam_23_interrogative_inverted":
        q_text = f"For Q{fq} of {fy}, what did {c_meta['common']} report for {k_meta['common']}?"
    elif family_id == "fam_24_passive_voice_reported":
        q_text = f"For FY{fy} Q{fq}, what was reported by {c_meta['legal']} as {k_meta['common']}?"
    elif family_id == "fam_25_calendar_three_months_ended":
        q_text = f"For the three months ended {month_str} {fy}, what was {c_meta['common']}'s {k_meta['common']}?"
    elif family_id == "fam_26_imperative_extract_metric":
        q_text = f"Extract {k_meta['formal']} for {c_meta['alias']} in fiscal {fy} quarter {fq}."
    elif family_id == "fam_27_structured_field_colon":
        q_text = f"Company: {c_meta['common']}; Metric: {k_meta['common']}; Period: FY{fy}Q{fq}"
    elif family_id == "fam_28_inquisitive_what_did_report":
        q_text = f"What figure did {c_meta['ticker']} announce for {k_meta['casual']} in {ord_str} quarter FY{fy}?"

    return {
        "family_id": family_id,
        "question": q_text,
        "expected_company": comp_id,
        "expected_kpi": kpi_id,
        "expected_year": fy,
        "expected_quarter": fq,
        "expected_period": f"FY{fy}Q{fq}",
        "expected_basis": expected_basis
    }


def generate_benchmark():
    dev_cases: List[Dict[str, Any]] = []
    heldout_cases: List[Dict[str, Any]] = []

    # Iterate deterministically across companies, KPIs, and periods
    comp_keys = sorted(COMPANIES.keys())
    kpi_keys = sorted(KPIS.keys())

    # Generate Dev Cases: 20 families x 6 companies x 10 KPIs x 2 sampled periods = 2,400 cases
    dev_periods = [(2022, 1), (2023, 3)]
    for fam in DEV_FAMILIES:
        for c in comp_keys:
            for k in kpi_keys:
                for fy, fq in dev_periods:
                    case = render_family(fam, c, k, fy, fq)
                    dev_cases.append(case)

    # Generate Held-Out Cases: 8 families x 6 companies x 10 KPIs x 2 sampled periods = 960 cases
    ho_periods = [(2022, 2), (2024, 1)]
    for fam in HELDOUT_FAMILIES:
        for c in comp_keys:
            for k in kpi_keys:
                for fy, fq in ho_periods:
                    case = render_family(fam, c, k, fy, fq)
                    heldout_cases.append(case)

    print(f"Generated Dev Cases: {len(dev_cases)} (across 20 dev families)")
    print(f"Generated Held-Out Cases: {len(heldout_cases)} (across 8 held-out families)")

    DEV_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(DEV_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(dev_cases, f, indent=2)

    with open(HELDOUT_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(heldout_cases, f, indent=2)

    # Cryptographic SHA-256 Freeze of Held-Out Families
    ho_bytes = HELDOUT_OUTPUT.read_bytes()
    ho_sha = hashlib.sha256(ho_bytes).hexdigest()

    HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    HASH_FILE.write_text(ho_sha + "\n", encoding="utf-8")

    print(f"\n✓ Saved Dev Families to: {DEV_OUTPUT}")
    print(f"✓ Saved Held-Out Families to: {HELDOUT_OUTPUT}")
    print(f"✓ FROZEN Held-Out Families SHA-256: {ho_sha}")
    print(f"✓ Written to: {HASH_FILE}\n")


if __name__ == "__main__":
    generate_benchmark()

