#!/usr/bin/env bash
set -euo pipefail

# Change to project root (adjust path if your project is elsewhere)
cd /home/asi/extrarank

# Activate virtualenv
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  echo "Warning: virtualenv not found at .venv. Activate your environment manually if needed."
fi

export PYTHONPATH=$(pwd)

# Load .env variables (ignore comments). If .env missing, continue silently.
if [ -f .env ]; then
  # Use awk to avoid xargs -d portability issues
  export $(awk -F= '/^[^#]/ && NF==2 {gsub(/^[ \t]+|[ \t]+$/,"",$1); gsub(/^[ \t]+|[ \t]+$/,"",$2); print $1"="$2}' .env)
fi

# Ensure output directories exist
mkdir -p data/reports logs

# PSI snapshot
python scripts/collect_psi.py --infile data/sample_urls.txt --out data/reports/psi_$(date +%F).csv --strategy mobile

# GEO snapshot
python scripts/collect_geo.py --queries data/geo_queries.txt --site yourdomain.co.za --out data/reports/geo_$(date +%F).csv

echo "OK $(date -Is)" >> logs/daily_reports.log
