"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { formatTagLabel } from "@/lib/utils";
import type { Advisor, Team } from "@/lib/types";

const STATUS_OPTIONS = ["QUEUED", "TRANSCRIBING", "ANALYZING", "COMPLETED", "FAILED"];
// Mirrors backend/app/schemas/analysis.py's call_type Literal.
const CALL_TYPE_OPTIONS = ["sales", "non_sales", "unclear"];
// Mirrors backend/app/schemas/analysis.py's ISSUE_TAG_TYPES.
const TAG_TYPE_OPTIONS = [
  "NO_NEEDS_DISCOVERY",
  "OVER_PROMISING",
  "PRESSURE_SELLING",
  "PRICE_BEFORE_VALUE",
  "UNDISCLOSED_COSTS",
  "WEAK_TRIAL_BOOKING",
  "NO_TRIAL_BOOKING",
  "TALKING_OVER_CUSTOMER",
  "NO_OBJECTION_HANDLING",
  "NO_NEXT_STEPS",
  "COMPLIANCE_VIOLATION",
];

const selectCls = "rounded-lg border bg-transparent px-2 py-1.5 text-sm";
const selectStyle = { borderColor: "var(--border)", color: "var(--text-primary)" };

export function CallsFilterBar({ teams, advisors }: { teams: Team[]; advisors: Advisor[] }) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [teamId, setTeamId] = useState(searchParams.get("team_id") ?? "");
  const [advisorId, setAdvisorId] = useState(searchParams.get("advisor_id") ?? "");
  const [status, setStatus] = useState(searchParams.get("status") ?? "");
  const [callType, setCallType] = useState(searchParams.get("call_type") ?? "");
  const [tagType, setTagType] = useState(searchParams.get("tag_type") ?? "");
  const [minScore, setMinScore] = useState(searchParams.get("min_score") ?? "");
  const [maxScore, setMaxScore] = useState(searchParams.get("max_score") ?? "");
  const [dateFrom, setDateFrom] = useState(searchParams.get("date_from") ?? "");
  const [dateTo, setDateTo] = useState(searchParams.get("date_to") ?? "");

  function apply() {
    const params = new URLSearchParams();
    const set = (key: string, value: string) => {
      if (value) params.set(key, value);
    };
    set("team_id", teamId);
    set("advisor_id", advisorId);
    set("status", status);
    set("call_type", callType);
    set("tag_type", tagType);
    set("min_score", minScore);
    set("max_score", maxScore);
    set("date_from", dateFrom);
    set("date_to", dateTo);
    router.push(`/calls${params.size ? `?${params}` : ""}`);
  }

  function clear() {
    setTeamId("");
    setAdvisorId("");
    setStatus("");
    setCallType("");
    setTagType("");
    setMinScore("");
    setMaxScore("");
    setDateFrom("");
    setDateTo("");
    router.push("/calls");
  }

  return (
    <div
      className="flex flex-wrap items-end gap-3 rounded-xl border p-4"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-1)" }}
    >
      <Field label="Team">
        <select className={selectCls} style={selectStyle} value={teamId} onChange={(e) => setTeamId(e.target.value)}>
          <option value="">All teams</option>
          {teams.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Advisor">
        <select
          className={selectCls}
          style={selectStyle}
          value={advisorId}
          onChange={(e) => setAdvisorId(e.target.value)}
        >
          <option value="">All advisors</option>
          {advisors
            .filter((a) => !teamId || a.team_id === teamId)
            .map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
        </select>
      </Field>

      <Field label="Status">
        <select className={selectCls} style={selectStyle} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any status</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Call type">
        <select
          className={selectCls}
          style={selectStyle}
          value={callType}
          onChange={(e) => setCallType(e.target.value)}
        >
          <option value="">Any type</option>
          {CALL_TYPE_OPTIONS.map((c) => (
            <option key={c} value={c}>
              {formatTagLabel(c)}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Flagged for">
        <select className={selectCls} style={selectStyle} value={tagType} onChange={(e) => setTagType(e.target.value)}>
          <option value="">Any issue</option>
          {TAG_TYPE_OPTIONS.map((t) => (
            <option key={t} value={t}>
              {formatTagLabel(t)}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Min score">
        <input
          type="number"
          min={0}
          max={100}
          className={`${selectCls} w-20`}
          style={selectStyle}
          value={minScore}
          onChange={(e) => setMinScore(e.target.value)}
        />
      </Field>

      <Field label="Max score">
        <input
          type="number"
          min={0}
          max={100}
          className={`${selectCls} w-20`}
          style={selectStyle}
          value={maxScore}
          onChange={(e) => setMaxScore(e.target.value)}
        />
      </Field>

      <Field label="From">
        <input
          type="date"
          className={selectCls}
          style={selectStyle}
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
        />
      </Field>

      <Field label="To">
        <input
          type="date"
          className={selectCls}
          style={selectStyle}
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
        />
      </Field>

      <div className="flex gap-2">
        <Button variant="primary" onClick={apply}>
          Apply
        </Button>
        <Button variant="ghost" onClick={clear}>
          Clear
        </Button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
        {label}
      </label>
      {children}
    </div>
  );
}
