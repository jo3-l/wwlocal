"""HTTP client for the WaterlooWorks job board.

Every call is a POST to jobs.htm carrying an `action` token. Tokens are embedded in the jobs page
and rotate on each page load (but stay valid for the session), so one GET yields a fresh set.
"""

import codecs
import json
import re
import sys
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode

import httpx2

from wwlocal.config import COOKIES_FILE, JOBS_URL, USER_AGENT

_TOKEN = r"_-_-[A-Za-z0-9_\-]+"
_DISPLAY_TOKEN = re.compile(rf"displayPosting\s*:\s*['\"]({_TOKEN})['\"]")
_CLUSTER_OPTIONS = re.compile(r'filter-key="clusterId".{0,20000}?:options="(\[.*?\])"', re.DOTALL)


class NotLoggedIn(Exception):  # noqa: N818 - reads better as a state than an error
    pass


def client() -> httpx2.Client:
    """A session carrying the cookies saved by `wwlocal login`."""
    if not COOKIES_FILE.exists():
        raise NotLoggedIn(f"no saved session at {COOKIES_FILE}")
    c = httpx2.Client(
        headers={"User-Agent": USER_AGENT, "Referer": JOBS_URL},
        follow_redirects=True,
        timeout=60,
    )
    for ck in json.loads(COOKIES_FILE.read_text() or "[]"):
        c.cookies.set(
            ck["name"], ck["value"], domain=ck.get("domain", ""), path=ck.get("path", "/")
        )
    return c


@dataclass
class Tokens:
    list: str
    data: str
    overview: str
    ratings: str
    display: str
    clusters: dict[str, str] = field(default_factory=dict)  # cluster id -> label


def fetch_tokens(c: httpx2.Client) -> Tokens:
    html = c.get(JOBS_URL).text
    if "isDataViewer" not in html:
        raise NotLoggedIn("WaterlooWorks session expired")
    m = _DISPLAY_TOKEN.search(html)
    if not m:
        raise RuntimeError("displayPosting token not found on jobs page (page changed?)")
    return Tokens(
        list=_token_near(html, "isDataViewer", before=True),
        data=_token_near(html, "function getPostingData"),
        overview=_token_near(html, "function getPostingOverview"),
        ratings=_token_near(html, "function getWorkTermRatingReportJson"),
        display=m.group(1),
        clusters=_clusters(html),
    )


def _token_near(html: str, marker: str, before: bool = False) -> str:
    i = html.find(marker)
    if i < 0:
        raise RuntimeError(f"marker {marker!r} not found in page (page changed?)")
    seg = html[max(0, i - 600) : i] if before else html[i : i + 2000]
    toks = re.findall(_TOKEN, seg)
    if not toks:
        raise RuntimeError(f"no token near {marker!r}")
    return toks[-1] if before else toks[0]


def _clusters(html: str) -> dict[str, str]:
    m = _CLUSTER_OPTIONS.search(html)
    if not m:
        return {}
    raw = m.group(1).replace("&quot;", '"').replace("&#39;", "'").replace("&amp;", "&")
    return {v: lbl.strip() for v, lbl in re.findall(r"'value':'(\d+)','label':'([^']*)'", raw)}


def _cp1252_fallback(e: UnicodeError) -> tuple[str, int]:
    """Decode an undecodable run as cp1252, leaving the rest of the body alone."""
    if not isinstance(e, UnicodeDecodeError):
        raise e
    return e.object[e.start : e.end].decode("cp1252", errors="replace"), e.end


codecs.register_error("wwlocal_cp1252", _cp1252_fallback)


def _text(r: httpx2.Response) -> str:
    """Postings occasionally carry stray cp1252 bytes in an otherwise UTF-8 body."""
    enc = r.encoding or "utf-8"
    try:
        return r.content.decode(enc)
    except UnicodeDecodeError:
        return r.content.decode(enc, errors="wwlocal_cp1252")


def _json(r: httpx2.Response) -> dict:
    """`Response.json` decodes the raw bytes as strict UTF-8; go through `_text` instead."""
    return json.loads(_text(r))


def _post(c: httpx2.Client, **form: str) -> httpx2.Response:
    for attempt in range(3):
        try:
            r = c.post(JOBS_URL, data=form, headers={"X-Requested-With": "XMLHttpRequest"})
            if r.status_code == 200:
                return r
        except httpx2.HTTPError:
            pass
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"request failed: {sorted(form)}")


def fetch_list(c: httpx2.Client, tok: Tokens, clusters: list[str], keyword: str) -> list[dict]:
    """One row per posting on the (filtered) board. The whole board fits in a single page."""
    filters = (
        json.dumps({"clusterId": {"type": "options", "value": clusters}}) if clusters else "null"
    )
    r = _post(
        c,
        page="1",
        sort='[{"key":"Id","direction":"desc"}]',
        itemsPerPage="5000",
        filters=filters,
        columns='[{"key":"Id","isId":true}]',
        keyword=keyword,
        action=tok.list,
        isDataViewer="true",
    )
    j = _json(r)
    rows = []
    for item in j["data"]:
        d = {kv["key"]: kv["value"] for kv in item["data"]}
        jt = d.get("JobTitle") or {}
        rows.append(
            {
                "id": int(d["Id"]),
                "title": jt.get("postingTitle"),
                "organization": d.get("Organization"),
                "division": d.get("Division"),
                "openings": d.get("Openings"),
                "city": d.get("City"),
                "level": d.get("Level"),
                "application_count": d.get("ApplicationCount"),
                "deadline": d.get("deadline"),
                "deadline_display": d.get("Deadline"),
                "can_apply": d.get("canApply"),
                "has_application": d.get("hasApplication"),
                "flags": {k: jt.get(k) for k in ("new", "featured", "applied", "viewed")},
            }
        )
    if len(rows) != j.get("totalResults"):
        print(f"warning: list returned {len(rows)} of {j.get('totalResults')}", file=sys.stderr)
    return rows


def fetch_posting_data(c: httpx2.Client, tok: Tokens, pid: int) -> dict:
    """Status, tags, default locations, divId. The application form is dropped."""
    j = _json(_post(c, action=tok.data, postingId=str(pid)))
    j.get("applicationData", {}).pop("form", None)
    return j


def fetch_overview_html(c: httpx2.Client, tok: Tokens, pid: int) -> str:
    return _text(_post(c, action=tok.overview, postingId=str(pid)))


def fetch_ratings(c: httpx2.Client, tok: Tokens, div_id: int) -> dict:
    """Hiring-history / work-term-rating report for an employer division."""
    return _json(
        _post(
            c,
            action=tok.ratings,
            reportHolder="com.orbis.web.content.crm.Company",
            reportHolderId=str(div_id),
            reportHolderField="t100",
        )
    )


def posting_url(pid: int | str, display_token: str) -> str:
    return f"{JOBS_URL}?{urlencode({'postingId': pid, 'action': display_token})}"
