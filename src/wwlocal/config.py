"""Paths, constants and the one helper every module needs."""

import os
from datetime import UTC, datetime
from pathlib import Path

BASE = "https://waterlooworks.uwaterloo.ca"
JOBS_PATH = "/myAccount/co-op/full/jobs.htm"
JOBS_URL = BASE + JOBS_PATH
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)

# Targeted Degrees and Disciplines cluster ids (OR-ed together server-side).
# 208 Computing: Software Development, 180 ENG Software Engineering, 190 MATH Computer Science.
# Others of interest: 211 Data Science, 176 ECE, 221 Info Systems & Data Mgmt, 193 Stats & ActSci.
DEFAULT_CLUSTERS = ["208", "180", "190"]
RATINGS_TTL_DAYS = 14

_repo_root = Path(__file__).resolve().parents[2]
DATA_DIR = Path(
    os.environ.get("WWLOCAL_DIR") or os.environ.get("WWSYNC_DIR") or _repo_root / "data"
)
COOKIES_FILE = DATA_DIR / "cookies.json"
JOBS_DB = DATA_DIR / "waterlooworks_jobs.db"
VIEWER_STATE_DB = DATA_DIR / "viewer_state.db"


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
