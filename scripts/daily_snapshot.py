#!/usr/bin/env python3
"""
Daily snapshot script.

Example crontab (run daily at 02:10):
# Edit crontab: crontab -e
10 2 * * * /path/to/venv/bin/python /full/path/to/ExtraRank/scripts/daily_snapshot.py --urls /full/path/to/ExtraRank/data/sample_urls.txt --queries /full/path/to/ExtraRank/data/geo_queries.txt --site yourdomain.co.za --db /full/path/to/ExtraRank/data/snapshots.db --server http://127.0.0.1:8000 >> /full/path/to/ExtraRank/logs/daily_snapshot.log 2>&1

Notes:
- Activate your virtualenv in the crontab command if needed.
- Ensure the FastAPI server is running before the cron job (uvicorn app.main:app --reload).
"""
import argparse
import sys
import json
from pathlib import Path
import httpx
from typing import List, Dict
# Import the DB helper from the package
from app.db import init_db, save_snapshot

def read_lines(p: Path) -> List[str]:
    if not p.exists():
        return []
    return [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

def collect_psi(server: str, urls: List[str], strategy: str = "mobile") -> List[Dict]:
    rows = []
    if not urls:
        return rows
    with httpx.Client(timeout=30) as client:
        for url in urls:
            try:
                r = client.get(f"{server.rstrip('/')}/audit/psi", params={"url": url, "strategy": strategy})
                r.raise_for_status()
                data = r.json()
                summary = data.get("lighthouse_summary", {}) or {}
                core = summary.get("core_web_vitals", {}) or {}
                rows.append({
                    "url": url,
                    "status": "ok",
                    "score": summary.get("performance_score"),
                    "lcp": core.get("lcp"),
                    "cls": core.get("cls"),
                    "raw": data.get("raw", {})
                })
            except Exception as e:
                rows.append({"url": url, "status": "error", "score": None, "lcp": None, "cls": None, "raw": str(e)})
    return rows

def collect_geo(server: str, queries: List[str], site: str) -> List[Dict]:
    rows = []
    if not queries:
        return rows
    with httpx.Client(timeout=30) as client:
        for q in queries:
            payload = {"queries": [q], "site_hostname": site}
            try:
                r = client.post(f"{server.rstrip('/')}/geo/check", json=payload)
                r.raise_for_status()
                data = r.json()
                rows.append({"query": q, "status": "ok", "result": data})
            except Exception as e:
                rows.append({"query": q, "status": "error", "result": str(e)})
    return rows

def main():
    p = argparse.ArgumentParser(description="Run daily snapshots and store to SQLite")
    p.add_argument("--urls", required=True, help="File with one URL per line")
    p.add_argument("--queries", required=True, help="File with one geo query per line")
    p.add_argument("--site", required=True, help="Site hostname for geo checks (example.co.za)")
    p.add_argument("--db", required=True, help="SQLite DB path to store snapshots")
    p.add_argument("--server", default="http://127.0.0.1:8000", help="FastAPI server base URL")
    p.add_argument("--strategy", default="mobile", help="PSI strategy (mobile|desktop)")
    args = p.parse_args()

    # Ensure DB schema exists
    try:
        init_db(args.db)
    except Exception as e:
        print(f"FATAL: could not initialize DB at {args.db}: {e}", file=sys.stderr)
        sys.exit(2)

    urls = read_lines(Path(args.urls))
    queries = read_lines(Path(args.queries))

    # Collect data
    psi_rows = collect_psi(args.server, urls, strategy=args.strategy)
    geo_rows = collect_geo(args.server, queries, site=args.site)

    # Save snapshot
    try:
        snapshot_id = save_snapshot(args.db, args.server, notes="daily cron run", psi_rows=psi_rows, geo_rows=geo_rows)
        print(f"Saved snapshot {snapshot_id} with {len(psi_rows)} PSI rows and {len(geo_rows)} GEO rows")
    except Exception as e:
        print(f"FATAL: could not save snapshot: {e}", file=sys.stderr)
        sys.exit(3)

if __name__ == "__main__":
    main()
