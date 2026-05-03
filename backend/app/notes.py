from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from .cleanup import cleanup_expired_notes, delete_note_files
from .config import (
    AUDIO_DIR,
    MAX_AUDIO_UPLOAD_BYTES,
    SUPPORTED_AUDIO_CONTENT_TYPES,
    SUPPORTED_AUDIO_EXTENSIONS,
)
from .database import create_note, delete_note_row, get_note, list_active_notes
from .database import update_note_status, update_note_summary, update_note_transcript
from .summary import generate_summary, save_summary
from .transcription import AudioTooLongError, save_transcript, transcribe_audio

router = APIRouter(prefix="/api/notes", tags=["notes"])


def read_optional_text(path_value: str | None) -> str | None:
    if not path_value:
        return None

    path = Path(path_value)

    if not path.exists():
        return None

    return path.read_text(encoding="utf-8")


def note_row_to_response(note) -> dict[str, str | int | None]:
    audio_path = Path(note["audio_path"])
    bytes_size = audio_path.stat().st_size if audio_path.exists() else 0

    return {
        "id": note["id"],
        "audio_url": f"/api/notes/{note['id']}/audio",
        "bytes": bytes_size,
        "created_at": note["created_at"],
        "expires_at": note["expires_at"],
        "language": "",
        "status": note["status"],
        "summary": read_optional_text(note["summary_path"]),
        "transcript": read_optional_text(note["transcript_path"]),
    }


def note_is_expired(note) -> bool:
    expires_at = datetime.fromisoformat(note["expires_at"])

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    return expires_at <= datetime.now(UTC)


def delete_expired_note_and_raise(note) -> None:
    delete_note_files(note)
    delete_note_row(note["id"])
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="File expired.",
    )


def parse_created_at(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)

    normalized_value = value.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized_value)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="created_at must be a valid ISO timestamp.",
        ) from error

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def validate_audio_file(audio: UploadFile) -> str:
    original_name = audio.filename or ""
    extension = Path(original_name).suffix.lower()

    if extension not in SUPPORTED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported audio format.",
        )

    if audio.content_type and audio.content_type not in SUPPORTED_AUDIO_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported audio format.",
        )

    return extension


async def save_upload(audio: UploadFile, destination: Path) -> int:
    total_bytes = 0
    upload_too_large = False

    with destination.open("wb") as output:
        while chunk := await audio.read(1024 * 1024):
            total_bytes += len(chunk)
            if total_bytes > MAX_AUDIO_UPLOAD_BYTES:
                upload_too_large = True
                break

            output.write(chunk)

    if upload_too_large:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file is too large.",
        )

    if total_bytes == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is empty.",
        )

    return total_bytes


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_note(
    audio: UploadFile = File(...),
    language: str = Form("en"),
    created_at: str | None = Form(None),
) -> dict[str, str | int]:
    extension = validate_audio_file(audio)
    note_id = uuid4().hex
    created_at_datetime = parse_created_at(created_at)
    expires_at_datetime = created_at_datetime + timedelta(hours=24)
    destination = AUDIO_DIR / f"{note_id}{extension}"

    saved_bytes = await save_upload(audio, destination)

    try:
        create_note(
            note_id=note_id,
            audio_path=str(destination),
            created_at=created_at_datetime.isoformat(),
            expires_at=expires_at_datetime.isoformat(),
            status="uploaded",
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    try:
        update_note_status(note_id, "transcribing")
        transcript = transcribe_audio(destination, language)
        transcript_path = save_transcript(note_id, transcript)
        update_note_transcript(note_id, str(transcript_path), "transcribed")
    except AudioTooLongError as error:
        update_note_status(note_id, "failed")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio too long.",
        ) from error
    except Exception as error:
        update_note_status(note_id, "failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcription failed. Please try again.",
        ) from error

    try:
        update_note_status(note_id, "summarizing")
        summary = generate_summary(transcript)
        summary_path = save_summary(note_id, summary)
        update_note_summary(note_id, str(summary_path), "completed")
    except Exception as error:
        update_note_status(note_id, "failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Summary failed. Please try again.",
        ) from error

    return {
        "id": note_id,
        "audio_url": f"/api/notes/{note_id}/audio",
        "bytes": saved_bytes,
        "created_at": created_at_datetime.isoformat(),
        "expires_at": expires_at_datetime.isoformat(),
        "language": language,
        "status": "completed",
        "summary": summary,
        "transcript": transcript,
    }


@router.get("")
def list_notes() -> list[dict[str, str | int | None]]:
    return [note_row_to_response(note) for note in list_active_notes()]


@router.post("/cleanup")
def cleanup_notes() -> dict[str, int]:
    return {"deleted": cleanup_expired_notes()}


@router.get("/{note_id}")
def get_note_detail(note_id: str) -> dict[str, str | int | None]:
    note = get_note(note_id)

    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File expired.",
        )

    if note_is_expired(note):
        delete_expired_note_and_raise(note)

    return note_row_to_response(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: str) -> None:
    note = get_note(note_id)

    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File expired.",
        )

    delete_note_files(note)
    delete_note_row(note_id)


@router.get("/{note_id}/audio")
def get_note_audio(note_id: str) -> FileResponse:
    note = get_note(note_id)

    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File expired.",
        )

    if note_is_expired(note):
        delete_expired_note_and_raise(note)

    audio_path = Path(note["audio_path"])

    if not audio_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File expired.",
        )

    return FileResponse(audio_path)
