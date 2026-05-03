from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

ONLINE_WINDOW_SECONDS = 45

router = APIRouter(prefix="/api/presence", tags=["presence"])
_clients: dict[str, datetime] = {}


class HeartbeatRequest(BaseModel):
    client_id: str


def _now() -> datetime:
    return datetime.now(UTC)


def prune_inactive_clients() -> None:
    cutoff = _now() - timedelta(seconds=ONLINE_WINDOW_SECONDS)

    inactive_client_ids = [
        client_id for client_id, last_seen in _clients.items() if last_seen < cutoff
    ]

    for client_id in inactive_client_ids:
        del _clients[client_id]


def get_online_count() -> int:
    prune_inactive_clients()
    return len(_clients)


@router.post("/heartbeat")
def heartbeat(payload: HeartbeatRequest) -> dict[str, int | str]:
    _clients[payload.client_id] = _now()

    return {
        "status": "ok",
        "online_users": get_online_count(),
        "online_window_seconds": ONLINE_WINDOW_SECONDS,
    }


@router.get("/status")
def presence_status() -> dict[str, int | str]:
    return {
        "status": "ok",
        "online_users": get_online_count(),
        "online_window_seconds": ONLINE_WINDOW_SECONDS,
    }


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
        color-scheme: light dark;
        font-family: Arial, sans-serif;
      }

      body {
        align-items: center;
        background: #f4f6f8;
        color: #111827;
        display: flex;
        justify-content: center;
        margin: 0;
        min-height: 100vh;
      }

      main {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
        box-sizing: border-box;
        max-width: 440px;
        padding: 28px;
        width: calc(100% - 32px);
      }

      h1 {
        font-size: 24px;
        line-height: 1.2;
        margin: 0 0 18px;
      }

      .metric {
        align-items: baseline;
        display: flex;
        gap: 12px;
        margin-bottom: 16px;
      }

      .count {
        color: #007aff;
        font-size: 56px;
        font-weight: 800;
        line-height: 1;
      }

      .label {
        color: #4b5563;
        font-size: 16px;
        font-weight: 700;
      }

      .row {
        border-top: 1px solid #e5e7eb;
        display: flex;
        justify-content: space-between;
        padding: 12px 0;
      }

      .value {
        font-weight: 700;
      }

      .ok {
        color: #0f9f6e;
      }

      @media (prefers-color-scheme: dark) {
        body {
          background: #0b0f14;
          color: #f9fafb;
        }

        main {
          background: #111827;
          border-color: #374151;
        }

        .label,
        .row {
          color: #d1d5db;
        }

        .row {
          border-top-color: #374151;
        }
      }
    </style>
  </head>
  <body>
    <main>
      <h1>YourNoteAI Backend</h1>
      <section class="metric">
        <div id="online-users" class="count">0</div>
        <div class="label">online users</div>
      </section>
      <div class="row">
        <span>Backend status</span>
        <span id="status" class="value">Checking...</span>
      </div>
      <div class="row">
        <span>Last update</span>
        <span id="last-update" class="value">-</span>
      </div>
    </main>
    <script>
      async function refreshStatus() {
        const statusEl = document.getElementById('status');
        const usersEl = document.getElementById('online-users');
        const updateEl = document.getElementById('last-update');

        try {
          const response = await fetch('/api/status', { cache: 'no-store' });
          const data = await response.json();

          usersEl.textContent = data.online_users ?? 0;
          statusEl.textContent = 'Connected';
          statusEl.className = 'value ok';
          updateEl.textContent = new Date().toLocaleTimeString();
        } catch {
          statusEl.textContent = 'Offline';
          statusEl.className = 'value';
        }
      }

      refreshStatus();
      setInterval(refreshStatus, 5000);
    </script>
  </body>
</html>
        """.strip()
    )
