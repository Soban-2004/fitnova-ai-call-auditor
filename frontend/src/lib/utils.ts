import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Score health -> status color role, matching the design doc's severity
 * color coding (red/amber/gray) extended to the score itself. */
export function scoreStatus(score: number | null | undefined): "good" | "warning" | "critical" | "muted" {
  if (score === null || score === undefined) return "muted";
  if (score >= 80) return "good";
  if (score >= 50) return "warning";
  return "critical";
}

/** Call.status -> status color role, matching the ternary already used on
 * the call detail page header — pulled out so the All Calls table can share
 * it instead of re-deriving the same three-way split. */
export function callStatusRole(status: string): "good" | "warning" | "critical" {
  if (status === "COMPLETED") return "good";
  if (status === "FAILED") return "critical";
  return "warning";
}

export function severityColorVar(severity: string): string {
  switch (severity) {
    case "critical":
      return "var(--status-critical)";
    case "major":
      return "var(--status-warning)";
    case "minor":
    default:
      return "var(--text-muted)";
  }
}

export function statusColorVar(status: "good" | "warning" | "critical" | "muted"): string {
  switch (status) {
    case "good":
      return "var(--status-good)";
    case "warning":
      return "var(--status-warning)";
    case "critical":
      return "var(--status-critical)";
    default:
      return "var(--text-muted)";
  }
}

export function formatDuration(secs: number | null | undefined): string {
  if (secs === null || secs === undefined) return "—";
  const m = Math.floor(secs / 60);
  const s = Math.round(secs % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function formatTagLabel(tag: string): string {
  return tag
    .split("_")
    .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
    .join(" ");
}

export function formatDimensionLabel(dim: string): string {
  return dim
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

// Fixed locale + explicit options (never `undefined`/omitted) so server-
// rendered HTML and client hydration always agree — Next.js SSR runs on the
// server's Node locale while the client uses the browser's, and the two
// don't always match (observed live: the server rendered "5/8/2026, 4:28 pm"
// while the browser rendered "8/5/2026, 4:28 PM" for the same timestamp),
// which throws a hydration error. Locking the locale removes the ambiguity.
const DATE_LOCALE = "en-GB";

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(DATE_LOCALE, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(DATE_LOCALE, { day: "numeric", month: "short", year: "numeric" });
}
