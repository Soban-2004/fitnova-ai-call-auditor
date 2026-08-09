import mimetypes
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.analysis import DimensionRating, IssueTag, PromptVersion
from app.models.call import Call
from app.models.org import Advisor, Team
from app.models.score import CallScore, ScoreAuditLog
from app.models.transcript import TranscriptSegment
from app.schemas.call import (
    CallDetail,
    CallListItem,
    CallListResponse,
    CallStatusResponse,
    DimensionRatingOut,
    IssueTagOut,
    ScoreHistoryEntry,
    TranscriptSegmentOut,
)
from app.services.audio_storage import B2_REF_PREFIX, presigned_url
from app.services.events import get_call_progress
from app.services.query_helpers import latest_scores_for_calls, open_issue_counts_for_calls

router = APIRouter(prefix="/api", tags=["calls"])

# Audio can only be served from these known storage roots — audio_ref is a
# plain filesystem path (see adapters/file_upload.py), so without this check
# a crafted advisor upload or a future adapter bug could turn this endpoint
# into an arbitrary-file-read. Resolved once at import time.
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ALLOWED_AUDIO_ROOTS = [
    (_BACKEND_DIR / "sample_calls").resolve(),
    Path(settings.UPLOAD_DIR).resolve(),
]

# The step checklist the frontend polls during upload. Progress is read from
# services/events.py's in-memory store (written live by processor.py's
# _report_step as the pipeline actually progresses) — NOT a DB column. A
# per-step DB write was tried first and reverted: it deadlocked against the
# row lock run_worker_once() holds for the pipeline's entire duration (see
# processor.py's _report_step docstring).
_STEP_ORDER = ["TRANSCRIPTION", "PII_REDACTION", "SPEAKER_ID", "ISSUE_DETECTION", "DIMENSION_RATING", "SCORING"]


@router.get("/calls", response_model=CallListResponse)
async def list_calls(
    advisor_id: str | None = None,
    team_id: str | None = None,
    status: str | None = None,
    call_type: str | None = None,
    tag_type: str | None = None,
    min_score: int | None = Query(None, ge=0, le=100),
    max_score: int | None = Query(None, ge=0, le=100),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
):
    """Powers the All Calls page's filter bar. Straightforward SQL filters
    (advisor/team/status/call_type/date range) run in the DB; score-range and
    tag_type filters run in Python after fetching candidates, since "latest
    score per call" isn't a single-row concept SQL can filter on without a
    window-function subquery — fine at this dataset's scale, would need
    revisiting if call volume grew into the tens of thousands."""
    query = select(Call, Advisor.name.label("advisor_name"), Team.name.label("team_name")).join(
        Advisor, Call.advisor_id == Advisor.id
    ).join(Team, Advisor.team_id == Team.id)

    if advisor_id:
        query = query.where(Call.advisor_id == advisor_id)
    if team_id:
        query = query.where(Advisor.team_id == team_id)
    if status:
        query = query.where(Call.status == status)
    if call_type:
        query = query.where(Call.call_type == call_type)
    if date_from:
        query = query.where(Call.called_at >= date_from)
    if date_to:
        query = query.where(Call.called_at <= date_to)

    rows = (await session.execute(query.order_by(Call.called_at.desc().nulls_last(), Call.created_at.desc()))).all()

    call_ids = [str(call.id) for call, _, _ in rows]
    latest_scores = await latest_scores_for_calls(session, call_ids)
    issue_counts = await open_issue_counts_for_calls(session, call_ids)

    if tag_type:
        tagged_rows = (
            await session.execute(
                select(IssueTag.call_id)
                .distinct()
                .where(IssueTag.call_id.in_(call_ids), IssueTag.tag_type == tag_type)
            )
        ).scalars().all()
        tagged_call_ids = {str(cid) for cid in tagged_rows}
        rows = [r for r in rows if str(r[0].id) in tagged_call_ids]

    if min_score is not None or max_score is not None:
        lo, hi = min_score if min_score is not None else 0, max_score if max_score is not None else 100
        rows = [
            r for r in rows
            if str(r[0].id) in latest_scores and lo <= latest_scores[str(r[0].id)].final_score <= hi
        ]

    total = len(rows)
    page = rows[offset : offset + limit]

    calls = [
        CallListItem(
            id=str(call.id),
            advisor_id=str(call.advisor_id),
            advisor_name=advisor_name,
            team_name=team_name,
            source_system=call.source_system,
            duration_secs=call.duration_secs,
            called_at=call.called_at,
            status=call.status,
            call_type=call.call_type,
            diarization_quality=call.diarization_quality,
            latest_score=latest_scores[str(call.id)].final_score if str(call.id) in latest_scores else None,
            issue_count=issue_counts.get(str(call.id), 0),
            created_at=call.created_at,
        )
        for call, advisor_name, team_name in page
    ]
    return CallListResponse(calls=calls, total=total, limit=limit, offset=offset)


@router.get("/calls/{call_id}", response_model=CallDetail)
async def get_call_detail(call_id: str, session: AsyncSession = Depends(get_db)):
    row = (
        await session.execute(
            select(Call, Advisor.name, Team.name)
            .join(Advisor, Call.advisor_id == Advisor.id)
            .join(Team, Advisor.team_id == Team.id)
            .where(Call.id == call_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    call, advisor_name, team_name = row

    segments = (
        await session.execute(
            select(TranscriptSegment).where(TranscriptSegment.call_id == call_id).order_by(TranscriptSegment.start_ts)
        )
    ).scalars().all()

    tags = (
        await session.execute(select(IssueTag).where(IssueTag.call_id == call_id).order_by(IssueTag.start_ts))
    ).scalars().all()
    prompt_version_ids = {t.prompt_version_id for t in tags if t.prompt_version_id}
    prompt_versions = {}
    if prompt_version_ids:
        pv_rows = (
            await session.execute(select(PromptVersion).where(PromptVersion.id.in_(prompt_version_ids)))
        ).scalars().all()
        prompt_versions = {pv.id: pv.version for pv in pv_rows}

    dimensions = (
        await session.execute(select(DimensionRating).where(DimensionRating.call_id == call_id))
    ).scalars().all()

    scores = (
        await session.execute(
            select(CallScore).where(CallScore.call_id == call_id).order_by(CallScore.version.desc())
        )
    ).scalars().all()

    audit_rows = (
        await session.execute(
            select(ScoreAuditLog).where(ScoreAuditLog.call_id == call_id).order_by(ScoreAuditLog.changed_at)
        )
    ).scalars().all()
    # Keyed by to_version — last write wins if a version was ever touched by
    # more than one audit row (not expected today, but not assumed either).
    audit_by_version = {row.to_version: row for row in audit_rows if row.to_version is not None}

    return CallDetail(
        id=str(call.id),
        advisor_id=str(call.advisor_id),
        advisor_name=advisor_name,
        team_name=team_name,
        source_system=call.source_system,
        duration_secs=call.duration_secs,
        called_at=call.called_at,
        status=call.status,
        call_type=call.call_type,
        diarization_quality=call.diarization_quality,
        error_message=call.error_message,
        transcript=[
            TranscriptSegmentOut(
                id=str(s.id), speaker_label=s.speaker_label, speaker_role=s.speaker_role,
                text=s.text, start_ts=s.start_ts, end_ts=s.end_ts,
            )
            for s in segments
        ],
        issue_tags=[
            IssueTagOut(
                id=str(t.id), tag_type=t.tag_type, severity=t.severity, quote=t.quote,
                start_ts=t.start_ts, end_ts=t.end_ts, reason=t.reason,
                validation_score=t.validation_score, status=t.status,
                contest_reason=t.contest_reason, review_comment=t.review_comment,
                prompt_version=prompt_versions.get(t.prompt_version_id),
            )
            for t in tags
        ],
        dimension_ratings=[
            DimensionRatingOut(dimension=d.dimension, score=d.score, evidence=d.evidence) for d in dimensions
        ],
        score_history=[
            ScoreHistoryEntry(
                version=s.version, base_score=s.base_score, deductions_total=s.deductions_total,
                final_score=s.final_score, trigger=s.trigger, computed_at=s.computed_at,
                reason=audit_by_version[s.version].reason if s.version in audit_by_version else None,
                changed_by=audit_by_version[s.version].changed_by if s.version in audit_by_version else None,
            )
            for s in scores
        ],
        current_score=scores[0].final_score if scores else None,
    )


@router.get("/calls/{call_id}/audio")
async def get_call_audio(call_id: str, session: AsyncSession = Depends(get_db)):
    """Serves the call's source audio for the call-detail page's player.

    Tries the local copy (audio_ref) first — every call has one, it's a
    plain file response, no extra round-trip. Falls back to the durable B2
    copy (audio_backup_ref) if the local file is gone, which is exactly what
    happens after a restart on a host with no persistent disk (see
    services/audio_storage.py). The B2 path redirects the browser straight
    to a presigned URL rather than proxying bytes through this process.

    Whole-file local response (no HTTP Range/206 support) — fine at these
    calls' length (under ~5 min); the B2 fallback redirects instead of
    proxying, so range requests against it are B2's problem, not this
    process's."""
    call = await session.get(Call, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")

    audio_path = Path(call.audio_ref).resolve()
    local_ok = any(audio_path.is_relative_to(root) for root in ALLOWED_AUDIO_ROOTS) and audio_path.is_file()
    if local_ok:
        media_type = mimetypes.guess_type(str(audio_path))[0] or "application/octet-stream"
        return FileResponse(audio_path, media_type=media_type, filename=audio_path.name)

    if call.audio_backup_ref and call.audio_backup_ref.startswith(B2_REF_PREFIX):
        key = call.audio_backup_ref[len(B2_REF_PREFIX):]
        url = await presigned_url(key)
        if url:
            return RedirectResponse(url, status_code=307)

    raise HTTPException(status_code=404, detail="Audio file not found (no local copy, no durable backup)")


@router.get("/calls/{call_id}/status", response_model=CallStatusResponse)
async def get_call_status(call_id: str, session: AsyncSession = Depends(get_db)):
    call = await session.get(Call, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")

    progress = get_call_progress(call_id)
    if call.status == "COMPLETED":
        steps_completed, current_step = _STEP_ORDER, None
    elif call.status == "FAILED":
        steps_completed, current_step = [], None
    elif progress in _STEP_ORDER:
        idx = _STEP_ORDER.index(progress)
        steps_completed, current_step = _STEP_ORDER[:idx], progress
    else:
        # QUEUED and not yet picked up by the worker (or the worker is on a
        # different process instance — in-memory progress is only visible
        # within the process that's actually running this call).
        steps_completed, current_step = [], _STEP_ORDER[0]

    return CallStatusResponse(
        call_id=str(call.id),
        status=call.status,
        retry_count=call.retry_count,
        steps_completed=steps_completed,
        current_step=current_step,
    )
