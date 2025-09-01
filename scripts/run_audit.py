import asyncio
import csv
from pathlib import Path
from app.services.psi import fetch_pagespeed

INPUT = Path("urls.txt")
OUTPUT = Path("psi_audit.csv")


async def run():
    if not INPUT.exists():
        print("Create a urls.txt file with one URL per line in the project root.")
        return

    urls = [line.strip() for line in INPUT.read_text().splitlines() if line.strip()]
    rows = []
    for u in urls:
        try:
            data = await fetch_pagespeed(u)
            score = data["lighthouse_summary"].get("performance_score")
            lcp = data["lighthouse_summary"]["core_web_vitals"].get("lcp")
            cls = data["lighthouse_summary"]["core_web_vitals"].get("cls")
            rows.append({"url": u, "score": score, "lcp": lcp, "cls": cls})
            print(f"Audited {u} -> score {score}")
        except Exception as e:
            print(f"Failed {u}: {e}")
            rows.append({"url": u, "score": "error", "lcp": "", "cls": ""})

    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "score", "lcp", "cls"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(run())
