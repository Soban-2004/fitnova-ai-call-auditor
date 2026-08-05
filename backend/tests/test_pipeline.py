"""Integration tests for the state machine's failure paths (design doc
Section 2 + Section 11 edge cases): vendor API failure -> FAILED + retry
bookkeeping, and the periodic sweep that recovers stuck/failed calls.

These run against the real dev DB (no separate test DB is set up for this
prototype) using throwaway Call rows cleaned up after each test — not mocks,
so a real TranscriptionError (file genuinely doesn't exist) drives the
failure path exactly as the background worker would hit it in production.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.config import settings
from app.database import async_session_factory
from app.models.call import Call
from app.services.processor import _mark_failed, process_single_call, sweep_once
from app.services.transcription import TranscriptionError

# Priya Sharma, seeded by scripts/seed_db.py — any seeded advisor works.
ADVISOR_ID = "c0000000-0000-0000-0000-000000000001"


async def _make_call(session, **overrides) -> Call:
    defaults = dict(
        id=uuid.uuid4(),
        advisor_id=ADVISOR_ID,
        source_system="file_upload",
        external_id=f"test-pipeline-{uuid.uuid4()}",
        audio_ref="sample_calls/does_not_exist.wav",
        status="QUEUED",
        retry_count=0,
    )
    defaults.update(overrides)
    call = Call(**defaults)
    session.add(call)
    await session.flush()
    return call


async def _cleanup(call_id):
    async with async_session_factory() as session:
        await session.execute(delete(Call).where(Call.id == call_id))
        await session.commit()


@pytest.mark.asyncio
async def test_transcription_failure_marks_call_failed_and_increments_retry():
    async with async_session_factory() as session:
        call = await _make_call(session)  # audio_ref points nowhere -> real TranscriptionError
        await session.commit()
        call_id = str(call.id)

    try:
        async with async_session_factory() as session:
            with pytest.raises(TranscriptionError):
                await process_single_call(call_id, session)
            await session.rollback()

        async with async_session_factory() as err_session:
            await _mark_failed(err_session, call_id, "Deepgram API error: file not found")

        async with async_session_factory() as session:
            call = await session.get(Call, call_id)
            assert call.status == "FAILED"
            assert call.retry_count == 1
            assert "Deepgram" in call.error_message
    finally:
        await _cleanup(call_id)


@pytest.mark.asyncio
async def test_sweep_marks_stuck_transcribing_call_as_failed():
    stuck_cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.STUCK_CALL_TIMEOUT_MINUTES + 5)
    async with async_session_factory() as session:
        call = await _make_call(session, status="TRANSCRIBING", updated_at=stuck_cutoff)
        await session.commit()
        call_id = str(call.id)

    try:
        await sweep_once()
        async with async_session_factory() as session:
            call = await session.get(Call, call_id)
            assert call.status == "FAILED"  # not immediately bounced back to QUEUED in the same pass
            assert call.retry_count == 1
            assert call.error_message == f"Stuck in TRANSCRIBING for over {settings.STUCK_CALL_TIMEOUT_MINUTES} minutes"
    finally:
        await _cleanup(call_id)


@pytest.mark.asyncio
async def test_sweep_requeues_failed_call_under_max_retries():
    async with async_session_factory() as session:
        call = await _make_call(session, status="FAILED", retry_count=settings.MAX_RETRIES - 1)
        await session.commit()
        call_id = str(call.id)

    try:
        await sweep_once()
        async with async_session_factory() as session:
            call = await session.get(Call, call_id)
            assert call.status == "QUEUED"
    finally:
        await _cleanup(call_id)


@pytest.mark.asyncio
async def test_sweep_leaves_call_at_max_retries_permanently_failed():
    """After MAX_RETRIES, a call stays FAILED — surfaced as 'needs manual
    review' on the dashboard rather than retried forever."""
    async with async_session_factory() as session:
        call = await _make_call(session, status="FAILED", retry_count=settings.MAX_RETRIES)
        await session.commit()
        call_id = str(call.id)

    try:
        await sweep_once()
        async with async_session_factory() as session:
            call = await session.get(Call, call_id)
            assert call.status == "FAILED"
            assert call.retry_count == settings.MAX_RETRIES
    finally:
        await _cleanup(call_id)


@pytest.mark.asyncio
async def test_sweep_does_not_touch_healthy_in_progress_calls():
    """A call that's genuinely still being processed (recently updated)
    must survive the sweep untouched."""
    async with async_session_factory() as session:
        call = await _make_call(session, status="ANALYZING", updated_at=datetime.now(timezone.utc))
        await session.commit()
        call_id = str(call.id)

    try:
        await sweep_once()
        async with async_session_factory() as session:
            call = await session.get(Call, call_id)
            assert call.status == "ANALYZING"
    finally:
        await _cleanup(call_id)
