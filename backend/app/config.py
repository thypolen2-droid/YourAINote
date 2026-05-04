from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "yournoteai.db"
STORAGE_DIR = BASE_DIR / "storage"
AUDIO_DIR = STORAGE_DIR / "audio"
TRANSCRIPTS_DIR = STORAGE_DIR / "transcripts"
SUMMARIES_DIR = STORAGE_DIR / "summaries"
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "1"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
MAX_AUDIO_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_AUDIO_DURATION_SECONDS = 30 * 60
PROCESSING_STALE_SECONDS = int(os.getenv("PROCESSING_STALE_SECONDS", "900"))
SUPPORTED_AUDIO_EXTENSIONS = {
    ".aac",
    ".caf",
    ".m4a",
    ".mp3",
    ".mp4",
    ".wav",
    ".webm",
}
SUPPORTED_AUDIO_CONTENT_TYPES = {
    "application/octet-stream",
    "audio/aac",
    "audio/caf",
    "audio/x-caf",
    "audio/m4a",
    "audio/mp3",
    "audio/mp4",
    "audio/mpeg",
    "audio/x-m4a",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/wave",
    "video/mp4",
}

STORAGE_DIRECTORIES = (
    AUDIO_DIR,
    TRANSCRIPTS_DIR,
    SUMMARIES_DIR,
)
