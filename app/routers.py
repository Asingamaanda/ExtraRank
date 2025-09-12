from fastapi import APIRouter, Query, Depends
from .services import psi as psi_svc
from .services import seo as seo_svc
from .services import indexnow as idx_svc
from app.auth import require_api_key
from .schemas import (
    PsiResponse,
    SeoGenerateRequest,
    SeoGenerateResponse,
    IndexNowRequest,
    GscRequest,
    GeoCheckRequest,
)
try:
    import openai
except Exception:
    openai = None

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
async def indexnow_submit(payload: IndexNowRequest, _key: str | None = Depends(require_api_key)):
    """
    Protected IndexNow submission endpoint.
    """
    result = await idx_svc.submit_indexnow(payload.host, payload.key, payload.urls)
    return result


@router.post("/gsc/performance")
def gsc_performance(payload: GscRequest):
    return {"message": "GSC performance is a stub. Implement OAuth and call Search Console API.", "received": payload.dict()}


@router.post("/geo/check")
def geo_check(payload: GeoCheckRequest, _key: str | None = Depends(require_api_key)):
    """
    If OPENAI_API_KEY configured, ask the model to return structured JSON with cited domains for each query.
    Fallback: return a helpful stub.
    """
    if settings.OPENAI_API_KEY and openai:
        try:
            openai.api_key = settings.OPENAI_API_KEY
            prompt = (
                "For each query in the input list, return a JSON array of objects with:\n"
                "  query: original query\n"
                "  ai_answer: a short (1-2 sentence) AI-style answer\n"
                "  cited_domains: array of domain strings that would be cited for this answer\n\n"
                f"Input queries:\n{payload.queries}\n\n"
                "Return valid JSON only."
            )
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=800,
            )
            text = resp.choices[0].message.content.strip()
            import json as _json
            parsed = _json.loads(text)
            results = []
            for item in parsed:
                q = item.get("query")
                ai_answer = item.get("ai_answer") or item.get("answer")
                cited = item.get("cited_domains") or item.get("cited") or []
                # normalize to list of domains (strings)
                if isinstance(cited, str):
                    cited = [cited]
                results.append({"query": q, "ai_answer": ai_answer, "cited_domains": cited})
            return {"site_hostname": payload.site_hostname, "results": results}
        except Exception as e:
            return {"message": "OpenAI request failed", "error": str(e), "received": payload.dict()}
    # fallback stub
    return {"message": "Geo check is a stub. Set OPENAI_API_KEY to enable LLM-based citation parsing.", "received": payload.dict()}
    # fallback stub
    return {"message": "Geo check is a stub. Set OPENAI_API_KEY to enable LLM-based citation parsing.", "received": payload.dict()}
