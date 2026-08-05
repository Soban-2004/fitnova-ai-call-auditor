"use client";

import { CheckCircle2, XCircle } from "lucide-react";

/** A single ephemeral confirmation — the caller owns the timer (setTimeout
 * clearing its own state) and mounts/unmounts this rather than the component
 * managing its own lifetime, so there's exactly one source of truth for
 * "is a toast currently showing." */
export function Toast({ message, tone = "success" }: { message: string; tone?: "success" | "error" }) {
  const color = tone === "success" ? "var(--status-good)" : "var(--status-critical)";
  const Icon = tone === "success" ? CheckCircle2 : XCircle;

  return (
    <div
      role="status"
      className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm shadow-lg animate-[fadeIn_0.15s_ease-out]"
      style={{
        borderColor: "var(--border)",
        backgroundColor: "var(--surface-2)",
        color: "var(--text-primary)",
      }}
    >
      <Icon size={16} style={{ color }} />
      {message}
    </div>
  );
}
