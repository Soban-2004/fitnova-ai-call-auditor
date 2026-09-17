"""In-memory rate limiting for POST /api/upload.

This is the only unauthenticated, state-mutating endpoint in this app (see
routers/upload.py) — a scripted curl loop against it would otherwise create
unbounded `calls` rows, each one burning a real transcription (Deepgram) plus
a 3-pass LLM analysis run against the same free-tier quotas the fallback
chain (Groq/Gemini/Ollama) is already tight on, for nothing real. This is
what actually bounds that: a per-client cooldown against one abuser looping
the endpoint, plus a global daily cap so upload traffic overall can only ever
eat a small, bounded slice of the pipeline's capacity.

Same in-memory-is-fine reasoning as services/events.py: this app runs as one
process on Render's free tier (asyncio, no threads), so there's no
cross-process state to share and no external store (Redis) is worth adding
just for this.
"""
import datetime as dt
import time
from collections import defaultdict

from fastapi import HTTPException

from app.config import settings

_upload_times: dict[str, list[float]] = defaultdict(list)
_daily_count: dict[str, int] = {}  # ISO date -> count, never pruned (one int/day, harmless)


def enforce_upload_rate_limit(client_key: str) -> None:
    now = time.time()
    today = dt.date.today().isoformat()

    window_start = now - settings.UPLOAD_RATE_LIMIT_WINDOW_SECONDS
    timestamps = _upload_times[client_key]
    timestamps[:] = [t for t in timestamps if t > window_start]
    if len(timestamps) >= settings.UPLOAD_RATE_LIMIT_MAX_PER_WINDOW:
        window_minutes = settings.UPLOAD_RATE_LIMIT_WINDOW_SECONDS // 60
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many uploads from this connection — limit is "
                f"{settings.UPLOAD_RATE_LIMIT_MAX_PER_WINDOW} every {window_minutes} minutes. "
                "Try again shortly."
            ),
        )

    if _daily_count.get(today, 0) >= settings.UPLOAD_DAILY_CAP:
        raise HTTPException(
            status_code=429,
            detail="Upload capacity is fully booked for today. Try again tomorrow.",
        )

    timestamps.append(now)
    _daily_count[today] = _daily_count.get(today, 0) + 1
