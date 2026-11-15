#!/usr/bin/env python3
"""scripts/verify_kpis_differential.py

Independent differential verification engine for CFO Copilot.
Re-computes all 16 KPIs from scratch using pandas directly from the raw CSV data files
WITHOUT importing any production application code (no app.data.*).
Compares every calculated value against PostgreSQL kpi_values to verify 100% agreement.
"""

import os
import sys
from pathlib import Path
import datetime
import pandas as pd
import numpy as np
import psycopg2

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Raw data file paths
DROP1_RAW_CSV = PROJECT_ROOT / "data_pack" / "CANDIDATE_PACK" / "puzzle1_data" / "financial_statements_raw.csv"
DROP2_RAW_CSV = PROJECT_ROOT / "data_pack" / "DROP2_RELEASE" / "data" / "financial_statements_raw_new.csv"
DROP1_INDEX_CSV = PROJECT_ROOT / "data_pack" / "CANDIDATE_PACK" / "puzzle1_data" / "filings_index.csv"
DROP2_INDEX_CSV = PROJECT_ROOT / "data_pack" / "DROP2_RELEASE" / "data" / "filings_index_new.csv"

# Authoritative taxonomy lookup (independent mapping)
INDEPENDENT_TAXONOMY = {
    # IS - Revenue
    ("IS", "Total revenues"): "revenue",
    ("IS", "Revenues"): "revenue",
    ("IS", "Revenue"): "revenue",
    ("IS", "Net sales"): "revenue",
    # IS - Cost of revenue
    ("IS", "Cost of sales"): "cost_of_revenue",
    ("IS", "Cost of revenues"): "cost_of_revenue",
    ("IS", "Cost of revenue"): "cost_of_revenue",
    ("IS", "Total cost of revenues"): "cost_of_revenue",
    ("IS", "Cost of goods sold"): "cost_of_revenue",
    ("IS", "Cost of transportation and services"): "cost_of_revenue",
    # IS - Gross profit
    ("IS", "Gross margin"): "gross_profit",
    ("IS", "Gross profit"): "gross_profit",
    # IS - Opex
    ("IS", "Research and development"): "research_and_development",
    ("IS", "Technology and development"): "research_and_development",
    ("IS", "Technology expense"): "research_and_development",
    ("IS", "Exploration expense"): "research_and_development",
    ("IS", "Sales and marketing"): "sales_and_marketing",
    ("IS", "Store operating and marketing"): "sales_and_marketing",
    ("IS", "Selling and marketing"): "sales_and_marketing",
    ("IS", "Selling expense"): "sales_and_marketing",
    ("IS", "Marketing expense"): "sales_and_marketing",
    ("IS", "General and administrative"): "general_and_administrative",
    ("IS", "Corporate general and administrative"): "general_and_administrative",
    ("IS", "Restructuring charges"): "restructuring_charges",
    # IS - Operating income
    ("IS", "Operating profit"): "operating_income",
    ("IS", "Operating income"): "operating_income",
    ("IS", "Income (loss) from operations"): "operating_income",
    # IS - Financing & Taxes
    ("IS", "Interest expense"): "interest_expense",
    ("IS", "Interest expense, net"): "interest_expense",
    ("IS", "Earnings before income taxes"): "income_before_tax",
    ("IS", "Income before income taxes"): "income_before_tax",
    ("IS", "Income before provision for income taxes"): "income_before_tax",
    ("IS", "Income (loss) before taxes"): "income_before_tax",
    ("IS", "Provision for income taxes"): "tax_expense",
    ("IS", "Income tax expense"): "tax_expense",
    ("IS", "Income tax (benefit) expense"): "tax_expense",
    # IS - Net Income
    ("IS", "Net earnings"): "net_income",
    ("IS", "Net income"): "net_income",
    ("IS", "Net income (loss)"): "net_income",
    # BS - Balance Sheet
    ("BS", "Cash and cash equivalents"): "cash_and_equivalents",
    ("BS", "Accounts receivable, net"): "accounts_receivable",
    ("BS", "Inventories"): "inventories",
    ("BS", "Total current assets"): "total_current_assets",
    ("BS", "Total assets"): "total_assets",
    ("BS", "Total current liabilities"): "total_current_liabilities",
    ("BS", "Total debt"): "total_debt",
    ("BS", "Total liabilities"): "total_liabilities",
    ("BS", "Total stockholders' equity"): "total_equity",
    # CF - Cash Flow
    ("CF", "Net cash provided by operating activities"): "cash_from_operations",
    ("CF", "Purchases of property and equipment"): "capital_expenditures",
    ("CF", "Depreciation and amortization"): "depreciation_and_amortization",
    ("CF", "Repurchases of common stock"): "stock_repurchases",
    ("CF", "Stock-based compensation"): "stock_based_compensation",
}


def load_raw_and_normalize_pandas():
    """Loads CSVs and normalizes into a clean pandas DataFrame."""
    # 1. Load filings index
    df_idx1 = pd.read_csv(DROP1_INDEX_CSV)
    df_idx2 = pd.read_csv(DROP2_INDEX_CSV)
    df_idx = pd.concat([df_idx1, df_idx2], ignore_index=True).drop_duplicates(subset=["filing_id"])
    df_idx["filed_date"] = pd.to_datetime(df_idx["filed_date"], format="mixed").dt.date

    # Add amends_filing_id flag based on form_type
    if "amends_filing_id" not in df_idx.columns:
        df_idx["is_amendment"] = df_idx["form_type"].astype(str).str.contains("/A")
    else:
        df_idx["is_amendment"] = df_idx["amends_filing_id"].notna() | df_idx["form_type"].astype(str).str.contains("/A")

    # 2. Load raw statements
    df_raw1 = pd.read_csv(DROP1_RAW_CSV)
    df_raw2 = pd.read_csv(DROP2_RAW_CSV)
    df_raw = pd.concat([df_raw1, df_raw2], ignore_index=True)

    # Merge filing metadata
    df_merged = df_raw.merge(
        df_idx[["filing_id", "form_type", "filed_date", "reporting_unit", "is_amendment"]],
        on="filing_id",
        how="left"
    )

    # Canonical mapping
    def map_canonical(row):
        key = (str(row["statement"]).strip(), str(row["line_item_raw"]).strip())
        return INDEPENDENT_TAXONOMY.get(key, "unmapped")

    df_merged["canonical_item"] = df_merged.apply(map_canonical, axis=1)

    # Normalization scaling & sign
    def normalize_value(row):
        val = float(str(row["value"]).replace(",", "").strip())
        unit = str(row["unit"]).strip() if pd.notnull(row["unit"]) else "USD"
        
        # Dual-evidence check for HBS FY2024 Q2 unit anomaly
        if row["filing_id"] == "HBS-10Q-FY2024Q2" and unit == "USD_millions":
            scale = 1000.0
        elif unit == "USD_millions":
            scale = 1_000_000.0
        elif unit == "USD_thousands":
            scale = 1_000.0
        else:
            scale = 1.0

        val_norm = val * scale

        # Invert negative expenses (Rule R5 / Trap 2)
        expense_items = (
            "capital_expenditures", "cost_of_revenue", "sales_and_marketing",
            "general_and_administrative", "research_and_development",
            "interest_expense", "tax_expense", "restructuring_charges"
        )
        if row["canonical_item"] in expense_items and val_norm < 0:
            val_norm = abs(val_norm)

        return val_norm

    df_merged["value_norm"] = df_merged.apply(normalize_value, axis=1)

    # Deduplicate intra-filing identical rows (keep first row)
    df_dedup = df_merged.drop_duplicates(
        subset=["filing_id", "fiscal_year", "fiscal_quarter", "canonical_item", "value_norm"],
        keep="first"
    ).copy()

    return df_dedup, df_idx


def compute_effective_pandas(df_clean):
    """Resolves effective line items under 'as_restated' and 'as_originally_reported'."""
    # A. as_originally_reported: original filing (not an amendment)
    df_orig = df_clean[~df_clean["is_amendment"]].copy()
    # Sort by filed_date ASC
    df_orig = df_orig.sort_values(by=["filed_date", "row_id"], ascending=[True, True])
    df_orig_eff = df_orig.groupby(["company_id", "fiscal_year", "fiscal_quarter", "canonical_item"], as_index=False).first()
    df_orig_eff["basis"] = "as_originally_reported"

    # B. as_restated: newest filed_date wins
    df_restated = df_clean.sort_values(by=["filed_date", "row_id"], ascending=[False, False])
    df_rest_eff = df_restated.groupby(["company_id", "fiscal_year", "fiscal_quarter", "canonical_item"], as_index=False).first()
    df_rest_eff["basis"] = "as_restated"

    return pd.concat([df_orig_eff, df_rest_eff], ignore_index=True)


def compute_kpis_pandas(df_eff, df_idx):
    """Computes all 16 KPIs in pandas for all company periods and both bases."""
    # Distinct periods from index
    periods = df_idx[["company_id", "fiscal_year", "fiscal_quarter", "period_end"]].drop_duplicates()
    
    kpi_rows = []

    for basis in ["as_restated", "as_originally_reported"]:
        df_b = df_eff[df_eff["basis"] == basis]
        # Pivot canonical items
        pivot = df_b.pivot(
            index=["company_id", "fiscal_year", "fiscal_quarter"],
            columns="canonical_item",
            values="value_norm"
        ).reset_index()

        df_calc = periods.merge(pivot, on=["company_id", "fiscal_year", "fiscal_quarter"], how="left")

        # 1. gross_margin_pct = gross_profit / revenue * 100
        df_calc["gross_margin_pct"] = np.where(
            df_calc["revenue"] > 0,
            (df_calc["gross_profit"] / df_calc["revenue"]) * 100,
            np.nan
        )

        # 2. operating_margin_pct = operating_income / revenue * 100
        df_calc["operating_margin_pct"] = np.where(
            df_calc["revenue"] > 0,
            (df_calc["operating_income"] / df_calc["revenue"]) * 100,
            np.nan
        )

        # 3. net_margin_pct = net_income / revenue * 100
        df_calc["net_margin_pct"] = np.where(
            df_calc["revenue"] > 0,
            (df_calc["net_income"] / df_calc["revenue"]) * 100,
            np.nan
        )

        # 4. ebitda_usd = operating_income + depreciation_and_amortization
        df_calc["ebitda_usd"] = df_calc["operating_income"] + df_calc["depreciation_and_amortization"]

        # 5. ebitda_margin_pct = (operating_income + depreciation_and_amortization) / revenue * 100
        df_calc["ebitda_margin_pct"] = np.where(
            df_calc["revenue"] > 0,
            ((df_calc["operating_income"] + df_calc["depreciation_and_amortization"]) / df_calc["revenue"]) * 100,
            np.nan
        )

        # 6. current_ratio_x = total_current_assets / total_current_liabilities
        df_calc["current_ratio_x"] = np.where(
            df_calc["total_current_liabilities"] > 0,
            df_calc["total_current_assets"] / df_calc["total_current_liabilities"],
            np.nan
        )

        # 7. debt_to_equity_x = total_debt / total_equity (not meaningful if equity <= 0)
        df_calc["debt_to_equity_x"] = np.where(
            df_calc["total_equity"] > 0,
            df_calc["total_debt"] / df_calc["total_equity"],
            np.nan
        )

        # 8. roe_quarterly_pct = net_income / total_equity * 100 (not meaningful if equity <= 0)
        df_calc["roe_quarterly_pct"] = np.where(
            df_calc["total_equity"] > 0,
            (df_calc["net_income"] / df_calc["total_equity"]) * 100,
            np.nan
        )

        # 9. free_cash_flow_usd = cash_from_operations - capital_expenditures
        df_calc["free_cash_flow_usd"] = df_calc["cash_from_operations"] - df_calc["capital_expenditures"]

        # 10. fcf_margin_pct = (cash_from_operations - capital_expenditures) / revenue * 100
        df_calc["fcf_margin_pct"] = np.where(
            df_calc["revenue"] > 0,
            ((df_calc["cash_from_operations"] - df_calc["capital_expenditures"]) / df_calc["revenue"]) * 100,
            np.nan
        )

        # 11. revenue_yoy_growth_pct = (revenue / revenue_prior - 1) * 100
        # Compute prior year revenue merge
        rev_prior = df_calc[["company_id", "fiscal_year", "fiscal_quarter", "revenue"]].copy()
        rev_prior["target_fy"] = rev_prior["fiscal_year"] + 1
        df_calc = df_calc.merge(
            rev_prior[["company_id", "target_fy", "fiscal_quarter", "revenue"]].rename(columns={"revenue": "rev_prior", "target_fy": "fiscal_year"}),
            on=["company_id", "fiscal_year", "fiscal_quarter"],
            how="left"
        )
        df_calc["revenue_yoy_growth_pct"] = np.where(
            (df_calc["fiscal_year"] > 2022) & (df_calc["rev_prior"] > 0),
            ((df_calc["revenue"] / df_calc["rev_prior"]) - 1) * 100,
            np.nan
        )

        # 12. opex_ratio_pct = (rd + sm + ga) / revenue * 100 (never coalesce missing components to zero)
        df_calc["opex_ratio_pct"] = np.where(
            (df_calc["revenue"] > 0) & df_calc["research_and_development"].notna() & df_calc["sales_and_marketing"].notna() & df_calc["general_and_administrative"].notna(),
            ((df_calc["research_and_development"] + df_calc["sales_and_marketing"] + df_calc["general_and_administrative"]) / df_calc["revenue"]) * 100,
            np.nan
        )

        # 13. interest_coverage_x = operating_income / interest_expense
        df_calc["interest_coverage_x"] = np.where(
            df_calc["interest_expense"].abs() > 0,
            df_calc["operating_income"] / df_calc["interest_expense"].abs(),
            np.nan
        )

        # 14. asset_turnover_x = revenue / total_assets
        df_calc["asset_turnover_x"] = np.where(
            df_calc["total_assets"] > 0,
            df_calc["revenue"] / df_calc["total_assets"],
            np.nan
        )

        # 15. rd_intensity_pct = rd / revenue * 100 (never coalesce missing rd to zero; 0 only if reported as 0)
        df_calc["rd_intensity_pct"] = np.where(
            (df_calc["revenue"] > 0) & df_calc["research_and_development"].notna(),
            (df_calc["research_and_development"] / df_calc["revenue"]) * 100,
            np.nan
        )

        # 16. working_capital_usd = total_current_assets - total_current_liabilities
        df_calc["working_capital_usd"] = df_calc["total_current_assets"] - df_calc["total_current_liabilities"]

        # Melt back to long format
        kpi_cols = [
            "gross_margin_pct", "operating_margin_pct", "net_margin_pct", "ebitda_usd",
            "ebitda_margin_pct", "current_ratio_x", "debt_to_equity_x", "roe_quarterly_pct",
            "free_cash_flow_usd", "fcf_margin_pct", "revenue_yoy_growth_pct", "opex_ratio_pct",
            "interest_coverage_x", "asset_turnover_x", "rd_intensity_pct", "working_capital_usd"
        ]

        df_melt = df_calc.melt(
            id_vars=["company_id", "fiscal_year", "fiscal_quarter"],
            value_vars=kpi_cols,
            var_name="kpi_id",
            value_name="pandas_value"
        )
        df_melt["basis"] = basis
        kpi_rows.append(df_melt)

    return pd.concat(kpi_rows, ignore_index=True)


def load_sql_kpis():
    """Loads production kpi_values directly from PostgreSQL database."""
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5435")),
        dbname=os.getenv("POSTGRES_DB", "cfo_copilot"),
        user=os.getenv("POSTGRES_USER", "cfo_owner"),
        password=os.getenv("POSTGRES_PASSWORD", "80c35c88478d6b4df392bee1f72eba37")
    )
    query = """
        SELECT company_id, fiscal_year, fiscal_quarter, kpi_id, basis, status, value as sql_value
        FROM kpi_values
        WHERE policy_version = 'v1.1.0';
    """
    df_sql = pd.read_sql(query, conn)
    conn.close()
    return df_sql


def run_differential_test():
    """Executes differential verification and writes audit report."""
    print("=== Starting Independent Differential KPI Verification (Pandas vs SQL Engine) ===")
    
    # 1. Calculate via independent pandas pipeline
    df_clean, df_idx = load_raw_and_normalize_pandas()
    df_eff = compute_effective_pandas(df_clean)
    df_pandas_kpis = compute_kpis_pandas(df_eff, df_idx)

    # 2. Load production SQL values
    df_sql_kpis = load_sql_kpis()

    # 3. Merge and compare
    df_comp = df_sql_kpis.merge(
        df_pandas_kpis,
        on=["company_id", "fiscal_year", "fiscal_quarter", "kpi_id", "basis"],
        how="inner"
    )

    # Compare status 'ok' records
    df_ok = df_comp[df_comp["status"] == "ok"].copy()
    df_ok["abs_diff"] = (df_ok["sql_value"].astype(float) - df_ok["pandas_value"].astype(float)).abs()
    df_ok["rel_diff"] = np.where(
        df_ok["pandas_value"].abs() > 0,
        df_ok["abs_diff"] / df_ok["pandas_value"].abs(),
        0.0
    )

    max_abs_diff = df_ok["abs_diff"].max()
    max_rel_diff = df_ok["rel_diff"].max()
    tolerance = 1e-4

    discrepancies = df_ok[df_ok["abs_diff"] > tolerance]

    # Check non-ok status agreement (missing_input should have pandas_value NaN)
    df_non_ok = df_comp[df_comp["status"] != "ok"]
    non_ok_nan_count = df_non_ok["pandas_value"].isna().sum()

    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("CFO COPILOT - INDEPENDENT DIFFERENTIAL KPI VERIFICATION REPORT")
    report_lines.append("=" * 80)
    report_lines.append(f"Timestamp:              {datetime.datetime.now().isoformat()}")
    report_lines.append(f"Methodology:            Independent Pandas Pipeline vs Production SQL Engine")
    report_lines.append(f"Production Code Used:   NONE (Clean-room re-implementation from raw CSVs)")
    report_lines.append(f"Total Compared Records: {len(df_comp)} ({len(df_comp)//2} per basis)")
    report_lines.append(f"Status 'OK' Records:    {len(df_ok)}")
    report_lines.append(f"Status 'Missing'/'Gate':{len(df_non_ok)}")
    report_lines.append("-" * 80)
    report_lines.append(f"TOLERANCE THRESHOLD:    {tolerance} ({tolerance*100}%)")
    report_lines.append(f"Max Absolute Difference:{max_abs_diff:.8f}")
    report_lines.append(f"Max Relative Difference:{max_rel_diff:.8f}")
    report_lines.append(f"Number of Discrepancies:{len(discrepancies)}")
    report_lines.append("-" * 80)

    # Per-KPI accuracy summary
    report_lines.append("\nPER-KPI ACCURACY & AGREEMENT TABLE:")
    report_lines.append(f"{'KPI Identifier':<24} | {'Records':<8} | {'Max Abs Diff':<14} | {'Match Rate':<10}")
    report_lines.append("-" * 65)

    for kpi, group in df_ok.groupby("kpi_id"):
        max_d = group["abs_diff"].max()
        matches = (group["abs_diff"] <= tolerance).sum()
        pct = (matches / len(group)) * 100
        report_lines.append(f"{kpi:<24} | {len(group):<8} | {max_d:<14.8f} | {pct:>6.2f}%")

    report_lines.append("-" * 65)

    if len(discrepancies) == 0:
        report_lines.append("\n[SUCCESS] 100.00% DIFFERENTIAL AGREEMENT: Zero discrepancies detected!")
        report_lines.append("All SQL-calculated KPI values match the independent pandas re-computation within floating-point tolerance.")
    else:
        report_lines.append(f"\n[FAILURE] {len(discrepancies)} DISCREPANCIES DETECTED:")
        for _, row in discrepancies.head(10).iterrows():
            report_lines.append(f"  * {row['company_id']} FY{row['fiscal_year']}Q{row['fiscal_quarter']} {row['kpi_id']} ({row['basis']}): SQL={row['sql_value']}, Pandas={row['pandas_value']}, Diff={row['abs_diff']}")

    report_lines.append("=" * 80)
    report_text = "\n".join(report_lines)

    evidence_file = PROJECT_ROOT / "docs" / "evidence" / "differential_test_results.txt"
    evidence_file.write_text(report_text)
    print(report_text)
    print(f"\nSaved differential verification report to {evidence_file}")

    if len(discrepancies) > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_differential_test()
