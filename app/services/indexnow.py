import httpx


INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"


async def submit_indexnow(host: str, key: str, urls: list) -> dict:
    payload = {
        "host": host,
        "key": key,
        "urlList": urls,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(INDEXNOW_ENDPOINT, json=payload)
        return {"status_code": r.status_code, "text": r.text}
        return {"status_code": r.status_code, "text": r.text}
