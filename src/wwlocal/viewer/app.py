"""`wwlocal view`: a local web page over the two databases.

The page itself is static/ (index.html, style.css, ES modules under js/, vendored Preact).
/jobs.json is rebuilt from waterlooworks_jobs.db (read-only) on every request, so a sync in the
background shows up on the next refresh. /api/state reads and writes viewer_state.db.
/apply/<id> turns the saved session into a fresh `displayPosting` token and redirects to the
posting on WaterlooWorks.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
import threading
import time
import webbrowser
from html import escape
from pathlib import Path
from typing import Any

import httpx2
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from wwlocal import jobs_db
from wwlocal import waterlooworks as ww
from wwlocal.config import JOBS_DB, JOBS_URL
from wwlocal.viewer import state

STATIC = Path(__file__).with_name("static")
INDEX = STATIC / "index.html"
TOKEN_TTL = 10 * 60  # seconds to reuse a scraped displayPosting token
NO_STORE = {"Cache-Control": "no-store"}


def create_app(include_closed: bool) -> FastAPI:
    app = FastAPI(title="wwlocal", docs_url=None, redoc_url=None, openapi_url=None)
    display_token = _DisplayToken()

    @app.middleware("http")
    async def no_store(request: Request, call_next: Any) -> Response:
        resp: Response = await call_next(request)
        resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    @app.get("/")
    @app.get("/index.html")
    def index() -> FileResponse:
        return FileResponse(INDEX, media_type="text/html; charset=utf-8")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/jobs.json")
    def jobs(closed: bool = Query(False)) -> Response:
        try:
            with jobs_db.open_ro() as con:
                payload = jobs_db.build_jobs(con, include_closed or closed)
        except sqlite3.Error as e:
            raise HTTPException(500, f"database error: {e}\n{JOBS_DB}") from e
        return JSONResponse(payload)

    @app.get("/api/state")
    def get_state() -> dict[str, dict[str, Any]]:
        return state.get_all()

    @app.patch("/api/state/{posting_id}")
    def patch_state(posting_id: int, changes: dict[str, Any]) -> dict[str, Any]:
        try:
            return state.patch(posting_id, changes)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    @app.get("/apply/{posting_id}")
    def apply(posting_id: int) -> Response:
        try:
            url = ww.posting_url(posting_id, display_token.get())
        except ww.NotLoggedIn as e:
            return _apply_error(
                posting_id, f"{escape(str(e))}. Run <code>uv run wwlocal login</code>."
            )
        except (httpx2.HTTPError, OSError, RuntimeError) as e:
            return _apply_error(posting_id, f"couldn't fetch an action token: {escape(str(e))}")
        return RedirectResponse(url, status_code=302, headers=NO_STORE)

    return app


class _DisplayToken:
    """The displayPosting token, scraped from the jobs page and reused for TOKEN_TTL seconds."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token: str | None = None
        self._fetched_at = 0.0

    def get(self) -> str:
        with self._lock:
            if self._token is None or time.time() - self._fetched_at > TOKEN_TTL:
                with ww.client() as c:
                    self._token = ww.fetch_tokens(c).display
                self._fetched_at = time.time()
            return self._token


def _apply_error(posting_id: int, msg: str) -> HTMLResponse:
    body = (
        "<!doctype html><meta charset=utf-8><title>Apply on WW</title>"
        "<body style='font:15px/1.5 system-ui;max-width:40em;margin:3em auto;padding:0 1em'>"
        f"<h2>Couldn't open posting {posting_id}</h2><p>{msg}</p>"
        f"<p>Meanwhile: <a href='{JOBS_URL}'>open the board</a> and search for "
        f"<code>{posting_id}</code>.</p>"
    )
    return HTMLResponse(body, status_code=502, headers=NO_STORE)


class _AccessFilter(logging.Filter):
    """Only log the requests worth seeing: data fetches, state edits and apply redirects."""

    def filter(self, record: logging.LogRecord) -> bool:
        return any(p in record.getMessage() for p in ("/jobs.json", "/api/", "/apply/"))


def serve(host: str, port: int, include_closed: bool, open_browser: bool) -> None:
    if not JOBS_DB.exists():
        sys.exit(f"no database at {JOBS_DB}: run `wwlocal sync` first")
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="%(message)s")
    access = logging.getLogger("uvicorn.access")
    access.setLevel(logging.INFO)
    access.addFilter(_AccessFilter())
    url = f"http://{host}:{port}/"
    print(f"viewer on {url}  (db: {JOBS_DB})  Ctrl-C to stop")
    if open_browser:
        threading.Timer(0.4, webbrowser.open, [url]).start()
    uvicorn.run(create_app(include_closed), host=host, port=port, log_config=None)
