import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .cleanup import run_cleanup_loop
from .database import init_db
from .dashboard import dashboard_html, router as dashboard_router
from .notes import router as notes_router
from .presence import get_online_count, router as presence_router
from .storage import ensure_storage_directories


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    ensure_storage_directories()
    init_db()
    cleanup_task = asyncio.create_task(run_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleanup_task


app = FastAPI(
    title="YourNoteAI API",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_origins=["*"],
)
app.include_router(notes_router)
app.include_router(presence_router)
app.include_router(dashboard_router)


@app.get("/", response_class=HTMLResponse)
def backend_dashboard() -> HTMLResponse:
    return dashboard_html()


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
def backend_status() -> dict[str, int | str]:
    return {
        "status": "ok",
        "online_users": get_online_count(),
    }
