import sqlite3
from datetime import UTC, datetime
from collections.abc import Iterator
from contextlib import contextmanager

from .config import DATABASE_PATH


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                audio_path TEXT NOT NULL,
                transcript_path TEXT,
                summary_path TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )


def create_note(
    *,
    note_id: str,
    audio_path: str,
    created_at: str,
    expires_at: str,
    status: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO notes (
                id,
                audio_path,
                transcript_path,
                summary_path,
                created_at,
                expires_at,
                status
            )
            VALUES (?, ?, NULL, NULL, ?, ?, ?)
            """,
            (note_id, audio_path, created_at, expires_at, status),
        )


def get_note(note_id: str) -> sqlite3.Row | None:
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT
                id,
                audio_path,
                transcript_path,
                summary_path,
                created_at,
                expires_at,
                status
            FROM notes
            WHERE id = ?
            """,
            (note_id,),
        ).fetchone()


def list_active_notes() -> list[sqlite3.Row]:
    now = datetime.now(UTC).isoformat()

    with get_connection() as connection:
        return connection.execute(
            """
            SELECT
                id,
                audio_path,
                transcript_path,
                summary_path,
                created_at,
                expires_at,
                status
            FROM notes
            WHERE expires_at > ?
            ORDER BY created_at DESC
            """,
            (now,),
        ).fetchall()


def list_expired_notes() -> list[sqlite3.Row]:
    now = datetime.now(UTC).isoformat()

    with get_connection() as connection:
        return connection.execute(
            """
            SELECT
                id,
                audio_path,
                transcript_path,
                summary_path,
                created_at,
                expires_at,
                status
            FROM notes
            WHERE expires_at <= ?
            ORDER BY expires_at ASC
            """,
            (now,),
        ).fetchall()


def delete_note_row(note_id: str) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM notes WHERE id = ?", (note_id,))


def update_note_status(note_id: str, status: str) -> None:
    with get_connection() as connection:
        connection.execute(
            "UPDATE notes SET status = ? WHERE id = ?",
            (status, note_id),
        )


def update_note_transcript(note_id: str, transcript_path: str, status: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE notes
            SET transcript_path = ?, status = ?
            WHERE id = ?
            """,
            (transcript_path, status, note_id),
        )


def update_note_summary(note_id: str, summary_path: str, status: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE notes
            SET summary_path = ?, status = ?
            WHERE id = ?
            """,
            (summary_path, status, note_id),
        )
