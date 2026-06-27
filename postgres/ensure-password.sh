#!/bin/bash
set -Eeuo pipefail

# Run the official entrypoint to handle init, config, and startup.
# It ultimately `exec postgres` so it replaces the subshell.
docker-entrypoint.sh "$@" &

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-admin}"

# Wait until postgres accepts connections (Unix socket → peer auth, no password needed).
until pg_isready -U "$POSTGRES_USER" -q; do
  sleep 1
done

# Sync the password so SPRING_DATASOURCE_PASSWORD always works,
# even when the volume was originally created with a different password.
psql -U "$POSTGRES_USER" -c "ALTER USER \"$POSTGRES_USER\" WITH PASSWORD '${POSTGRES_PASSWORD}';"

# Re-attach to postgres so signals (SIGTERM from docker stop) reach it.
wait
