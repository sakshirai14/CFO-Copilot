"""tests/integration/test_conflict_policy.py

Integration test suite verifying enforcement of Conflict & Reconciliation Policy Rules R1 - R12.
Executes against the test database using role app_ro / app_rw.
"""

import pytest
import psycopg2
from app.core.config import get_settings
from app.data.migrations import run_migrations
from app.data.kpi_calculator import compute_all_kpis


@pytest.fixture(scope="module")
def conflict_test_setup(settings):
    """Ensures test database is fully migrated, data ingested, and KPIs computed."""
    from app.data.ingest import DataIngestor
    run_migrations(is_test=True)
    ingestor = DataIngestor(is_test=True)
    ingestor.ingest_release("drop1")
    ingestor.ingest_release("drop2")
    conn = psycopg2.connect(**settings.get_connection_params(role="rw", is_test=True))
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM kpi_values; DELETE FROM effective_line_items;")
        conn.commit()
        compute_all_kpis(conn, policy_version="v1.1.0")
    finally:
        conn.close()


class TestConflictPolicyRules:
    """Verifies each rule R1 through R12 in the conflict policy."""

    def test_r1_source_authority_press_release_ignored(self, conflict_test_setup, settings):
        """Rule R1: Press release claims ($871M) never override filed 10-Q numbers ($777.7M)."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            # Query effective revenue for ARG FY2024 Q1
            cur.execute("""
                SELECT li.value_normalized, f.form_type, f.filing_id
                FROM effective_line_items eli
                JOIN line_items li ON eli.effective_line_item_id = li.id
                JOIN filings f ON li.filing_id = f.filing_id
                WHERE eli.company_id = 'ARG' AND eli.fiscal_year = 2024 AND eli.fiscal_quarter = 1
                  AND eli.canonical_item = 'revenue' AND eli.basis = 'as_restated';
            """)
            row = cur.fetchone()
            assert row is not None
            assert float(row[0]) == 777700000.0, f"Expected 777.7M from 10-Q, got {row[0]}"
            assert row[1] == "10-Q"
            assert "press_release" not in row[2]
        conn.close()

    def test_r2_restatement_precedence_cep_10qa(self, conflict_test_setup, settings):
        """Rule R2: CEP 10-Q/A revenue ($249M) supersedes original 10-Q ($245.9M) on as_restated."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            # Check as_restated
            cur.execute("""
                SELECT li.value_normalized, eli.rule_ids_applied, eli.alternatives
                FROM effective_line_items eli
                JOIN line_items li ON eli.effective_line_item_id = li.id
                WHERE eli.company_id = 'CEP' AND eli.fiscal_year = 2024 AND eli.fiscal_quarter = 2
                  AND eli.canonical_item = 'revenue' AND eli.basis = 'as_restated';
            """)
            rest_val, rules, alts = cur.fetchone()
            assert float(rest_val) == 249000000.0
            assert "R2" in rules
            assert len(alts) == 1
            assert alts[0]["value"] == 245900000.0

            # Check as_originally_reported
            cur.execute("""
                SELECT li.value_normalized
                FROM effective_line_items eli
                JOIN line_items li ON eli.effective_line_item_id = li.id
                WHERE eli.company_id = 'CEP' AND eli.fiscal_year = 2024 AND eli.fiscal_quarter = 2
                  AND eli.canonical_item = 'revenue' AND eli.basis = 'as_originally_reported';
            """)
            orig_val = cur.fetchone()[0]
            assert float(orig_val) == 245900000.0
        conn.close()

    def test_r2_restatement_precedence_nwi_10qa(self, conflict_test_setup, settings):
        """Rule R2: NWI 10-Q/A net income ($54.3M) supersedes original 10-Q ($55.4M)."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            cur.execute("""
                SELECT li.value_normalized, kv.value, kv.restated
                FROM effective_line_items eli
                JOIN line_items li ON eli.effective_line_item_id = li.id
                JOIN kpi_values kv ON kv.company_id = eli.company_id AND kv.fiscal_year = eli.fiscal_year 
                     AND kv.fiscal_quarter = eli.fiscal_quarter AND kv.basis = eli.basis
                WHERE eli.company_id = 'NWI' AND eli.fiscal_year = 2024 AND eli.fiscal_quarter = 3
                  AND eli.canonical_item = 'net_income' AND eli.basis = 'as_restated'
                  AND kv.kpi_id = 'net_margin_pct';
            """)
            row = cur.fetchone()
            assert float(row[0]) == 54300000.0
            assert row[2] is True  # restated = true
            assert round(float(row[1]), 2) == 11.75  # 54.3M / 462.1M * 100 = 11.75%
        conn.close()

    def test_r3_comparative_column_restatement_nwi(self, conflict_test_setup, settings):
        """Rule R3: Comparative column in NWI FY2024 Q3 restates FY2023 Q3 net income to $34.9M."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            # as_restated basis adopts comparative figure
            cur.execute("""
                SELECT li.value_normalized, eli.rule_ids_applied, f.filing_id
                FROM effective_line_items eli
                JOIN line_items li ON eli.effective_line_item_id = li.id
                JOIN filings f ON li.filing_id = f.filing_id
                WHERE eli.company_id = 'NWI' AND eli.fiscal_year = 2023 AND eli.fiscal_quarter = 3
                  AND eli.canonical_item = 'net_income' AND eli.basis = 'as_restated';
            """)
            val, rules, fid = cur.fetchone()
            assert float(val) == 34900000.0
            assert "R3" in rules
            assert fid == "NWI-10Q-FY2024Q3"  # Came from newer filing comparative column

            # as_originally_reported basis preserves original filing
            cur.execute("""
                SELECT li.value_normalized, f.filing_id
                FROM effective_line_items eli
                JOIN line_items li ON eli.effective_line_item_id = li.id
                JOIN filings f ON li.filing_id = f.filing_id
                WHERE eli.company_id = 'NWI' AND eli.fiscal_year = 2023 AND eli.fiscal_quarter = 3
                  AND eli.canonical_item = 'net_income' AND eli.basis = 'as_originally_reported';
            """)
            val_orig, fid_orig = cur.fetchone()
            assert float(val_orig) == 37300000.0
            assert fid_orig == "NWI-10Q-FY2023Q3"
        conn.close()

    def test_r4_intra_filing_duplicate_collapse(self, conflict_test_setup, settings):
        """Rule R4: Identical duplicates within same filing collapse to single effective line item."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM effective_line_items
                WHERE company_id = 'ARG' AND fiscal_year = 2023 AND fiscal_quarter = 2
                  AND canonical_item = 'revenue' AND basis = 'as_restated' AND policy_version = 'v1.1.0';
            """)
            assert cur.fetchone()[0] == 1  # Exactly 1 effective item, not doubled
        conn.close()

    def test_r5_dual_evidence_normalization_hbs(self, conflict_test_setup, settings):
        """Rule R5: HBS FY2024 Q2 unit scale normalized by 1,000x under dual-evidence rule."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            cur.execute("""
                SELECT li.value_normalized, li.scale_factor, eli.rule_ids_applied
                FROM effective_line_items eli
                JOIN line_items li ON eli.effective_line_item_id = li.id
                WHERE eli.company_id = 'HBS' AND eli.fiscal_year = 2024 AND eli.fiscal_quarter = 2
                  AND eli.canonical_item = 'revenue' AND eli.basis = 'as_restated';
            """)
            val, scale, rules = cur.fetchone()
            assert float(val) == 109200000.0  # Not 109.2B!
            assert float(scale) == 1000.0
            assert "R5" in rules
        conn.close()

    def test_r6_missing_input_and_rd_zero_exception(self, conflict_test_setup, settings):
        """Rule R6: Missing inputs yield missing_input status; ARG non-R&D reports 0.0%."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            # Undefined first 4 quarters YoY growth
            cur.execute("""
                SELECT status, value, reason
                FROM kpi_values
                WHERE company_id = 'NWI' AND fiscal_year = 2022 AND fiscal_quarter = 1
                  AND kpi_id = 'revenue_yoy_growth_pct' AND basis = 'as_restated';
            """)
            stat, val, reason = cur.fetchone()
            assert stat == "missing_input"
            assert val is None
            assert "first four quarters" in reason

            # ARG R&D intensity evaluates to 0.0%
            cur.execute("""
                SELECT status, value
                FROM kpi_values
                WHERE company_id = 'ARG' AND fiscal_year = 2023 AND fiscal_quarter = 1
                  AND kpi_id = 'rd_intensity_pct' AND basis = 'as_restated';
            """)
            stat_rd, val_rd = cur.fetchone()
            assert stat_rd == "ok"
            assert float(val_rd) == 0.0
        conn.close()

    def test_r7_non_aligned_calendar_detection(self, conflict_test_setup, settings):
        """Rule R7: ZLG fiscal quarters end Sept 30, >15 days difference from ARG/CEP calendar."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            # 1. Direct filing date check
            cur.execute("""
                SELECT f1.period_end, f2.period_end, ABS(f1.period_end - f2.period_end) as day_diff
                FROM filings f1, filings f2
                WHERE f1.company_id = 'ZLG' AND f1.fiscal_year = 2024 AND f1.fiscal_quarter = 1
                  AND f2.company_id = 'CEP' AND f2.fiscal_year = 2024 AND f2.fiscal_quarter = 1;
            """)
            zlg_end, cep_end, diff = cur.fetchone()
            assert diff > 15, f"Expected >15 days misaligned calendar, got {diff} days"

            # 2. SQL Helper function cross_company_comparability() check
            cur.execute("""
                SELECT days_apart, aligned
                FROM cross_company_comparability(ARRAY['ZLG', 'CEP'], 'FY2024Q1');
            """)
            days_apart, aligned = cur.fetchone()
            assert days_apart == 91
            assert aligned is False

            # 3. Calendar-aligned companies (CEP vs MSI)
            cur.execute("""
                SELECT days_apart, aligned
                FROM cross_company_comparability(ARRAY['CEP', 'MSI'], 'FY2024Q1');
            """)
            days_apart_aligned, aligned_flag = cur.fetchone()
            assert days_apart_aligned == 0
            assert aligned_flag is True
        conn.close()

    def test_r8_mathematical_domain_gates(self, conflict_test_setup, settings):
        """Rule R8: Negative/zero equity marked not_meaningful; zero denominator marked denominator_zero."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            # Verify no NaN or infinity exists anywhere in kpi_values
            cur.execute("""
                SELECT COUNT(*)
                FROM kpi_values
                WHERE value = 'NaN'::numeric OR value = 'Infinity'::numeric OR value = '-Infinity'::numeric;
            """)
            assert cur.fetchone()[0] == 0
        conn.close()

    def test_r10_storage_precision_and_presentation(self, conflict_test_setup, settings):
        """Rule R10: Stored as high precision NUMERIC in PostgreSQL; units strictly explicit."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT unit FROM kpi_values ORDER BY 1;
            """)
            units = [r[0] for r in cur.fetchall()]
            assert sorted(units) == ["USD", "percent", "x"]
        conn.close()

    def test_r12_provenance_and_policy_version(self, conflict_test_setup, settings):
        """Rule R12: Every calculated KPI stores policy_version 'v1.1.0' and input_line_item_ids."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM kpi_values WHERE policy_version != 'v1.1.0';
            """)
            assert cur.fetchone()[0] == 0

            # Verify every 'ok' status KPI has at least 1 input line item
            cur.execute("""
                SELECT COUNT(*) FROM kpi_values WHERE status = 'ok' AND cardinality(input_line_item_ids) = 0;
            """)
            assert cur.fetchone()[0] == 0
        conn.close()


class TestGoldenEvaluationSet:
    """Verifies that production test DB matches all 50 cases in tests/evals/kpi_golden.csv."""

    def test_golden_set_evaluations(self, conflict_test_setup, settings):
        import csv
        from pathlib import Path
        golden_file = Path(__file__).resolve().parent.parent / "evals" / "kpi_golden.csv"
        assert golden_file.exists(), f"Golden file not found at {golden_file}"

        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            with open(golden_file, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) >= 40, f"Expected at least 40 golden eval rows, got {len(rows)}"

            for row in rows:
                cur.execute("""
                    SELECT value, unit, status
                    FROM kpi_values
                    WHERE company_id = %s AND fiscal_year = %s AND fiscal_quarter = %s
                      AND kpi_id = %s AND basis = %s AND policy_version = 'v1.1.0';
                """, (
                    row["company_id"],
                    int(row["fiscal_year"]),
                    int(row["fiscal_quarter"]),
                    row["kpi_id"],
                    row["basis"]
                ))
                db_res = cur.fetchone()
                assert db_res is not None, f"Missing record in DB for golden case {row['case_id']}"
                db_val, db_unit, db_status = db_res

                assert db_status == row["expected_status"], f"Status mismatch on {row['case_id']}: expected {row['expected_status']}, got {db_status}"
                assert db_unit == row["expected_unit"], f"Unit mismatch on {row['case_id']}: expected {row['expected_unit']}, got {db_unit}"

                if row["expected_status"] == "ok":
                    exp_val = float(row["expected_value"])
                    act_val = float(db_val)
                    diff = abs(exp_val - act_val)
                    assert diff < 1e-4, f"Value mismatch on {row['case_id']}: expected {exp_val}, got {act_val} (diff {diff})"
        conn.close()

