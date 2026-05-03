from functools import lru_cache
from pathlib import Path

from .config import (
    MAX_AUDIO_DURATION_SECONDS,
    TRANSCRIPTS_DIR,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL_SIZE,
)

LANGUAGE_MAP = {
    "en": "en",
    "km": "km",
}


class AudioTooLongError(RuntimeError):
    """Raised when an uploaded recording is longer than the MVP limit."""


@lru_cache(maxsize=1)
def get_whisper_model():
    from faster_whisper import WhisperModel

    return WhisperModel(
        WHISPER_MODEL_SIZE,
        compute_type=WHISPER_COMPUTE_TYPE,
        device=WHISPER_DEVICE,
    )


def transcribe_audio(audio_path: Path, language: str) -> str:
    model = get_whisper_model()
    whisper_language = LANGUAGE_MAP.get(language)
    segments, info = model.transcribe(
        str(audio_path),
        beam_size=5,
        language=whisper_language,
        vad_filter=True,
    )

    if info.duration and info.duration > MAX_AUDIO_DURATION_SECONDS:
        raise AudioTooLongError("Audio too long.")

    transcript_parts = [segment.text.strip() for segment in segments if segment.text.strip()]

    return "\n".join(transcript_parts).strip()


def save_transcript(note_id: str, transcript: str) -> Path:
    destination = TRANSCRIPTS_DIR / f"{note_id}.txt"
    destination.write_text(transcript, encoding="utf-8")

    return destination
