// Mirrors backend/app/schemas/*.py — kept hand-in-sync since this is a
// small, fixed API surface (no codegen needed at this scale).

export interface Org {
  id: string;
  name: string;
  created_at: string;
}

export interface Team {
  id: string;
  org_id: string;
  org_name: string;
  name: string;
  created_at: string;
}

export interface Advisor {
  id: string;
  team_id: string;
  team_name: string;
  name: string;
  email: string | null;
  created_at: string;
}

export interface CallListItem {
  id: string;
  advisor_id: string;
  advisor_name: string;
  team_name: string;
  source_system: string;
  duration_secs: number | null;
  called_at: string | null;
  status: string;
  call_type: string | null;
  diarization_quality: string;
  latest_score: number | null;
  issue_count: number;
  created_at: string;
}

export interface CallListResponse {
  calls: CallListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface CallListFilters {
  advisor_id?: string;
  team_id?: string;
  status?: string;
  call_type?: string;
  tag_type?: string;
  min_score?: number;
  max_score?: number;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export interface TranscriptSegmentOut {
  id: string;
  speaker_label: string | null;
  speaker_role: string | null;
  text: string;
  start_ts: number;
  end_ts: number;
}

export interface IssueTagOut {
  id: string;
  tag_type: string;
  severity: "critical" | "major" | "minor";
  quote: string;
  start_ts: number | null;
  end_ts: number | null;
  reason: string | null;
  validation_score: number | null;
  status: string;
  contest_reason: string | null;
  review_comment: string | null;
  prompt_version: number | null;
}

export interface DimensionRatingOut {
  dimension: string;
  score: number;
  evidence: string | null;
}

export interface ScoreHistoryEntry {
  version: number;
  base_score: number;
  deductions_total: number;
  final_score: number;
  trigger: string;
  computed_at: string;
  reason: string | null;
  changed_by: string | null;
}

export interface CallDetail {
  id: string;
  advisor_id: string;
  advisor_name: string;
  team_name: string;
  source_system: string;
  duration_secs: number | null;
  called_at: string | null;
  status: string;
  call_type: string | null;
  diarization_quality: string;
  error_message: string | null;
  transcript: TranscriptSegmentOut[];
  issue_tags: IssueTagOut[];
  dimension_ratings: DimensionRatingOut[];
  score_history: ScoreHistoryEntry[];
  current_score: number | null;
}

export interface ScoreTrendPoint {
  week: string;
  avg_score: number;
  call_count: number;
}

export interface DirectorDashboard {
  org_name: string;
  summary: {
    total_calls: number;
    avg_score: number | null;
    calls_this_week: number;
    score_trend: ScoreTrendPoint[];
  };
  score_distribution: { range: string; count: number }[];
  top_issues: { tag_type: string; count: number }[];
  team_comparison: {
    team_id: string;
    team_name: string;
    avg_score: number | null;
    call_count: number;
    top_issue: string | null;
  }[];
  attention_needed: { failed_calls: number; needs_review_tags: number };
}

export interface TeamDashboard {
  team_id: string;
  team_name: string;
  summary: { avg_score: number | null; call_count: number; score_trend: ScoreTrendPoint[] };
  advisor_leaderboard: {
    advisor_id: string;
    advisor_name: string;
    avg_score: number | null;
    call_count: number;
    trend: "up" | "down" | "flat";
    top_issue: string | null;
  }[];
  flagged_calls: {
    call_id: string;
    advisor_name: string;
    called_at: string | null;
    score: number | null;
    critical_tags: string[];
  }[];
  contest_queue: {
    tag_id: string;
    call_id: string;
    advisor_name: string;
    tag_type: string;
    severity: string;
    quote: string;
    contest_reason: string | null;
    contested_at: string | null;
  }[];
  issue_distribution: { tag_type: string; count: number }[];
}

export interface AdvisorDashboard {
  advisor_id: string;
  advisor_name: string;
  team_name: string;
  summary: {
    avg_score: number | null;
    call_count: number;
    best_score: number | null;
    worst_score: number | null;
    score_trend: ScoreTrendPoint[];
  };
  recent_calls: {
    call_id: string;
    called_at: string | null;
    duration_secs: number | null;
    score: number | null;
    issue_count: number;
    call_type: string | null;
  }[];
}
