"""Shared read-side query helpers for routers/calls.py and routers/dashboard.py.

Batches "latest score per call" / "open issue count per call" lookups across
a set of call_ids in one query each, rather than N+1-ing per call — the
dashboards can list dozens of calls per view.
"""
from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import IssueTag
from app.models.score import CallScore
from app.models.telemetry import LLMCallLog
from app.schemas.dashboard import ScoreTrendPoint


async def latest_scores_for_calls(session: AsyncSession, call_ids: list) -> dict[str, CallScore]:
    """One CallScore (the highest `version`) per call_id, or absent if the
    call hasn't been scored yet."""
    if not call_ids:
        return {}
    rows = (
        await session.execute(select(CallScore).where(CallScore.call_id.in_(call_ids)))
    ).scalars().all()
    latest: dict[str, CallScore] = {}
    for row in rows:
        key = str(row.call_id)
        if key not in latest or row.version > latest[key].version:
            latest[key] = row
    return latest


async def open_issue_counts_for_calls(session: AsyncSession, call_ids: list) -> dict[str, int]:
    if not call_ids:
        return {}
    rows = await session.execute(
        select(IssueTag.call_id, func.count(IssueTag.id))
        .where(IssueTag.call_id.in_(call_ids), IssueTag.status == "open")
        .group_by(IssueTag.call_id)
    )
    return {str(call_id): count for call_id, count in rows.all()}


async def critical_open_tags_for_calls(session: AsyncSession, call_ids: list) -> dict[str, list[str]]:
    if not call_ids:
        return {}
    rows = (
        await session.execute(
            select(IssueTag).where(
                IssueTag.call_id.in_(call_ids), IssueTag.status == "open", IssueTag.severity == "critical"
            )
        )
    ).scalars().all()
    result: dict[str, list[str]] = defaultdict(list)
    for tag in rows:
        result[str(tag.call_id)].append(tag.tag_type)
    return dict(result)


async def top_tag_types(session: AsyncSession, call_ids: list, limit: int = 5) -> list[tuple[str, int]]:
    if not call_ids:
        return []
    rows = await session.execute(
        select(IssueTag.tag_type, func.count(IssueTag.id).label("cnt"))
        .where(IssueTag.call_id.in_(call_ids), IssueTag.status == "open")
        .group_by(IssueTag.tag_type)
        .order_by(func.count(IssueTag.id).desc())
        .limit(limit)
    )
    return [(tag_type, cnt) for tag_type, cnt in rows.all()]


async def llm_call_stats(session: AsyncSession, since: datetime) -> list[dict]:
    """Aggregated call counts/latency/error breakdown per (provider, model,
    purpose, outcome) since a given timestamp -- see routers/admin.py, the
    only caller. The whole point of LLMCallLog: see at a glance which tier
    of the Groq->Gemini->Ollama chain is actually carrying traffic, and how
    often each one is failing, instead of grepping logs by hand."""
    rows = await session.execute(
        select(
            LLMCallLog.provider,
            LLMCallLog.model,
            LLMCallLog.purpose,
            LLMCallLog.outcome,
            func.count().label("count"),
            func.avg(LLMCallLog.latency_ms).label("avg_latency_ms"),
        )
        .where(LLMCallLog.created_at >= since)
        .group_by(LLMCallLog.provider, LLMCallLog.model, LLMCallLog.purpose, LLMCallLog.outcome)
        .order_by(LLMCallLog.provider, LLMCallLog.model, LLMCallLog.purpose)
    )
    return [
        {
            "provider": r.provider,
            "model": r.model,
            "purpose": r.purpose,
            "outcome": r.outcome,
            "count": r.count,
            "avg_latency_ms": round(float(r.avg_latency_ms), 1) if r.avg_latency_ms is not None else None,
        }
        for r in rows.all()
    ]


def build_score_trend(
    points: list[tuple[datetime | None, int]], weeks: int = 8
) -> list[ScoreTrendPoint]:
    """Groups (timestamp, final_score) pairs into ISO-week buckets and
    returns the most recent `weeks` of them, oldest first."""
    buckets: dict[str, list[int]] = defaultdict(list)
    for dt, score in points:
        if dt is None:
            continue
        iso_year, iso_week, _ = dt.isocalendar()
        buckets[f"{iso_year}-W{iso_week:02d}"].append(score)

    trend = [
        ScoreTrendPoint(week=week, avg_score=round(sum(scores) / len(scores), 1), call_count=len(scores))
        for week, scores in sorted(buckets.items())
    ]
    return trend[-weeks:] if weeks else trend
