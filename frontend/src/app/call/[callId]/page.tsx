import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { CallDetailClient } from "@/components/call/CallDetailClient";
import { Badge } from "@/components/ui/Badge";
import { api, ApiError } from "@/lib/api";
import { callStatusRole, formatDateTime, formatDuration } from "@/lib/utils";

export const dynamic = "force-dynamic";

const DIARIZATION_LABEL: Record<string, string> = {
  good: "Diarization: good",
  mono: "Diarization: mono / single speaker detected",
};

export default async function CallDetailPage({ params }: { params: Promise<{ callId: string }> }) {
  const { callId } = await params;
  let call;
  try {
    call = await api.callDetail(callId);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <div className="p-6 lg:p-8">
      <Link href={`/dashboard/advisor/${call.advisor_id}`} className="mb-4 inline-flex items-center gap-1 text-sm hover:underline" style={{ color: "var(--text-muted)" }}>
        <ArrowLeft size={14} />
        Back to {call.advisor_name}
      </Link>

      <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
            Call with {call.advisor_name}
          </h1>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            {call.team_name} · {formatDateTime(call.called_at)} ·{" "}
            {formatDuration(call.duration_secs)}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge role={callStatusRole(call.status)}>
            {call.status}
          </Badge>
          {call.call_type && <Badge role="muted">{call.call_type}</Badge>}
          {call.diarization_quality !== "good" && (
            <Badge role="warning">{DIARIZATION_LABEL[call.diarization_quality] ?? call.diarization_quality}</Badge>
          )}
        </div>
      </header>

      {call.status === "FAILED" && call.error_message && (
        <div className="mb-4 rounded-lg border px-4 py-3 text-sm" style={{ borderColor: "var(--status-critical)", color: "var(--status-critical)" }}>
          Processing failed: {call.error_message}
        </div>
      )}

      <CallDetailClient callId={callId} initialCall={call} />
    </div>
  );
}
