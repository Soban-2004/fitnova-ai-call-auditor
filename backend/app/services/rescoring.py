"""Recalculates and versions a call's score after a tag's status changes
(design doc Section 7 "Score versioning — never overwrite" + Section 10
"What happens on dismiss").

Never UPDATEs an existing call_scores row — always INSERTs the next version
and writes a score_audit_log entry explaining the delta. The scoring math
itself is untouched: this just re-runs services.scoring.compute_score with
the current tag statuses and stores the result as a new version.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import DimensionRating, IssueTag
from app.models.score import CallScore, ScoreAuditLog
from app.services.scoring import compute_score


@dataclass
class RescoreResult:
    old_score: int
    new_score: int
    new_version: int


async def recalculate_score(
    session: AsyncSession,
    call_id: str,
    trigger: str,
    tag_id_affected: str | None,
    changed_by: str,
    reason: str,
) -> RescoreResult:
    dimensions = (
        await session.execute(select(DimensionRating).where(DimensionRating.call_id == call_id))
    ).scalars().all()
    dimension_dict = {d.dimension: {"score": d.score} for d in dimensions}

    tags = (await session.execute(select(IssueTag).where(IssueTag.call_id == call_id))).scalars().all()
    tag_dicts = [{"tag_type": t.tag_type, "severity": t.severity, "status": t.status} for t in tags]

    latest = (
        await session.execute(
            select(CallScore).where(CallScore.call_id == call_id).order_by(CallScore.version.desc())
        )
    ).scalars().first()
    old_version = latest.version if latest else 0
    old_score = latest.final_score if latest else 0
    new_version = old_version + 1

    result = compute_score(dimension_dict, tag_dicts)

    session.add(
        CallScore(
            call_id=call_id,
            version=new_version,
            base_score=result.base_score,
            deductions_total=result.deductions_total,
            final_score=result.final_score,
            trigger=trigger,
        )
    )
    session.add(
        ScoreAuditLog(
            call_id=call_id,
            from_version=old_version or None,
            to_version=new_version,
            tag_id_affected=tag_id_affected,
            delta=result.final_score - old_score,
            changed_by=changed_by,
            reason=reason,
        )
    )
    await session.flush()

    return RescoreResult(old_score=old_score, new_score=result.final_score, new_version=new_version)


async def log_confirmation(
    session: AsyncSession,
    call_id: str,
    tag_id: str,
    changed_by: str,
    reason: str,
) -> None:
    """Confirming a tag is a deliberate no-op for the score (design doc
    Section 10: "no-op for the scoring engine but still logged — it means a
    human agreed this tag is valid"). Unlike dismiss, this does NOT insert a
    new call_scores version (matches the API contract's confirm response,
    which returns score_updated=false with no new_version) — it only leaves
    an audit trail entry pointing at the unchanged current version.
    """
    latest = (
        await session.execute(
            select(CallScore).where(CallScore.call_id == call_id).order_by(CallScore.version.desc())
        )
    ).scalars().first()
    current_version = latest.version if latest else None

    session.add(
        ScoreAuditLog(
            call_id=call_id,
            from_version=current_version,
            to_version=current_version,
            tag_id_affected=tag_id,
            delta=0,
            changed_by=changed_by,
            reason=reason,
        )
    )
    await session.flush()
