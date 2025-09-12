#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
import httpx

def main():
    p = argparse.ArgumentParser(description="Collect PageSpeed Insights via local API")
    p.add_argument("--infile", required=True, help="File with one URL per line")
    p.add_argument("--out", required=True, help="Output CSV path")
    p.add_argument("--strategy", default="mobile", help="pagespeed strategy (mobile|desktop)")
    p.add_argument("--server", default="http://127.0.0.1:8000", help="FastAPI server base URL")
    args = p.parse_args()

    infile = Path(args.infile)
    if not infile.exists():
        raise SystemExit(f"Input file not found: {infile}")

    urls = [l.strip() for l in infile.read_text(encoding="utf-8").splitlines() if l.strip()]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    with httpx.Client(timeout=30) as client:
        for url in urls:
            try:
                r = client.get(f"{args.server}/audit/psi", params={"url": url, "strategy": args.strategy})
                r.raise_for_status()
                data = r.json()
                summary = data.get("lighthouse_summary", {})
                core = summary.get("core_web_vitals", {}) if isinstance(summary, dict) else {}
                rows.append({
                    "url": url,
                    "status": "ok",
                    "score": summary.get("performance_score"),
                    "lcp": core.get("lcp"),
                    "cls": core.get("cls"),
                    "raw": json.dumps(data.get("raw", {}), ensure_ascii=False)
                })
                print(f"OK: {url} -> score {summary.get('performance_score')}")
            except Exception as e:
                rows.append({
                    "url": url,
                    "status": "error",
                    "score": "",
                    "lcp": "",
                    "cls": "",
                    "raw": str(e)
                })
                print(f"ERROR: {url} -> {e}")

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "status", "score", "lcp", "cls", "raw"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()
