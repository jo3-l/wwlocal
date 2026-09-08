"""Record assets/demo.gif: the viewer over mock postings, with the keys pressed shown on screen.

    uv run --with pillow scripts/demo_gif.py [out.gif]

Nothing here touches data/: the mock database and the viewer state live in a temporary
WWLOCAL_DIR. Needs the Playwright chromium from `uv run playwright install chromium`.
"""

import io
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, ViewportSize, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PORT = 8814
VIEWPORT: ViewportSize = {"width": 1200, "height": 660}
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "assets/demo.gif"

# ---------------------------------------------------------------- mock board

TERMS = [
    "2024 - Fall",
    "2025 - Winter",
    "2025 - Spring",
    "2025 - Fall",
    "2026 - Winter",
    "2026 - Spring",
]
FIELDS = (
    "org",
    "division",
    "title",
    "city",
    "region",
    "arrangement",
    "levels",
    "duration",
    "applicants",
    "comp",
    "skills",
    "hires",
    "rating",
    "rating_n",
)
# fmt: off
ROWS = [
    ("Lakefield Robotics", "Perception", "Software Developer, Perception", "Kitchener",
     "Southwestern Ontario", "Hybrid", "Junior, Intermediate", "4 month work term", 14,
     "$32 - $38 per hour", "C++17, Python, ROS 2. Familiarity with Rust or embedded Linux a plus.",
     [2, 3, 3, 4, 4, 5], 8.9, 31),
    ("Northbank Financial", "Capital Markets Technology", "Backend Developer Co-op", "Toronto",
     "Greater Toronto Area", "In-person", "Intermediate, Senior", "4 month work term", 63,
     "$29.50/hr plus $1,500 housing stipend",
     "Java, Spring Boot, Kafka, PostgreSQL. Interest in low-latency systems.",
     [12, 10, 14, 11, 13, 15], 8.1, 88),
    ("Tessellate", "", "Rust Systems Engineering Intern", None, "Anywhere in Canada", "Remote",
     "Intermediate, Senior", "8 month work term preferred", 9, "$40 - $45 per hour CAD",
     "Rust, Tokio, gRPC. You'll work on our storage engine and its replication layer.",
     [1, 1, 2, 2, 2, 3], 9.4, 9),
    ("Halcyon Health", "Clinical Platforms", "Full Stack Developer", "Waterloo",
     "Southwestern Ontario", "Hybrid", "Junior, Intermediate", "4 month work term", 27,
     "$26 - $30 per hour", "TypeScript, React, Node.js, PostgreSQL. HL7/FHIR experience is nice.",
     [4, 4, 5, 4, 6, 5], 8.6, 27),
    ("Meridian Grid", "Software", "Embedded Firmware Developer", "Calgary", "Alberta", "In-person",
     "Junior", "4 month work term", 6, "$27 per hour",
     "C, FreeRTOS, ARM Cortex-M, oscilloscopes. Some Rust in our newer boards.",
     [1, 0, 2, 1, 2, 2], None, 0),
    ("Quillwork", "", "Developer Tools Intern", None, "Anywhere in Canada", "Remote",
     "Junior, Intermediate, Senior", "4 month work term", 41, "$8,000 per month",
     "Go, TypeScript, language servers, tree-sitter. Strong writing skills.",
     [3, 3, 4, 5, 6, 6], 9.1, 19),
    ("Brightwater Studios", "Engine", "Game Engine Programmer", "Montréal", "Quebec", "In-person",
     "Intermediate, Senior", "8 month work term required", 118, "$25 per hour",
     "C++, Vulkan/DirectX 12, math. Portfolio required.", [6, 8, 7, 9, 8, 10], 7.6, 44),
    ("Fernway Analytics", "", "Data Engineering Co-op", "Ottawa", "Eastern Ontario", "Hybrid",
     "Junior, Intermediate", "4 month work term", 35, "$28 - $34 per hour",
     "Python, dbt, Snowflake, Airflow, SQL.", [2, 2, 3, 3, 3, 4], 8.4, 15),
    ("Orchard Labs", "Platform", "Site Reliability Engineer Intern", "Vancouver",
     "British Columbia", "Hybrid", "Intermediate, Senior", "8 month work term preferred", 22,
     "$36/hour", "Kubernetes, Terraform, Go, Prometheus. On-call shadowing in your second term.",
     [3, 4, 4, 5, 5, 5], 8.8, 22),
    ("Cobalt Ledger", "", "Blockchain Protocol Developer", None, "Anywhere in Canada", "Remote",
     "Senior", "4 month work term", 3, "$45 - $55 per hour USD",
     "Rust, cryptography, distributed consensus. Open-source contributions welcome.",
     [0, 1, 1, 1, 2, 1], None, 0),
    ("Province of Ontario", "Digital Service", "Web Developer", "Toronto", "Greater Toronto Area",
     "Hybrid", "Junior", "4 month work term", 84, "$24.10 - $27.80 per hour",
     "HTML, CSS, JavaScript, accessibility (WCAG 2.1), Drupal.", [9, 11, 10, 12, 10, 11], 8.3, 63),
    ("Sable Semiconductor", "Design Verification", "Verification Engineering Co-op", "Markham",
     "Greater Toronto Area", "In-person", "Intermediate, Senior", "8 month work term preferred",
     17, "$33 per hour", "SystemVerilog, UVM, Python scripting. Formal verification a plus.",
     [5, 5, 6, 6, 7, 7], 8.7, 36),
    ("Kestrel Aerospace", "Flight Software", "Flight Software Developer", "Mississauga",
     "Greater Toronto Area", "In-person", "Intermediate", "4 month work term", 29, "$31 per hour",
     "C++, real-time systems, DO-178C processes. Rust prototyping on ground tooling.",
     [2, 3, 2, 3, 4, 3], 8.5, 18),
    ("Pinegrove Software", "", "iOS Developer Intern", None, "Anywhere in Canada", "Remote",
     "Junior, Intermediate", "4 month work term", 52, "$30 per hour",
     "Swift, SwiftUI, Combine. Ship features to a few million users.",
     [2, 2, 2, 3, 3, 3], 8.9, 14),
]
# fmt: on
POSTINGS = [dict(zip(FIELDS, row, strict=True)) for row in ROWS]
CLUSTERS = ["- Theme - Computing: Software Development", "- Theme - ENG - Software Engineering"]
DOCS = ["Résumé", "Cover Letter", "Grade Report"]


def build_mock_db(path: Path) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from wwlocal import jobs_db

    con = sqlite3.connect(path)
    con.executescript(jobs_db.SCHEMA)
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    for i, p in enumerate(POSTINGS):
        pid, div_id = 400_000 + i * 37, 9_000 + i
        summary = {
            "id": pid,
            "title": p["title"],
            "organization": p["org"],
            "division": p["division"] or "Divisional Office",
            "openings": 1 + i % 3,
            "city": p["city"],
            "level": p["levels"],
            "deadline": f"2026-09-{12 + i % 9:02d}T23:59:00",
            "application_count": p["applicants"],
            "flags": {},
        }
        blurb = (
            f"{p['org']} is hiring a {p['title'].lower()} for the Winter 2027 term. You'll join "
            "a small team, ship to production in your first weeks, and own a project end to end."
        )
        fields = {
            "job_summary": {"text": blurb},
            "job_responsibilities": {
                "html": "<ul><li>Design, implement and test features with your team</li>"
                "<li>Review code and write design notes</li>"
                "<li>Take part in planning and retros</li></ul>"
            },
            "required_skills": {"text": p["skills"]},
            "compensation_and_benefits": {"text": p["comp"]},
            "application_documents_required": {"text": ", ".join(DOCS)},
            "application_method": {"text": "WaterlooWorks"},
            "targeted_degrees_and_disciplines": {"list": CLUSTERS},
        }
        normalized = {
            "work_term": "2027 - Winter",
            "job_type": "Co-op Main",
            "levels": p["levels"].split(", "),
            "region": p["region"],
            "address": {"city": p["city"], "country": "Canada"},
            "location_arrangement": p["arrangement"],
            "work_term_duration": p["duration"],
            "summary": blurb,
            "required_skills": p["skills"],
            "compensation": p["comp"],
            "targeted_clusters": CLUSTERS,
            "application_deadline": summary["deadline"],
            "documents_required": DOCS,
            "application_method": "WaterlooWorks",
        }
        con.execute(
            "INSERT INTO postings (id, first_seen, last_seen, summary_json, summary_hash,"
            " detail_fetched_at, data_json, overview_json, div_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                pid,
                now,
                now,
                json.dumps(summary),
                jobs_db.summary_hash(summary),
                now,
                json.dumps({"internalStatus": "Approved", "tags": [], "defaultLocations": []}),
                json.dumps({"sections": {}, "fields": fields, "normalized": normalized}),
                div_id,
            ),
        )
        con.execute(
            "INSERT INTO ratings (div_id, fetched_at, report_json) VALUES (?,?,?)",
            (div_id, now, json.dumps(rating_report(p["hires"], p["rating"], p["rating_n"]))),
        )
    con.execute("INSERT INTO runs (started_at, finished_at) VALUES (?, ?)", (now, now))
    con.commit()
    con.close()


def rating_report(hires: list[int], rating: float | None, n: int) -> dict:
    """The shape of getWorkTermRatingReportJson, reduced to what parse.rating_summary reads."""
    sections: list[dict] = [
        {
            "type": "table",
            "title": "Hiring History",
            "columns": ["", "", *TERMS],
            "rows": [["Employer Organization", "", *hires], ["Employer Division", "", *hires]],
        }
    ]
    if rating is not None:
        sections.append(
            {
                "type": "table",
                "title": "Work Term Ratings Summary",
                "columns": ["", "", "Rating", "Count"],
                "rows": [
                    ["Employer Organization", "", rating, n],
                    ["Employer Division", "", rating, n],
                    ["All Employers", "", 8.5, 40000],
                ],
            }
        )
        sections.append(
            {
                "type": "chart",
                "title": "Overall Work Term Satisfaction",
                "categories": ["Outstanding", "Excellent", "Very Good", "Good", "Satisfactory"],
                "series": [{"data": [round(rating * 5), round(100 - rating * 7), 12, 6, 2]}],
            }
        )
    return {"sections": sections}


# ---------------------------------------------------------------- recording

# Bottom-centre key bar in the style of VS Code's screencast mode: the keys pressed in a row,
# each in its own box, with the command name in smaller text beside them.
OVERLAY_JS = """
(() => {
  const el = document.createElement('div');
  el.id = 'demo-hud';
  el.style.cssText = [
    'position:fixed', 'left:50%', 'bottom:28px', 'transform:translateX(-50%)', 'display:flex',
    'align-items:center', 'gap:14px', 'padding:12px 20px', 'border-radius:10px',
    'background:rgba(30,30,30,.88)', 'color:#eee', 'font:15px -apple-system,system-ui,sans-serif',
    'z-index:99999', 'pointer-events:none', 'white-space:nowrap',
  ].join(';');
  document.body.appendChild(el);
  const box = 'display:inline-block;min-width:22px;text-align:center;padding:4px 14px;'
    + 'border:1px solid #8a8a8a;border-radius:6px;background:#3c3c3c;color:#fff;'
    + 'font:500 30px/1.3 -apple-system,system-ui,sans-serif;box-shadow:inset 0 -2px 0 #2a2a2a';
  window.__hud = (keys, command) => {
    el.innerHTML = keys.map(k => `<span style="${box}">${k}</span>`).join('')
      + (command ? `<span style="color:#bbb;margin-left:4px">${command}</span>` : '');
    el.style.display = keys.length || command ? 'flex' : 'none';
  };
  window.__hud([], '');
})();
"""


class Recorder:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.frames: list[tuple[Image.Image, int]] = []
        self.keys: list[str] = []  # the keys shown in the bar; a new command starts a new run
        self.command = ""

    def hud(self, keys: Sequence[str] = (), command: str = "") -> None:
        self.keys, self.command = list(keys), command
        self.page.evaluate("([k, c]) => window.__hud(k, c)", [self.keys, command])

    def snap(self, ms: int, settle: int = 80) -> None:
        """Screenshot the page as one GIF frame shown for `ms`."""
        self.page.wait_for_timeout(settle)
        png = self.page.screenshot(type="png")
        self.frames.append((Image.open(io.BytesIO(png)).convert("RGB"), ms))

    def key(self, key: str, command: str, label: str = "", ms: int = 420) -> None:
        """Press `key`; it joins the bar if the command is unchanged, else the bar restarts."""
        keys = [*self.keys, label or key] if command == self.command else [label or key]
        self.hud(keys[-6:], command)
        self.page.keyboard.press(key)
        self.snap(ms)


def record(page: Page) -> list[tuple[Image.Image, int]]:
    r = Recorder(page)
    page.goto(f"http://127.0.0.1:{PORT}/")
    page.wait_for_selector(".row")
    page.evaluate(OVERLAY_JS)
    r.snap(900)

    # 1. keyboard navigation
    r.key("j", "next posting", ms=550)
    r.key("j", "next posting")
    r.key("ArrowDown", "next posting", label="↓")
    r.key("k", "previous posting", label="k", ms=550)
    r.key("s", "shortlist", ms=1000)
    r.key("j", "next posting")
    r.key("x", "hide", ms=1000)
    r.hud()
    r.snap(300)

    # 2. search
    r.key("/", "search", ms=450)
    for ch in "lakefield":
        r.key(ch, "search", ms=130)
    r.snap(900)
    # Esc in a type=search box empties it natively without an input event, so clear it by hand.
    page.locator("#search").select_text()
    r.key("Backspace", "clear search", label="⌫", ms=450)
    page.keyboard.press("Escape")
    r.hud()
    r.snap(300)

    # 3. a filter
    r.hud(command="filter: work mode")
    page.click("details.dd summary:has-text('Work mode')")
    r.snap(600)
    page.click("details.dd[open] .menu label:has-text('Remote')")
    r.snap(1000)
    page.keyboard.press("Escape")
    r.hud()
    r.key("j", "next posting")
    r.key("j", "next posting", ms=1600)
    return r.frames


def write_gif(frames: list[tuple[Image.Image, int]], out: Path) -> None:
    # One palette for the whole clip keeps colours stable and lets Pillow store frame deltas.
    w, h = frames[0][0].size
    picks = [0, len(frames) // 3, 2 * len(frames) // 3, len(frames) - 1]
    sample = Image.new("RGB", (w, h * len(picks)))
    for i, k in enumerate(picks):
        sample.paste(frames[k][0], (0, i * h))
    palette = sample.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    quantized = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f, _ in frames]
    out.parent.mkdir(parents=True, exist_ok=True)
    quantized[0].save(
        out,
        save_all=True,
        append_images=quantized[1:],
        duration=[ms for _, ms in frames],
        loop=0,
        optimize=True,
        disposal=1,
    )


def wait_port(port: int, timeout: float = 20) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise SystemExit("viewer did not start")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="wwlocal-demo-") as tmp:
        build_mock_db(Path(tmp) / "waterlooworks_jobs.db")
        env = {**os.environ, "WWLOCAL_DIR": tmp, "PYTHONPATH": str(ROOT / "src")}
        serve = f"from wwlocal.viewer import serve; serve('127.0.0.1', {PORT}, False, False)"
        server = subprocess.Popen(
            [sys.executable, "-c", serve],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            wait_port(PORT)
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(
                    viewport=VIEWPORT,
                    device_scale_factor=1,
                    color_scheme="light",
                    timezone_id="America/Toronto",
                    locale="en-CA",
                )
                frames = record(page)
                browser.close()
        finally:
            server.terminate()
            server.wait()
    write_gif(frames, OUT)
    print(f"{OUT}: {len(frames)} frames, {OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
