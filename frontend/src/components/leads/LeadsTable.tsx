"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import { Phone } from "lucide-react";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { MiniBar } from "@/components/ui/MiniBar";
import { EmptyState } from "@/components/dashboard/ScoreTrendChart";
import { api, ApiError } from "@/lib/api";
import { LEAD_STATUSES, type Advisor, type LeadOut, type LeadStatus } from "@/lib/types";
import { categoryColorVar, cn, formatDateTime, formatTagLabel, initials, scoreStatus } from "@/lib/utils";

const rowHoverClass = "transition-colors hover:bg-[color-mix(in_srgb,var(--series-1)_5%,transparent)]";

/** Horizontal New -> Assigned -> Contacted -> Trial Booked pipeline. Completed
 * and current stages fill with the accent; later stages stay outlined. Click
 * a stage to jump the lead there directly, instead of a separate dropdown. */
function StageTrack({
  status,
  onChange,
  disabled,
}: {
  status: LeadStatus;
  onChange: (status: LeadStatus) => void;
  disabled: boolean;
}) {
  const currentIndex = LEAD_STATUSES.indexOf(status);
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center">
        {LEAD_STATUSES.map((s, i) => {
          const reached = i <= currentIndex;
          const isLast = i === LEAD_STATUSES.length - 1;
          const color = s === "TRIAL_BOOKED" ? "var(--status-good)" : "var(--series-1)";
          return (
            <div key={s} className="flex items-center">
              <button
                type="button"
                disabled={disabled}
                onClick={() => onChange(s)}
                title={formatTagLabel(s)}
                aria-label={formatTagLabel(s)}
                aria-current={i === currentIndex}
                className="h-2.5 w-2.5 rounded-full transition-transform hover:scale-125 disabled:cursor-not-allowed"
                style={{
                  backgroundColor: reached ? color : "transparent",
                  border: reached ? "none" : "2px solid var(--border)",
                  boxShadow: i === currentIndex ? `0 0 0 3px color-mix(in srgb, ${color} 22%, transparent)` : "none",
                }}
              />
              {!isLast && (
                <div
                  className="h-0.5 w-4"
                  style={{ backgroundColor: i < currentIndex ? color : "var(--border)" }}
                />
              )}
            </div>
          );
        })}
      </div>
      <span className="text-[11px] font-medium" style={{ color: "var(--text-secondary)" }}>
        {formatTagLabel(status)}
      </span>
    </div>
  );
}

export function LeadsTable({ leads: initialLeads, advisors }: { leads: LeadOut[]; advisors: Advisor[] }) {
  const [leads, setLeads] = useState(initialLeads);
  const [errorFor, setErrorFor] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function patchLead(updated: LeadOut) {
    setLeads((prev) => prev.map((l) => (l.id === updated.id ? updated : l)));
  }

  function handleAssign(leadId: string, advisorId: string) {
    if (!advisorId) return;
    setErrorFor(null);
    startTransition(async () => {
      try {
        patchLead(await api.assignLead(leadId, advisorId));
      } catch (e) {
        setErrorFor(e instanceof ApiError ? e.message : "Failed to assign lead");
      }
    });
  }

  function handleStatus(leadId: string, status: LeadStatus) {
    setErrorFor(null);
    startTransition(async () => {
      try {
        patchLead(await api.updateLeadStatus(leadId, status));
      } catch (e) {
        setErrorFor(e instanceof ApiError ? e.message : "Failed to update status");
      }
    });
  }

  return (
    <Card>
      <CardContent className="pt-4">
        {errorFor && (
          <p className="mb-3 text-sm" style={{ color: "var(--status-critical)" }}>
            {errorFor}
          </p>
        )}
        {leads.length === 0 ? (
          <EmptyState message="No leads yet — the voice intake agent creates one whenever a qualification call finishes." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr
                  className="sticky top-0 z-10 border-b text-left text-xs uppercase"
                  style={{ borderColor: "var(--border)", color: "var(--text-muted)", backgroundColor: "var(--surface-1)" }}
                >
                  <th className="pb-2 pr-3 font-medium">Customer</th>
                  <th className="pb-2 pr-3 font-medium">Goal</th>
                  <th className="pb-2 pr-3 font-medium">Confirmed time</th>
                  <th className="pb-2 pr-3 text-right font-medium">Intake score</th>
                  <th className="pb-2 pr-3 font-medium">Assigned to</th>
                  <th className="pb-2 pr-3 font-medium">Pipeline stage</th>
                  <th className="pb-2 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr
                    key={lead.id}
                    className={cn("border-b last:border-0", rowHoverClass)}
                    style={{ borderColor: "var(--gridline)" }}
                  >
                    <td className="py-2.5 pr-3">
                      <Link
                        href={`/call/${lead.call_id}`}
                        className="font-medium hover:underline"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {lead.customer_name ?? "Unknown caller"}
                      </Link>
                      {lead.customer_phone && (
                        <div className="mt-0.5 flex items-center gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
                          <Phone size={11} />
                          {lead.customer_phone}
                        </div>
                      )}
                    </td>
                    <td className="py-2.5 pr-3 max-w-xs" style={{ color: "var(--text-secondary)" }}>
                      {lead.fitness_goal ?? "—"}
                    </td>
                    <td className="py-2.5 pr-3" style={{ color: "var(--text-secondary)" }}>
                      {lead.confirmed_time ?? "—"}
                    </td>
                    <td className="py-2.5 pr-3">
                      <div className="flex items-center justify-end gap-2">
                        {lead.call_score !== null && <MiniBar value={lead.call_score} role={scoreStatus(lead.call_score)} />}
                        <Badge role={scoreStatus(lead.call_score)} className="tabular-nums">
                          {lead.call_score ?? "—"}
                        </Badge>
                      </div>
                    </td>
                    <td className="py-2.5 pr-3">
                      <div className="flex items-center gap-2">
                        {lead.assigned_advisor_id && (
                          <span
                            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold"
                            style={{
                              backgroundColor: `color-mix(in srgb, ${categoryColorVar(lead.assigned_advisor_id)} 18%, transparent)`,
                              color: categoryColorVar(lead.assigned_advisor_id),
                            }}
                          >
                            {initials(lead.assigned_advisor_name)}
                          </span>
                        )}
                        <select
                          value={lead.assigned_advisor_id ?? ""}
                          onChange={(e) => handleAssign(lead.id, e.target.value)}
                          disabled={isPending}
                          className="rounded-lg border px-2 py-1 text-xs transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--series-1)]"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text-primary)" }}
                        >
                          <option value="">Unassigned</option>
                          {advisors.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      {lead.assigned_advisor_id && (
                        <Link
                          href={`/live?advisor_id=${lead.assigned_advisor_id}`}
                          className="mt-1 flex items-center gap-1 text-xs hover:underline"
                          style={{ color: "var(--series-1)" }}
                        >
                          <Phone size={11} />
                          Call now
                        </Link>
                      )}
                    </td>
                    <td className="py-2.5 pr-3">
                      <StageTrack
                        status={lead.status}
                        disabled={isPending}
                        onChange={(s) => handleStatus(lead.id, s)}
                      />
                    </td>
                    <td className="py-2.5" style={{ color: "var(--text-muted)" }}>
                      {formatDateTime(lead.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
