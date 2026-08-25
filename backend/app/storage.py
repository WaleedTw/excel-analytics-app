import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.config import ANALYSIS_DIR, DATABASE_PATH, UPLOAD_DIR


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database() -> None:
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY, original_name TEXT NOT NULL, safe_name TEXT NOT NULL,
                size_bytes INTEGER NOT NULL, mime_type TEXT NOT NULL,
                metadata_json TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY, file_id TEXT NOT NULL, sheet_name TEXT NOT NULL,
                status TEXT NOT NULL, dashboard_path TEXT, quality_json TEXT,
                trace_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY(file_id) REFERENCES files(id)
            );
            """
        )


def save_file_record(record: dict[str, Any]) -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record["file_id"], record["original_name"], record["safe_name"],
                record["size_bytes"], record["mime_type"], json.dumps(record, ensure_ascii=False, default=str),
                record["created_at"].isoformat() if hasattr(record["created_at"], "isoformat") else record["created_at"],
            ),
        )


def get_file_record(file_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute("SELECT metadata_json FROM files WHERE id = ?", (file_id,)).fetchone()
    return json.loads(row[0]) if row else None


def delete_file_record(file_id: str) -> None:
    """Remove upload metadata after the source workbook has been deleted."""
    with _connect() as connection:
        connection.execute("DELETE FROM files WHERE id = ?", (file_id,))


def purge_previous_data() -> None:
    """Remove data left by an earlier server session.

    Bayyinah now treats uploads and generated dashboards as session data, so a
    server reload starts with an empty private workspace.
    """
    for pattern in ("*.xlsx", "*.csv"):
        for path in UPLOAD_DIR.glob(pattern):
            path.unlink(missing_ok=True)
    for path in ANALYSIS_DIR.glob("*.json"):
        path.unlink(missing_ok=True)
    with _connect() as connection:
        connection.execute("DELETE FROM analyses")
        connection.execute("DELETE FROM files")