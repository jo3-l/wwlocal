"""waterlooworks_jobs.db: the local mirror of the board. Written by sync, read by the viewer."""

from __future__ import annotations

import hashlib
import json
import sqlite3

from wwlocal import parse
from wwlocal.config import JOBS_DB, JOBS_URL, now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS postings (
  id INTEGER PRIMARY KEY,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  closed_at TEXT,
  summary_json TEXT NOT NULL,
  summary_hash TEXT NOT NULL,
  detail_fetched_at TEXT,
  data_json TEXT,
  overview_json TEXT,
  overview_html TEXT,
  div_id INTEGER
);
CREATE TABLE IF NOT EXISTS ratings (
  div_id INTEGER PRIMARY KEY,
  fetched_at TEXT NOT NULL,
  report_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  started_at TEXT PRIMARY KEY,
  finished_at TEXT,
  listed INTEGER, added INTEGER, updated INTEGER, closed INTEGER, details INTEGER, ratings INTEGER,
  clusters TEXT
);
CREATE TABLE IF NOT EXISTS clusters (id TEXT PRIMARY KEY, label TEXT NOT NULL);
"""


def open_rw() -> sqlite3.Connection:
    JOBS_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(JOBS_DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def open_ro() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{JOBS_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def summary_hash(row: dict) -> str:
    """Hash of the list row minus the fields that churn without the posting changing."""
    keep = {
        k: v for k, v in row.items() if k not in ("flags", "application_count", "has_application")
    }
    return hashlib.sha1(json.dumps(keep, sort_keys=True).encode()).hexdigest()


def build_jobs(con: sqlite3.Connection, include_closed: bool) -> dict:
    """The payload the viewer page loads: every posting joined with its detail and ratings."""
    ratings = {
        r["div_id"]: parse.parse_ratings(json.loads(r["report_json"]))
        for r in con.execute("SELECT div_id, report_json FROM ratings")
    }
    where = "" if include_closed else " WHERE closed_at IS NULL"
    jobs = []
    for r in con.execute(f"SELECT * FROM postings{where} ORDER BY id DESC"):
        data = json.loads(r["data_json"] or "{}")
        overview = json.loads(r["overview_json"] or "{}")
        summary = json.loads(r["summary_json"])
        detail = overview.get("normalized")
        fields = overview.get("fields") or {}
        comp_text = parse.field_text(fields.get("compensation_and_benefits"))
        external = parse.external_application(fields, detail)
        jobs.append(
            {
                **summary,
                "first_seen": r["first_seen"],
                "last_seen": r["last_seen"],
                "closed_at": r["closed_at"],
                "status": data.get("internalStatus"),
                "tags": data.get("tags"),
                "div_id": r["div_id"],
                "locations": data.get("defaultLocations"),
                "detail": detail,
                "fields": fields or None,
                "ratings": ratings.get(r["div_id"]),
                "url": f"{JOBS_URL}#posting-{r['id']}",
                # derived for the viewer; see parse.py
                "facets": parse.facets(summary, detail, external),
                "external_apply": external,
                "comp_text": comp_text,
                "comp": parse.compensation(comp_text),
                "rating_summary": parse.rating_summary(ratings.get(r["div_id"])),
            }
        )
    last_run = con.execute(
        "SELECT started_at, finished_at FROM runs ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    generated = (last_run["finished_at"] or last_run["started_at"]) if last_run else now_iso()
    return {"generated_at": generated, "count": len(jobs), "jobs": jobs, "db": str(JOBS_DB)}
