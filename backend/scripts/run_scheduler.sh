#!/usr/bin/env bash
# ==============================================================================
# Production Scheduler Runner for Public Speaking Workshop
# Executes: dispatch_reminders --process-outbox inside Docker backend container
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${REPO_ROOT}"

TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%SZ")
echo "[${TIMESTAMP}] Running reminder dispatcher and outbox processor inside Docker..."

# Check if psw-backend container is running
if docker compose ps --services --filter "status=running" | grep -q "^backend$"; then
  docker compose exec -T backend python manage.py dispatch_reminders --process-outbox "$@"
else
  echo "[${TIMESTAMP}] Warning: backend container is not running. Skipping run." >&2
  exit 0
fi

echo "[${TIMESTAMP}] Completed successfully."
