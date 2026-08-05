"""Integration tests for the idempotency contract (design doc Section 1):
  UNIQUE(source_system, external_id)
    COMPLETED -> reject
    FAILED    -> allow retry (reset to QUEUED)
    otherwise -> reject (already in flight)

Live-curl-tested in Phase 1 against a running server; these give the same
behavior automated regression coverage without needing the server up.
"""
import uuid

import pytest
from sqlalchemy import delete

from app.adapters.base import CallEvent
from app.database import async_session_factory
from app.models.call import Call
from app.services.ingestion import DuplicateCallError, ingest_call_event

ADVISOR_ID = "c0000000-0000-0000-0000-000000000001"  # Priya Sharma, seeded


def _event(external_id: str, **overrides) -> CallEvent:
    defaults = dict(
        external_id=external_id,
        source_system="file_upload",
        advisor_id=ADVISOR_ID,
        audio_ref="sample_calls/test.wav",
    )
    defaults.update(overrides)
    return CallEvent(**defaults)


async def _cleanup(external_id: str):
    async with async_session_factory() as session:
        await session.execute(
            delete(Call).where(Call.source_system == "file_upload", Call.external_id == external_id)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_fresh_call_queues_successfully():
    external_id = f"test-ingest-{uuid.uuid4()}"
    try:
        async with async_session_factory() as session:
            result = await ingest_call_event(session, _event(external_id))
            await session.commit()
        assert result.status == "QUEUED"
        assert result.is_retry is False
    finally:
        await _cleanup(external_id)


@pytest.mark.asyncio
async def test_duplicate_while_completed_rejected():
    external_id = f"test-ingest-{uuid.uuid4()}"
    try:
        async with async_session_factory() as session:
            call = Call(
                advisor_id=ADVISOR_ID, source_system="file_upload", external_id=external_id,
                audio_ref="x.wav", status="COMPLETED",
            )
            session.add(call)
            await session.commit()

        async with async_session_factory() as session:
            with pytest.raises(DuplicateCallError, match="already exists"):
                await ingest_call_event(session, _event(external_id))
    finally:
        await _cleanup(external_id)


@pytest.mark.asyncio
async def test_duplicate_while_in_flight_rejected():
    """A call still QUEUED/TRANSCRIBING/ANALYZING must reject a duplicate
    submission — this is what stops a webhook firing twice from
    double-processing a call."""
    external_id = f"test-ingest-{uuid.uuid4()}"
    try:
        async with async_session_factory() as session:
            call = Call(
                advisor_id=ADVISOR_ID, source_system="file_upload", external_id=external_id,
                audio_ref="x.wav", status="TRANSCRIBING",
            )
            session.add(call)
            await session.commit()

        async with async_session_factory() as session:
            with pytest.raises(DuplicateCallError, match="already being processed"):
                await ingest_call_event(session, _event(external_id))
    finally:
        await _cleanup(external_id)


@pytest.mark.asyncio
async def test_duplicate_while_failed_allows_retry():
    external_id = f"test-ingest-{uuid.uuid4()}"
    try:
        async with async_session_factory() as session:
            call = Call(
                advisor_id=ADVISOR_ID, source_system="file_upload", external_id=external_id,
                audio_ref="old.wav", status="FAILED", retry_count=2,
            )
            session.add(call)
            await session.commit()

        async with async_session_factory() as session:
            result = await ingest_call_event(session, _event(external_id, audio_ref="corrected.wav"))
            await session.commit()
            assert result.status == "QUEUED"
            assert result.is_retry is True

        async with async_session_factory() as session:
            call = await session.get(Call, result.call_id)
            assert call.retry_count == 0  # manual re-upload resets the counter
            assert call.audio_ref == "corrected.wav"
    finally:
        await _cleanup(external_id)


@pytest.mark.asyncio
async def test_customer_phone_never_stored_raw():
    external_id = f"test-ingest-{uuid.uuid4()}"
    try:
        async with async_session_factory() as session:
            result = await ingest_call_event(session, _event(external_id, customer_phone="9876543210"))
            await session.commit()

        async with async_session_factory() as session:
            call = await session.get(Call, result.call_id)
            assert call.raw_metadata["customer_phone"] == "[PHONE]"
            assert "9876543210" not in str(call.raw_metadata)
    finally:
        await _cleanup(external_id)
