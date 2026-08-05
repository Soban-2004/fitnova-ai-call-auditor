from datetime import datetime

from pydantic import BaseModel


class UploadResponse(BaseModel):
    call_id: str
    status: str
    message: str


class CallStatusResponse(BaseModel):
    call_id: str
    status: str
    retry_count: int
    steps_completed: list[str]
    current_step: str | None


class CallListItem(BaseModel):
    id: str
    advisor_id: str
    advisor_name: str
    team_name: str
    source_system: str
    duration_secs: int | None
    called_at: datetime | None
    status: str
    call_type: str | None
    diarization_quality: str
    latest_score: int | None
    issue_count: int
    created_at: datetime


class CallListResponse(BaseModel):
    calls: list[CallListItem]
    total: int
    limit: int
    offset: int


class TranscriptSegmentOut(BaseModel):
    id: str
    speaker_label: str | None
    speaker_role: str | None
    text: str
    start_ts: float
    end_ts: float


class IssueTagOut(BaseModel):
    id: str
    tag_type: str
    severity: str
    quote: str
    start_ts: float | None
    end_ts: float | None
    reason: str | None
    validation_score: float | None
    status: str
    contest_reason: str | None
    review_comment: str | None
    prompt_version: int | None


class DimensionRatingOut(BaseModel):
    dimension: str
    score: int
    evidence: str | None


class ScoreHistoryEntry(BaseModel):
    version: int
    base_score: float
    deductions_total: float
    final_score: int
    trigger: str
    computed_at: datetime
    reason: str | None = None
    changed_by: str | None = None


class CallDetail(BaseModel):
    id: str
    advisor_id: str
    advisor_name: str
    team_name: str
    source_system: str
    duration_secs: int | None
    called_at: datetime | None
    status: str
    call_type: str | None
    diarization_quality: str
    error_message: str | None

    transcript: list[TranscriptSegmentOut]
    issue_tags: list[IssueTagOut]
    dimension_ratings: list[DimensionRatingOut]
    score_history: list[ScoreHistoryEntry]
    current_score: int | None
