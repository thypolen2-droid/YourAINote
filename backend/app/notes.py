from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from .cleanup import cleanup_expired_notes, delete_note_files
from .config import (
    AUDIO_DIR,
    MAX_AUDIO_UPLOAD_BYTES,
    PROCESSING_STALE_SECONDS,
    SUPPORTED_AUDIO_CONTENT_TYPES,
    SUPPORTED_AUDIO_EXTENSIONS,
)
from .database import create_note, delete_note_row, get_note, list_active_notes
from .database import (
    update_note_language,
    update_note_status,
    update_note_summary,
    update_note_transcript,
)
from .summary import generate_summary, save_summary
from .transcription import AudioTooLongError, save_transcript, transcribe_audio

router = APIRouter(prefix="/api/notes", tags=["notes"])
PROCESSING_STATUSES = {"uploaded", "transcribing", "transcribed", "summarizing"}
PROCESSING_STALE_AFTER = timedelta(seconds=PROCESSING_STALE_SECONDS)
SUPPORTED_LANGUAGES = {"en", "km"}


def read_optional_text(path_value: str | None) -> str | None:
    if not path_value:
        return None

    path = Path(path_value)

    if not path.exists():
        return None

    return path.read_text(encoding="utf-8")


def note_row_to_response(note) -> dict[str, str | int | bool | None]:
    audio_path = Path(note["audio_path"])
    bytes_size = audio_path.stat().st_size if audio_path.exists() else 0

    return {
        "id": note["id"],
        "audio_url": f"/api/notes/{note['id']}/audio",
        "bytes": bytes_size,
        "created_at": note["created_at"],
        "expires_at": note["expires_at"],
        "is_stale": note_is_stale(note),
        "language": note["language"] or "en",
        "status": note["status"],
        "summary": read_optional_text(note["summary_path"]),
        "transcript": read_optional_text(note["transcript_path"]),
        "updated_at": note["updated_at"] or note["created_at"],
    }


def iso_to_utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def note_is_expired(note) -> bool:
    expires_at = iso_to_utc_datetime(note["expires_at"])

    return expires_at <= datetime.now(UTC)


def note_is_stale(note) -> bool:
    if note["status"] not in PROCESSING_STATUSES:
        return False

    updated_at = iso_to_utc_datetime(note["updated_at"] or note["created_at"])

    return datetime.now(UTC) - updated_at > PROCESSING_STALE_AFTER


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


def normalize_language(language: str) -> str:
    normalized_language = language.strip().lower()

    return normalized_language if normalized_language in SUPPORTED_LANGUAGES else "en"


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


def process_note_audio(note_id: str, audio_path: Path, language: str) -> tuple[str, str]:
    try:
        update_note_status(note_id, "transcribing")
        transcript = transcribe_audio(audio_path, language)
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
        summary = generate_summary(transcript, language)
        summary_path = save_summary(note_id, summary)
        update_note_summary(note_id, str(summary_path), "completed")
    except Exception as error:
        update_note_status(note_id, "failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Summary failed. Please try again.",
        ) from error

    return transcript, summary


def process_note_audio_task(note_id: str, audio_path: Path, language: str) -> None:
    try:
        process_note_audio(note_id, audio_path, language)
    except HTTPException:
        pass


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_note(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    language: str = Form("en"),
    created_at: str | None = Form(None),
) -> dict[str, str | int | bool | None]:
    extension = validate_audio_file(audio)
    note_id = uuid4().hex
    normalized_language = normalize_language(language)
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
            language=normalized_language,
            status="uploaded",
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    background_tasks.add_task(
        process_note_audio_task,
        note_id,
        destination,
        normalized_language,
    )
    queued_note = get_note(note_id)

    if queued_note is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload queued, but note could not be loaded.",
        )

    response = note_row_to_response(queued_note)
    response["bytes"] = saved_bytes

    return response


@router.get("")
def list_notes() -> list[dict[str, str | int | bool | None]]:
    return [note_row_to_response(note) for note in list_active_notes()]


@router.post("/{note_id}/retry")
def retry_note(
    note_id: str,
    background_tasks: BackgroundTasks,
    language: str = Form("en"),
) -> dict[str, str | int | bool | None]:
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
        update_note_status(note_id, "failed")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File expired.",
        )

    normalized_language = normalize_language(language)
    update_note_language(note_id, normalized_language)
    update_note_status(note_id, "uploaded")
    background_tasks.add_task(
        process_note_audio_task,
        note_id,
        audio_path,
        normalized_language,
    )
    updated_note = get_note(note_id)

    if updated_note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File expired.",
        )

    return note_row_to_response(updated_note)


@router.post("/cleanup")
def cleanup_notes() -> dict[str, int]:
    return {"deleted": cleanup_expired_notes()}


@router.get("/{note_id}")
def get_note_detail(note_id: str) -> dict[str, str | int | bool | None]:
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
