import asyncio
import logging
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import calls, contest, dashboard, events, org, upload
from app.services.processor import run_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s: %(message)s")
logger = logging.getLogger("fitnova")

_worker_task: asyncio.Task | None = None
_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _run_migrations() -> None:
    """Self-migrating on boot: `alembic upgrade head` runs as a subprocess
    (not in-process — alembic/env.py calls asyncio.run() internally, which
    can't nest inside the event loop this lifespan is already running on)
    before the worker starts. A no-op (already at head) returns in well
    under a second, so this costs nothing on every normal restart; it's what
    makes a deploy self-contained instead of relying on a separate manual
    step or a platform-specific pre-deploy hook that's easy to forget."""
    logger.info("Running database migrations (alembic upgrade head)...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("Migration failed:\n%s", (result.stdout + result.stderr).strip())
        raise RuntimeError("Database migration failed — refusing to start with a possibly out-of-date schema")
    logger.info("Migrations up to date.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task
    _run_migrations()
    logger.info("FitNova API starting up (LLM_PROVIDER=%s)", settings.LLM_PROVIDER)
    _worker_task = asyncio.create_task(run_worker())
    yield
    logger.info("FitNova API shutting down")
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="FitNova Call Intelligence API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(calls.router)
app.include_router(dashboard.router)
app.include_router(org.router)
app.include_router(contest.router)
app.include_router(events.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
