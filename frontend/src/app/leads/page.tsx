import { LeadsTable } from "@/components/leads/LeadsTable";
import { Card, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { api, ApiError } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function LeadsPage() {
  let leads;
  let advisors;
  try {
    [leads, advisors] = await Promise.all([api.listLeads(), api.listAdvisors()]);
  } catch (e) {
    return <ApiUnreachable error={e} />;
  }

  return (
    <div className="p-6 lg:p-8">
      <header className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Leads
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          The voice intake agent&apos;s hand-off to a human — every qualifying call it finishes lands here, ready
          to assign to an advisor and move toward a booked trial. {leads.length} total.
        </p>
      </header>

      <LeadsTable leads={leads} advisors={advisors} />
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
