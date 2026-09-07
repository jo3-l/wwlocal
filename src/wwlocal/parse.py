"""Turn the board's HTML/JSON blobs into plain dicts."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def slug(label: str) -> str:
    label = label.strip().rstrip(":").strip()
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def parse_overview(html: str) -> dict:
    """Sections, every labelled field, and a normalized subset.

    Shape: {"sections": {panel: [keys]}, "fields": {key: {text?, html?, list?}},
            "normalized": {...}}

    `fields` keeps every label on the posting verbatim (slugified) so nothing is lost if the form
    changes; `normalized` is the subset the viewer relies on.
    """
    soup = BeautifulSoup(html, "html.parser")
    sections: dict[str, list[str]] = {}
    fields: dict[str, dict] = {}
    for panel in soup.select(".panel"):
        heading = panel.find(["h1", "h2", "h3", "h4", "div"])
        section = slug(heading.get_text(" ", strip=True)) if heading else "misc"
        keys = []
        for q in panel.select(".js--question--container"):
            lbl = q.select_one(".label")
            if not lbl:
                continue
            key = slug(lbl.get_text(" ", strip=True))
            lbl.extract()
            fields[key] = _field_value(q)
            keys.append(key)
        sections[section] = keys

    def text(k: str) -> str | None:
        return fields.get(k, {}).get("text")

    def lst(k: str) -> list[str]:
        return fields.get(k, {}).get("list") or []

    normalized = {
        "work_term": text("work_term"),
        "job_type": text("job_type"),
        "levels": lst("level"),
        "region": text("region"),
        "address": {
            "line1": text("job_address_line_one"),
            "line2": text("job_address_line_two"),
            "city": text("job_city"),
            "province": text("job_province_state"),
            "postal_code": text("job_postal_zip_code"),
            "country": text("job_country"),
        },
        "location_arrangement": text("employment_location_arrangement"),
        "work_term_duration": text("work_term_duration"),
        "special_dates": text("special_work_term_start_end_date_considerations"),
        "special_requirements": text("special_job_requirements"),
        "summary": text("job_summary"),
        "responsibilities": text("job_responsibilities"),
        "required_skills": text("required_skills"),
        "compensation": text("compensation_and_benefits"),
        "targeted_clusters": lst("targeted_degrees_and_disciplines"),
        "application_deadline": text("application_deadline"),
        "documents_required": [
            d.strip()
            for d in (text("application_documents_required") or "").split(",")
            if d.strip()
        ],
        "application_method": text("application_method"),
        "additional_application_info": text("additional_application_information"),
    }
    return {"sections": sections, "fields": fields, "normalized": normalized}


def _field_value(q) -> dict:
    if q.select("td.table__value"):
        return {"list": [td.get_text(" ", strip=True) for td in q.select("td.table__value")]}
    if q.select("ul.targetedClusters li"):
        return {"list": [li.get_text(" ", strip=True) for li in q.select("ul.targetedClusters li")]}
    val: dict = {}
    inner = re.sub(r"\s*\n\s*", "\n", "".join(str(c) for c in q.contents).strip())
    if re.search(r"<(strong|ul|ol|li|b|em|a|br|table)\b", inner):
        val["html"] = inner
    for br in q.find_all("br"):
        br.replace_with("\n")
    for p in q.find_all(["p", "li", "div"]):
        p.append("\n")
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", q.get_text())
    val["text"] = re.sub(r"\n{3,}", "\n\n", text).strip()
    return val


def parse_ratings(report: dict) -> dict:
    """{"tables": [{title, columns, rows}], "charts": [...]} from the raw rating report."""
    out: dict = {"tables": [], "charts": []}
    for sec in report.get("sections", []):
        t = sec.get("type")
        if t == "table":
            out["tables"].append(
                {
                    "title": BeautifulSoup(sec.get("title", ""), "html.parser").get_text(
                        " ", strip=True
                    ),
                    "columns": sec.get("columns"),
                    "rows": sec.get("rows"),
                }
            )
        elif t in ("chart", "graph") or "series" in sec:
            out["charts"].append({k: v for k, v in sec.items() if k != "type"})
    return out


# ---------------------------------------------------------------- derived fields for the viewer


def rating_summary(ratings: dict | None) -> dict:
    """The numbers the viewer shows, pulled out of `parse_ratings` output by table/chart title."""
    out: dict = {
        "terms": [],
        "org_hires": [],
        "div_hires": [],
        "hires_total": 0,
        "hires_recent": 0,
        "rating": None,
        "rating_n": 0,
        "all_avg": None,
        "div_rating": None,
        "div_n": 0,
        "programs": None,
        "dist": None,
        "questions": None,
        "questions_range": "",
    }
    r = ratings or {}
    for t in r.get("tables") or []:
        rows = t.get("rows") or []
        if t.get("title") == "Hiring History":
            out["terms"] = (t.get("columns") or [])[2:]
            for row in rows:
                nums = [_num(x) or 0 for x in row[2:]]
                if row[0] == "Employer Organization":
                    out["org_hires"] = nums
                elif row[0] == "Employer Division":
                    out["div_hires"] = nums
            if not out["org_hires"]:
                out["org_hires"] = out["div_hires"]
            out["hires_total"] = sum(out["org_hires"])
            out["hires_recent"] = sum(out["org_hires"][-4:])
        elif t.get("title") == "Work Term Ratings Summary":
            for row in rows:
                if row[0] == "Employer Organization":
                    out["rating"], out["rating_n"] = _num(row[2]), _num(row[3]) or 0
                elif row[0] == "Employer Division":
                    out["div_rating"], out["div_n"] = _num(row[2]), _num(row[3]) or 0
                elif str(row[0]).startswith("All"):
                    out["all_avg"] = _num(row[2])
            if out["rating"] is None and out["div_rating"] is not None:
                out["rating"], out["rating_n"] = out["div_rating"], out["div_n"]
    for c in r.get("charts") or []:
        title = c.get("title") or ""
        cats, series = c.get("categories") or [], c.get("series") or []
        if not series:
            continue
        if title.startswith("Most Frequently Hired"):
            out["programs"] = list(zip(cats, series[0]["data"], strict=False))
        elif title.startswith("Overall Work Term Satisfaction"):
            out["dist"] = list(zip(cats, series[0]["data"], strict=False))
        elif title.startswith("Average Rating by Question"):
            emp = next((s for s in series if s.get("type") != "spline"), series[0])
            everyone = next((s for s in series if s.get("type") == "spline"), None)
            out["questions"] = [
                (q, emp["data"][i], everyone["data"][i] if everyone else None)
                for i, q in enumerate(cats)
            ]
            m = re.search(r"<br>(.*)$", title)
            out["questions_range"] = m.group(1) if m else ""
    return out


def _num(x) -> float | int | None:
    """Blanks are 0, non-numbers ("N/A") are None; integral values stay ints."""
    try:
        f = float(str(x).strip() or 0)
    except ValueError:
        return None
    return int(f) if f.is_integer() else f


def duration_key(d: str | None) -> str:
    if not d:
        return "unspecified"
    if re.search(r"8 month.*required", d, re.I):
        return "8 months required"
    if re.search(r"8 month", d, re.I):
        return "8 months preferred"
    if re.search(r"4 month", d, re.I):
        return "4 months"
    return d


# Division names WaterlooWorks fills in when the employer has not set up real divisions.
_BOILERPLATE_DIVISION_RE = re.compile(
    r"^(divisional?|head|main|corporate(\s+head)?)\s+(office|headquarters)$", re.I
)


def division(summary: dict) -> str | None:
    """The employer division, or None when it only repeats the organization or a stock label."""
    d = (summary.get("division") or "").strip()
    if not d or d == (summary.get("organization") or "").strip():
        return None
    if _BOILERPLATE_DIVISION_RE.match(d):
        return None
    return d


def facets(summary: dict, detail: dict | None, external: dict | None = None) -> dict:
    """The values the viewer's filter menus are built from, one key per menu."""
    d = detail or {}
    levels = d.get("levels") or (
        re.split(r",\s*", summary["level"]) if summary.get("level") else []
    )
    return {
        "arrangement": d.get("location_arrangement") or "unspecified",
        "region": d.get("region") or "unspecified",
        "country": (d.get("address") or {}).get("country") or "unspecified",
        "levels": levels,
        "duration": duration_key(d.get("work_term_duration")),
        "clusters": [re.sub(r"^- Theme - ", "", c) for c in d.get("targeted_clusters") or []],
        "docs": d.get("documents_required") or [],
        "apply": "Also on employer site" if external else "WaterlooWorks only",
    }


# Hosts of applicant-tracking systems. A link to one of these in "Additional Application
# Information" means the employer wants a second application there.
_ATS_HOST_RE = re.compile(
    r"greenhouse\.io|grnh\.se|ashbyhq\.com|lever\.co|myworkdayjobs\.com|recruitee\.com"
    r"|jobs\.gem\.com|smartrecruiters\.com|icims\.com|jobvite\.com|bamboohr\.com"
    r"|workable\.com|rippling\.com|dover\.io|breezy\.hr|applytojob\.com",
    re.I,
)
# The co-op office's stock sentence ("Interested applicants must apply through WaterlooWorks
# and directly to the employer …") and the ways employers paraphrase it.
_DUAL_APPLY_RE = re.compile(
    r"waterloo\s*works\s+and\s+directly"
    r"|in\s+addition\s+to\s+(?:submitting|applying)"
    r"|also\s+apply\b"
    r"|apply\s+directly\b"
    r"|complete\s+our\s+online\s+application",
    re.I,
)
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
_HREF_RE = re.compile(r'href="([^"]+)"')
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.I)


def external_application(fields: dict | None, detail: dict | None) -> dict | None:
    """Whether the posting wants a second application outside WaterlooWorks, and where.

    Returns {"url", "email", "why"} or None. `why` is "ats" (a link to a known applicant-tracking
    host), "boilerplate" (the stock "apply through WaterlooWorks and directly to the employer"
    wording), or "method" (an Application Method other than WaterlooWorks). Detection reads only
    "Additional Application Information", which is where employers put it.
    """
    v = (fields or {}).get("additional_application_information") or {}
    text = v.get("text") or ""
    html = v.get("html") or ""
    urls: list[str] = []
    for u in _HREF_RE.findall(html) + _URL_RE.findall(text):
        u = u.rstrip(".,;:")
        host = u.split("/")[2] if u.count("/") >= 2 else ""
        if u.startswith("mailto:") or "@" in host:  # mailto: and "http://name@host" pseudo-links
            continue
        if u not in urls:
            urls.append(u)
    ats = [u for u in urls if _ATS_HOST_RE.search(u)]
    method = (detail or {}).get("application_method")
    if ats:
        why = "ats"
    elif _DUAL_APPLY_RE.search(text):
        why = "boilerplate"
    elif method and method.strip().lower() != "waterlooworks":
        why = "method"
    else:
        return None
    emails = [e for e in _EMAIL_RE.findall(text) if not re.match(r"aoda@|accessib", e, re.I)]
    return {
        "url": (ats or urls or [None])[0],
        "email": None if (ats or urls) else (emails or [None])[0],
        "why": why,
    }


def field_text(v) -> str:
    """One line of plain text from a `fields` value ({text?, html?, list?} or a string)."""
    if v is None:
        return ""
    if isinstance(v, str):
        raw = v
    elif v.get("text"):
        raw = v["text"]
    elif v.get("html"):
        raw = BeautifulSoup(v["html"], "html.parser").get_text(" ")
    else:
        raw = " ".join(v.get("list") or [])
    return re.sub(r"\s+", " ", raw).strip()


_COMP_UNITS = [
    (re.compile(r"\b(?:hour|hourly|hr|hrly|h)\b", re.I), "hr"),
    (re.compile(r"\b(?:week|weekly|wk)\b", re.I), "wk"),
    (re.compile(r"\b(?:month|monthly|mo)\b", re.I), "mo"),
    (re.compile(r"\b(?:year|yearly|yr|annum|annual|annually|annualized)\b", re.I), "yr"),
    (re.compile(r"\b(?:term|work term)\b", re.I), "term"),
]
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+)(?:\s?[.,](\d{1,2}))?\s*(k)?"
_CUR = r"(CA\$|CAD|US\$|USD|\$|€|C\$|A\$)"
_UNIT_WORD = r"(?:hour|hourly|hr|hrly|week|weekly|wk|month|monthly|mo|year|yr|annum|annually)"
_COMP_RE = re.compile(
    rf"(?:{_CUR}\s*)?(?:{_CUR}\s*)?{_NUM}(?:\s*{_CUR})?(?:\s*(?:/|per|an?)\s*{_UNIT_WORD})?"
    rf"(?:\s*(?:-{{1,2}}|\u2013|\u2014|~|to(?: a max(?:imum)? of)?|and)\s*(?:{_CUR}\s*)?{_NUM})?",
    re.I,
)
_AFTER_UNIT_RE = re.compile(
    r"^\s*(?:CAD|USD|CA|US|€|\(euro\)|euros?)?\s*(?:/|per|an?\b|a\b)?\s*"
    r"(hour|hourly|hr|hrly|h\b|week|weekly|wk|month|monthly|mo|year|yearly|yr|annum|annual"
    r"|annually|annualized|term)\b",
    re.I,
)
_BEFORE_UNIT_RE = re.compile(
    r"\b(hourly|hr|weekly|monthly|annual(?:ized|ly)?|yearly|per (?:hour|week|month|year))\b", re.I
)
_NOT_MONEY_RE = re.compile(r"^\s*(?:%|hours?\b|hrs?\b|h/w|\+?\s*years?)", re.I)
_EURO_AFTER_RE = re.compile(r"^\s*(€|euros?\b|\(euro\))", re.I)
_STRIP_NUM_RE = re.compile(r"\d[\d,]*(?:\s?[.,]\d{1,2})?\s*k?", re.I)
_STRIP_CUR_RE = re.compile(
    r"[$€]|\b(?:CAD|USD|CA|US|C\$|A\$|to|and|a max(?:imum)? of)\b|-{1,2}|\u2013|\u2014|~", re.I
)
_NEAR_CUR_RE = re.compile(r"\b(USD|CAD)\b|\bUS\s*\$|€|\beuros?\b", re.I)


def _unit_for(word: str) -> str | None:
    return next((u for rx, u in _COMP_UNITS if rx.search(word)), None)


def compensation(text: str) -> dict | None:
    """First money figure (single or range) in free-form compensation text.

    Returns {lo, hi, unit, currency}: unit is hr/wk/mo/yr/term, currency CAD/USD/EUR or None.
    Numbers with neither a currency mark nor an explicit unit are skipped, as are figures that
    read as hours, percentages or years.
    """
    if not text:
        return None
    for m in _COMP_RE.finditer(text):
        c1, c2, n1, d1, k1, c2b, c3, n2, d2, k2 = m.groups()
        cur_tok = " ".join(c for c in (c1, c2, c2b, c3) if c) or None
        end = m.end()
        cur_after = bool(_EURO_AFTER_RE.search(text[end : end + 8]))
        after = text[end : end + 40]
        before = text[max(0, m.start() - 30) : m.start()]
        if _NOT_MONEY_RE.search(after):
            continue
        unit = None
        tail = _STRIP_CUR_RE.sub(" ", _STRIP_NUM_RE.sub(" ", m.group(0))).strip() + " " + after
        after_unit = _AFTER_UNIT_RE.search(tail)
        if after_unit:
            unit = _unit_for(after_unit.group(1))
        else:
            b = _BEFORE_UNIT_RE.search(before)
            if b:
                unit = _unit_for(re.sub(r"^per ", "", b.group(1)))

        def val(n: str, d: str | None, k: str | None) -> float:
            return (float(n.replace(",", "")) + (float("0." + d) if d else 0)) * (1000 if k else 1)

        lo = val(n1, d1, k1)
        hi = val(n2, d2, k2) if n2 else None
        if k2 and not k1 and lo < 1000:
            lo *= 1000
        if not (cur_tok or cur_after) and not after_unit and not k1 and not k2:
            continue
        if not unit:
            unit = "hr" if lo < 250 else "wk" if lo < 2600 else "mo" if lo < 25000 else "yr"
        if not lo or (hi is not None and hi < lo):
            continue
        if unit == "hr" and (lo < 12 or lo > 500):
            continue
        if unit == "term" and lo < 1000:
            continue
        ct = cur_tok or ""
        if re.search("US", ct, re.I):
            currency = "USD"
        elif re.search(r"CA|C\$", ct, re.I):
            currency = "CAD"
        elif "€" in ct or cur_after:
            currency = "EUR"
        else:
            currency = None
        if not currency:
            near = _NEAR_CUR_RE.search(before + after)
            if near:
                w = near.group(0)
                currency = (
                    "USD"
                    if re.search("US", w, re.I)
                    else "EUR"
                    if re.search("€|euro", w, re.I)
                    else "CAD"
                )
        return {"lo": _tidy(lo), "hi": _tidy(hi), "unit": unit, "currency": currency}
    return None


def _tidy(x: float | None) -> float | int | None:
    return int(x) if x is not None and x.is_integer() else x
