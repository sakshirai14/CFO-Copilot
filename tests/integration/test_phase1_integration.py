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
