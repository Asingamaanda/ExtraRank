import httpx
from typing import Optional
from ..config import settings


PAGESPEED_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


async def fetch_pagespeed(url: str, strategy: str = "mobile") -> dict:
    params = {"url": url, "strategy": strategy}
    if settings.GOOGLE_API_KEY:
        params["key"] = settings.GOOGLE_API_KEY

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(PAGESPEED_URL, params=params)
        r.raise_for_status()
        data = r.json()

    lighthouse = data.get("lighthouseResult", {})
    loading_experience = data.get("loadingExperience")
    origin_loading_experience = data.get("originLoadingExperience")

    summary = {
        "performance_score": lighthouse.get("categories", {}).get("performance", {}).get("score"),
        "core_web_vitals": {
            "lcp": lighthouse.get("audits", {}).get("largest-contentful-paint", {}).get("displayValue"),
            "fid": lighthouse.get("audits", {}).get("max-potential-fid", {}).get("displayValue"),
            "cls": lighthouse.get("audits", {}).get("cumulative-layout-shift", {}).get("displayValue"),
        },
    }

    return {
        "url": url,
        "lighthouse_summary": summary,
        "loading_experience": loading_experience,
        "origin_loading_experience": origin_loading_experience,
        "raw": {"lighthouseResult": lighthouse},
    }
    }
