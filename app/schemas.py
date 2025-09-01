from pydantic import BaseModel
from typing import List, Optional


class PsiResponse(BaseModel):
    url: str
    lighthouse_summary: dict
    loading_experience: Optional[dict]
    origin_loading_experience: Optional[dict]


class SeoGenerateRequest(BaseModel):
    url: str
    content_excerpt: str
    brand: Optional[str] = None


class SeoGenerateResponse(BaseModel):
    title: str
    meta_description: str
    og: dict


class IndexNowRequest(BaseModel):
    host: str
    key: str
    urls: List[str]


class GscRequest(BaseModel):
    site_url: str
    start_date: str
    end_date: str


class GeoCheckRequest(BaseModel):
    queries: List[str]
    site_hostname: str
