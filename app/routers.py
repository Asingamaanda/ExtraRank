from fastapi import APIRouter, Query
from .services import psi as psi_svc
from .services import seo as seo_svc
from .services import indexnow as idx_svc
from .schemas import (
    PsiResponse,
    SeoGenerateRequest,
    SeoGenerateResponse,
    IndexNowRequest,
    GscRequest,
    GeoCheckRequest,
)
from typing import Optional

router = APIRouter(prefix="", tags=["api"])


@router.get("/audit/psi", response_model=PsiResponse)
async def audit_psi(url: str = Query(..., description="Page URL to audit"), strategy: Optional[str] = "mobile"):
    data = await psi_svc.fetch_pagespeed(url, strategy=strategy)
    return {
        "url": data.get("url"),
        "lighthouse_summary": data.get("lighthouse_summary"),
        "loading_experience": data.get("loading_experience"),
        "origin_loading_experience": data.get("origin_loading_experience"),
    }


@router.post("/seo/generate-meta", response_model=SeoGenerateResponse)
def seo_generate_meta(payload: SeoGenerateRequest):
    out = seo_svc.generate_meta(payload.dict())
    return {"title": out["title"], "meta_description": out["meta_description"], "og": out["og"]}


@router.post("/indexnow/submit")
async def indexnow_submit(payload: IndexNowRequest):
    result = await idx_svc.submit_indexnow(payload.host, payload.key, payload.urls)
    return result


@router.post("/gsc/performance")
def gsc_performance(payload: GscRequest):
    return {"message": "GSC performance is a stub. Implement OAuth and call Search Console API.", "received": payload.dict()}


@router.post("/geo/check")
def geo_check(payload: GeoCheckRequest):
    return {"message": "Geo check is a stub. Implement LLM-based citation parsing.", "received": payload.dict()}
    # Stub: estimate AI visibility by querying an LLM and parsing cited domains. Implement when ready.
    return {"message": "Geo check is a stub. Implement LLM-based citation parsing.", "received": payload.dict()}
