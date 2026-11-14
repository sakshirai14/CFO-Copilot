"""tests/integration/test_phase1_integration.py

Integration tests for Phase 1 Database & Normalization Layer.
Executed against the isolated test database 'cfo_copilot_test'.
Implements:
- Lock 4 (Idempotency)
- Lock 5 (Data Integrity & Migrations)
- Lock 6 (Role segregation & Tenant RLS Isolation)
"""

import uuid
import psycopg2
import pytest

from app.core.config import get_settings
from app.data.migrations import run_migrations
from app.data.ingest import DataIngestor


@pytest.fixture(scope="module")
def settings():
    return get_settings()


@pytest.fixture(scope="module")
def test_db_setup(settings):
    """Ensures test database migrations and baseline data are loaded."""
    run_migrations(is_test=True)
    ingestor = DataIngestor(is_test=True)
    ingestor.ingest_release("drop1")
    ingestor.ingest_release("drop2")
    return settings


class TestMigrationIntegrity:
    def test_migrations_rerun_is_noop(self, test_db_setup, settings):
        """Foundation Lock 5: Re-running migrations is an idempotent no-op."""
        newly_applied = run_migrations(is_test=True)
        assert len(newly_applied) == 0

        # Verify schema_migrations table
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            cur.execute("SELECT version, name FROM schema_migrations;")
            rows = cur.fetchall()
            versions = [r[0] for r in rows]
            assert "001" in versions
        conn.close()


class TestIngestionIdempotency:
    def test_reingestion_produces_identical_counts(self, test_db_setup, settings):
        """Foundation Lock 4: Re-running Drop 1 and Drop 2 changes zero row counts."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        cur = conn.cursor()
        tables = ["companies", "filings", "raw_financial_rows", "line_items", "data_quality_issues", "documents"]
        counts_before = {}
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t};")
            counts_before[t] = cur.fetchone()[0]
        conn.close()

        # Re-run both drops
        ingestor = DataIngestor(is_test=True)
        ingestor.ingest_release("drop1")
        ingestor.ingest_release("drop2")

        # Verify counts after
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        cur = conn.cursor()
        counts_after = {}
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t};")
            counts_after[t] = cur.fetchone()[0]
        conn.close()

        assert counts_before == counts_after, f"Row count drifted! Before: {counts_before}, After: {counts_after}"
        assert counts_after["companies"] == 6
        assert counts_after["filings"] == 74
        assert counts_after["raw_financial_rows"] == 1732
        assert counts_after["line_items"] == 1732
        assert counts_after["documents"] == 77


class TestRolePermissions:
    def test_app_ro_read_only_enforcement(self, test_db_setup, settings):
        """Foundation Lock 6: app_ro cannot execute INSERT, UPDATE, or DELETE."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        cur = conn.cursor()

        # Read must succeed
        cur.execute("SELECT COUNT(*) FROM companies;")
        assert cur.fetchone()[0] > 0

        # INSERT must fail
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("""
                INSERT INTO companies (company_id, name, sector, fiscal_year_end_month, fiscal_year_note)
                VALUES ('HACK', 'Hacked Corp', 'Tech', 12, 'Test');
            """)
        conn.rollback()

        # UPDATE must fail
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("UPDATE companies SET name = 'Defaced' WHERE company_id = 'ARG';")
        conn.rollback()

        # DELETE must fail
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM companies WHERE company_id = 'ARG';")
        conn.rollback()

        conn.close()


class TestTenantIsolationRLS:
    def test_rls_cross_tenant_isolation_and_canary_leakage(self, test_db_setup, settings):
        """Foundation Lock 6: Tenant isolation via PostgreSQL Row-Level Security (RLS).
        
        Writes canary string under tenant 'acme'. Asserts it is 100% invisible to tenant 'borealis'.
        """
        canary_uuid = f"CANARY_SECRET_TOKEN_{uuid.uuid4().hex}"
        session_id_acme = f"sess_acme_{uuid.uuid4().hex[:8]}"
        msg_id_acme = f"msg_acme_{uuid.uuid4().hex[:8]}"

        conn_acme = psycopg2.connect(**settings.get_connection_params(role="rw", is_test=True))
        conn_borealis = psycopg2.connect(**settings.get_connection_params(role="rw", is_test=True))

        try:
            # 1. Tenant Acme sets context and inserts canary session and message
            with conn_acme.cursor() as cur:
                cur.execute("SET app.current_tenant = 'acme';")
                cur.execute("""
                    INSERT INTO chat_sessions (session_id, tenant_id, user_id, title)
                    VALUES (%s, 'acme', 'cfo_user_acme', 'Confidential Acme Strategy');
                """, (session_id_acme,))

                cur.execute("""
                    INSERT INTO chat_messages (message_id, session_id, tenant_id, role, content)
                    VALUES (%s, %s, 'acme', 'user', %s);
                """, (msg_id_acme, session_id_acme, f"Strategic M&A payload: {canary_uuid}"))
            conn_acme.commit()

            # Verify Acme can see its own message
            with conn_acme.cursor() as cur:
                cur.execute("SET app.current_tenant = 'acme';")
                cur.execute("SELECT content FROM chat_messages WHERE session_id = %s;", (session_id_acme,))
                row = cur.fetchone()
                assert row is not None
                assert canary_uuid in row[0]

            # 2. Tenant Borealis connects and attempts to read or leak Acme data
            with conn_borealis.cursor() as cur:
                cur.execute("SET app.current_tenant = 'borealis';")

                # Borealis queries all chat messages for the canary string
                cur.execute("SELECT COUNT(*) FROM chat_messages WHERE content LIKE %s;", (f"%{canary_uuid}%",))
                cnt = cur.fetchone()[0]
                assert cnt == 0, "CRITICAL SECURITY BREACH: Borealis saw Acme's canary string!"

                # Borealis queries chat_sessions for Acme's session ID
                cur.execute("SELECT COUNT(*) FROM chat_sessions WHERE session_id = %s;", (session_id_acme,))
                assert cur.fetchone()[0] == 0, "CRITICAL SECURITY BREACH: Borealis saw Acme's session!"

                # Borealis tries to spoof and insert a message under tenant 'acme'
                with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                    cur.execute("""
                        INSERT INTO chat_messages (message_id, session_id, tenant_id, role, content)
                        VALUES (%s, %s, 'acme', 'user', 'Spoofed Message');
                    """, (f"spoof_{uuid.uuid4().hex[:8]}", session_id_acme))
                conn_borealis.rollback()

        finally:
            conn_acme.close()
            conn_borealis.close()


class TestIsolationHardening:
    """Verifies Lock 6 isolation hardening: role privileges, bypassrls, and tenant_documents."""

    def test_role_privileges_and_bypassrls_prohibited(self, test_db_setup, settings):
        """Asserts app_rw, app_ro, and cfo_owner are NOT superusers and do NOT possess BYPASSRLS."""
        conn = psycopg2.connect(**settings.get_connection_params(role="owner", is_test=True))
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rolname, rolsuper, rolbypassrls 
                FROM pg_roles 
                WHERE rolname IN ('cfo_owner', 'app_rw', 'app_ro');
            """)
            roles = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

        conn.close()

        for role_name in ("cfo_owner", "app_rw", "app_ro"):
            assert role_name in roles, f"Role {role_name} missing from pg_roles!"
            is_super, bypass_rls = roles[role_name]
            assert not is_super, f"SECURITY VIOLATION: Role {role_name} has superuser privileges!"
            assert not bypass_rls, f"SECURITY VIOLATION: Role {role_name} has BYPASSRLS privilege!"

    def test_tenant_documents_rls_canary(self, test_db_setup, settings):
        """Tests RLS enforcement on tenant_documents table using seeded canary records."""
        conn_acme = psycopg2.connect(**settings.get_connection_params(role="rw", is_test=True))
        conn_borealis = psycopg2.connect(**settings.get_connection_params(role="rw", is_test=True))

        try:
            # Acme context
            with conn_acme.cursor() as cur:
                cur.execute("SET app.current_tenant = 'acme';")
                cur.execute("SELECT doc_text FROM tenant_documents;")
                acme_docs = [r[0] for r in cur.fetchall()]
                assert any("CANARY_ACME_CONFIDENTIAL_DOCUMENT_PAYLOAD" in d for d in acme_docs)
                assert not any("CANARY_BOREALIS" in d for d in acme_docs)

            # Borealis context
            with conn_borealis.cursor() as cur:
                cur.execute("SET app.current_tenant = 'borealis';")
                cur.execute("SELECT doc_text FROM tenant_documents;")
                borealis_docs = [r[0] for r in cur.fetchall()]
                assert any("CANARY_BOREALIS_CONFIDENTIAL_DOCUMENT_PAYLOAD" in d for d in borealis_docs)
                assert not any("CANARY_ACME" in d for d in borealis_docs)

                # Borealis cannot insert under tenant 'acme'
                with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                    cur.execute("""
                        INSERT INTO tenant_documents (tenant_id, title, doc_text, content_hash)
                        VALUES ('acme', 'Hacked Doc', 'Payload', 'hash_hack');
                    """)
                conn_borealis.rollback()

        finally:
            conn_acme.close()
            conn_borealis.close()


class TestMissingPhase1Requirements:
    """Verifies ARG duplicate collapse, NWI amendment linking, and natural key conflict logging."""

    def test_arg_duplicate_collapse(self, test_db_setup, settings):
        """Verifies duplicate line items in ARG-10Q-FY2023Q2 are linked via duplicate_of_id."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, status, duplicate_of_id, value_normalized
                FROM line_items
                WHERE filing_id = 'ARG-10Q-FY2023Q2' AND canonical_item = 'revenue'
                ORDER BY id ASC;
            """)
            rows = cur.fetchall()
            assert len(rows) == 2, f"Expected exactly 2 rows for ARG revenue, got {len(rows)}"
            orig, dup = rows[0], rows[1]

            assert orig[1] == "valid"
            assert orig[2] is None
            assert float(orig[3]) == 774400000.0

            assert dup[1] == "duplicate"
            assert dup[2] == orig[0], f"Expected duplicate_of_id={orig[0]}, got {dup[2]}"
            assert float(dup[3]) == 774400000.0

            # Verified: SUM over valid items does NOT double revenue
            cur.execute("""
                SELECT SUM(value_normalized)
                FROM line_items
                WHERE filing_id = 'ARG-10Q-FY2023Q2' AND canonical_item = 'revenue' AND status = 'valid';
            """)
            valid_sum = cur.fetchone()[0]
            assert float(valid_sum) == 774400000.0
        conn.close()

    def test_nwi_amendment_linked_not_overwritten(self, test_db_setup, settings):
        """Verifies NWI-10QA-FY2024Q3 links to NWI-10Q-FY2024Q3 and original rows are preserved."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            cur.execute("""
                SELECT filing_id, form_type, amends_filing_id
                FROM filings
                WHERE filing_id = 'NWI-10QA-FY2024Q3';
            """)
            f = cur.fetchone()
            assert f is not None
            assert f[1] == "10-Q/A"
            assert f[2] == "NWI-10Q-FY2024Q3"

            # Check both original and restated revenue coexist in line_items
            cur.execute("""
                SELECT f.filing_id, l.value_normalized
                FROM line_items l
                JOIN filings f ON l.filing_id = f.filing_id
                WHERE f.filing_id IN ('NWI-10Q-FY2024Q3', 'NWI-10QA-FY2024Q3')
                  AND l.canonical_item = 'revenue'
                ORDER BY f.filing_id;
            """)
            revs = dict(cur.fetchall())
            assert "NWI-10Q-FY2024Q3" in revs
            assert "NWI-10QA-FY2024Q3" in revs
            assert float(revs["NWI-10Q-FY2024Q3"]) == 466300000.0  # Original
            assert float(revs["NWI-10QA-FY2024Q3"]) == 462100000.0  # Amended (-$4.2M)
        conn.close()

    def test_natural_key_conflict_creates_issue_not_overwritten(self, test_db_setup, settings):
        """Verifies conflicting natural keys are logged as issues and never silently overwrite data."""
        conn = psycopg2.connect(**settings.get_connection_params(role="ro", is_test=True))
        with conn.cursor() as cur:
            # Check data_quality_issues has logged intra-filing duplicate issues
            cur.execute("""
                SELECT COUNT(*) FROM data_quality_issues
                WHERE issue_type = 'intra_filing_duplicate' AND company_id = 'ARG';
            """)
            cnt = cur.fetchone()[0]
            assert cnt >= 3, "Expected intra_filing_duplicate issues logged for ARG Q2 2023"
        conn.close()


class TestMigrationDiscipline:
    def test_migration_checksum_mismatch_fails(self, test_db_setup, settings):
        """Verifies migration runner halts with ValueError when an applied migration is modified."""
        conn = psycopg2.connect(**settings.get_connection_params(role="owner", is_test=True))
        with conn.cursor() as cur:
            # Temporarily simulate a checksum corruption in schema_migrations
            cur.execute("SELECT checksum FROM schema_migrations WHERE version = '001';")
            real_checksum = cur.fetchone()[0]

            cur.execute("UPDATE schema_migrations SET checksum = 'corrupted_fake_hash' WHERE version = '001';")
        conn.commit()

        try:
            with pytest.raises(ValueError, match="checksum mismatch"):
                run_migrations(is_test=True)
        finally:
            # Restore genuine checksum
            with conn.cursor() as cur:
                cur.execute("UPDATE schema_migrations SET checksum = %s WHERE version = '001';", (real_checksum,))
            conn.commit()
            conn.close()


