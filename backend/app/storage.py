import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import ANALYSIS_DIR, DATABASE_PATH


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


def save_analysis_record(analysis_id: str, state: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    dashboard_path = None
    if state.get("dashboard"):
        path = ANALYSIS_DIR / f"{analysis_id}.json"
        path.write_text(json.dumps(state["dashboard"], ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        dashboard_path = str(path)
    with _connect() as connection:
        connection.execute(
            """INSERT INTO analyses(id,file_id,sheet_name,status,dashboard_path,quality_json,trace_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET status=excluded.status,dashboard_path=excluded.dashboard_path,
               quality_json=excluded.quality_json,trace_json=excluded.trace_json,updated_at=excluded.updated_at""",
            (
                analysis_id, state["file_id"], state["sheet_name"], state.get("status", "running"), dashboard_path,
                json.dumps(state.get("quality"), ensure_ascii=False), json.dumps(state.get("trace", []), ensure_ascii=False),
                now, now,
            ),
        )


def list_analyses() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """SELECT a.id,a.file_id,a.sheet_name,a.status,a.created_at,f.original_name
               FROM analyses a JOIN files f ON f.id=a.file_id ORDER BY a.updated_at DESC"""
        ).fetchall()
    return [dict(row) for row in rows]


def get_analysis_record(analysis_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            """SELECT id,status,dashboard_path,quality_json,trace_json
               FROM analyses WHERE id = ?""",
            (analysis_id,),
        ).fetchone()
    if not row:
        return None
    record = dict(row)
    dashboard_path = record.pop("dashboard_path", None)
    record["dashboard"] = (
        json.loads(Path(dashboard_path).read_text(encoding="utf-8"))
        if dashboard_path
        else None
    )
    record["quality"] = json.loads(record.pop("quality_json") or "null")
    record["trace"] = json.loads(record.pop("trace_json") or "[]")
    return record
