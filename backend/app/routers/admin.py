from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.query_helpers import llm_call_stats

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Gates the LLM-telemetry endpoint behind a single static shared
    secret -- this app has no user auth system anywhere else to hang a real
    admin role off of (see routers/upload.py's own lack of auth), and one
    read-only aggregate endpoint doesn't justify adding one just for this.
    settings.ADMIN_TOKEN empty means nobody passes, same "closed by
    default" pattern as the B2/OLLAMA settings in config.py.
    """
    if not settings.ADMIN_TOKEN or x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin access required.")


@router.get("/llm-stats", dependencies=[Depends(require_admin)])
async def llm_stats(hours: int = 24, session: AsyncSession = Depends(get_db)) -> dict:
    """Aggregate LLM-call telemetry -- counts, avg latency, and error rate
    per (provider, model, purpose, outcome) over the trailing window. Never
    touches the pipeline itself, only what services/telemetry.py has
    already recorded.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = await llm_call_stats(session, since)
    return {"since": since.isoformat(), "hours": hours, "calls": rows}
