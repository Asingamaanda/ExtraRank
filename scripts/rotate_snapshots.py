#!/usr/bin/env python3
"""
Rotate (delete) old snapshots.

Usage examples:
  # dry-run, check what would be deleted
  python scripts/rotate_snapshots.py --db data/snapshots.db --keep-days 90 --dry-run

  # actually delete
  python scripts/rotate_snapshots.py --db data/snapshots.db --keep-days 90

This script returns exit code 0 on success, 2 on DB errors.
"""
import argparse
import sys
import datetime
from app.db import get_conn

def parse_args():
    p = argparse.ArgumentParser(description="Rotate old snapshot records from SQLite")
    p.add_argument("--db", default=None, help="SQLite DB path (env SNAPSHOT_DB or default data/snapshots.db)")
    p.add_argument("--keep-days", type=int, default=90, help="Keep snapshots newer than this many days (default 90)")
    p.add_argument("--dry-run", action="store_true", help="Do not delete, just report")
    return p.parse_args()

def main():
    args = parse_args()
    db_path = args.db or __import__("os").environ.get("SNAPSHOT_DB", "data/snapshots.db")
    try:
        conn = get_conn(db_path)
    except Exception as e:
        print(f"FATAL: cannot open DB '{db_path}': {e}", file=sys.stderr)
        sys.exit(2)

    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=args.keep_days)).isoformat() + "Z"

    cur = conn.cursor()
    cur.execute("SELECT id, created_at FROM snapshots WHERE created_at < ? ORDER BY created_at ASC", (cutoff,))
    rows = cur.fetchall()
    ids = [r["id"] for r in rows]

    if not ids:
        print(f"No snapshots older than {args.keep_days} days (cutoff {cutoff}).")
        conn.close()
        return

    print(f"Found {len(ids)} snapshot(s) older than {args.keep_days} days (cutoff {cutoff}):")
    for r in rows:
        print(f"  id={r['id']} created_at={r['created_at']}")

    if args.dry_run:
        print("Dry-run enabled; no deletions performed.")
        conn.close()
        return

    # perform deletion; ON DELETE CASCADE will remove related rows
    try:
        cur.execute("DELETE FROM snapshots WHERE created_at < ?", (cutoff,))
        deleted = conn.total_changes
        conn.commit()
        print(f"Deleted snapshots older than cutoff; total rows changed: {deleted}")
    except Exception as e:
        print(f"FATAL: deletion failed: {e}", file=sys.stderr)
        conn.rollback()
        conn.close()
        sys.exit(2)

    conn.close()

if __name__ == "__main__":
    main()
