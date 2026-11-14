#!/usr/bin/env bash
# scripts/init_db.sh
# Container entrypoint initialization script for PostgreSQL + pgvector
# Configures databases, extensions, and the 3 segregated roles (Lock 6).

set -e

echo "[init_db] Initializing databases and roles..."

# Check if test database exists, create if not
TEST_DB="${POSTGRES_TEST_DB:-cfo_copilot_test}"
MAIN_DB="${POSTGRES_DB:-cfo_copilot}"
OWNER_USER="${DB_OWNER_USER:-cfo_owner}"
RW_USER="${DB_APP_RW_USER:-app_rw}"
RO_USER="${DB_APP_RO_USER:-app_ro}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$MAIN_DB" <<-EOSQL
    SELECT 'CREATE DATABASE $TEST_DB'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$TEST_DB')\gexec
EOSQL

for db in "$MAIN_DB" "$TEST_DB"; do
    echo "[init_db] Configuring database: $db"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" <<-EOSQL
        -- Enable pgvector extension
        CREATE EXTENSION IF NOT EXISTS vector;

        -- Create or update roles
        DO \$\$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$OWNER_USER') THEN
                CREATE ROLE $OWNER_USER WITH LOGIN PASSWORD '$DB_OWNER_PASSWORD';
            ELSE
                ALTER ROLE $OWNER_USER WITH PASSWORD '$DB_OWNER_PASSWORD';
            END IF;

            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$RW_USER') THEN
                CREATE ROLE $RW_USER WITH LOGIN PASSWORD '$DB_APP_RW_PASSWORD';
            ELSE
                ALTER ROLE $RW_USER WITH PASSWORD '$DB_APP_RW_PASSWORD';
            END IF;

            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$RO_USER') THEN
                CREATE ROLE $RO_USER WITH LOGIN PASSWORD '$DB_APP_RO_PASSWORD';
            ELSE
                ALTER ROLE $RO_USER WITH PASSWORD '$DB_APP_RO_PASSWORD';
            END IF;
        END
        \$\$;

        -- Assign database and schema permissions to owner
        ALTER DATABASE $db OWNER TO $OWNER_USER;
        GRANT ALL ON SCHEMA public TO $OWNER_USER;

        -- Grant usage and table access
        GRANT USAGE ON SCHEMA public TO $RW_USER, $RO_USER;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $RW_USER;
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO $RO_USER;

        ALTER DEFAULT PRIVILEGES FOR ROLE $OWNER_USER IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $RW_USER;

        ALTER DEFAULT PRIVILEGES FOR ROLE $OWNER_USER IN SCHEMA public
            GRANT SELECT ON TABLES TO $RO_USER;

        ALTER DEFAULT PRIVILEGES FOR ROLE $OWNER_USER IN SCHEMA public
            GRANT USAGE, SELECT ON SEQUENCES TO $RW_USER;

        ALTER DEFAULT PRIVILEGES FOR ROLE $OWNER_USER IN SCHEMA public
            GRANT SELECT ON SEQUENCES TO $RO_USER;
EOSQL
done

echo "[init_db] Database roles and permissions successfully initialized."

