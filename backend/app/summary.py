from pathlib import Path

import httpx

from .config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS, SUMMARIES_DIR


class SummaryError(RuntimeError):
    """Raised when Ollama cannot generate a summary."""


LANGUAGE_INSTRUCTIONS = {
    "en": "Respond in English.",
    "km": "Respond in Khmer.",
}


NO_SPEECH_MESSAGES = {
    "en": "No clear speech was detected, so there is no transcript to summarize.",
    "km": "រកមិនឃើញសំឡេងនិយាយច្បាស់ទេ ដូច្នេះមិនមានអត្ថបទសម្រាប់សង្ខេបទេ។",
}


def normalize_summary_language(language: str) -> str:
    return language if language in LANGUAGE_INSTRUCTIONS else "en"


def build_summary_prompt(transcript: str, language: str) -> str:
    normalized_language = normalize_summary_language(language)

    return f"""Summarize this voice note clearly.
Keep it short, useful, and easy to understand.
{LANGUAGE_INSTRUCTIONS[normalized_language]}
Return:
1. Short Summary
2. Key Points
3. Action Items if any

Text:
{transcript}
"""


def generate_summary(transcript: str, language: str = "en") -> str:
    normalized_language = normalize_summary_language(language)

    if not transcript.strip():
        return NO_SPEECH_MESSAGES[normalized_language]

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": build_summary_prompt(transcript, normalized_language),
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
