import Link from "next/link";
import { CallsFilterBar } from "@/components/calls/CallsFilterBar";
import { CallsTable } from "@/components/calls/CallsTable";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { api, ApiError } from "@/lib/api";
import type { Advisor, Team } from "@/lib/types";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 25;

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

function buildPageHref(sp: Record<string, string | string[] | undefined>, page: number): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(sp)) {
    if (key === "page") continue;
    const val = first(value);
    if (val) params.set(key, val);
  }
  if (page > 1) params.set("page", String(page));
  const qs = params.toString();
  return `/calls${qs ? `?${qs}` : ""}`;
}

export default async function AllCallsPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const page = Math.max(1, Number(first(sp.page)) || 1);

  const filters = {
    advisor_id: first(sp.advisor_id),
    team_id: first(sp.team_id),
    status: first(sp.status),
    call_type: first(sp.call_type),
    tag_type: first(sp.tag_type),
    min_score: first(sp.min_score) ? Number(first(sp.min_score)) : undefined,
    max_score: first(sp.max_score) ? Number(first(sp.max_score)) : undefined,
    date_from: first(sp.date_from),
    date_to: first(sp.date_to),
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  };

  let data;
  let teams: Team[] = [];
  let advisors: Advisor[] = [];
  try {
    [data, teams, advisors] = await Promise.all([api.listCalls(filters), api.listTeams(), api.listAdvisors()]);
  } catch (e) {
    return <ApiUnreachable error={e} />;
  }

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  return (
    <div className="p-6 lg:p-8">
      <header className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          All Calls
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Browse, filter, and search every call the pipeline has processed — {data.total} total
        </p>
      </header>

      <CallsFilterBar teams={teams} advisors={advisors} />

      <div className="mt-4">
        <CallsTable calls={data.calls} />
      </div>

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between">
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <Link
              href={buildPageHref(sp, Math.max(1, page - 1))}
              aria-disabled={page <= 1}
              className="rounded-lg border px-3 py-1.5 text-sm"
              style={{
                borderColor: "var(--border)",
                color: page <= 1 ? "var(--text-muted)" : "var(--text-primary)",
                pointerEvents: page <= 1 ? "none" : "auto",
              }}
            >
              Previous
            </Link>
            <Link
              href={buildPageHref(sp, Math.min(totalPages, page + 1))}
              aria-disabled={page >= totalPages}
              className="rounded-lg border px-3 py-1.5 text-sm"
              style={{
                borderColor: "var(--border)",
                color: page >= totalPages ? "var(--text-muted)" : "var(--text-primary)",
                pointerEvents: page >= totalPages ? "none" : "auto",
              }}
            >
              Next
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

function ApiUnreachable({ error }: { error: unknown }) {
  const message = error instanceof ApiError ? error.message : "Could not reach the FitNova API.";
  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <Card className="max-w-md">
        <CardContent className="pt-4">
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Backend unreachable
          </p>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            {message}
          </p>
          <div className="mt-3">
            <Badge role="critical">offline</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
