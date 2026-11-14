"""app/data/taxonomy.py

Authoritative taxonomy mapping between company-specific line items and canonical financial names.
Mirrors kpi_glossary.csv and data_dictionary.csv requirements.
"""

from typing import Dict, Tuple, Optional

# Mapping: (statement, raw_line_item) -> (canonical_name, default_sign_multiplier, notes)
GLOBAL_TAXONOMY: Dict[Tuple[str, str], Tuple[str, int, str]] = {
    # Income Statement (IS) - Revenues
    ("IS", "Total revenues"): ("revenue", 1, "Top-line revenue"),
    ("IS", "Revenues"): ("revenue", 1, "Top-line revenue"),
    ("IS", "Revenue"): ("revenue", 1, "Top-line revenue"),
    ("IS", "Net sales"): ("revenue", 1, "Top-line revenue / net sales"),

    # IS - Cost of Goods Sold / Cost of Revenue
    ("IS", "Cost of sales"): ("cost_of_revenue", 1, "Cost of goods sold"),
    ("IS", "Cost of revenues"): ("cost_of_revenue", 1, "Cost of goods sold"),
    ("IS", "Cost of revenue"): ("cost_of_revenue", 1, "Cost of goods sold"),
    ("IS", "Total cost of revenues"): ("cost_of_revenue", 1, "Cost of goods sold"),
    ("IS", "Cost of goods sold"): ("cost_of_revenue", 1, "Cost of goods sold"),
    ("IS", "Cost of transportation and services"): ("cost_of_revenue", 1, "Freight / carrier costs (ZLG)"),

    # IS - Gross Profit
    ("IS", "Gross margin"): ("gross_profit", 1, "Gross profit dollar amount (ARG terminology)"),
    ("IS", "Gross profit"): ("gross_profit", 1, "Gross profit dollar amount"),

    # IS - Operating Expenses
    ("IS", "Research and development"): ("research_and_development", 1, "R&D expense"),
    ("IS", "Technology and development"): ("research_and_development", 1, "ARG technology (0.0)"),
    ("IS", "Technology expense"): ("research_and_development", 1, "ZLG technology operations"),
    ("IS", "Exploration expense"): ("research_and_development", 1, "CEP upstream exploration"),

    ("IS", "Sales and marketing"): ("sales_and_marketing", 1, "Commercial / customer acquisition"),
    ("IS", "Store operating and marketing"): ("sales_and_marketing", 1, "ARG retail operations"),
    ("IS", "Selling and marketing"): ("sales_and_marketing", 1, "NWI commercial"),
    ("IS", "Selling expense"): ("sales_and_marketing", 1, "ZLG commercial"),
    ("IS", "Marketing expense"): ("sales_and_marketing", 1, "CEP commercial"),

    ("IS", "General and administrative"): ("general_and_administrative", 1, "G&A corporate overhead"),
    ("IS", "Corporate general and administrative"): ("general_and_administrative", 1, "ARG corporate G&A"),

    ("IS", "Restructuring charges"): ("restructuring_charges", 1, "Severance / facility exit"),

    # IS - Operating Income
    ("IS", "Operating profit"): ("operating_income", 1, "Operating profit / EBIT"),
    ("IS", "Operating income"): ("operating_income", 1, "Operating income / EBIT"),
    ("IS", "Income (loss) from operations"): ("operating_income", 1, "Operating income / EBIT"),

    # IS - Financing & Taxes
    ("IS", "Interest expense"): ("interest_expense", 1, "Borrowing interest cost"),
    ("IS", "Interest expense, net"): ("interest_expense", 1, "Net interest expense"),
    ("IS", "Earnings before income taxes"): ("income_before_tax", 1, "Pre-tax earnings"),
    ("IS", "Income before income taxes"): ("income_before_tax", 1, "Pre-tax earnings"),
    ("IS", "Income before provision for income taxes"): ("income_before_tax", 1, "Pre-tax earnings"),
    ("IS", "Income (loss) before taxes"): ("income_before_tax", 1, "Pre-tax earnings"),

    ("IS", "Provision for income taxes"): ("tax_expense", 1, "Income tax expense"),
    ("IS", "Income tax expense"): ("tax_expense", 1, "Income tax expense"),
    ("IS", "Income tax (benefit) expense"): ("tax_expense", 1, "Income tax expense"),

    # IS - Net Income
    ("IS", "Net earnings"): ("net_income", 1, "Bottom-line net earnings"),
    ("IS", "Net income"): ("net_income", 1, "Bottom-line net income"),
    ("IS", "Net income (loss)"): ("net_income", 1, "Bottom-line net income"),

    # Balance Sheet (BS)
    ("BS", "Cash and cash equivalents"): ("cash_and_equivalents", 1, "Liquid cash balances"),
    ("BS", "Accounts receivable, net"): ("accounts_receivable", 1, "Trade receivables"),
    ("BS", "Inventories"): ("inventories", 1, "Merchandise and raw inventory"),
    ("BS", "Total current assets"): ("total_current_assets", 1, "Assets convertible within 1 year"),
    ("BS", "Total assets"): ("total_assets", 1, "Total balance sheet assets"),
    ("BS", "Total current liabilities"): ("total_current_liabilities", 1, "Liabilities due within 1 year"),
    ("BS", "Total debt"): ("total_debt", 1, "Short-term plus long-term debt"),
    ("BS", "Total liabilities"): ("total_liabilities", 1, "Total balance sheet liabilities"),
    ("BS", "Total stockholders' equity"): ("total_equity", 1, "Book equity value"),

    # Cash Flow (CF)
    ("CF", "Net cash provided by operating activities"): ("cash_from_operations", 1, "Operating cash flow"),
    ("CF", "Purchases of property and equipment"): ("capital_expenditures", 1, "Capex purchases"),
    ("CF", "Depreciation and amortization"): ("depreciation_and_amortization", 1, "Non-cash D&A addback"),
    ("CF", "Repurchases of common stock"): ("stock_repurchases", 1, "Treasury share repurchases"),
    ("CF", "Stock-based compensation"): ("stock_based_compensation", 1, "Non-cash equity compensation"),
}


def get_canonical_line_item(company_id: str, statement: str, raw_item: str) -> Tuple[str, int, str]:
    """Resolves raw line item to (canonical_name, sign_multiplier, notes)."""
    clean_raw = str(raw_item).strip()
    key = (statement.upper(), clean_raw)
    if key in GLOBAL_TAXONOMY:
        return GLOBAL_TAXONOMY[key]

    # Fallback to sanitized snake_case name
    sanitized = clean_raw.lower().replace(" ", "_").replace("-", "_").replace(",", "")
    return sanitized, 1, "Auto-mapped fallback"

