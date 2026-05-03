from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.config import AUDIO_DIR, SUMMARIES_DIR, TRANSCRIPTS_DIR
from app.database import create_note, get_connection, update_note_status, update_note_summary, update_note_transcript
from app.main import app


TEST_IDS = (
    "qa_active_note",
    "qa_expired_note",
    "qa_failed_note",
    "qa_delete_note",
)


def remove_note(note_id: str) -> None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT audio_path, transcript_path, summary_path FROM notes WHERE id = ?",
            (note_id,),
        ).fetchone()

        if row:
            for key in row.keys():
                if row[key]:
                    Path(row[key]).unlink(missing_ok=True)

        connection.execute("DELETE FROM notes WHERE id = ?", (note_id,))


def seed_note(note_id: str, *, expired: bool = False, status: str = "completed") -> None:
    now = datetime.now(UTC)
    audio_path = AUDIO_DIR / f"{note_id}.m4a"
    transcript_path = TRANSCRIPTS_DIR / f"{note_id}.txt"
    summary_path = SUMMARIES_DIR / f"{note_id}.txt"

    audio_path.write_bytes(b"audio")
    transcript_path.write_text(f"{note_id} transcript", encoding="utf-8")
    summary_path.write_text(f"{note_id} summary", encoding="utf-8")
    create_note(
        note_id=note_id,
        audio_path=str(audio_path),
        created_at=(now - timedelta(hours=25) if expired else now).isoformat(),
        expires_at=(now - timedelta(hours=1) if expired else now + timedelta(hours=1)).isoformat(),
        status=status,
    )
    update_note_transcript(note_id, str(transcript_path), status)
    update_note_summary(note_id, str(summary_path), status)
    update_note_status(note_id, status)


def main() -> None:
    for note_id in TEST_IDS:
        remove_note(note_id)

    seed_note("qa_active_note")
    seed_note("qa_failed_note", status="failed")
    seed_note("qa_delete_note")

    with TestClient(app) as client:
        seed_note("qa_expired_note", expired=True)

        dashboard = client.get("/")
        assert dashboard.status_code == 200, dashboard.text
        assert "YourNoteAI Backend" in dashboard.text
        assert "/api/admin/overview" in dashboard.text

        overview = client.get("/api/admin/overview")
        assert overview.status_code == 200, overview.text
        overview_body = overview.json()
        for key in ("status", "online_users", "notes", "storage", "services", "cleanup", "updated_at"):
            assert key in overview_body
        assert overview_body["notes"]["active"] >= 3
        assert overview_body["notes"]["completed"] >= 2
        assert overview_body["notes"]["failed"] >= 1
        assert overview_body["notes"]["expired"] >= 1
        assert overview_body["storage"]["breakdown"]["audio"] >= 4
        assert overview_body["storage"]["breakdown"]["transcripts"] >= len("qa_active_note transcript")
        assert overview_body["storage"]["breakdown"]["summaries"] >= len("qa_active_note summary")

        health = client.get("/api/health")
        assert health.status_code == 200, health.text
        assert health.json() == {"status": "ok"}

        notes = client.get("/api/notes")
        assert notes.status_code == 200, notes.text
        note_ids = {note["id"] for note in notes.json()}
        assert "qa_active_note" in note_ids
        assert "qa_expired_note" not in note_ids

        detail = client.get("/api/notes/qa_active_note")
        assert detail.status_code == 200, detail.text
        detail_body = detail.json()
        assert detail_body["transcript"] == "qa_active_note transcript"
        assert detail_body["summary"] == "qa_active_note summary"

        audio = client.get("/api/notes/qa_active_note/audio")
        assert audio.status_code == 200, audio.text
        assert audio.content == b"audio"

        expired = client.get("/api/notes/qa_expired_note")
        assert expired.status_code in (404, 410), expired.text
        assert expired.json()["detail"] == "File expired."

        invalid = client.post(
            "/api/notes/upload",
            files={"audio": ("bad.txt", b"bad", "text/plain")},
            data={"language": "en"},
        )
        assert invalid.status_code == 400, invalid.text
        assert invalid.json()["detail"] == "Unsupported audio format."

        delete_response = client.delete("/api/notes/qa_delete_note")
        assert delete_response.status_code == 204, delete_response.text

        cleanup = client.post("/api/notes/cleanup")
        assert cleanup.status_code == 200, cleanup.text
        assert "deleted" in cleanup.json()

    for note_id in TEST_IDS:
        remove_note(note_id)

    print("backend QA passed")


if __name__ == "__main__":
    main()
