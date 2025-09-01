import os
from typing import Dict
from ..config import settings

try:
    import openai
except Exception:
    openai = None


def _heuristic_title(url: str, excerpt: str, brand: str | None) -> str:
    base = excerpt.strip().split(".")[0][:60].strip()
    if brand:
        return f"{base} — {brand}"
    return base


def _heuristic_description(excerpt: str) -> str:
    desc = excerpt.strip().replace("\n", " ")
    return (desc[:155]).strip()


def generate_meta(payload: Dict) -> Dict:
    url = payload.get("url")
    excerpt = payload.get("content_excerpt", "")
    brand = payload.get("brand")

    if settings.OPENAI_API_KEY and openai:
        try:
            openai.api_key = settings.OPENAI_API_KEY
            prompt = (
                f"Create an SEO title (<=60 chars) and meta description (<=155 chars) for this page.\n\n"
                f"URL: {url}\n\nExcerpt:\n{excerpt}\n\nBrand: {brand or ''}\n\n"
                "Return JSON with keys: title, description, og_title, og_description"
            )
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=180,
            )
            text = resp.choices[0].message.content.strip()
            import json

            parsed = json.loads(text)
            title = parsed.get("title") or parsed.get("og_title")
            description = parsed.get("description") or parsed.get("og_description")
            return {
                "title": title,
                "meta_description": description,
                "og": {"og:title": parsed.get("og_title") or title, "og:description": parsed.get("og_description") or description},
            }
        except Exception:
            pass

    title = _heuristic_title(url, excerpt, brand)
    description = _heuristic_description(excerpt)
    return {
        "title": title,
        "meta_description": description,
        "og": {"og:title": title, "og:description": description},
    }
        "meta_description": description,
        "og": {"og:title": title, "og:description": description},
    }
