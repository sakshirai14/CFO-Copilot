"""app/data/migrations.py

Versioned SQL Migration Runner for CFO Copilot.
Implements Foundation Lock 5 (Data Integrity & Migrations).
Re-running migrations is guaranteed to be an idempotent no-op.
"""

import hashlib
import os
import sys
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import psycopg2
from app.core.config import get_settings


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"


def get_migration_files() -> List[Tuple[str, str, Path]]:
    """Discovers and returns sorted list of (version, name, filepath)."""
    if not MIGRATIONS_DIR.exists():
        return []
    files = sorted([f for f in MIGRATIONS_DIR.iterdir() if f.suffix == ".sql"])
    results = []
    for f in files:
        parts = f.stem.split("_", 1)
        version = parts[0]
        name = parts[1] if len(parts) > 1 else f.stem
        results.append((version, name, f))
    return results


def compute_file_hash(filepath: Path) -> str:
    """Computes SHA-256 checksum of SQL migration content."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        sha.update(f.read())
    return sha.hexdigest()


def ensure_migration_table(conn):
    """Creates schema_migrations table if not exists."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                checksum VARCHAR(64) NOT NULL
            );
        """)
    conn.commit()


def run_migrations(is_test: bool = False) -> List[str]:
    """Runs all pending migrations using cfo_owner role.
    
    Returns list of applied migration versions.
    """
    settings = get_settings()
    db_name = settings.POSTGRES_TEST_DB if is_test else settings.POSTGRES_DB
    print(f"[migrations] Applying migrations to database '{db_name}' as {settings.DB_OWNER_USER}...")

    conn_params = settings.get_connection_params(role="owner", is_test=is_test)
    conn = psycopg2.connect(**conn_params)

    try:
        ensure_migration_table(conn)

        with conn.cursor() as cur:
            cur.execute("SELECT version, checksum FROM schema_migrations;")
            applied = dict(cur.fetchall())

        applied_versions = []
        migration_files = get_migration_files()

        for version, name, filepath in migration_files:
            file_hash = compute_file_hash(filepath)

            if version in applied:
                if applied[version] != file_hash:
                    raise ValueError(
                        f"Migration {version}_{name}.sql checksum mismatch! "
                        f"Recorded: {applied[version]}, Current: {file_hash}. "
                        "Altering applied migrations violates data integrity."
                    )
                print(f"[migrations] Migration {version}_{name}.sql already applied (checksum OK). Skipping.")
                continue

            print(f"[migrations] Executing {version}_{name}.sql...")
            with open(filepath, "r", encoding="utf-8") as f:
                sql_content = f.read()

            with conn.cursor() as cur:
                cur.execute(sql_content)
                cur.execute(
                    "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s);",
                    (version, name, file_hash)
                )
            conn.commit()
            print(f"[migrations] [SUCCESS] Applied {version}_{name}.sql")
            applied_versions.append(version)

        print(f"[migrations] All migrations up to date on '{db_name}'. ({len(applied_versions)} newly applied).")
        return applied_versions

    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument("--test", action="store_true", help="Apply migrations to test database")
    args = parser.parse_args()
    run_migrations(is_test=args.test)
