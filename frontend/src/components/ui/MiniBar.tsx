import { statusColorVar, type StatusRole } from "@/lib/utils";

/** Thin inline magnitude bar for a 0-100 value, paired with a score badge in
 * dense tables so the number's scale reads at a glance instead of only its
 * color band (h/t Feedly's dashboard panels, where every metric row carries
 * a bar alongside the figure, not just the figure alone). */
export function MiniBar({ value, role, width = 32 }: { value: number; role: StatusRole; width?: number }) {
  const pct = Math.max(0, Math.min(100, value));
  const color = statusColorVar(role);
  return (
    <span
      className="inline-block h-1.5 shrink-0 overflow-hidden rounded-full align-middle"
      style={{ width, backgroundColor: "var(--gridline)" }}
    >
      <span className="block h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
    </span>
  );
}
