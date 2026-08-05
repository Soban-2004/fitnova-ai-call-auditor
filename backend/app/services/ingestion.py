"""Turns a normalized CallEvent (from any source adapter) into a `calls` row,
enforcing the idempotency contract from the design doc:

  UNIQUE(source_system, external_id)
    status = COMPLETED -> reject, already processed
    status = FAILED     -> allow retry (reset to QUEUED)
    otherwise            -> reject, already in progress

This is the one place that decides whether a call is new work, a legitimate
retry, or a duplicate — regardless of which adapter produced the CallEvent.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import CallEvent
from app.models.call import Call
from app.services.pii_redaction import redact_text


class DuplicateCallError(Exception):
    """Raised when a call with the same (source_system, external_id) is
    already COMPLETED or currently in progress."""
    def __init__(self, message: str, existing_call_id: str):
        super().__init__(message)
        self.existing_call_id = existing_call_id


@dataclass
class IngestResult:
    call_id: str
    status: str
    is_retry: bool


async def ingest_call_event(session: AsyncSession, event: CallEvent) -> IngestResult:
    existing = await session.scalar(
        select(Call).where(
            Call.source_system == event.source_system,
            Call.external_id == event.external_id,
        )
    )

    if existing is not None:
        if existing.status == "COMPLETED":
            raise DuplicateCallError(
                "Call with this source and external_id already exists", str(existing.id)
            )
        if existing.status == "FAILED":
            existing.status = "QUEUED"
            existing.retry_count = 0
            existing.audio_ref = event.audio_ref  # allow re-upload with corrected audio
            await session.flush()
            return IngestResult(call_id=str(existing.id), status="QUEUED", is_retry=True)
        # QUEUED / TRANSCRIBING / ANALYZING — already in flight
        raise DuplicateCallError(
            "Call with this source and external_id is already being processed", str(existing.id)
        )

    # customer_phone is never persisted raw — redact immediately, fold into
    # raw_metadata (the `calls` table has no dedicated column for it; see
    # design doc Section 8, calls schema).
    raw_metadata = dict(event.raw_metadata)
    if event.customer_phone:
        raw_metadata["customer_phone"] = redact_text(event.customer_phone)

    call = Call(
        advisor_id=event.advisor_id,
        source_system=event.source_system,
        external_id=event.external_id,
        audio_ref=event.audio_ref,
        duration_secs=event.duration_secs,
        called_at=event.called_at,
        raw_metadata=raw_metadata,
        status="QUEUED",
    )
    session.add(call)
    await session.flush()
    return IngestResult(call_id=str(call.id), status="QUEUED", is_retry=False)
