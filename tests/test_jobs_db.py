"""`build_jobs` on a one-posting database: the payload carries the derived fields."""

import json
import sqlite3

from wwlocal import jobs_db


def test_build_jobs_derives_fields():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(jobs_db.SCHEMA)
    summary = {"id": 1, "title": "Dev", "organization": "Acme", "level": "Junior, Intermediate"}
    overview = {
        "fields": {"compensation_and_benefits": {"text": "$30 per hour", "html": "<p>$30</p>"}},
        "normalized": {"location_arrangement": "Hybrid", "work_term_duration": "4 month work term"},
    }
    con.execute(
        "INSERT INTO postings"
        " (id, first_seen, last_seen, summary_json, summary_hash, overview_json, div_id)"
        " VALUES (1, 't', 't', ?, 'h', ?, 7)",
        (json.dumps(summary), json.dumps(overview)),
    )
    con.execute(
        "INSERT INTO ratings (div_id, fetched_at, report_json) VALUES (7, 't', ?)",
        (json.dumps({"sections": []}),),
    )
    payload = jobs_db.build_jobs(con, include_closed=False)
    assert payload["count"] == 1
    j = payload["jobs"][0]
    assert j["comp_text"] == "$30 per hour"
    assert j["comp"] == {"lo": 30, "hi": None, "unit": "hr", "currency": None}
    assert j["facets"]["arrangement"] == "Hybrid"
    assert j["facets"]["duration"] == "4 months"
    assert j["facets"]["levels"] == ["Junior", "Intermediate"]
    assert j["ratings"] == {"tables": [], "charts": []}
    assert j["rating_summary"]["rating"] is None


def test_build_jobs_without_detail_or_ratings():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(jobs_db.SCHEMA)
    con.execute(
        "INSERT INTO postings (id, first_seen, last_seen, summary_json, summary_hash)"
        " VALUES (2, 't', 't', ?, 'h')",
        (json.dumps({"id": 2, "title": "x", "organization": "y"}),),
    )
    j = jobs_db.build_jobs(con, include_closed=True)["jobs"][0]
    assert j["detail"] is None and j["fields"] is None and j["ratings"] is None
    assert j["comp"] is None and j["comp_text"] == ""
    assert j["facets"]["levels"] == [] and j["rating_summary"]["hires_total"] == 0
