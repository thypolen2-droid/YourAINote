from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import HTMLResponse

from .cleanup import CLEANUP_INTERVAL_SECONDS
from .config import (
    AUDIO_DIR,
    DATABASE_PATH,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    STORAGE_DIRECTORIES,
    SUMMARIES_DIR,
    TRANSCRIPTS_DIR,
    WHISPER_BEAM_SIZE,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL_SIZE,
)
from .database import get_note, list_active_notes, list_expired_notes, update_note_status
from .notes import note_is_expired, note_is_stale, process_note_audio_task
from .presence import get_online_count

router = APIRouter(prefix="/api/admin", tags=["admin"])

EXPIRING_SOON_WINDOW = timedelta(hours=2)
RECENT_NOTE_LIMIT = 20


def _directory_size(directory: Path) -> int:
    if not directory.exists():
        return 0

    total = 0
    for path in directory.rglob("*"):
        if path.is_file():
            total += path.stat().st_size

    return total


def _file_size(path_value: str | None) -> int:
    if not path_value:
        return 0

    path = Path(path_value)
    return path.stat().st_size if path.exists() else 0


def _iso_to_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def _note_to_admin_row(note) -> dict[str, Any]:
    audio_bytes = _file_size(note["audio_path"])
    transcript_bytes = _file_size(note["transcript_path"])
    summary_bytes = _file_size(note["summary_path"])

    return {
        "id": note["id"],
        "status": note["status"],
        "created_at": note["created_at"],
        "expires_at": note["expires_at"],
        "bytes": audio_bytes,
        "has_audio": audio_bytes > 0,
        "has_transcript": transcript_bytes > 0,
        "has_summary": summary_bytes > 0,
    }


def _step_status(
    *,
    status: str,
    has_artifact: bool,
    active_status: str,
    completed_statuses: set[str],
    failed_after_previous_step: bool = False,
) -> str:
    if has_artifact or status in completed_statuses:
        return "complete"
    if status == active_status:
        return "active"
    if status == "failed" and failed_after_previous_step:
        return "failed"
    return "pending"


def _note_to_job_row(note) -> dict[str, Any]:
    audio_bytes = _file_size(note["audio_path"])
    transcript_bytes = _file_size(note["transcript_path"])
    summary_bytes = _file_size(note["summary_path"])
    status = str(note["status"])
    has_audio = audio_bytes > 0
    has_transcript = transcript_bytes > 0
    has_summary = summary_bytes > 0
    is_stale = note_is_stale(note)
    status_progress = {
        "uploaded": 25,
        "transcribing": 45,
        "transcribed": 65,
        "summarizing": 85,
        "completed": 100,
        "failed": 100 if has_summary else 75 if has_transcript else 45 if has_audio else 0,
    }

    return {
        "id": note["id"],
        "status": status,
        "is_stale": is_stale,
        "created_at": note["created_at"],
        "expires_at": note["expires_at"],
        "bytes": audio_bytes,
        "progress": status_progress.get(status, 0),
        "steps": [
            {
                "key": "voice",
                "label": "Voice uploaded",
                "status": "complete" if has_audio else "pending",
                "bytes": audio_bytes,
            },
            {
                "key": "transcript",
                "label": "Voice to text",
                "status": _step_status(
                    status=status,
                    has_artifact=has_transcript,
                    active_status="transcribing",
                    completed_statuses={"transcribed", "summarizing", "completed"},
                    failed_after_previous_step=has_audio and not has_transcript,
                ),
                "bytes": transcript_bytes,
            },
            {
                "key": "summary",
                "label": "Text to summary",
                "status": _step_status(
                    status=status,
                    has_artifact=has_summary,
                    active_status="summarizing",
                    completed_statuses={"completed"},
                    failed_after_previous_step=has_transcript and not has_summary,
                ),
                "bytes": summary_bytes,
            },
        ],
    }


def _service_status(name: str, status: str, detail: str, meta: dict[str, Any] | None = None):
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "meta": meta or {},
    }


def _ollama_service_status() -> dict[str, Any]:
    try:
        with httpx.Client(base_url=OLLAMA_BASE_URL, timeout=2.0) as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
    except httpx.HTTPError as error:
        return _service_status(
            "Ollama",
            "warning",
            "Not reachable from the backend.",
            {
                "base_url": OLLAMA_BASE_URL,
                "model": OLLAMA_MODEL,
                "error": error.__class__.__name__,
            },
        )

    model_names = {str(model.get("name", "")) for model in models if isinstance(model, dict)}
    model_names.update(str(model.get("model", "")) for model in models if isinstance(model, dict))
    if OLLAMA_MODEL not in model_names:
        return _service_status(
            "Ollama",
            "warning",
            "Reachable, but the configured model is not installed.",
            {
                "base_url": OLLAMA_BASE_URL,
                "model": OLLAMA_MODEL,
                "installed_models": sorted(name for name in model_names if name),
            },
        )

    return _service_status(
        "Ollama",
        "ok",
        "Reachable and ready for summaries.",
        {
            "base_url": OLLAMA_BASE_URL,
            "model": OLLAMA_MODEL,
        },
    )


def build_overview() -> dict[str, Any]:
    now = datetime.now(UTC)
    active_notes = list_active_notes()
    expired_notes = list_expired_notes()
    status_counts: dict[str, int] = {}

    for note in active_notes:
        status = str(note["status"])
        status_counts[status] = status_counts.get(status, 0) + 1

    completed_count = status_counts.get("completed", 0)
    failed_count = status_counts.get("failed", 0)
    in_progress_statuses = {"uploaded", "transcribing", "transcribed", "summarizing"}
    in_progress_count = sum(status_counts.get(status, 0) for status in in_progress_statuses)
    expiring_soon_count = sum(
        1
        for note in active_notes
        if _iso_to_datetime(note["expires_at"]) <= now + EXPIRING_SOON_WINDOW
    )

    storage_breakdown = {
        "audio": _directory_size(AUDIO_DIR),
        "transcripts": _directory_size(TRANSCRIPTS_DIR),
        "summaries": _directory_size(SUMMARIES_DIR),
        "database": DATABASE_PATH.stat().st_size if DATABASE_PATH.exists() else 0,
    }
    storage_total = sum(storage_breakdown.values())
    missing_storage_directories = [
        str(directory) for directory in STORAGE_DIRECTORIES if not directory.exists()
    ]

    sqlite_status = "ok" if DATABASE_PATH.exists() else "warning"
    storage_status = "ok" if not missing_storage_directories else "warning"

    return {
        "status": "ok",
        "online_users": get_online_count(),
        "updated_at": now.isoformat(),
        "notes": {
            "active": len(active_notes),
            "completed": completed_count,
            "failed": failed_count,
            "in_progress": in_progress_count,
            "expired": len(expired_notes),
            "expiring_soon": expiring_soon_count,
            "status_counts": status_counts,
            "recent": [_note_to_admin_row(note) for note in active_notes[:RECENT_NOTE_LIMIT]],
        },
        "storage": {
            "total_bytes": storage_total,
            "breakdown": storage_breakdown,
            "missing_directories": missing_storage_directories,
        },
        "services": [
            _service_status("FastAPI", "ok", "Backend process is responding."),
            _service_status(
                "SQLite",
                sqlite_status,
                "Database file is available." if DATABASE_PATH.exists() else "Database file is missing.",
                {"path": str(DATABASE_PATH), "bytes": storage_breakdown["database"]},
            ),
            _service_status(
                "Storage",
                storage_status,
                "Storage directories are ready."
                if storage_status == "ok"
                else "One or more storage directories are missing.",
                {
                    "audio_dir": str(AUDIO_DIR),
                    "transcripts_dir": str(TRANSCRIPTS_DIR),
                    "summaries_dir": str(SUMMARIES_DIR),
                },
            ),
            _service_status(
                "Whisper",
                "ok",
                "Configured for transcription. Model is loaded on first upload.",
                {
                    "model_size": WHISPER_MODEL_SIZE,
                    "device": WHISPER_DEVICE,
                    "compute_type": WHISPER_COMPUTE_TYPE,
                    "beam_size": WHISPER_BEAM_SIZE,
                },
            ),
            _ollama_service_status(),
            _service_status(
                "Cleanup",
                "ok",
                "Expired notes are cleaned by the background loop.",
                {
                    "interval_seconds": CLEANUP_INTERVAL_SECONDS,
                    "expired_notes": len(expired_notes),
                },
            ),
        ],
        "cleanup": {
            "interval_seconds": CLEANUP_INTERVAL_SECONDS,
            "expired_notes": len(expired_notes),
        },
    }


@router.get("/overview")
def admin_overview() -> dict[str, Any]:
    return build_overview()


@router.get("/jobs")
def admin_jobs() -> dict[str, Any]:
    now = datetime.now(UTC)
    active_notes = list_active_notes()
    status_counts: dict[str, int] = {}

    for note in active_notes:
        status = str(note["status"])
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "status": "ok",
        "updated_at": now.isoformat(),
        "jobs": [_note_to_job_row(note) for note in active_notes],
        "status_counts": status_counts,
    }


@router.post("/jobs/{note_id}/retry")
def admin_retry_job(note_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    note = get_note(note_id)

    if note is None or note_is_expired(note):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File expired.",
        )

    audio_path = Path(note["audio_path"])
    if not audio_path.exists():
        update_note_status(note_id, "failed")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file is missing.",
        )

    update_note_status(note_id, "uploaded")
    background_tasks.add_task(process_note_audio_task, note_id, audio_path, note["language"] or "en")
    refreshed_note = get_note(note_id)

    return {
        "status": "queued",
        "job": _note_to_job_row(refreshed_note or note),
    }


def job_progress_html() -> HTMLResponse:
    return HTMLResponse(
        """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>YourNoteAI Job Progress</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f5f7fb;
        --surface: #ffffff;
        --text: #111827;
        --muted: #667085;
        --line: #dfe4ea;
        --blue: #1d6ef2;
        --green: #0f9f6e;
        --amber: #b7791f;
        --red: #d92d20;
        --soft-blue: #eaf2ff;
        --soft-green: #e7f7ef;
        --soft-amber: #fff4dc;
        --soft-red: #fdecec;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }

      * { box-sizing: border-box; }
      body { background: var(--bg); color: var(--text); margin: 0; }
      .main { margin: 0 auto; max-width: 1180px; padding: 24px; }
      .topbar { align-items: center; display: flex; gap: 16px; justify-content: space-between; margin-bottom: 18px; }
      h1 { font-size: 28px; line-height: 34px; margin: 0; }
      .subtitle { color: var(--muted); font-size: 14px; font-weight: 650; margin-top: 4px; }
      .actions { align-items: center; display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }
      .button {
        align-items: center; background: var(--blue); border: 0; border-radius: 8px; color: #fff; cursor: pointer;
        display: inline-flex; font: inherit; font-size: 14px; font-weight: 800; min-height: 38px; padding: 9px 13px; text-decoration: none;
      }
      .button.secondary { background: var(--surface); border: 1px solid var(--line); color: var(--text); }
      .button:disabled { cursor: wait; opacity: 0.62; }
      .time-pill { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; font-size: 14px; font-weight: 750; min-height: 38px; padding: 9px 12px; }
      .summary { display: grid; gap: 12px; grid-template-columns: repeat(6, minmax(0, 1fr)); margin-bottom: 16px; }
      .metric { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
      .metric-label { color: var(--muted); font-size: 11px; font-weight: 900; text-transform: uppercase; }
      .metric-value { font-size: 24px; font-weight: 900; margin-top: 8px; }
      .jobs { display: grid; gap: 12px; }
      .job { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
      .job-head { align-items: center; border-bottom: 1px solid var(--line); display: flex; gap: 12px; justify-content: space-between; padding: 14px 16px; }
      .job-title { font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; font-size: 13px; font-weight: 850; }
      .job-meta { color: var(--muted); font-size: 12px; font-weight: 700; margin-top: 4px; }
      .badge { border-radius: 999px; display: inline-flex; font-size: 12px; font-weight: 850; padding: 4px 9px; white-space: nowrap; }
      .badge.complete { background: var(--soft-green); color: var(--green); }
      .badge.active { background: var(--soft-blue); color: var(--blue); }
      .badge.pending { background: #eef2f6; color: var(--muted); }
      .badge.failed { background: var(--soft-red); color: var(--red); }
      .badge.stuck { background: var(--soft-amber); color: var(--amber); }
      .job-body { padding: 16px; }
      .track { background: #edf1f6; border-radius: 999px; height: 10px; overflow: hidden; }
      .fill { background: var(--blue); border-radius: inherit; height: 100%; min-width: 3px; transition: width 200ms ease; }
      .steps { display: grid; gap: 10px; grid-template-columns: repeat(3, minmax(0, 1fr)); margin-top: 14px; }
      .step { border: 1px solid var(--line); border-radius: 8px; padding: 12px; }
      .step-top { align-items: center; display: flex; gap: 8px; justify-content: space-between; }
      .step-label { font-size: 14px; font-weight: 900; }
      .step-bytes { color: var(--muted); font-size: 12px; font-weight: 700; margin-top: 7px; }
      .empty { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; color: var(--muted); font-weight: 750; padding: 28px; text-align: center; }
      .message { color: var(--muted); font-size: 13px; font-weight: 700; min-height: 18px; }

      @media (max-width: 860px) {
        .topbar { align-items: flex-start; flex-direction: column; }
        .actions { justify-content: flex-start; }
        .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .steps { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body>
    <main class="main">
      <header class="topbar">
        <div>
          <h1>Job Progress</h1>
          <div class="subtitle">Live backend view of voice upload, transcription, and summary generation.</div>
        </div>
        <div class="actions">
          <div class="time-pill">Updated <strong id="updated">-</strong></div>
          <button id="refresh" class="button" type="button">Refresh</button>
          <a class="button secondary" href="/">Dashboard</a>
        </div>
      </header>

      <section id="summary" class="summary"></section>
      <div id="message" class="message"></div>
      <section id="jobs" class="jobs"></section>
    </main>

    <script>
      const updated = document.getElementById('updated');
      const refreshButton = document.getElementById('refresh');
      const summary = document.getElementById('summary');
      const jobs = document.getElementById('jobs');
      const message = document.getElementById('message');
      const statuses = ['uploaded', 'transcribing', 'transcribed', 'summarizing', 'completed', 'failed'];

      function formatBytes(bytes) {
        if (!bytes) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB'];
        let value = bytes;
        let index = 0;
        while (value >= 1024 && index < units.length - 1) {
          value = value / 1024;
          index += 1;
        }
        return `${value >= 10 || index === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
      }

      function formatDate(value) {
        return new Date(value).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
      }

      function renderSummary(counts) {
        summary.innerHTML = statuses.map((status) => `
          <article class="metric">
            <div class="metric-label">${status}</div>
            <div class="metric-value">${counts[status] || 0}</div>
          </article>
        `).join('');
      }

      function renderJobs(rows) {
        if (!rows.length) {
          jobs.innerHTML = '<div class="empty">No active processing jobs yet.</div>';
          return;
        }

        jobs.innerHTML = rows.map((job) => `
          <article class="job">
            <div class="job-head">
              <div>
                <div class="job-title">${job.id}</div>
                <div class="job-meta">Created ${formatDate(job.created_at)} · expires ${formatDate(job.expires_at)} · ${formatBytes(job.bytes)}</div>
              </div>
              <span class="badge ${job.is_stale ? 'stuck' : job.status === 'failed' ? 'failed' : job.status === 'completed' ? 'complete' : 'active'}">${job.is_stale ? 'stuck' : job.status}</span>
            </div>
            <div class="job-body">
              <div class="track"><div class="fill" style="width: ${job.progress}%"></div></div>
              <div class="steps">
                ${job.steps.map((step) => `
                  <div class="step">
                    <div class="step-top">
                      <div class="step-label">${step.label}</div>
                      <span class="badge ${step.status}">${step.status}</span>
                    </div>
                    <div class="step-bytes">${formatBytes(step.bytes)}</div>
                  </div>
                `).join('')}
              </div>
              ${job.status === 'completed' ? '' : `<button class="button secondary" type="button" data-retry-job="${job.id}" style="margin-top: 14px;">Retry</button>`}
            </div>
          </article>
        `).join('');
      }

      async function refresh() {
        refreshButton.disabled = true;
        message.textContent = '';
        try {
          const response = await fetch('/api/admin/jobs', { cache: 'no-store' });
          if (!response.ok) throw new Error('Could not load job progress.');
          const data = await response.json();
          updated.textContent = new Date(data.updated_at).toLocaleTimeString();
          renderSummary(data.status_counts || {});
          renderJobs(data.jobs || []);
        } catch (error) {
          message.textContent = error.message || 'Could not load job progress.';
        } finally {
          refreshButton.disabled = false;
        }
      }

      async function retryJob(noteId) {
        message.textContent = `Retrying ${noteId.slice(0, 10)}...`;
        try {
          const response = await fetch(`/api/admin/jobs/${noteId}/retry`, { method: 'POST' });
          if (!response.ok) throw new Error('Could not retry job.');
          message.textContent = 'Job queued again.';
          await refresh();
        } catch (error) {
          message.textContent = error.message || 'Could not retry job.';
        }
      }

      refreshButton.addEventListener('click', refresh);
      jobs.addEventListener('click', (event) => {
        const button = event.target.closest('[data-retry-job]');
        if (button) retryJob(button.dataset.retryJob);
      });
      refresh();
      setInterval(refresh, 3000);
    </script>
  </body>
</html>
        """.strip()
    )


def dashboard_html() -> HTMLResponse:
    return HTMLResponse(
        """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>YourNoteAI Backend</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f5f7fb;
        --surface: #ffffff;
        --surface-soft: #f8fafc;
        --text: #111827;
        --muted: #667085;
        --line: #dfe4ea;
        --blue: #1d6ef2;
        --blue-soft: #eaf2ff;
        --green: #0f9f6e;
        --green-soft: #e7f7ef;
        --amber: #b7791f;
        --amber-soft: #fff4dc;
        --red: #d92d20;
        --red-soft: #fdecec;
        --shadow: 0 16px 45px rgba(17, 24, 39, 0.08);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }

      * {
        box-sizing: border-box;
      }

      body {
        background: var(--bg);
        color: var(--text);
        margin: 0;
      }

      button {
        font: inherit;
      }

      .shell {
        display: grid;
        grid-template-columns: 248px minmax(0, 1fr);
        min-height: 100vh;
      }

      .rail {
        background: #101828;
        color: #f9fafb;
        display: flex;
        flex-direction: column;
        gap: 28px;
        padding: 24px 18px;
      }

      .brand {
        display: flex;
        gap: 12px;
        align-items: center;
        padding: 4px 6px;
      }

      .brand-mark {
        align-items: center;
        background: #ffffff;
        border-radius: 8px;
        color: var(--blue);
        display: grid;
        font-size: 18px;
        font-weight: 900;
        height: 38px;
        place-items: center;
        width: 38px;
      }

      .brand-title {
        font-size: 16px;
        font-weight: 800;
        line-height: 20px;
      }

      .brand-subtitle {
        color: #98a2b3;
        font-size: 12px;
        font-weight: 700;
        line-height: 16px;
      }

      .nav {
        display: grid;
        gap: 6px;
      }

      .nav a {
        align-items: center;
        border-radius: 8px;
        color: #d0d5dd;
        display: flex;
        font-size: 14px;
        font-weight: 700;
        gap: 10px;
        padding: 11px 12px;
        text-decoration: none;
      }

      .nav a.active,
      .nav a:hover {
        background: #1d2939;
        color: #ffffff;
      }

      .rail-footer {
        border-top: 1px solid #344054;
        color: #98a2b3;
        font-size: 12px;
        line-height: 18px;
        margin-top: auto;
        padding: 16px 8px 0;
      }

      .main {
        min-width: 0;
        padding: 24px;
      }

      .topbar {
        align-items: center;
        display: flex;
        gap: 16px;
        justify-content: space-between;
        margin-bottom: 20px;
      }

      .page-title {
        margin: 0;
        font-size: 28px;
        letter-spacing: 0;
        line-height: 34px;
      }

      .page-subtitle {
        color: var(--muted);
        font-size: 14px;
        font-weight: 600;
        margin: 4px 0 0;
      }

      .toolbar {
        align-items: center;
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        justify-content: flex-end;
      }

      .status-pill,
      .time-pill {
        align-items: center;
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        display: flex;
        gap: 8px;
        min-height: 38px;
        padding: 8px 12px;
        white-space: nowrap;
      }

      .status-dot {
        background: var(--muted);
        border-radius: 999px;
        height: 9px;
        width: 9px;
      }

      .status-dot.ok {
        background: var(--green);
      }

      .status-dot.warning {
        background: var(--amber);
      }

      .status-dot.error {
        background: var(--red);
      }

      .button {
        align-items: center;
        background: var(--blue);
        border: 0;
        border-radius: 8px;
        color: #ffffff;
        cursor: pointer;
        display: inline-flex;
        font-size: 14px;
        font-weight: 800;
        gap: 8px;
        min-height: 38px;
        padding: 9px 13px;
      }

      .button.secondary {
        background: var(--surface);
        border: 1px solid var(--line);
        color: var(--text);
      }

      .button.danger {
        background: var(--red-soft);
        color: var(--red);
      }

      .button:disabled {
        cursor: wait;
        opacity: 0.64;
      }

      .grid {
        display: grid;
        gap: 16px;
      }

      .kpis {
        grid-template-columns: repeat(5, minmax(0, 1fr));
      }

      .content-grid {
        grid-template-columns: minmax(0, 1.4fr) minmax(340px, 0.6fr);
        margin-top: 16px;
      }

      .panel,
      .kpi {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: var(--shadow);
      }

      .kpi {
        min-height: 116px;
        padding: 16px;
      }

      .kpi-label {
        color: var(--muted);
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0;
        text-transform: uppercase;
      }

      .kpi-value {
        font-size: 30px;
        font-weight: 900;
        line-height: 36px;
        margin-top: 12px;
      }

      .kpi-foot {
        color: var(--muted);
        font-size: 13px;
        font-weight: 650;
        margin-top: 6px;
      }

      .panel {
        overflow: hidden;
      }

      .panel-header {
        align-items: center;
        border-bottom: 1px solid var(--line);
        display: flex;
        gap: 10px;
        justify-content: space-between;
        padding: 16px 18px;
      }

      .panel-title {
        font-size: 16px;
        font-weight: 900;
        margin: 0;
      }

      .panel-subtitle {
        color: var(--muted);
        font-size: 13px;
        font-weight: 650;
        margin-top: 3px;
      }

      .panel-body {
        padding: 18px;
      }

      .table-wrap {
        overflow-x: auto;
      }

      table {
        border-collapse: collapse;
        min-width: 760px;
        width: 100%;
      }

      th,
      td {
        border-bottom: 1px solid var(--line);
        font-size: 13px;
        padding: 12px 10px;
        text-align: left;
        vertical-align: middle;
        white-space: nowrap;
      }

      th {
        color: var(--muted);
        font-size: 11px;
        font-weight: 900;
        text-transform: uppercase;
      }

      td {
        font-weight: 650;
      }

      tr:last-child td {
        border-bottom: 0;
      }

      .mono {
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      }

      .badge {
        border-radius: 999px;
        display: inline-flex;
        font-size: 12px;
        font-weight: 850;
        padding: 4px 9px;
      }

      .badge.ok {
        background: var(--green-soft);
        color: var(--green);
      }

      .badge.warning {
        background: var(--amber-soft);
        color: var(--amber);
      }

      .badge.error {
        background: var(--red-soft);
        color: var(--red);
      }

      .badge.neutral {
        background: var(--blue-soft);
        color: var(--blue);
      }

      .stack {
        display: grid;
        gap: 12px;
      }

      .service {
        align-items: flex-start;
        border: 1px solid var(--line);
        border-radius: 8px;
        display: flex;
        gap: 12px;
        padding: 13px;
      }

      .service-icon {
        align-items: center;
        background: var(--blue-soft);
        border-radius: 8px;
        color: var(--blue);
        display: grid;
        flex: 0 0 auto;
        font-weight: 900;
        height: 34px;
        place-items: center;
        width: 34px;
      }

      .service-main {
        min-width: 0;
        flex: 1;
      }

      .service-head {
        align-items: center;
        display: flex;
        gap: 8px;
        justify-content: space-between;
      }

      .service-name {
        font-size: 14px;
        font-weight: 900;
      }

      .service-detail,
      .meta-list {
        color: var(--muted);
        font-size: 12px;
        font-weight: 650;
        line-height: 18px;
        margin-top: 4px;
      }

      .bars {
        display: grid;
        gap: 14px;
      }

      .bar-row {
        display: grid;
        gap: 7px;
      }

      .bar-head {
        align-items: center;
        display: flex;
        color: var(--muted);
        font-size: 13px;
        font-weight: 750;
        justify-content: space-between;
      }

      .bar-track {
        background: #edf1f6;
        border-radius: 999px;
        height: 9px;
        overflow: hidden;
      }

      .bar-fill {
        background: var(--blue);
        border-radius: inherit;
        height: 100%;
        min-width: 3px;
      }

      .action-row {
        align-items: center;
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        justify-content: space-between;
      }

      .message {
        color: var(--muted);
        font-size: 13px;
        font-weight: 700;
        margin-top: 12px;
      }

      .empty {
        color: var(--muted);
        font-size: 14px;
        font-weight: 700;
        padding: 22px;
        text-align: center;
      }

      @media (max-width: 1120px) {
        .shell {
          grid-template-columns: 1fr;
        }

        .rail {
          display: none;
        }

        .kpis,
        .content-grid {
          grid-template-columns: 1fr 1fr;
        }

        .content-grid > .panel:first-child {
          grid-column: 1 / -1;
        }
      }

      @media (max-width: 760px) {
        .main {
          padding: 16px;
        }

        .topbar {
          align-items: flex-start;
          flex-direction: column;
        }

        .toolbar {
          justify-content: flex-start;
          width: 100%;
        }

        .kpis,
        .content-grid {
          grid-template-columns: 1fr;
        }

        .page-title {
          font-size: 24px;
          line-height: 30px;
        }
      }
    </style>
  </head>
  <body>
    <div class="shell">
      <aside class="rail">
        <div class="brand">
          <div class="brand-mark">Y</div>
          <div>
            <div class="brand-title">YourNoteAI</div>
            <div class="brand-subtitle">Backend Ops</div>
          </div>
        </div>
        <nav class="nav" aria-label="Dashboard sections">
          <a class="active" href="#overview">Overview</a>
          <a href="/jobs">Job Progress</a>
          <a href="#notes">Notes</a>
          <a href="#processing">Processing</a>
          <a href="#storage">Storage</a>
          <a href="#services">Services</a>
          <a href="#settings">Settings</a>
        </nav>
        <div class="rail-footer">
          Local FastAPI dashboard for development monitoring.
        </div>
      </aside>

      <main class="main">
        <header class="topbar" id="overview">
          <div>
            <h1 class="page-title">YourNoteAI Backend</h1>
            <p class="page-subtitle">Operational monitor for notes, processing, storage, and services.</p>
          </div>
          <div class="toolbar">
            <div class="status-pill">
              <span id="status-dot" class="status-dot"></span>
              <strong id="backend-status">Checking</strong>
            </div>
            <div class="time-pill">Updated <strong id="last-updated">-</strong></div>
            <button id="refresh-button" class="button" type="button">Refresh</button>
          </div>
        </header>

        <section class="grid kpis" aria-label="Key metrics">
          <article class="kpi">
            <div class="kpi-label">Online users</div>
            <div id="kpi-users" class="kpi-value">-</div>
            <div class="kpi-foot">45 second active window</div>
          </article>
          <article class="kpi">
            <div class="kpi-label">Active notes</div>
            <div id="kpi-active" class="kpi-value">-</div>
            <div id="kpi-expiring" class="kpi-foot">- expiring soon</div>
          </article>
          <article class="kpi">
            <div class="kpi-label">Completed</div>
            <div id="kpi-completed" class="kpi-value">-</div>
            <div class="kpi-foot">Ready summaries</div>
          </article>
          <article class="kpi">
            <div class="kpi-label">Failed</div>
            <div id="kpi-failed" class="kpi-value">-</div>
            <div id="kpi-progress" class="kpi-foot">- in progress</div>
          </article>
          <article class="kpi">
            <div class="kpi-label">Storage used</div>
            <div id="kpi-storage" class="kpi-value">-</div>
            <div class="kpi-foot">Audio, text, and SQLite</div>
          </article>
        </section>

        <section class="grid content-grid">
          <article class="panel" id="notes">
            <div class="panel-header">
              <div>
                <h2 class="panel-title">Recent notes</h2>
                <div class="panel-subtitle">Active notes ordered by creation time</div>
              </div>
              <button id="cleanup-button" class="button danger" type="button">Run cleanup</button>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Expires</th>
                    <th>Size</th>
                    <th>Files</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody id="notes-body">
                  <tr><td colspan="7" class="empty">Loading notes...</td></tr>
                </tbody>
              </table>
            </div>
          </article>

          <div class="grid">
            <article class="panel" id="processing">
              <div class="panel-header">
                <div>
                  <h2 class="panel-title">Processing</h2>
                  <div class="panel-subtitle">Upload to summary pipeline</div>
                </div>
              </div>
              <div id="processing-body" class="panel-body stack"></div>
            </article>

            <article class="panel" id="storage">
              <div class="panel-header">
                <div>
                  <h2 class="panel-title">Storage</h2>
                  <div class="panel-subtitle">Local file footprint</div>
                </div>
              </div>
              <div id="storage-body" class="panel-body bars"></div>
            </article>
          </div>
        </section>

        <section class="grid content-grid" style="margin-top: 16px;">
          <article class="panel" id="services">
            <div class="panel-header">
              <div>
                <h2 class="panel-title">Services</h2>
                <div class="panel-subtitle">FastAPI, SQLite, Whisper, Ollama, and cleanup readiness</div>
              </div>
            </div>
            <div id="services-body" class="panel-body stack"></div>
          </article>

          <article class="panel" id="settings">
            <div class="panel-header">
              <div>
                <h2 class="panel-title">Settings</h2>
                <div class="panel-subtitle">Runtime configuration</div>
              </div>
            </div>
            <div class="panel-body">
              <div class="action-row">
                <span class="meta-list" id="cleanup-summary">Cleanup interval: -</span>
                <button id="secondary-refresh-button" class="button secondary" type="button">Refresh now</button>
              </div>
              <div id="message" class="message"></div>
            </div>
          </article>
        </section>
      </main>
    </div>

    <script>
      const els = {
        statusDot: document.getElementById('status-dot'),
        backendStatus: document.getElementById('backend-status'),
        lastUpdated: document.getElementById('last-updated'),
        refreshButton: document.getElementById('refresh-button'),
        secondaryRefreshButton: document.getElementById('secondary-refresh-button'),
        cleanupButton: document.getElementById('cleanup-button'),
        message: document.getElementById('message'),
        users: document.getElementById('kpi-users'),
        active: document.getElementById('kpi-active'),
        completed: document.getElementById('kpi-completed'),
        failed: document.getElementById('kpi-failed'),
        storage: document.getElementById('kpi-storage'),
        expiring: document.getElementById('kpi-expiring'),
        progress: document.getElementById('kpi-progress'),
        notesBody: document.getElementById('notes-body'),
        servicesBody: document.getElementById('services-body'),
        storageBody: document.getElementById('storage-body'),
        processingBody: document.getElementById('processing-body'),
        cleanupSummary: document.getElementById('cleanup-summary'),
      };

      function formatBytes(bytes) {
        if (!bytes) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB'];
        let value = bytes;
        let index = 0;
        while (value >= 1024 && index < units.length - 1) {
          value = value / 1024;
          index += 1;
        }
        return `${value >= 10 || index === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
      }

      function formatDate(value) {
        if (!value) return '-';
        return new Date(value).toLocaleString([], {
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        });
      }

      function statusClass(status) {
        if (status === 'completed' || status === 'ok') return 'ok';
        if (status === 'failed' || status === 'error') return 'error';
        if (status === 'warning') return 'warning';
        return 'neutral';
      }

      function noteFiles(note) {
        const parts = [];
        if (note.has_audio) parts.push('audio');
        if (note.has_transcript) parts.push('transcript');
        if (note.has_summary) parts.push('summary');
        return parts.length ? parts.join(', ') : '-';
      }

      function renderNotes(notes) {
        if (!notes.length) {
          els.notesBody.innerHTML = '<tr><td colspan="7" class="empty">No active notes yet.</td></tr>';
          return;
        }

        els.notesBody.innerHTML = notes.map((note) => `
          <tr>
            <td class="mono">${note.id.slice(0, 10)}...</td>
            <td><span class="badge ${statusClass(note.status)}">${note.status}</span></td>
            <td>${formatDate(note.created_at)}</td>
            <td>${formatDate(note.expires_at)}</td>
            <td>${formatBytes(note.bytes)}</td>
            <td>${noteFiles(note)}</td>
            <td><button class="button secondary" type="button" data-delete-note="${note.id}">Delete</button></td>
          </tr>
        `).join('');
      }

      function renderStorage(storage) {
        const breakdown = storage.breakdown || {};
        const total = storage.total_bytes || 0;
        const rows = [
          ['Audio', breakdown.audio || 0],
          ['Transcripts', breakdown.transcripts || 0],
          ['Summaries', breakdown.summaries || 0],
          ['SQLite', breakdown.database || 0],
        ];

        els.storageBody.innerHTML = rows.map(([label, bytes]) => {
          const percent = total ? Math.max(3, Math.round((bytes / total) * 100)) : 0;
          return `
            <div class="bar-row">
              <div class="bar-head"><span>${label}</span><strong>${formatBytes(bytes)}</strong></div>
              <div class="bar-track"><div class="bar-fill" style="width: ${percent}%"></div></div>
            </div>
          `;
        }).join('');
      }

      function renderServices(services) {
        els.servicesBody.innerHTML = services.map((service) => {
          const meta = Object.entries(service.meta || {})
            .filter(([, value]) => value !== undefined && value !== null && value !== '')
            .map(([key, value]) => `${key.replaceAll('_', ' ')}: ${value}`)
            .join(' · ');

          return `
            <div class="service">
              <div class="service-icon">${service.name.slice(0, 1)}</div>
              <div class="service-main">
                <div class="service-head">
                  <div class="service-name">${service.name}</div>
                  <span class="badge ${statusClass(service.status)}">${service.status}</span>
                </div>
                <div class="service-detail">${service.detail}</div>
                ${meta ? `<div class="meta-list">${meta}</div>` : ''}
              </div>
            </div>
          `;
        }).join('');
      }

      function renderProcessing(notes) {
        const counts = notes.status_counts || {};
        const rows = [
          ['Uploaded', counts.uploaded || 0],
          ['Transcribing', counts.transcribing || 0],
          ['Transcribed', counts.transcribed || 0],
          ['Summarizing', counts.summarizing || 0],
          ['Completed', counts.completed || 0],
          ['Failed', counts.failed || 0],
        ];
        const max = Math.max(1, ...rows.map(([, count]) => count));

        els.processingBody.innerHTML = rows.map(([label, count]) => `
          <div class="bar-row">
            <div class="bar-head"><span>${label}</span><strong>${count}</strong></div>
            <div class="bar-track"><div class="bar-fill" style="width: ${Math.round((count / max) * 100)}%"></div></div>
          </div>
        `).join('');
      }

      function renderOverview(data) {
        els.statusDot.className = 'status-dot ok';
        els.backendStatus.textContent = 'Connected';
        els.lastUpdated.textContent = new Date(data.updated_at).toLocaleTimeString();
        els.users.textContent = data.online_users;
        els.active.textContent = data.notes.active;
        els.completed.textContent = data.notes.completed;
        els.failed.textContent = data.notes.failed;
        els.storage.textContent = formatBytes(data.storage.total_bytes);
        els.expiring.textContent = `${data.notes.expiring_soon} expiring soon`;
        els.progress.textContent = `${data.notes.in_progress} in progress`;
        els.cleanupSummary.textContent = `Cleanup interval: ${Math.round(data.cleanup.interval_seconds / 60)} minutes · expired notes waiting: ${data.cleanup.expired_notes}`;

        renderNotes(data.notes.recent || []);
        renderStorage(data.storage || {});
        renderServices(data.services || []);
        renderProcessing(data.notes || {});
      }

      async function refresh() {
        els.refreshButton.disabled = true;
        els.secondaryRefreshButton.disabled = true;
        els.message.textContent = '';

        try {
          const response = await fetch('/api/admin/overview', { cache: 'no-store' });
          if (!response.ok) throw new Error('Dashboard refresh failed.');
          renderOverview(await response.json());
        } catch (error) {
          els.statusDot.className = 'status-dot error';
          els.backendStatus.textContent = 'Offline';
          els.message.textContent = error.message || 'Dashboard refresh failed.';
        } finally {
          els.refreshButton.disabled = false;
          els.secondaryRefreshButton.disabled = false;
        }
      }

      async function cleanup() {
        els.cleanupButton.disabled = true;
        els.message.textContent = 'Running cleanup...';

        try {
          const response = await fetch('/api/notes/cleanup', { method: 'POST' });
          if (!response.ok) throw new Error('Cleanup failed.');
          const data = await response.json();
          els.message.textContent = `Cleanup complete. Deleted ${data.deleted} expired note${data.deleted === 1 ? '' : 's'}.`;
          await refresh();
        } catch (error) {
          els.message.textContent = error.message || 'Cleanup failed.';
        } finally {
          els.cleanupButton.disabled = false;
        }
      }

      async function deleteNote(noteId) {
        els.message.textContent = `Deleting ${noteId.slice(0, 10)}...`;
        try {
          const response = await fetch(`/api/notes/${noteId}`, { method: 'DELETE' });
          if (!response.ok) throw new Error('Delete failed.');
          els.message.textContent = 'Note deleted.';
          await refresh();
        } catch (error) {
          els.message.textContent = error.message || 'Delete failed.';
        }
      }

      els.refreshButton.addEventListener('click', refresh);
      els.secondaryRefreshButton.addEventListener('click', refresh);
      els.cleanupButton.addEventListener('click', cleanup);
      els.notesBody.addEventListener('click', (event) => {
        const button = event.target.closest('[data-delete-note]');
        if (button) deleteNote(button.dataset.deleteNote);
      });

      refresh();
      setInterval(refresh, 10000);
    </script>
  </body>
</html>
        """.strip()
    )
