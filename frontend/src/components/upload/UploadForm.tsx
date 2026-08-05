"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { UploadCloud, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { api, ApiError } from "@/lib/api";
import type { Advisor } from "@/lib/types";

const STEP_LABELS: Record<string, string> = {
  TRANSCRIPTION: "Transcribing (Deepgram)",
  PII_REDACTION: "Redacting PII",
  SPEAKER_ID: "Identifying speakers",
  ISSUE_DETECTION: "Detecting issues",
  DIMENSION_RATING: "Rating dimensions",
  SCORING: "Computing score",
};

export function UploadForm() {
  const router = useRouter();
  const [advisors, setAdvisors] = useState<Advisor[]>([]);
  const [advisorId, setAdvisorId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [state, setState] = useState<"idle" | "uploading" | "processing" | "done" | "error">("idle");
  const [callId, setCallId] = useState<string | null>(null);
  const [status, setStatus] = useState<{ status: string; current_step: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listAdvisors().then(setAdvisors).catch(() => {});
  }, []);

  useEffect(() => {
    if (state !== "processing" || !callId) return;
    const interval = setInterval(async () => {
      try {
        const s = await api.callStatus(callId);
        setStatus(s);
        if (s.status === "COMPLETED") {
          setState("done");
          clearInterval(interval);
        } else if (s.status === "FAILED") {
          setState("error");
          setError("Processing failed after retries — check the backend logs.");
          clearInterval(interval);
        }
      } catch {
        /* transient — keep polling */
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [state, callId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !advisorId) return;
    setState("uploading");
    setError(null);
    const formData = new FormData();
    formData.append("audio_file", file);
    formData.append("advisor_id", advisorId);
    try {
      const res = await api.upload(formData);
      setCallId(res.call_id);
      setState("processing");
    } catch (e) {
      setState("error");
      setError(e instanceof ApiError ? e.message : "Upload failed");
    }
  }

  return (
    <Card className="max-w-lg">
      <CardHeader className="flex-col items-start">
        <CardTitle>Upload a call</CardTitle>
        <CardDescription>
          Runs the full pipeline: transcription → diarization → analysis → scoring.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {state === "idle" || state === "uploading" ? (
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                Advisor
              </label>
              <select
                required
                value={advisorId}
                onChange={(e) => setAdvisorId(e.target.value)}
                className="w-full rounded-lg border px-2.5 py-1.5 text-sm"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text-primary)" }}
              >
                <option value="">Select advisor…</option>
                {advisors.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.team_name})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium" style={{ color: "var(--text-secondary)" }}>
                Audio file
              </label>
              <input
                required
                type="file"
                accept=".wav,.mp3,.ogg,.m4a,.webm"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="w-full text-sm"
              />
            </div>
            <Button type="submit" variant="primary" disabled={state === "uploading" || !file || !advisorId}>
              <UploadCloud size={16} />
              {state === "uploading" ? "Uploading…" : "Upload & process"}
            </Button>
          </form>
        ) : state === "processing" ? (
          <div className="flex flex-col items-center gap-3 py-4 text-center">
            <Loader2 className="animate-spin" size={28} style={{ color: "var(--series-1)" }} />
            <div>
              <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                {status?.current_step ? STEP_LABELS[status.current_step] ?? status.current_step : "Queued…"}
              </div>
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                This can take 1-2 minutes for a full call.
              </div>
            </div>
          </div>
        ) : state === "done" && callId ? (
          <div className="flex flex-col items-center gap-3 py-4 text-center">
            <CheckCircle2 size={28} style={{ color: "var(--status-good)" }} />
            <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              Call processed
            </div>
            <Button variant="primary" onClick={() => router.push(`/call/${callId}`)}>
              View results
            </Button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 py-4 text-center">
            <XCircle size={28} style={{ color: "var(--status-critical)" }} />
            <div className="text-sm" style={{ color: "var(--status-critical)" }}>
              {error}
            </div>
            <Button
              variant="secondary"
              onClick={() => {
                setState("idle");
                setCallId(null);
                setError(null);
              }}
            >
              Try again
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
