#!/usr/bin/env bash
set -euo pipefail

# Change to project root (directory containing this script)
cd "$(dirname "$0")"

# Activate virtualenv if present
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  echo "Warning: virtualenv not found at .venv. Activate your environment manually if needed." >&2
fi

export PYTHONPATH="$(pwd)"

# Load .env (simple KEY=VALUE lines)
if [ -f .env ]; then
  # Use awk for portability
  export $(awk -F= '/^[^#]/ && NF>=2 {gsub(/^[ \t]+|[ \t]+$/,"",$1); gsub(/^[ \t]+|[ \t]+$/,"",$2); print $1"="$2}' .env)
fi

# Ensure output directories exist
mkdir -p data/reports logs

# Prefer running the unix snapshot script; fallback to python collector if missing
if [ -x "scripts/daily_snapshot_unix.sh" ]; then
  exec "scripts/daily_snapshot_unix.sh"
else
  # fallback: call the python cron script which writes to DB and reports
  python scripts/daily_snapshot.py --urls data/sample_urls.txt --queries data/geo_queries.txt --site yourdomain.co.za --db data/snapshots.db --server http://127.0.0.1:8000
fi

# Log success timestamp (this line is reached only if the fallback returns)
echo "OK $(date -Is)" >> logs/daily_reports.log
