#!/usr/bin/env python3
"""scripts/setup_db_roles.py

Idempotent setup for PostgreSQL databases, pgvector extension, and 3-tier role architecture.
Can be executed against any running PostgreSQL instance (Docker or local).
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from app.core.config import get_settings


def setup_databases_and_roles():
    settings = get_settings()
    print("=" * 60)
    print("INITIALIZING POSTGRESQL ROLES & DATABASES (Foundation Lock 6)")
    print("=" * 60)

    admin_params = {
        "host": settings.POSTGRES_HOST,
        "port": settings.POSTGRES_PORT,
        "user": settings.POSTGRES_USER,
        "password": settings.POSTGRES_PASSWORD,
        "dbname": "postgres",
        "connect_timeout": 5,
    }

    print(f"Connecting to Postgres at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT} as {settings.POSTGRES_USER}...")
    conn = None
    last_err = None
    for attempt in range(15):
        try:
            conn = psycopg2.connect(**admin_params)
            break
        except psycopg2.OperationalError as e:
            last_err = e
            try:
                admin_params_alt = dict(admin_params)
                admin_params_alt["dbname"] = settings.POSTGRES_DB
                conn = psycopg2.connect(**admin_params_alt)
                break
            except psycopg2.OperationalError:
                pass
            time.sleep(1.0)
    
    if conn is None:
        raise last_err

    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # 1. Ensure databases exist
    for db_name in [settings.POSTGRES_DB, settings.POSTGRES_TEST_DB]:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
        if not cur.fetchone():
            print(f"Creating database: {db_name}")
            cur.execute(f'CREATE DATABASE "{db_name}";')
        else:
            print(f"Database already exists: {db_name}")

    # 2. Ensure roles exist with configured passwords
    roles = [
        (settings.DB_OWNER_USER, settings.DB_OWNER_PASSWORD, "cfo_owner (DDL/Migrations)"),
        (settings.DB_APP_RW_USER, settings.DB_APP_RW_PASSWORD, "app_rw (Ingest/Chat RW)"),
        (settings.DB_APP_RO_USER, settings.DB_APP_RO_PASSWORD, "app_ro (Strictly Read-Only)"),
    ]

    for role_name, password, desc in roles:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s;", (role_name,))
        if not cur.fetchone():
            print(f"Creating role: {desc}")
            cur.execute(f"CREATE ROLE {role_name} WITH LOGIN PASSWORD %s;", (password,))
        else:
            print(f"Updating password for role: {desc}")
            cur.execute(f"ALTER ROLE {role_name} WITH PASSWORD %s;", (password,))

    cur.close()
    conn.close()

    # 3. Configure each database (extensions, permissions, default privileges)
    for db_name in [settings.POSTGRES_DB, settings.POSTGRES_TEST_DB]:
        print(f"\nConfiguring schema permissions on database: {db_name}")
        db_admin_params = dict(admin_params)
        db_admin_params["dbname"] = db_name

        db_conn = psycopg2.connect(**db_admin_params)
        db_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        db_cur = db_conn.cursor()

        # Enable pgvector
        try:
            db_cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            print(f"  [+] pgvector extension verified on {db_name}")
        except Exception as e:
            print(f"  [-] Warning: could not enable pgvector: {e}")

        # Set owner
        db_cur.execute(f'ALTER DATABASE "{db_name}" OWNER TO {settings.DB_OWNER_USER};')
        db_cur.execute(f"GRANT ALL ON SCHEMA public TO {settings.DB_OWNER_USER};")

        # Grant public schema usage
        db_cur.execute(f"GRANT USAGE ON SCHEMA public TO {settings.DB_APP_RW_USER}, {settings.DB_APP_RO_USER};")

        # Table & sequence permissions for app_rw
        db_cur.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {settings.DB_APP_RW_USER};")
        db_cur.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {settings.DB_APP_RW_USER};")

        # Table & sequence permissions for app_ro (READ-ONLY)
        db_cur.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {settings.DB_APP_RO_USER};")
        db_cur.execute(f"GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO {settings.DB_APP_RO_USER};")

        # Set default privileges for objects created in future by cfo_owner
        db_cur.execute(f"""
            ALTER DEFAULT PRIVILEGES FOR ROLE {settings.DB_OWNER_USER} IN SCHEMA public
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {settings.DB_APP_RW_USER};
        """)
        db_cur.execute(f"""
            ALTER DEFAULT PRIVILEGES FOR ROLE {settings.DB_OWNER_USER} IN SCHEMA public
                GRANT SELECT ON TABLES TO {settings.DB_APP_RO_USER};
        """)
        db_cur.execute(f"""
            ALTER DEFAULT PRIVILEGES FOR ROLE {settings.DB_OWNER_USER} IN SCHEMA public
                GRANT USAGE, SELECT ON SEQUENCES TO {settings.DB_APP_RW_USER};
        """)
        db_cur.execute(f"""
            ALTER DEFAULT PRIVILEGES FOR ROLE {settings.DB_OWNER_USER} IN SCHEMA public
                GRANT SELECT ON SEQUENCES TO {settings.DB_APP_RO_USER};
        """)

        db_cur.close()
        db_conn.close()

    print("\nRole and database configuration completed successfully.")


if __name__ == "__main__":
    setup_databases_and_roles()
