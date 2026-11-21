"""SQLite key-value cache for AI results (analyses, top themes, suggested replies).

Each AI result is stored under a namespace ("analysis", "themes", "reply") and a key built from a
hash of its input, so uploading the same reviews again costs zero AI calls.
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    namespace  TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (namespace, key)
)
"""


class Cache:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(SCHEMA)

    def get(self, namespace: str, key: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM entries WHERE namespace = ? AND key = ?", (namespace, key)
            ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None  # a damaged entry is treated as a miss and gets overwritten

    def put(self, namespace: str, key: str, value: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO entries (namespace, key, value) VALUES (?, ?, ?)",
                (namespace, key, json.dumps(value, ensure_ascii=False)),
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        # A short-lived connection per operation keeps this safe across FastAPI's worker threads.
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:  # commit on success, roll back on error
                yield conn
        finally:
            conn.close()
