#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
import httpx

def main():
    p = argparse.ArgumentParser(description="Collect geo/AEO checks via local API")
    p.add_argument("--queries", required=True, help="File with one query per line")
    p.add_argument("--site", required=True, help="Site hostname to check (e.g. example.co.za)")
    p.add_argument("--out", required=True, help="Output CSV path")
    p.add_argument("--server", default="http://127.0.0.1:8000", help="FastAPI server base URL")
    args = p.parse_args()

    queries_file = Path(args.queries)
    if not queries_file.exists():
        raise SystemExit(f"Queries file not found: {queries_file}")

    queries = [l.strip() for l in queries_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    with httpx.Client(timeout=30) as client:
        for q in queries:
            payload = {"queries": [q], "site_hostname": args.site}
            try:
                r = client.post(f"{args.server}/geo/check", json=payload)
                r.raise_for_status()
                data = r.json()
                rows.append({"query": q, "status": "ok", "result": json.dumps(data, ensure_ascii=False)})
                print(f"OK: {q}")
            except Exception as e:
                rows.append({"query": q, "status": "error", "result": str(e)})
                print(f"ERROR: {q} -> {e}")

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["query", "status", "result"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()
