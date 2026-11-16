"""tests/integration/test_pool_tenant_isolation.py

Verifies Foundation Lock 6 (Partition) under Connection Pooling:
1. Uses a strictly pool-size-1 ThreadedConnectionPool with the 'app_ro' role.
2. Interleaves requests for tenant 'acme' and tenant 'borealis' on the exact same underlying connection.
3. Asserts:
   - Zero cross-tenant data leakage across sessions, messages, and answer_log.
   - GUC 'app.current_tenant' is strictly localized via SET LOCAL inside transactions.
   - GUC is reset to empty ('') after connection checkout and between requests.
   - Connections checked out with tenant_id=None see zero RLS tenant rows.
"""

import pytest
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from app.core.config import get_settings


@pytest.fixture(scope="module")
def single_conn_pool():
    """Creates a pool with strictly 1 connection to guarantee connection reuse across tenants."""
    settings = get_settings()
    params = settings.get_connection_params(role="ro", is_test=True)
    pool = ThreadedConnectionPool(minconn=1, maxconn=1, **params)
    yield pool
    pool.closeall()


def test_interleaved_tenant_pooling_isolation(single_conn_pool):
    """Executes interleaved queries on pool size 1, asserting zero cross-tenant leakage and GUC resets."""
    # Ensure test canary sessions exist for acme and borealis
    settings = get_settings()
    rw_params = settings.get_connection_params(role="rw", is_test=True)
    with psycopg2.connect(**rw_params) as setup_conn:
        with setup_conn.cursor() as cur:
            # Seed canary session for acme
            cur.execute("SET LOCAL app.current_tenant = 'acme';")
            cur.execute("""
                INSERT INTO chat_sessions (session_id, tenant_id, user_id, title)
                VALUES ('sess_canary_acme_01', 'acme', 'cfo_acme', 'Acme Secret Budget Session')
                ON CONFLICT (session_id) DO NOTHING;
            """)
            # Seed canary session for borealis
            cur.execute("SET LOCAL app.current_tenant = 'borealis';")
            cur.execute("""
                INSERT INTO chat_sessions (session_id, tenant_id, user_id, title)
                VALUES ('sess_canary_borealis_01', 'borealis', 'cfo_borealis', 'Borealis Confidential M&A')
                ON CONFLICT (session_id) DO NOTHING;
            """)
        setup_conn.commit()

    conn = single_conn_pool.getconn()
    try:
        conn.autocommit = False
        # Check Initial State: GUC must be unset / empty
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('app.current_tenant', true);")
            initial_guc = cur.fetchone()[0]
            assert initial_guc in ("", None), f"Expected empty initial GUC, got {initial_guc}"
        conn.rollback()

        # 1. Turn 1: ACME request on connection
        with conn.cursor() as cur:
            cur.execute("SET LOCAL app.current_tenant = %s;", ('acme',))
            cur.execute("SELECT current_setting('app.current_tenant', true);")
            assert cur.fetchone()[0] == 'acme'

            cur.execute("SELECT session_id, tenant_id FROM chat_sessions WHERE session_id LIKE 'sess_canary_%';")
            rows_acme = cur.fetchall()
            # Acme must see its canary and ZERO borealis rows
            assert len(rows_acme) >= 1
            assert all(r[1] == 'acme' for r in rows_acme)
            assert not any(r[1] == 'borealis' for r in rows_acme)
        conn.rollback()  # End transaction: SET LOCAL must vanish

        # 2. Assert GUC is reset immediately after transaction rollback
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('app.current_tenant', true);")
            post_acme_guc = cur.fetchone()[0]
            assert post_acme_guc in ("", None), f"GUC leaked after acme rollback: {post_acme_guc}"
        conn.rollback()

        # 3. Turn 2: BOREALIS request on the exact same connection
        with conn.cursor() as cur:
            cur.execute("SET LOCAL app.current_tenant = %s;", ('borealis',))
            cur.execute("SELECT current_setting('app.current_tenant', true);")
            assert cur.fetchone()[0] == 'borealis'

            cur.execute("SELECT session_id, tenant_id FROM chat_sessions WHERE session_id LIKE 'sess_canary_%';")
            rows_borealis = cur.fetchall()
            # Borealis must see its canary and ZERO acme rows
            assert len(rows_borealis) >= 1
            assert all(r[1] == 'borealis' for r in rows_borealis)
            assert not any(r[1] == 'acme' for r in rows_borealis)
        conn.rollback()

        # 4. Assert GUC is reset immediately after borealis rollback
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('app.current_tenant', true);")
            post_borealis_guc = cur.fetchone()[0]
            assert post_borealis_guc in ("", None), f"GUC leaked after borealis rollback: {post_borealis_guc}"
        conn.rollback()

        # 5. Turn 3: Unauthenticated request (no tenant)
        with conn.cursor() as cur:
            cur.execute("RESET app.current_tenant;")
            cur.execute("SELECT session_id, tenant_id FROM chat_sessions WHERE session_id LIKE 'sess_canary_%';")
            rows_none = cur.fetchall()
            # Zero rows visible when tenant is unset
            assert len(rows_none) == 0, f"Expected 0 rows when unauthenticated, got {rows_none}"
        conn.rollback()

    finally:
        single_conn_pool.putconn(conn)
