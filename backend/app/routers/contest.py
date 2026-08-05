"""Tag lifecycle state machine (design doc Section 10):

OPEN -> [advisor contests] -> CONTESTED -> [team leader confirms] -> CONFIRMED (no-op)
                                         -> [team leader dismisses] -> DISMISSED (recalculates score)
NEEDS_REVIEW (from validator) -> [team leader reviews] -> CONFIRMED or DISMISSED (same as above)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.analysis import IssueTag
from app.schemas.contest import ContestRequest, ContestResponse, ReviewRequest, ReviewResponse
from app.services.rescoring import log_confirmation, recalculate_score

router = APIRouter(prefix="/api/tags", tags=["contest"])


@router.post("/{tag_id}/contest", response_model=ContestResponse)
async def contest_tag(tag_id: str, body: ContestRequest, session: AsyncSession = Depends(get_db)):
    tag = await session.get(IssueTag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail=f"Tag {tag_id} not found")
    if tag.status != "open":
        raise HTTPException(
            status_code=409,
            detail=f"Tag is '{tag.status}' — only 'open' tags can be contested",
        )

    tag.status = "contested"
    tag.contest_reason = body.reason
    await session.commit()

    return ContestResponse(tag_id=str(tag.id), status=tag.status, message="Tag contested successfully")


@router.post("/{tag_id}/review", response_model=ReviewResponse)
async def review_tag(tag_id: str, body: ReviewRequest, session: AsyncSession = Depends(get_db)):
    tag = await session.get(IssueTag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail=f"Tag {tag_id} not found")
    if tag.status not in ("contested", "needs_review"):
        raise HTTPException(
            status_code=409,
            detail=f"Tag is '{tag.status}' — only 'contested' or 'needs_review' tags can be reviewed",
        )

    tag.review_comment = body.comment
    tag.reviewed_by = body.reviewed_by

    if body.action == "confirm":
        tag.status = "confirmed"
        await log_confirmation(
            session,
            call_id=str(tag.call_id),
            tag_id=str(tag.id),
            changed_by=body.reviewed_by,
            reason=body.comment or "Tag confirmed as valid",
        )
        await session.commit()
        return ReviewResponse(tag_id=str(tag.id), status=tag.status, score_updated=False)

    # dismiss
    tag.status = "dismissed"
    await session.flush()  # tag.status must be committed-visible before recompute reads it back
    rescore = await recalculate_score(
        session,
        call_id=str(tag.call_id),
        trigger=f"tag_dismissed:{tag.id}",
        tag_id_affected=str(tag.id),
        changed_by=body.reviewed_by,
        reason=body.comment or "Tag dismissed",
    )
    await session.commit()

    return ReviewResponse(
        tag_id=str(tag.id),
        status=tag.status,
        score_updated=True,
        old_score=rescore.old_score,
        new_score=rescore.new_score,
        new_version=rescore.new_version,
    )
