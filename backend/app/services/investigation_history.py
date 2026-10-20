"""Shared, persistent investigation history. No end-user ownership is tracked."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.core.errors import BadRequestError
from app.schemas.investigations import InvestigationWrite, SavedInvestigation
from app.services.masking import mask_message


_SCHEMA = """
CREATE TABLE IF NOT EXISTS investigations (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    turns_json TEXT NOT NULL
)
"""
_UPDATED_INDEX = """
CREATE INDEX IF NOT EXISTS investigations_updated_at_idx
ON investigations (updated_at DESC, id DESC)
"""


@contextmanager
def _database(path: str) -> Iterator[sqlite3.Connection]:
    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=5)
    try:
        connection.execute(_SCHEMA)
        connection.execute(_UPDATED_INDEX)
        yield connection
        connection.commit()
    finally:
        connection.close()


def _serialized_turns(record: InvestigationWrite) -> str:
    turns = []
    for turn in record.turns:
        response = turn.response.model_copy(update={
            "analysis": mask_message(turn.response.analysis),
            "warnings": [mask_message(warning) for warning in turn.response.warnings],
        })
        turns.append(turn.model_copy(update={
            "question": mask_message(turn.question),
            "response": response,
        }).model_dump(mode="json"))
    payload = json.dumps(turns, ensure_ascii=False, separators=(",", ":"))
    if len(payload.encode("utf-8")) > 1_000_000:
        raise BadRequestError("Investigation history is too large to save (max 1 MB).")
    return payload


def _row_to_record(row: sqlite3.Row) -> SavedInvestigation:
    return SavedInvestigation.model_validate({
        "id": row["id"],
        "source": row["source"],
        "startTime": row["start_time"],
        "endTime": row["end_time"],
        "updatedAt": row["updated_at"],
        "turns": json.loads(row["turns_json"]),
    })


def list_investigations(path: str, limit: int, offset: int) -> tuple[list[SavedInvestigation], int | None]:
    with _database(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM investigations ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
            (limit + 1, offset),
        ).fetchall()
    has_more = len(rows) > limit
    return [_row_to_record(row) for row in rows[:limit]], offset + limit if has_more else None


def save_investigation(path: str, investigation_id: str, record: InvestigationWrite) -> SavedInvestigation:
    updated_at = datetime.now(timezone.utc).isoformat()
    turns_json = _serialized_turns(record)
    with _database(path) as connection:
        connection.execute(
            """INSERT INTO investigations (id, source, start_time, end_time, updated_at, turns_json)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 source=excluded.source, start_time=excluded.start_time,
                 end_time=excluded.end_time, updated_at=excluded.updated_at,
                 turns_json=excluded.turns_json""",
            (investigation_id, mask_message(record.source), record.start_time,
             record.end_time, updated_at, turns_json),
        )
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM investigations WHERE id = ?", (investigation_id,)
        ).fetchone()
    return _row_to_record(row)


def import_investigations(path: str, records: list[SavedInvestigation]) -> int:
    prepared = [
        (record.id, mask_message(record.source), record.start_time, record.end_time,
         record.updated_at.isoformat(), _serialized_turns(record))
        for record in records
    ]
    with _database(path) as connection:
        before = connection.total_changes
        connection.executemany(
            """INSERT OR IGNORE INTO investigations
               (id, source, start_time, end_time, updated_at, turns_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            prepared,
        )
        return connection.total_changes - before


def delete_investigation(path: str, investigation_id: str) -> None:
    with _database(path) as connection:
        connection.execute("DELETE FROM investigations WHERE id = ?", (investigation_id,))
