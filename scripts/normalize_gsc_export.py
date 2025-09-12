#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

# Common header mapping (lowercased keys -> normalized name)
HEADER_MAP = {
    "query": "query",
    "search query": "query",
    "clicks": "clicks",
    "impressions": "impressions",
    "ctr": "ctr",
    "click-through rate": "ctr",
    "position": "position",
    "avg. position": "position",
    "average position": "position",
}

def normalize_row(row):
    out = {"query": "", "clicks": "", "impressions": "", "ctr": "", "position": ""}
    for k, v in row.items():
        if k is None:
            continue
        nk = k.strip().lower()
        mapped = HEADER_MAP.get(nk)
        if mapped:
            out[mapped] = v
    # If query blank, try first non-empty value
    if not out["query"]:
        for v in row.values():
            if v and v.strip():
                out["query"] = v.strip()
                break
    return out

def main():
    p = argparse.ArgumentParser(description="Normalize Google Search Console CSV export")
    p.add_argument("--infile", required=True, help="Raw GSC CSV file path")
    p.add_argument("--out", required=True, help="Normalized CSV output path")
    args = p.parse_args()

    infile = Path(args.infile)
    if not infile.exists():
        raise SystemExit(f"infile not found: {infile}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with infile.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        rows = [normalize_row(r) for r in reader]

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["query", "clicks", "impressions", "ctr", "position"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote normalized GSC CSV to {out_path}")

if __name__ == "__main__":
    main()
