#!/usr/bin/env bash
# scripts/bootstrap_env.sh
# Generates a git-ignored .env file with secure random passwords if missing.
# Adheres to Foundation Lock 11 (No secrets in repository).

set -euo pipefail

ENV_FILE=".env"
EXAMPLE_FILE=".env.example"

if [ -f "$ENV_FILE" ]; then
    if grep -qE "POSTGRES_PASSWORD=$|POSTGRES_PASSWORD=\"\"" "$ENV_FILE"; then
        echo "[bootstrap_env] Generating random passwords for empty $ENV_FILE..."
    else
        echo "[bootstrap_env] $ENV_FILE already configured. Preserving existing configuration."
        exit 0
    fi
fi

if [ ! -f "$EXAMPLE_FILE" ]; then
    echo "[bootstrap_env] Error: $EXAMPLE_FILE not found!" >&2
    exit 1
fi

echo "[bootstrap_env] Generating fresh $ENV_FILE with cryptographically random passwords..."

# Generate random passwords
PG_PASS=$(openssl rand -hex 16)
OWNER_PASS=$(openssl rand -hex 16)
RW_PASS=$(openssl rand -hex 16)
RO_PASS=$(openssl rand -hex 16)

# Copy template and substitute placeholders
sed \
  -e "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG_PASS}|g" \
  -e "s|DB_OWNER_PASSWORD=.*|DB_OWNER_PASSWORD=${OWNER_PASS}|g" \
  -e "s|DB_APP_RW_PASSWORD=.*|DB_APP_RW_PASSWORD=${RW_PASS}|g" \
  -e "s|DB_APP_RO_PASSWORD=.*|DB_APP_RO_PASSWORD=${RO_PASS}|g" \
  "$EXAMPLE_FILE" > "$ENV_FILE"

# Restrict permissions so only the owner can read/write
chmod 600 "$ENV_FILE"

echo "[bootstrap_env] Successfully created $ENV_FILE (permissions 600)."
echo "[bootstrap_env] Database roles configured: cfo_owner (migrations), app_rw (ingest/write), app_ro (read-only)."

