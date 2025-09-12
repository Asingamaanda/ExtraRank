from fastapi import FastAPI, HTTPException, Depends
from .routers import router
from .config import settings
import pathlib
import yaml
import re
import unicodedata
from typing import Dict
from pydantic import BaseModel
from string import Template
import string
import os
import json
from app.db import init_db, get_conn, rotate_old_snapshots, save_snapshot
from app.auth import require_api_key
from app.services import psi as psi_svc
import asyncio
try:
    import openai
except Exception:
    openai = None

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
        raise HTTPException(status_code=404, detail=f"Pack '{name}' not found in {PACKS_DIR}")
    # parse YAML
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse YAML for pack '{name}': {e}")

    # Validate with jsonschema
    try:
        import jsonschema
    except Exception:
        hint = (
            "Missing required dependency 'jsonschema'.\n\n"
            "Install it in your environment, for example:\n"
            "  # Create & activate a virtualenv (recommended)\n"
            "  python -m venv .venv\n"
            "  # Windows:\n"
            "  .venv\\Scripts\\activate\n"
            "  # macOS / Linux:\n"
            "  source .venv/bin/activate\n\n"
            "  python -m pip install jsonschema\n\n"
            "Or add 'jsonschema' to requirements.txt and run:\n"
            "  python -m pip install -r requirements.txt\n\n"
            "If you use Docker, add jsonschema to your image. After installing, restart the server."
        )
        raise HTTPException(status_code=500, detail=hint)

    try:
        jsonschema.validate(instance=data, schema=PACK_SCHEMA)
    except jsonschema.ValidationError as ve:
        # return concise validation message
        raise HTTPException(status_code=400, detail=f"Pack '{name}' failed schema validation: {ve.message}")
    except jsonschema.SchemaError as se:
        raise HTTPException(status_code=500, detail=f"Pack schema error: {se}")

    return data


def fill(text: str, tokens: Dict[str, str]) -> str:
    """
    Safe template substitution:
    - Translates {Var} placeholders into ${safe_var} for string.Template.
    - safe_var: non-alphanum chars -> underscore; if starts with digit, prefix with underscore.
    - Uses Template.safe_substitute and falls back to legacy replace on error.
    """
    if not text:
        return ""

    # Build mapping of safe variable names
    safe_map = {}
    for k, v in tokens.items():
        safe_key = re.sub(r'[^0-9a-zA-Z_]', '_', k)
        if re.match(r'^[0-9]', safe_key):
            safe_key = '_' + safe_key
        safe_map[safe_key] = v

    # Replace {Key} occurrences with ${safe_key}
    def _repl(m):
        key = m.group(1)
        safe_key = re.sub(r'[^0-9a-zA-Z_]', '_', key)
        if re.match(r'^[0-9]', safe_key):
            safe_key = '_' + safe_key
        return '${' + safe_key + '}'

    try:
        pattern = re.compile(r'\{([^}]+)\}')
        templated = pattern.sub(_repl, text)
        tpl = Template(templated)
        return tpl.safe_substitute(safe_map)
    except Exception:
        # Fallback: simple replacement (legacy behaviour)
        out = text
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


# ensure DB exists on startup
@app.on_event("startup")
def _ensure_snapshot_db():
    db_path = os.getenv("SNAPSHOT_DB", "data/snapshots.db")
    try:
        init_db(db_path)
    except Exception as e:
        # startup should not crash; log a warning so cron/scripts still run
        print(f"Warning: failed to initialize snapshot DB '{db_path}': {e}")

    # Ensure runtime directories exist
    for d in ("data", os.path.join("data", "reports"), "logs"):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as ex:
            print(f"Warning: could not create directory '{d}': {ex}")

    # Attempt to set executable bit on common UNIX snapshot scripts (no-op on Windows)
    script_candidates = [
        pathlib.Path("run_daily.sh"),
        pathlib.Path("scripts/run_daily.sh"),
        pathlib.Path("scripts/daily_snapshot_unix.sh"),
        pathlib.Path("scripts/daily_snapshot.sh"),
        pathlib.Path("scripts/run_daily.sh")
    ]
    for sp in script_candidates:
        if sp.exists():
            try:
                current_mode = sp.stat().st_mode
                sp.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                print(f"Set executable bit on {sp}")
            except Exception as ex:
                print(f"Warning: could not set executable bit for {sp}: {ex}")


@app.get("/snapshots")
def list_snapshots(limit: int = 50, offset: int = 0, _key: str | None = Depends(require_api_key)):
    """
    Return snapshot metadata (id, created_at, server, notes).
    Protected by API key if SNAPSHOT_API_KEY is set.
    """
    db_path = os.getenv("SNAPSHOT_DB", "data/snapshots.db")
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, created_at, server, notes FROM snapshots ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"snapshots": rows, "limit": limit, "offset": offset}


@app.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: int, _key: str | None = Depends(require_api_key)):
    """
    Return a snapshot with its PSI and GEO rows. Protected by API key if configured.
    """
    db_path = os.getenv("SNAPSHOT_DB", "data/snapshots.db")
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, created_at, server, notes FROM snapshots WHERE id = ?", (snapshot_id,))
    snap = cur.fetchone()
    if not snap:
        conn.close()
        raise HTTPException(status_code=404, detail="Snapshot not found")
    snap = dict(snap)

    cur.execute("SELECT url, status, score, lcp, cls, raw_json FROM psi_results WHERE snapshot_id = ?", (snapshot_id,))
    psi_rows = []
    for r in cur.fetchall():
        row = dict(r)
        raw_json = row.pop("raw_json", None)
        try:
            row["raw"] = json.loads(raw_json) if raw_json else {}
        except Exception:
            row["raw"] = raw_json
        psi_rows.append(row)

    cur.execute("SELECT query, status, result_json FROM geo_results WHERE snapshot_id = ?", (snapshot_id,))
    geo_rows = []
    for r in cur.fetchall():
        row = dict(r)
        result_json = row.pop("result_json", None)
        try:
            row["result"] = json.loads(result_json) if result_json else None
        except Exception:
            row["result"] = result_json
        geo_rows.append(row)

    conn.close()
    return {"snapshot": snap, "psi_results": psi_rows, "geo_results": geo_rows}


@app.post("/snapshots/rotate")
def api_rotate_snapshots(keep_days: int = 90, dry_run: bool = True, _key: str | None = Depends(require_api_key)):
    """
    Rotate (delete) snapshots older than keep_days.
    By default dry_run=True (no deletion) — set dry_run=false to actually delete.
    """
    db_path = os.getenv("SNAPSHOT_DB", "data/snapshots.db")
    if dry_run:
        # report how many would be deleted
        # use rotate function on a copy? Instead compute count without deleting
        import datetime
        conn = get_conn(db_path)
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=keep_days)).isoformat() + "Z"
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM snapshots WHERE created_at < ?", (cutoff,))
        c = cur.fetchone()["c"]
        conn.close()
        return {"dry_run": True, "keep_days": keep_days, "would_delete_snapshots": c}
    else:
        deleted_snapshots = rotate_old_snapshots(db_path, keep_days)
        return {"dry_run": False, "keep_days": keep_days, "deleted_snapshots": deleted_snapshots}


class SnapshotTriggerRequest(BaseModel):
    urls: Optional[List[str]] = None
    queries: Optional[List[str]] = None
    site_hostname: Optional[str] = None
    strategy: str = "mobile"
    save: bool = True
    notes: Optional[str] = None


@app.post("/snapshots/trigger")
async def snapshots_trigger(payload: SnapshotTriggerRequest, _key: str | None = Depends(require_api_key)):
    """
    Trigger an immediate snapshot:
      - runs PageSpeed audits for payload.urls (concurrently)
      - runs Geo/AEO checks for payload.queries (OpenAI if configured)
      - saves results to SNAPSHOT_DB if payload.save is True
    Protected by API key if SNAPSHOT_API_KEY is set.
    """
    db_path = os.getenv("SNAPSHOT_DB", "data/snapshots.db")
    server = os.getenv("SNAPSHOT_SERVER", "local")
    psi_rows: List[Dict[str, Any]] = []
    geo_rows: List[Dict[str, Any]] = []

    # Run PSI audits concurrently
    urls = payload.urls or []
    if urls:
        tasks = [psi_svc.fetch_pagespeed(u, strategy=payload.strategy) for u in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for u, res in zip(urls, results):
            if isinstance(res, Exception):
                psi_rows.append({"url": u, "status": "error", "score": None, "lcp": None, "cls": None, "raw": str(res)})
            else:
                summary = res.get("lighthouse_summary", {}) or {}
                core = summary.get("core_web_vitals", {}) or {}
                psi_rows.append({
                    "url": u,
                    "status": "ok",
                    "score": summary.get("performance_score"),
                    "lcp": core.get("lcp"),
                    "cls": core.get("cls"),
                    "raw": res.get("raw", {})
                })

    # Run GEO checks (OpenAI-backed) or fallback
    queries = payload.queries or []
    if queries:
        if settings.OPENAI_API_KEY and openai:
            try:
                openai.api_key = settings.OPENAI_API_KEY
                prompt = (
                    "For each query in the input list, return a JSON array of objects with:\n"
                    "  query: original query\n"
                    "  ai_answer: a short (1-2 sentence) AI-style answer\n"
                    "  cited_domains: array of domain strings that would be cited for this answer\n\n"
                    f"Input queries:\n{queries}\n\n"
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
                for item in parsed:
                    q = item.get("query")
                    ai_answer = item.get("ai_answer") or item.get("answer")
                    cited = item.get("cited_domains") or item.get("cited") or []
                    if isinstance(cited, str):
                        cited = [cited]
                    geo_rows.append({"query": q, "status": "ok", "result": {"ai_answer": ai_answer, "cited_domains": cited}})
            except Exception as e:
                for q in queries:
                    geo_rows.append({"query": q, "status": "error", "result": str(e)})
        else:
            # fallback stub rows
            for q in queries:
                geo_rows.append({"query": q, "status": "stub", "result": {"note": "OpenAI not configured"}})

    # Save to DB if requested
    snapshot_id = None
    if payload.save:
        try:
            init_db(db_path)  # ensure schema
            snapshot_id = save_snapshot(db_path, server, payload.notes or "manual trigger", psi_rows, geo_rows)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save snapshot: {e}")

    return {
        "snapshot_id": snapshot_id,
        "psi_count": len(psi_rows),
        "geo_count": len(geo_rows),
        "saved": bool(snapshot_id),
        "psi_rows": psi_rows if len(psi_rows) <= 10 else psi_rows[:10],
        "geo_rows": geo_rows if len(geo_rows) <= 10 else geo_rows[:10],
    }
