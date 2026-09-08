"""`wwlocal sync`: pull the board into waterlooworks_jobs.db.

Incremental: only new or changed postings get their details re-fetched; postings that drop off
the (filtered) board are marked closed; employer ratings are refreshed every RATINGS_TTL_DAYS.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from wwlocal import jobs_db
from wwlocal import waterlooworks as ww
from wwlocal.config import RATINGS_TTL_DAYS, now_iso
from wwlocal.parse import parse_overview, unescape

WORKERS = 4


def run(clusters: list[str], keyword: str, refresh_details: bool) -> None:
    c = ww.client()
    tok = ww.fetch_tokens(c)
    con = jobs_db.open_rw()
    started = now_iso()
    con.executemany("INSERT OR REPLACE INTO clusters VALUES (?,?)", tok.clusters.items())

    rows = ww.fetch_list(c, tok, clusters, keyword)
    print(f"listed {len(rows)} postings (clusters={','.join(clusters) or 'ALL'})")

    added = updated = 0
    need_detail: list[int] = []
    for r in rows:
        h = jobs_db.summary_hash(r)
        r = unescape(r)  # the board's JSON is HTML-escaped ("R&amp;D"); store it decoded
        ex = con.execute(
            "SELECT summary_hash, detail_fetched_at, closed_at FROM postings WHERE id=?", (r["id"],)
        ).fetchone()
        if ex is None:
            con.execute(
                "INSERT INTO postings (id, first_seen, last_seen, summary_json, summary_hash)"
                " VALUES (?,?,?,?,?)",
                (r["id"], started, started, json.dumps(r), h),
            )
            added += 1
            need_detail.append(r["id"])
            continue
        changed = ex["summary_hash"] != h
        updated += changed
        con.execute(
            "UPDATE postings SET last_seen=?, closed_at=NULL, summary_json=?, summary_hash=?"
            " WHERE id=?",
            (started, json.dumps(r), h, r["id"]),
        )
        if changed or refresh_details or ex["detail_fetched_at"] is None or ex["closed_at"]:
            need_detail.append(r["id"])

    closed = con.execute(
        "UPDATE postings SET closed_at=? WHERE closed_at IS NULL AND last_seen<>?",
        (started, started),
    ).rowcount
    con.commit()
    print(f"added {added}, changed {updated}, closed {closed}, details to fetch {len(need_detail)}")

    def get_detail(pid: int) -> tuple[int, dict, str]:
        data = unescape(ww.fetch_posting_data(c, tok, pid))
        return pid, data, ww.fetch_overview_html(c, tok, pid)

    with ThreadPoolExecutor(WORKERS) as pool:
        for n, (pid, data, html) in enumerate(pool.map(get_detail, need_detail), 1):
            try:
                overview = parse_overview(html)
            except Exception as e:
                print(f"  parse failed for {pid}: {e}", file=sys.stderr)
                overview = {"error": str(e)}
            con.execute(
                "UPDATE postings SET detail_fetched_at=?, data_json=?, overview_json=?,"
                " overview_html=?, div_id=? WHERE id=?",
                (now_iso(), json.dumps(data), json.dumps(overview), html, data.get("divId"), pid),
            )
            if n % 25 == 0:
                con.commit()
                print(f"  details {n}/{len(need_detail)}")
    con.commit()

    cutoff = (datetime.now(UTC) - timedelta(days=RATINGS_TTL_DAYS)).isoformat()
    stale = [
        r["div_id"]
        for r in con.execute(
            "SELECT DISTINCT p.div_id FROM postings p LEFT JOIN ratings r ON r.div_id=p.div_id"
            " WHERE p.div_id IS NOT NULL AND p.closed_at IS NULL"
            " AND (r.div_id IS NULL OR r.fetched_at < ?)",
            (cutoff,),
        )
    ]
    if stale:
        print(f"fetching ratings for {len(stale)} employer divisions")
        with ThreadPoolExecutor(WORKERS) as pool:
            reports = pool.map(lambda d: ww.fetch_ratings(c, tok, d), stale)
            for div_id, report in zip(stale, reports, strict=True):
                con.execute(
                    "INSERT OR REPLACE INTO ratings VALUES (?,?,?)",
                    (div_id, now_iso(), json.dumps(unescape(report))),
                )

    con.execute(
        "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?)",
        (
            started,
            now_iso(),
            len(rows),
            added,
            updated,
            closed,
            len(need_detail),
            len(stale),
            ",".join(clusters),
        ),
    )
    con.commit()
