import asyncio
import logging
from pathlib import Path

from .database import delete_note_row, list_expired_notes

LOGGER = logging.getLogger("yournoteai.cleanup")
CLEANUP_INTERVAL_SECONDS = 60 * 60


def delete_note_files(note) -> None:
    for key in ("audio_path", "transcript_path", "summary_path"):
        path_value = note[key]

        if path_value:
            Path(path_value).unlink(missing_ok=True)


def cleanup_expired_notes() -> int:
    expired_notes = list_expired_notes()

    for note in expired_notes:
        delete_note_files(note)
        delete_note_row(note["id"])

    if expired_notes:
        LOGGER.info("Deleted %s expired notes.", len(expired_notes))

    return len(expired_notes)


async def run_cleanup_loop() -> None:
    while True:
        try:
            cleanup_expired_notes()
        except Exception:
            LOGGER.exception("Expired note cleanup failed.")

        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
