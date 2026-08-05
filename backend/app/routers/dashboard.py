"""Dashboard read endpoints (design doc Section 9).

Scoring aggregates (avg_score, score_distribution, top_issues, team/advisor
comparisons) are scoped to status='COMPLETED' AND call_type='sales' — the
design doc calls out that non-sales calls (wrong numbers, internal calls)
must be "excluded from scoring aggregates". Call *volume* counts (total_calls,
flagged/recent call lists) are not scoped this way — those describe what
came through the pipeline, not how it scored.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.analysis import IssueTag
from app.models.call import Call
from app.models.org import Advisor, Org, Team
from app.schemas.dashboard import (
    AdvisorDashboard,
    AdvisorLeaderboardRow,
    AdvisorRecentCall,
    AdvisorSummary,
    AttentionNeeded,
    ContestQueueItem,
    DirectorDashboard,
    DirectorSummary,
    FlaggedCall,
    IssueDistributionRow,
    ScoreDistributionBucket,
    ScoreTrendResponse,
    TeamComparisonRow,
    TeamDashboard,
    TeamSummary,
    TopIssue,
)
from app.services.query_helpers import (
    build_score_trend,
    critical_open_tags_for_calls,
    latest_scores_for_calls,
    open_issue_counts_for_calls,
    top_tag_types,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

SCORE_BUCKETS = [("0-20", 0, 20), ("21-40", 21, 40), ("41-60", 41, 60), ("61-80", 61, 80), ("81-100", 81, 100)]


async def _scoring_calls(session: AsyncSession, advisor_ids: list[str] | None = None) -> list[Call]:
    """COMPLETED + call_type='sales' calls — the set every scoring aggregate
    in this router is computed over."""
    query = select(Call).where(Call.status == "COMPLETED", Call.call_type == "sales")
    if advisor_ids is not None:
        query = query.where(Call.advisor_id.in_(advisor_ids))
    return (await session.execute(query)).scalars().all()


def _bucket_scores(scores: list[int]) -> list[ScoreDistributionBucket]:
    buckets = {label: 0 for label, _, _ in SCORE_BUCKETS}
    for score in scores:
        for label, lo, hi in SCORE_BUCKETS:
            if lo <= score <= hi:
                buckets[label] += 1
                break
    return [ScoreDistributionBucket(range=label, count=buckets[label]) for label, _, _ in SCORE_BUCKETS]


def _trend_direction(scores_in_order: list[int]) -> str:
    """Simple, explainable heuristic: split into two halves (chronological),
    compare average of the second half against the first. Not a regression —
    intentionally simple enough to defend in the demo."""
    if len(scores_in_order) < 2:
        return "flat"
    mid = len(scores_in_order) // 2
    first_half, second_half = scores_in_order[:mid], scores_in_order[mid:]
    if not first_half or not second_half:
        return "flat"
    delta = (sum(second_half) / len(second_half)) - (sum(first_half) / len(first_half))
    if delta > 2:
        return "up"
    if delta < -2:
        return "down"
    return "flat"


@router.get("/trend", response_model=ScoreTrendResponse)
async def score_trend(
    scope: str,
    id: str | None = None,
    weeks: int = Query(8, ge=1, le=26),
    session: AsyncSession = Depends(get_db),
):
    """Backs the trend chart's week-range selector (4/8/12 weeks) so the
    frontend can re-fetch just the trend line instead of the whole dashboard
    payload when the user changes the window. Same scoring-call rules as the
    embedded trend on each dashboard (COMPLETED + call_type='sales')."""
    if scope == "org":
        scoring_calls = await _scoring_calls(session)
    elif scope == "team":
        if not id:
            raise HTTPException(status_code=400, detail="id is required for scope=team")
        team = await session.get(Team, id)
        if team is None:
            raise HTTPException(status_code=404, detail=f"Team {id} not found")
        advisor_ids = [
            str(a.id) for a in (await session.execute(select(Advisor).where(Advisor.team_id == id))).scalars().all()
        ]
        scoring_calls = await _scoring_calls(session, advisor_ids)
    elif scope == "advisor":
        if not id:
            raise HTTPException(status_code=400, detail="id is required for scope=advisor")
        advisor = await session.get(Advisor, id)
        if advisor is None:
            raise HTTPException(status_code=404, detail=f"Advisor {id} not found")
        scoring_calls = await _scoring_calls(session, [id])
    else:
        raise HTTPException(status_code=400, detail="scope must be one of: org, team, advisor")

    scoring_call_ids = [str(c.id) for c in scoring_calls]
    latest_scores = await latest_scores_for_calls(session, scoring_call_ids)
    trend_points = [
        (c.called_at, latest_scores[str(c.id)].final_score) for c in scoring_calls if str(c.id) in latest_scores
    ]
    return ScoreTrendResponse(trend=build_score_trend(trend_points, weeks=weeks))


@router.get("/director", response_model=DirectorDashboard)
async def director_dashboard(session: AsyncSession = Depends(get_db)):
    org = (await session.execute(select(Org).limit(1))).scalar_one_or_none()
    org_name = org.name if org else "FitNova"

    all_calls = (await session.execute(select(Call))).scalars().all()
    total_calls = len(all_calls)

    scoring_calls = [c for c in all_calls if c.status == "COMPLETED" and c.call_type == "sales"]
    scoring_call_ids = [str(c.id) for c in scoring_calls]
    latest_scores = await latest_scores_for_calls(session, scoring_call_ids)

    final_scores = [latest_scores[cid].final_score for cid in scoring_call_ids if cid in latest_scores]
    avg_score = round(sum(final_scores) / len(final_scores), 1) if final_scores else None

    week_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    calls_this_week = sum(1 for c in all_calls if c.called_at and c.called_at >= week_cutoff)

    trend_points = [
        (c.called_at, latest_scores[str(c.id)].final_score)
        for c in scoring_calls
        if str(c.id) in latest_scores
    ]
    score_trend = build_score_trend(trend_points)

    score_distribution = _bucket_scores(final_scores)
    top_issues_raw = await top_tag_types(session, scoring_call_ids, limit=5)
    top_issues = [TopIssue(tag_type=t, count=c) for t, c in top_issues_raw]

    # --- team comparison ---
    teams = (await session.execute(select(Team))).scalars().all()
    advisors = (await session.execute(select(Advisor))).scalars().all()
    advisors_by_team: dict[str, list[str]] = defaultdict(list)
    for a in advisors:
        advisors_by_team[str(a.team_id)].append(str(a.id))

    team_comparison = []
    for team in teams:
        team_advisor_ids = advisors_by_team.get(str(team.id), [])
        team_calls = [c for c in scoring_calls if str(c.advisor_id) in team_advisor_ids]
        team_call_ids = [str(c.id) for c in team_calls]
        team_scores = [latest_scores[cid].final_score for cid in team_call_ids if cid in latest_scores]
        team_top = await top_tag_types(session, team_call_ids, limit=1)
        team_comparison.append(
            TeamComparisonRow(
                team_id=str(team.id),
                team_name=team.name,
                avg_score=round(sum(team_scores) / len(team_scores), 1) if team_scores else None,
                call_count=len(team_calls),
                top_issue=team_top[0][0] if team_top else None,
            )
        )

    failed_calls = sum(1 for c in all_calls if c.status == "FAILED")
    needs_review_tags = (
        await session.execute(select(IssueTag).where(IssueTag.status == "needs_review"))
    ).scalars().all()

    return DirectorDashboard(
        org_name=org_name,
        summary=DirectorSummary(
            total_calls=total_calls, avg_score=avg_score, calls_this_week=calls_this_week, score_trend=score_trend
        ),
        score_distribution=score_distribution,
        top_issues=top_issues,
        team_comparison=team_comparison,
        attention_needed=AttentionNeeded(failed_calls=failed_calls, needs_review_tags=len(needs_review_tags)),
    )


@router.get("/team/{team_id}", response_model=TeamDashboard)
async def team_dashboard(team_id: str, session: AsyncSession = Depends(get_db)):
    team = await session.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")

    advisors = (await session.execute(select(Advisor).where(Advisor.team_id == team_id))).scalars().all()
    advisor_ids = [str(a.id) for a in advisors]
    advisor_names = {str(a.id): a.name for a in advisors}

    scoring_calls = await _scoring_calls(session, advisor_ids)
    scoring_call_ids = [str(c.id) for c in scoring_calls]
    latest_scores = await latest_scores_for_calls(session, scoring_call_ids)
    final_scores = [latest_scores[cid].final_score for cid in scoring_call_ids if cid in latest_scores]

    trend_points = [
        (c.called_at, latest_scores[str(c.id)].final_score) for c in scoring_calls if str(c.id) in latest_scores
    ]
    score_trend = build_score_trend(trend_points)

    # --- advisor leaderboard ---
    leaderboard = []
    for advisor in advisors:
        advisor_calls = sorted(
            [c for c in scoring_calls if str(c.advisor_id) == str(advisor.id)],
            key=lambda c: c.called_at or c.created_at,
        )
        advisor_call_ids = [str(c.id) for c in advisor_calls]
        advisor_scores = [latest_scores[cid].final_score for cid in advisor_call_ids if cid in latest_scores]
        top = await top_tag_types(session, advisor_call_ids, limit=1)
        leaderboard.append(
            AdvisorLeaderboardRow(
                advisor_id=str(advisor.id),
                advisor_name=advisor.name,
                avg_score=round(sum(advisor_scores) / len(advisor_scores), 1) if advisor_scores else None,
                call_count=len(advisor_calls),
                trend=_trend_direction(advisor_scores),
                top_issue=top[0][0] if top else None,
            )
        )
    leaderboard.sort(key=lambda row: row.avg_score or 0, reverse=True)

    # --- flagged calls: any (COMPLETED) call on this team with an open critical tag ---
    team_calls_all = (
        await session.execute(
            select(Call).where(Call.advisor_id.in_(advisor_ids), Call.status == "COMPLETED")
        )
    ).scalars().all()
    team_call_ids_all = [str(c.id) for c in team_calls_all]
    critical_tags_map = await critical_open_tags_for_calls(session, team_call_ids_all)
    all_latest_scores = await latest_scores_for_calls(session, team_call_ids_all)

    flagged_calls = [
        FlaggedCall(
            call_id=str(c.id),
            advisor_name=advisor_names.get(str(c.advisor_id), "Unknown"),
            called_at=c.called_at.isoformat() if c.called_at else None,
            score=all_latest_scores[str(c.id)].final_score if str(c.id) in all_latest_scores else None,
            critical_tags=critical_tags_map[str(c.id)],
        )
        for c in sorted(team_calls_all, key=lambda c: c.called_at or c.created_at, reverse=True)
        if str(c.id) in critical_tags_map
    ]

    # --- contest queue: tags awaiting a Team Leader decision ---
    contested = (
        await session.execute(
            select(IssueTag, Call.advisor_id)
            .join(Call, IssueTag.call_id == Call.id)
            .where(Call.advisor_id.in_(advisor_ids), IssueTag.status == "contested")
            .order_by(IssueTag.updated_at.desc())
        )
    ).all()
    contest_queue = [
        ContestQueueItem(
            tag_id=str(tag.id),
            call_id=str(tag.call_id),
            advisor_name=advisor_names.get(str(advisor_id), "Unknown"),
            tag_type=tag.tag_type,
            severity=tag.severity,
            quote=tag.quote,
            contest_reason=tag.contest_reason,
            contested_at=tag.updated_at.isoformat() if tag.updated_at else None,
        )
        for tag, advisor_id in contested
    ]

    issue_distribution_raw = await top_tag_types(session, scoring_call_ids, limit=10)
    issue_distribution = [IssueDistributionRow(tag_type=t, count=c) for t, c in issue_distribution_raw]

    return TeamDashboard(
        team_id=str(team.id),
        team_name=team.name,
        summary=TeamSummary(
            avg_score=round(sum(final_scores) / len(final_scores), 1) if final_scores else None,
            call_count=len(scoring_calls),
            score_trend=score_trend,
        ),
        advisor_leaderboard=leaderboard,
        flagged_calls=flagged_calls,
        contest_queue=contest_queue,
        issue_distribution=issue_distribution,
    )


@router.get("/advisor/{advisor_id}", response_model=AdvisorDashboard)
async def advisor_dashboard(advisor_id: str, session: AsyncSession = Depends(get_db)):
    advisor = await session.get(Advisor, advisor_id)
    if advisor is None:
        raise HTTPException(status_code=404, detail=f"Advisor {advisor_id} not found")
    team = await session.get(Team, advisor.team_id)

    scoring_calls = await _scoring_calls(session, [advisor_id])
    scoring_call_ids = [str(c.id) for c in scoring_calls]
    latest_scores = await latest_scores_for_calls(session, scoring_call_ids)
    final_scores = [latest_scores[cid].final_score for cid in scoring_call_ids if cid in latest_scores]

    trend_points = [
        (c.called_at, latest_scores[str(c.id)].final_score) for c in scoring_calls if str(c.id) in latest_scores
    ]
    score_trend = build_score_trend(trend_points)

    # recent_calls covers all statuses/types (an advisor should see every
    # call they made, not just the ones counted in their scoring average)
    recent_calls_raw = (
        await session.execute(
            select(Call)
            .where(Call.advisor_id == advisor_id)
            .order_by((Call.called_at).desc().nulls_last(), Call.created_at.desc())
            .limit(25)
        )
    ).scalars().all()
    recent_call_ids = [str(c.id) for c in recent_calls_raw]
    recent_latest_scores = await latest_scores_for_calls(session, recent_call_ids)
    recent_issue_counts = await open_issue_counts_for_calls(session, recent_call_ids)

    recent_calls = [
        AdvisorRecentCall(
            call_id=str(c.id),
            called_at=c.called_at.isoformat() if c.called_at else None,
            duration_secs=c.duration_secs,
            score=recent_latest_scores[str(c.id)].final_score if str(c.id) in recent_latest_scores else None,
            issue_count=recent_issue_counts.get(str(c.id), 0),
            call_type=c.call_type,
        )
        for c in recent_calls_raw
    ]

    return AdvisorDashboard(
        advisor_id=str(advisor.id),
        advisor_name=advisor.name,
        team_name=team.name if team else "Unknown",
        summary=AdvisorSummary(
            avg_score=round(sum(final_scores) / len(final_scores), 1) if final_scores else None,
            call_count=len(scoring_calls),
            best_score=max(final_scores) if final_scores else None,
            worst_score=min(final_scores) if final_scores else None,
            score_trend=score_trend,
        ),
        recent_calls=recent_calls,
    )
