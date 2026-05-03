from pathlib import Path

import httpx

from .config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS, SUMMARIES_DIR


class SummaryError(RuntimeError):
    """Raised when Ollama cannot generate a summary."""


def build_summary_prompt(transcript: str) -> str:
    return f"""Summarize this voice note clearly.
Keep it short, useful, and easy to understand.
Return:
1. Short Summary
2. Key Points
3. Action Items if any

Text:
{transcript}
"""


def generate_summary(transcript: str) -> str:
    if not transcript.strip():
        return "No clear speech was detected, so there is no transcript to summarize."

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": build_summary_prompt(transcript),
        "stream": False,
    }

    try:
        with httpx.Client(base_url=OLLAMA_BASE_URL, timeout=OLLAMA_TIMEOUT_SECONDS) as client:
            response = client.post("/api/generate", json=payload)
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise SummaryError("Ollama summary failed.") from error

    data = response.json()
    summary = str(data.get("response", "")).strip()

    if not summary:
        raise SummaryError("Ollama returned an empty summary.")

    return summary


def save_summary(note_id: str, summary: str) -> Path:
    destination = SUMMARIES_DIR / f"{note_id}.txt"
    destination.write_text(summary, encoding="utf-8")

    return destination
