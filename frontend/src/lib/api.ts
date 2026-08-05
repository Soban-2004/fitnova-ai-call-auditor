import type {
  Advisor,
  AdvisorDashboard,
  CallDetail,
  CallListFilters,
  CallListResponse,
  DirectorDashboard,
  ScoreTrendPoint,
  Team,
  TeamDashboard,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* body wasn't JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

export const api = {
  listTeams: () => apiFetch<Team[]>("/api/teams"),
  listAdvisors: (teamId?: string) =>
    apiFetch<Advisor[]>(`/api/advisors${teamId ? `?team_id=${teamId}` : ""}`),

  directorDashboard: () => apiFetch<DirectorDashboard>("/api/dashboard/director"),
  teamDashboard: (teamId: string) => apiFetch<TeamDashboard>(`/api/dashboard/team/${teamId}`),
  advisorDashboard: (advisorId: string) => apiFetch<AdvisorDashboard>(`/api/dashboard/advisor/${advisorId}`),

  scoreTrend: (scope: "org" | "team" | "advisor", id: string | undefined, weeks: number) => {
    const params = new URLSearchParams({ scope, weeks: String(weeks) });
    if (id) params.set("id", id);
    return apiFetch<{ trend: ScoreTrendPoint[] }>(`/api/dashboard/trend?${params}`);
  },

  callDetail: (callId: string) => apiFetch<CallDetail>(`/api/calls/${callId}`),

  listCalls: (filters: CallListFilters = {}) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
    }
    const qs = params.toString();
    return apiFetch<CallListResponse>(`/api/calls${qs ? `?${qs}` : ""}`);
  },

  audioUrl: (callId: string) => `${API_URL}/api/calls/${callId}/audio`,

  contestTag: (tagId: string, reason: string) =>
    apiFetch<{ tag_id: string; status: string; message: string }>(`/api/tags/${tagId}/contest`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  reviewTag: (tagId: string, action: "confirm" | "dismiss", comment: string, reviewedBy: string) =>
    apiFetch<{ tag_id: string; status: string; score_updated: boolean; old_score?: number; new_score?: number; new_version?: number }>(
      `/api/tags/${tagId}/review`,
      {
        method: "POST",
        body: JSON.stringify({ action, comment, reviewed_by: reviewedBy }),
      }
    ),

  upload: (formData: FormData) =>
    fetch(`${API_URL}/api/upload`, { method: "POST", body: formData }).then(async (res) => {
      const body = await res.json();
      if (!res.ok) throw new ApiError(res.status, body.detail || res.statusText);
      return body as { call_id: string; status: string; message: string };
    }),

  callStatus: (callId: string) =>
    apiFetch<{ call_id: string; status: string; retry_count: number; steps_completed: string[]; current_step: string | null }>(
      `/api/calls/${callId}/status`
    ),
};
