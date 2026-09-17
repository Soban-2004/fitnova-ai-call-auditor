"""Per-LLM-call telemetry: latency, outcome, and which provider in the
Groq->Gemini->Ollama fallback chain actually served a call — persisted to
llm_call_logs so it survives a Render restart, unlike the stdlib `logging`
output already in this app (main.py's logging.basicConfig).

A telemetry write must never be allowed to break the pipeline it's
observing — wrapped in its own try/except, logged and swallowed on failure
rather than propagated. See routers/admin.py for the read side.
"""
import logging
import time
from contextlib import asynccontextmanager

from app.database import async_session_factory
from app.models.telemetry import LLMCallLog

logger = logging.getLogger("fitnova.telemetry")


@asynccontextmanager
async def track_llm_call(provider: str, model: str, purpose: str):
    """Wrap one LLM provider call:

        async with track_llm_call("groq", model, "issue_detection"):
            result = await provider.complete(...)

    Records latency and outcome (success, or the exception's type name on
    failure) once the block exits. Re-raises whatever the wrapped call
    raised -- this never changes control flow, only observes it.
    """
    start = time.monotonic()
    outcome = "success"
    error_type: str | None = None
    try:
        yield
    except Exception as e:
        outcome = "error"
        error_type = type(e).__name__
        raise
    finally:
        latency_ms = int((time.monotonic() - start) * 1000)
        await _record(provider, model, purpose, outcome, latency_ms, error_type)


async def _record(
    provider: str, model: str, purpose: str, outcome: str, latency_ms: int, error_type: str | None
) -> None:
    try:
        async with async_session_factory() as session:
            session.add(
                LLMCallLog(
                    provider=provider,
                    model=model,
                    purpose=purpose,
                    outcome=outcome,
                    latency_ms=latency_ms,
                    error_type=error_type,
                )
            )
            await session.commit()
    except Exception as e:
        # A telemetry outage is not a pipeline outage -- log it via the
        # existing stdlib logger (no DB dependency) and move on.
        logger.warning("Failed to record LLM call log (%s: %s)", type(e).__name__, e)
