import sqlite3
from pathlib import Path
from typing import List, Dict, Any
import json
import datetime

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    server TEXT,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS psi_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    url TEXT,
    status TEXT,
    score REAL,
    lcp TEXT,
    cls TEXT,
    raw_json TEXT
);
CREATE TABLE IF NOT EXISTS geo_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    query TEXT,
    status TEXT,
    result_json TEXT
);
"""

def get_conn(db_path: str):
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str):
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.executescript(SCHEMA)
    conn.commit()
    conn.close()

def save_snapshot(db_path: str, server: str, notes: str, psi_rows: List[Dict[str, Any]], geo_rows: List[Dict[str, Any]]):
    """
    psi_rows: list of {url,status,score,lcp,cls,raw}
    geo_rows: list of {query,status,result}
    """
    now = datetime.datetime.utcnow().isoformat() + "Z"
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO snapshots(created_at, server, notes) VALUES (?, ?, ?)", (now, server, notes))
    snapshot_id = cur.lastrowid

    for r in psi_rows:
        cur.execute(
            "INSERT INTO psi_results(snapshot_id, url, status, score, lcp, cls, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (snapshot_id, r.get("url"), r.get("status"), _safe_float(r.get("score")), r.get("lcp"), r.get("cls"), json.dumps(r.get("raw", {}), ensure_ascii=False))
        )

    for r in geo_rows:
        cur.execute(
            "INSERT INTO geo_results(snapshot_id, query, status, result_json) VALUES (?, ?, ?, ?)",
            (snapshot_id, r.get("query"), r.get("status"), json.dumps(r.get("result") if isinstance(r.get("result"), (dict, list)) else r.get("result"), ensure_ascii=False))
        )

    conn.commit()
    conn.close()
    return snapshot_id

def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return None

def rotate_old_snapshots(db_path: str, keep_days: int) -> int:
    """
    Delete snapshots older than keep_days (UTC). Returns number of snapshot rows deleted.
    """
    import datetime
    conn = get_conn(db_path)
    cur = conn.cursor()
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=keep_days)).isoformat() + "Z"
    cur.execute("SELECT id FROM snapshots WHERE created_at < ?", (cutoff,))
    rows = cur.fetchall()
    ids = [r["id"] for r in rows]
    if not ids:
        conn.close()
        return 0
    try:
        cur.execute("DELETE FROM snapshots WHERE created_at < ?", (cutoff,))
        conn.commit()
        deleted_snapshots = len(ids)
    finally:
        conn.close()
    return deleted_snapshots
    return len(ids)
