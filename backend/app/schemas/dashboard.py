from pydantic import BaseModel


class ScoreTrendPoint(BaseModel):
    week: str
    avg_score: float
    call_count: int


class ScoreTrendResponse(BaseModel):
    trend: list[ScoreTrendPoint]


class DirectorSummary(BaseModel):
    total_calls: int
    avg_score: float | None
    calls_this_week: int
    score_trend: list[ScoreTrendPoint]


class ScoreDistributionBucket(BaseModel):
    range: str
    count: int


class TopIssue(BaseModel):
    tag_type: str
    count: int


class TeamComparisonRow(BaseModel):
    team_id: str
    team_name: str
    avg_score: float | None
    call_count: int
    top_issue: str | None


class AttentionNeeded(BaseModel):
    failed_calls: int
    needs_review_tags: int


class DirectorDashboard(BaseModel):
    org_name: str
    summary: DirectorSummary
    score_distribution: list[ScoreDistributionBucket]
    top_issues: list[TopIssue]
    team_comparison: list[TeamComparisonRow]
    attention_needed: AttentionNeeded


class TeamSummary(BaseModel):
    avg_score: float | None
    call_count: int
    score_trend: list[ScoreTrendPoint]


class AdvisorLeaderboardRow(BaseModel):
    advisor_id: str
    advisor_name: str
    avg_score: float | None
    call_count: int
    trend: str  # 'up' | 'down' | 'flat'
    top_issue: str | None


class FlaggedCall(BaseModel):
    call_id: str
    advisor_name: str
    called_at: str | None
    score: int | None
    critical_tags: list[str]


class ContestQueueItem(BaseModel):
    tag_id: str
    call_id: str
    advisor_name: str
    tag_type: str
    severity: str
    quote: str
    contest_reason: str | None
    contested_at: str | None


class IssueDistributionRow(BaseModel):
    tag_type: str
    count: int


class TeamDashboard(BaseModel):
    team_id: str
    team_name: str
    summary: TeamSummary
    advisor_leaderboard: list[AdvisorLeaderboardRow]
    flagged_calls: list[FlaggedCall]
    contest_queue: list[ContestQueueItem]
    issue_distribution: list[IssueDistributionRow]


class AdvisorSummary(BaseModel):
    avg_score: float | None
    call_count: int
    best_score: int | None
    worst_score: int | None
    score_trend: list[ScoreTrendPoint]


class AdvisorRecentCall(BaseModel):
    call_id: str
    called_at: str | None
    duration_secs: int | None
    score: int | None
    issue_count: int
    call_type: str | None


class AdvisorDashboard(BaseModel):
    advisor_id: str
    advisor_name: str
    team_name: str
    summary: AdvisorSummary
    recent_calls: list[AdvisorRecentCall]
