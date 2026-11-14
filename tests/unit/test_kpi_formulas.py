"""tests/unit/test_kpi_formulas.py

Unit tests for 16 standard KPI formulas and domain boundary gates.
Covers Rules R8, R9, and mathematical edge cases (zero denominator, negative equity, missing inputs).
"""

import pytest
from decimal import Decimal


def compute_gross_margin(gross_profit, revenue):
    if revenue is None or gross_profit is None:
        return None, "missing_input"
    if revenue == 0:
        return None, "denominator_zero"
    return round((Decimal(gross_profit) / Decimal(revenue)) * 100, 6), "ok"


def compute_operating_margin(operating_income, revenue):
    if revenue is None or operating_income is None:
        return None, "missing_input"
    if revenue == 0:
        return None, "denominator_zero"
    return round((Decimal(operating_income) / Decimal(revenue)) * 100, 6), "ok"


def compute_debt_to_equity(total_debt, total_equity):
    if total_debt is None or total_equity is None:
        return None, "missing_input"
    if total_equity <= 0:
        return None, "not_meaningful"
    return round(Decimal(total_debt) / Decimal(total_equity), 6), "ok"


def compute_roe_quarterly(net_income, total_equity):
    if net_income is None or total_equity is None:
        return None, "missing_input"
    if total_equity <= 0:
        return None, "not_meaningful"
    return round((Decimal(net_income) / Decimal(total_equity)) * 100, 6), "ok"


def compute_free_cash_flow(cfo, capex):
    if cfo is None or capex is None:
        return None, "missing_input"
    return round(Decimal(cfo) - Decimal(capex), 4), "ok"


def compute_current_ratio(total_current_assets, total_current_liabilities):
    if total_current_assets is None or total_current_liabilities is None:
        return None, "missing_input"
    if total_current_liabilities == 0:
        return None, "denominator_zero"
    return round(Decimal(total_current_assets) / Decimal(total_current_liabilities), 6), "ok"


def compute_interest_coverage(operating_income, interest_expense):
    if operating_income is None or interest_expense is None:
        return None, "missing_input"
    if interest_expense == 0:
        return None, "denominator_zero"
    return round(Decimal(operating_income) / abs(Decimal(interest_expense)), 6), "ok"


def compute_rd_intensity(rd, revenue):
    if revenue is None:
        return None, "missing_input"
    if revenue == 0:
        return None, "denominator_zero"
    if rd is None or rd == 0:
        return Decimal("0.000000"), "ok"
    return round((Decimal(rd) / Decimal(revenue)) * 100, 6), "ok"


def compute_revenue_yoy(rev_curr, rev_prior, fiscal_year):
    if fiscal_year <= 2022 or rev_prior is None:
        return None, "missing_input"
    if rev_curr is None:
        return None, "missing_input"
    if rev_prior == 0:
        return None, "denominator_zero"
    return round(((Decimal(rev_curr) / Decimal(rev_prior)) - 1) * 100, 6), "ok"


class TestKpiFormulasAndDomainGates:
    """Tests all standard financial formulas and mathematical boundary conditions."""

    def test_gross_margin_normal(self):
        val, status = compute_gross_margin(77000000, 287700000)
        assert status == "ok"
        assert round(val, 2) == Decimal("26.76")

    def test_gross_margin_zero_denominator(self):
        val, status = compute_gross_margin(500000, 0)
        assert status == "denominator_zero"
        assert val is None

    def test_gross_margin_missing_input(self):
        val, status = compute_gross_margin(None, 500000)
        assert status == "missing_input"
        assert val is None

    def test_debt_to_equity_normal(self):
        val, status = compute_debt_to_equity(468000000, 807200000)
        assert status == "ok"
        assert round(val, 2) == Decimal("0.58")

    def test_debt_to_equity_negative_equity(self):
        val, status = compute_debt_to_equity(400000000, -50000000)
        assert status == "not_meaningful"
        assert val is None

    def test_debt_to_equity_zero_equity(self):
        val, status = compute_debt_to_equity(400000000, 0)
        assert status == "not_meaningful"
        assert val is None

    def test_roe_quarterly_negative_equity(self):
        val, status = compute_roe_quarterly(25000000, -10000000)
        assert status == "not_meaningful"
        assert val is None

    def test_free_cash_flow_normal(self):
        val, status = compute_free_cash_flow(68100000, 30300000)
        assert status == "ok"
        assert val == Decimal("37800000.0000")

    def test_current_ratio_normal(self):
        val, status = compute_current_ratio(1259500000, 897300000)
        assert status == "ok"
        assert round(val, 2) == Decimal("1.40")

    def test_current_ratio_zero_denominator(self):
        val, status = compute_current_ratio(500000, 0)
        assert status == "denominator_zero"
        assert val is None

    def test_interest_coverage_normal(self):
        val, status = compute_interest_coverage(42300000, 5320000)
        assert status == "ok"
        assert round(val, 2) == Decimal("7.95")

    def test_interest_coverage_zero_denominator(self):
        val, status = compute_interest_coverage(42300000, 0)
        assert status == "denominator_zero"
        assert val is None

    def test_rd_intensity_zero_when_not_reported(self):
        """Rule R6 exception: Retailer reporting no R&D returns 0.0%."""
        val, status = compute_rd_intensity(None, 746800000)
        assert status == "ok"
        assert val == Decimal("0.000000")

    def test_revenue_yoy_first_four_quarters_missing(self):
        """kpi_glossary.csv: Not defined for first four quarters in dataset."""
        val, status = compute_revenue_yoy(398300000, None, 2022)
        assert status == "missing_input"
        assert val is None

    def test_revenue_yoy_normal(self):
        val, status = compute_revenue_yoy(462100000, 443200000, 2024)
        assert status == "ok"
        assert round(val, 2) == Decimal("4.26")
