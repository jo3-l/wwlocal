"""viewer_state.db: what the user adds about a posting. Never touched by sync.

Columns are the contract. To add a kind of state, add a column to SCHEMA and an
`ALTER TABLE ... ADD COLUMN` line to MIGRATIONS; the API picks it up automatically.
"""

import contextlib
import sqlite3
import threading
from typing import Any

from wwlocal.config import VIEWER_STATE_DB, now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS posting_state (
  posting_id INTEGER PRIMARY KEY,
  star       INTEGER NOT NULL DEFAULT 0,
  hidden     INTEGER NOT NULL DEFAULT 0,
  applied    INTEGER NOT NULL DEFAULT 0,
  viewed     INTEGER NOT NULL DEFAULT 0,
  notes      TEXT,
  updated_at TEXT NOT NULL
);
"""
MIGRATIONS: list[str] = []  # e.g. "ALTER TABLE posting_state ADD COLUMN resume TEXT"
BOOL_COLUMNS = frozenset({"star", "hidden", "applied", "viewed"})
_lock = threading.Lock()


def _open() -> sqlite3.Connection:
    VIEWER_STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(VIEWER_STATE_DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    for stmt in MIGRATIONS:
        with contextlib.suppress(sqlite3.OperationalError):  # already applied
            con.execute(stmt)
    return con


def editable_columns(con: sqlite3.Connection) -> list[str]:
    cols = [r["name"] for r in con.execute("PRAGMA table_info(posting_state)")]
    return [c for c in cols if c not in ("posting_id", "updated_at")]


def _public(row: sqlite3.Row, cols: list[str]) -> dict[str, Any]:
    """Only the values that differ from the column default."""
    return {c: (bool(row[c]) if c in BOOL_COLUMNS else row[c]) for c in cols if row[c]}


def get_all() -> dict[str, dict[str, Any]]:
    with _lock, _open() as con:
        cols = editable_columns(con)
        return {
            str(r["posting_id"]): _public(r, cols)
            for r in con.execute("SELECT * FROM posting_state")
        }


def patch(posting_id: int, changes: dict[str, Any]) -> dict[str, Any]:
    """Merge `changes` into the posting's row. Returns the row as the API shows it."""
    with _lock, _open() as con:
        cols = editable_columns(con)
        bad = sorted(set(changes) - set(cols))
        if bad:
            raise ValueError(f"unknown state keys: {bad}")
        values = {c: int(bool(v)) if c in BOOL_COLUMNS else v for c, v in changes.items()}
        assignments = ", ".join(f"{c}=excluded.{c}" for c in values)
        con.execute(
            f"INSERT INTO posting_state (posting_id, updated_at, {', '.join(values)})"
            f" VALUES (?, ?, {', '.join('?' * len(values))})"
            f" ON CONFLICT(posting_id) DO UPDATE SET updated_at=excluded.updated_at, {assignments}",
            (posting_id, now_iso(), *values.values()),
        )
        row = con.execute(
            "SELECT * FROM posting_state WHERE posting_id=?", (posting_id,)
        ).fetchone()
        public = _public(row, cols)
        if not public:
            con.execute("DELETE FROM posting_state WHERE posting_id=?", (posting_id,))
        return public
