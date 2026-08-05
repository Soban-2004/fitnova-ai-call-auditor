"""Background worker + processing state machine.

QUEUED -> TRANSCRIBING -> ANALYZING -> COMPLETED
             |failure|      |failure|
              v               v
            FAILED  <-------------
              |
        retry_count < MAX_RETRIES ? -> QUEUED (auto-retry via sweep)
        retry_count >= MAX_RETRIES ? -> stays FAILED (manual review)

Why DB polling instead of Celery/Redis: for a prototype processing calls
sequentially, a distributed queue adds infra without demonstrable benefit.
The state machine lives in the `calls.status` column and works no matter what
executes it — swapping to Celery later only changes the executor, not the
schema (documented production upgrade path).

process_single_call() is the full 15-step pipeline: transcribe, redact,
store, speaker ID, issue detection + validation, dimension ratings, score,
-> COMPLETED. Each step's failure (TranscriptionError, LLMProviderError,
etc.) propagates up to run_worker_once(), which drives the FAILED + retry
transition uniformly regardless of which step broke.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.analysis import DimensionRating, IssueTag
from app.models.call import Call
from app.models.score import CallScore
from app.models.transcript import TranscriptSegment
from app.services.analysis import detect_issues, get_active_prompt, identify_speakers, rate_dimensions
from app.services.events import broadcaster, set_call_progress
from app.services.pii_redaction import redact_transcript_segments
from app.services.scoring import compute_score
from app.services.transcription import transcribe_call
from app.services.validation import validate_tag

logger = logging.getLogger("fitnova.processor")

SHORT_CALL_THRESHOLD_SECS = 30


def _touch(call: Call, status: str, **extra) -> None:
    """Update the in-memory Call object directly (not a bulk UPDATE) so the
    rest of process_single_call always sees consistent, current attributes —
    a bulk `update()` statement would silently leave this object's Python
    attributes stale since it bypasses the ORM identity map."""
    call.status = status
    call.updated_at = datetime.now(timezone.utc)
    for k, v in extra.items():
        setattr(call, k, v)


async def _store_segments(session: AsyncSession, call_id: str, segments: list[dict]) -> list[TranscriptSegment]:
    rows = []
    for seg in segments:
        row = TranscriptSegment(
            call_id=call_id,
            speaker_label=seg["speaker_label"],
            speaker_role=seg.get("speaker_role"),
            text=seg["text"],
            start_ts=seg["start_ts"],
            end_ts=seg["end_ts"],
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


async def _report_step(call_id: str, step: str | None) -> None:
    """Records progress in-memory (services/events.py) so a concurrent
    GET /calls/{id}/status can see it — deliberately NOT a DB write. This
    function used to UPDATE calls.current_step in its own committed
    transaction, on the theory that a separate connection can't see this
    session's uncommitted flushes. True, but that UPDATE targets the exact
    row run_worker_once() holds under `SELECT ... FOR UPDATE` for the whole
    pipeline duration — Postgres blocks a conflicting UPDATE from another
    connection until that lock is released, so the "independent commit"
    would just hang until the pipeline finished anyway (confirmed by
    directly reproducing the block). No DB round-trip needed here at all:
    same-process visibility is all this requires."""
    set_call_progress(call_id, step)


def _seg_dicts(rows: list[TranscriptSegment]) -> list[dict]:
    return [
        {
            "speaker_label": r.speaker_label,
            "speaker_role": r.speaker_role,
            "text": r.text,
            "start_ts": r.start_ts,
            "end_ts": r.end_ts,
        }
        for r in rows
    ]


async def process_single_call(call_id: str, session: AsyncSession) -> None:
    """Runs one call through the full pipeline. Raises on failure — caller
    handles the FAILED transition + retry bookkeeping."""

    call = await session.get(Call, call_id)
    if call is None:
        raise ValueError(f"Call {call_id} not found")

    # --- Step 1: TRANSCRIBING ---
    _touch(call, "TRANSCRIBING")
    await session.flush()
    await _report_step(call_id, "TRANSCRIPTION")

    # --- Step 2: Deepgram transcription (+ diarization) ---
    transcript = await transcribe_call(call.audio_ref)

    # --- Edge case: mono / poor diarization — skip per-speaker analysis
    # (speaker ID call below), still process content normally. ---
    diarization_quality = "good" if transcript.distinct_speakers >= 2 else "mono"

    # --- Edge case: very short call. Not written to `call_type` — that
    # column holds the LLM's sales/non_sales/unclear classification (Step 8
    # below); "short" is fully derivable from duration_secs at query time,
    # so storing it here would just create two writers fighting over one
    # column (the design doc's own edge-case table conflates the two). ---
    is_short = transcript.duration_secs < SHORT_CALL_THRESHOLD_SECS

    # --- Step 3: PII redaction (before anything is stored or sent to an LLM) ---
    await _report_step(call_id, "PII_REDACTION")
    segments = redact_transcript_segments(transcript.segments)

    # --- Step 4: store transcript segments ---
    segment_rows = await _store_segments(session, call_id, segments)

    _touch(
        call,
        "ANALYZING",
        duration_secs=int(transcript.duration_secs),
        diarization_quality=diarization_quality,
    )
    await session.flush()
    logger.info(
        "Call %s transcribed: %d segments, %.1fs, diarization=%s%s",
        call_id, len(segments), transcript.duration_secs, diarization_quality,
        " (short call)" if is_short else "",
    )

    # --- Step 5-6: Speaker role identification (skipped for mono audio —
    # there's only one detected speaker, nothing to disambiguate) ---
    await _report_step(call_id, "SPEAKER_ID")
    metadata = dict(call.raw_metadata or {})
    if diarization_quality == "good":
        speaker_prompt = await get_active_prompt(session, "speaker_identification")
        speaker_result = await identify_speakers(_seg_dicts(segment_rows), speaker_prompt.system_prompt)

        role_map = {"Speaker 0": speaker_result.speaker_0, "Speaker 1": speaker_result.speaker_1}
        for row in segment_rows:
            role = role_map.get(row.speaker_label)
            if role:
                row.speaker_role = role

        metadata["speaker_id_confidence"] = speaker_result.confidence
        if speaker_result.confidence == "low":
            metadata["needs_manual_review"] = True
            logger.warning("Call %s: low-confidence speaker ID — flagged for manual review", call_id)
    else:
        metadata["speaker_id_skipped"] = "mono_audio"
    call.raw_metadata = metadata
    await session.flush()

    # --- Step 7-9: Issue detection + three-layer validation + storage ---
    await _report_step(call_id, "ISSUE_DETECTION")
    issue_prompt = await get_active_prompt(session, "issue_detection")
    issues_result = await detect_issues(_seg_dicts(segment_rows), issue_prompt.system_prompt)
    call.call_type = issues_result.call_type

    validated_tags: list[dict] = []
    rejected_count = 0
    for issue in issues_result.issues:
        tag_dict = issue.model_dump()
        result = await validate_tag(tag_dict, _seg_dicts(segment_rows), transcript.duration_secs)
        if result.status == "rejected":
            rejected_count += 1
            logger.info("Call %s: rejected tag %s — %s", call_id, tag_dict.get("tag"), result.reason)
            continue
        session.add(
            IssueTag(
                call_id=call_id,
                prompt_version_id=issue_prompt.id,
                tag_type=tag_dict["tag"],
                severity=tag_dict["severity"],
                quote=tag_dict["quote"],
                start_ts=tag_dict["start_ts"],
                end_ts=tag_dict["end_ts"],
                reason=tag_dict.get("reason"),
                validation_score=result.validation_score,
                status=result.status,
            )
        )
        validated_tags.append(
            {"tag_type": tag_dict["tag"], "severity": tag_dict["severity"], "status": result.status}
        )
    await session.flush()
    logger.info(
        "Call %s: call_type=%s, %d issues found, %d validated, %d rejected",
        call_id, issues_result.call_type, len(issues_result.issues), len(validated_tags), rejected_count,
    )

    # --- Step 10-11: Dimension ratings ---
    await _report_step(call_id, "DIMENSION_RATING")
    dimension_prompt = await get_active_prompt(session, "dimension_rating")
    dimension_result = await rate_dimensions(_seg_dicts(segment_rows), dimension_prompt.system_prompt)

    dimension_dict: dict[str, dict] = {}
    for name, dim in dimension_result.dimensions.items():
        session.add(
            DimensionRating(
                call_id=call_id,
                prompt_version_id=dimension_prompt.id,
                dimension=name,
                score=dim.score,
                evidence=dim.evidence,
            )
        )
        dimension_dict[name] = {"score": dim.score}
    await session.flush()

    # --- Step 12-13: Deterministic scoring (the LLM never does arithmetic) ---
    await _report_step(call_id, "SCORING")
    score_result = compute_score(dimension_dict, validated_tags)
    session.add(
        CallScore(
            call_id=call_id,
            version=1,
            base_score=score_result.base_score,
            deductions_total=score_result.deductions_total,
            final_score=score_result.final_score,
            trigger="initial",
        )
    )
    await session.flush()
    logger.info(
        "Call %s: base=%.1f deductions=%.0f final=%d",
        call_id, score_result.base_score, score_result.deductions_total, score_result.final_score,
    )

    # --- Step 14: COMPLETED ---
    _touch(call, "COMPLETED")
    await session.flush()


async def _mark_failed(session: AsyncSession, call_id: str, error_message: str) -> None:
    call = await session.get(Call, call_id)
    if call is None:
        return
    call.status = "FAILED"
    call.retry_count = (call.retry_count or 0) + 1
    call.error_message = error_message[:2000]
    call.updated_at = datetime.now(timezone.utc)
    await session.commit()
    set_call_progress(call_id, None)
    logger.warning("Call %s marked FAILED (retry_count=%d): %s", call_id, call.retry_count, error_message)
    await broadcaster.publish({"type": "call_status_changed", "call_id": call_id, "status": "FAILED"})


async def run_worker_once() -> bool:
    """Pick up and process a single QUEUED call, if any. Returns True if a
    call was picked up (used by tests / manual invocation), False if the
    queue was empty."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Call)
            .where(Call.status == "QUEUED")
            .order_by(Call.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        call = result.scalar_one_or_none()
        if call is None:
            return False

        call_id = str(call.id)
        logger.info("Processing call %s", call_id)
        try:
            await process_single_call(call_id, session)
            await session.commit()
            await _report_step(call_id, None)
            logger.info("Call %s COMPLETED", call_id)
            await broadcaster.publish({"type": "call_status_changed", "call_id": call_id, "status": "COMPLETED"})
        except Exception as e:
            await session.rollback()
            async with async_session_factory() as err_session:
                await _mark_failed(err_session, call_id, str(e))
        return True


async def sweep_once() -> None:
    """Periodic sweep (every POLL_INTERVAL_SECONDS * N, invoked on its own
    timer from run_worker loop):
      1. Calls stuck in TRANSCRIBING/ANALYZING past the timeout -> FAILED.
      2. FAILED calls with retry_count < MAX_RETRIES -> requeued as QUEUED.
      3. FAILED calls at MAX_RETRIES stay FAILED -> surfaced as manual review.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.STUCK_CALL_TIMEOUT_MINUTES)
    async with async_session_factory() as session:
        # Both querysets are fetched up front, before either mutation loop
        # runs. This matters: SQLAlchemy autoflushes pending changes ahead of
        # a new SELECT on the same session, so if the "retryable" query ran
        # *after* the stuck-call loop, a call just marked FAILED (with
        # retry_count now < MAX_RETRIES) would satisfy that query too and
        # get instantly bounced back to QUEUED in the same pass — collapsing
        # "fail now, retry on a later sweep" into one atomic no-op that never
        # leaves the FAILED state observable. Snapshotting first guarantees
        # "retryable" only ever means calls that were already FAILED coming
        # into this sweep.
        stuck_calls = (
            await session.execute(
                select(Call).where(Call.status.in_(["TRANSCRIBING", "ANALYZING"]), Call.updated_at < cutoff)
            )
        ).scalars().all()
        retryable_calls = (
            await session.execute(
                select(Call).where(Call.status == "FAILED", Call.retry_count < settings.MAX_RETRIES)
            )
        ).scalars().all()

        for call in stuck_calls:
            stuck_state = call.status  # capture before overwriting — used in the message below
            call.status = "FAILED"
            call.retry_count = (call.retry_count or 0) + 1
            call.error_message = f"Stuck in {stuck_state} for over {settings.STUCK_CALL_TIMEOUT_MINUTES} minutes"
            call.updated_at = datetime.now(timezone.utc)
            set_call_progress(str(call.id), None)
            logger.warning("Swept stuck call %s (was %s) -> FAILED", call.id, stuck_state)

        for call in retryable_calls:
            call.status = "QUEUED"
            call.updated_at = datetime.now(timezone.utc)
            logger.info("Requeued call %s for retry %d/%d", call.id, call.retry_count, settings.MAX_RETRIES)

        await session.commit()

        for call in stuck_calls:
            await broadcaster.publish({"type": "call_status_changed", "call_id": str(call.id), "status": "FAILED"})


async def run_worker() -> None:
    """Main worker loop. Polls for QUEUED calls every POLL_INTERVAL_SECONDS;
    runs the stuck/retry sweep every 5 minutes worth of poll cycles."""
    logger.info("Background processor started (poll interval=%ss)", settings.POLL_INTERVAL_SECONDS)
    sweep_every_n_polls = max(1, int(300 / settings.POLL_INTERVAL_SECONDS))
    poll_count = 0
    while True:
        try:
            picked_up = await run_worker_once()
            poll_count += 1
            if poll_count % sweep_every_n_polls == 0:
                await sweep_once()
            if not picked_up:
                await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("Background processor shutting down")
            raise
        except Exception:
            logger.exception("Unexpected error in worker loop — continuing")
            await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)
