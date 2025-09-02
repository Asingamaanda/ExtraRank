from fastapi import FastAPI, HTTPException
from .routers import router
from .config import settings
import pathlib
import yaml
import re
import unicodedata
from typing import Dict
from pydantic import BaseModel
from string import Template

app = FastAPI(title="Extraordinary Media — SEO + GEO Automation")
app.include_router(router)

PACKS_DIR = pathlib.Path("packs")

# Add JSON Schema for pack validation
PACK_SCHEMA = {
  "$schema":"https://json-schema.org/draft/2020-12/schema",
  "type":"object",
  "required":["vertical","aliases","geo_mode","entities","locations_tokens","keyword_clusters","templates","content_brief","schema","internal_linking","local_seo","kpis"],
  "properties":
    {
      "vertical":{"type":"string"},
      "aliases":{"type":"array","items":{"type":"string"}},
      "geo_mode":{"enum":["local","regional","national","intl"]},
      "entities":
        {
          "type":"object",
          "required":["business_types","services"],
          "properties":
            {
              "business_types":{"type":"array","items":{"type":"string"}},
              "services":{"type":"array","items":{"type":"string","minLength":2}}
            }
        },
      "locations_tokens":{"type":"array","items":{"type":"string"}},
      "keyword_clusters":
        {
          "type":"object",
          "properties":
            {
              "core":{"type":"array","items":{"type":"string"}},
              "long_tail":{"type":"array","items":{"type":"string"}},
              "questions":{"type":"array","items":{"type":"string"}}
            }
        },
      "templates":
        {
          "type":"object",
          "required":["title","meta","h1","slug"],
          "properties":
            {
              "title":{"type":"string"},
              "meta":{"type":"string"},
              "h1":{"type":"string"},
              "slug":{"type":"string"}
            }
        },
      "content_brief":{"type":"object"},
      "schema":{"type":"object"},
      "internal_linking":{"type":"object"},
      "local_seo":{"type":"object"},
      "kpis":{"type":"array","items":{"type":"string"}}
    }
}


def _slugify(s: str) -> str:
    if not s:
        return ""
    # normalize unicode (remove accents), keep ascii only
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    # remove any character that's not alphanumeric, hyphen or space
    s = re.sub(r"[^a-zA-Z0-9\- ]+", "", s).strip().lower()
    # collapse spaces to hyphens and collapse repeated hyphens
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s


def load_pack(name: str) -> dict:
    p = PACKS_DIR / f"{name}.yaml"
    if not p.exists():
        raise HTTPException(status_code=404, detail=f
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse YAML for pack '{name}': {e}")

    # Validate with jsonschema
    try:
        import jsonschema
    except
        # return concise validation message
        raise HTTPException(status_code=400, detail=f"Pack '{name}' failed schema validation: {ve.message}")
    except jsonschema.SchemaError as se:
        raise HTTPException(status_code=500, detail=f"Pack schema error: {se}")

    return data


def fill(text: str, tokens: Dict[str, str]) -> str:
    # lightweight token replacer that supports keys with hyphens (e.g., {service-slug})
    out = text or ""
    for k, v in tokens.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def generate_page_specs(pack: dict, client: dict):
    outputs = []
    services = pack.get("entities", {}).get("services", []) or []
    for svc in services:
        tokens = {**client}
        tokens["Service"] = svc
        tokens["service-slug"] = _slugify(svc)
        tokens["city-slug"] = _slugify(client.get("City", ""))
        title = fill(pack.get("templates", {}).get("title", ""), tokens)
        meta = fill(pack.get("templates", {}).get("meta", ""), tokens)
        h1 = fill(pack.get("templates", {}).get("h1", ""), tokens)
        slug = fill(pack.get("templates", {}).get("slug", ""), tokens)
        # include content brief and schema snippets (tokens applied shallowly)
        content_brief = pack.get("content_brief", {})
        schema = pack.get("schema", {})
        outputs.append({
            "service": svc,
            "title": title,
            "meta": meta,
            "h1": h1,
            "slug": slug,
            "content_brief": content_brief,
            "schema": schema,
        })
    return outputs


class ApplyVerticalIn(BaseModel):
    vertical: str
    client: Dict[str, str]  # {Brand, SiteURL, City, Province, Phone, LogoURL, ...}


@app.post("/vertical/apply")
def vertical_apply(inp: ApplyVerticalIn):
    pack = load_pack(inp.vertical)
    pages = generate_page_specs(pack, inp.client)
    return {"pages": pages, "kpis": pack.get("kpis", []), "local_seo": pack.get("local_seo", {})}


@app.get("/")
def root():
    return {"service": "Extraordinary Media", "env": settings.ENV}
