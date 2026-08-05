"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, User, Upload, Activity, PhoneCall } from "lucide-react";
import { api } from "@/lib/api";
import type { Advisor, Team } from "@/lib/types";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();
  const [teams, setTeams] = useState<Team[]>([]);
  const [advisors, setAdvisors] = useState<Advisor[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    Promise.all([api.listTeams(), api.listAdvisors()])
      .then(([t, a]) => {
        setTeams(t);
        setAdvisors(a);
      })
      .catch((err) => {
        console.error("Sidebar fetch failed:", err);
      })
      .finally(() => setLoaded(true));
  }, []);

  const advisorsByTeam = teams.map((team) => ({
    team,
    advisors: advisors.filter((a) => a.team_id === team.id),
  }));

  return (
    <aside
      className="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r"
      style={{ backgroundColor: "var(--surface-1)", borderColor: "var(--border)" }}
    >
      <div className="flex items-center gap-2 px-5 py-5">
        <Activity size={20} style={{ color: "var(--series-1)" }} />
        <span className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          FitNova
        </span>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          Call Intelligence
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-4">
        <SectionLabel>Browse</SectionLabel>
        <NavLink href="/calls" active={pathname === "/calls"}>
          <PhoneCall size={16} />
          All Calls
        </NavLink>

        <SectionLabel>Director</SectionLabel>
        <NavLink href="/dashboard/director" active={pathname === "/dashboard/director"}>
          <LayoutDashboard size={16} />
          Org Overview
        </NavLink>

        <SectionLabel>Team Leader</SectionLabel>
        {teams.map((team) => (
          <NavLink
            key={team.id}
            href={`/dashboard/team/${team.id}`}
            active={pathname === `/dashboard/team/${team.id}`}
          >
            <Users size={16} />
            {team.name}
          </NavLink>
        ))}
        {loaded && teams.length === 0 && <EmptyHint />}

        <SectionLabel>Advisor</SectionLabel>
        {advisorsByTeam.map(({ team, advisors: teamAdvisors }) => (
          <div key={team.id} className="mb-1">
            {teamAdvisors.map((advisor) => (
              <NavLink
                key={advisor.id}
                href={`/dashboard/advisor/${advisor.id}`}
                active={pathname === `/dashboard/advisor/${advisor.id}`}
                indent
              >
                <User size={14} />
                {advisor.name}
              </NavLink>
            ))}
          </div>
        ))}

        <SectionLabel>Demo</SectionLabel>
        <NavLink href="/upload" active={pathname === "/upload"}>
          <Upload size={16} />
          Upload a Call
        </NavLink>
      </nav>
    </aside>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-4 mb-1.5 px-2 text-[11px] font-semibold uppercase tracking-wide first:mt-0" style={{ color: "var(--text-muted)" }}>
      {children}
    </div>
  );
}

function EmptyHint() {
  return (
    <div className="px-2 py-1 text-xs" style={{ color: "var(--text-muted)" }}>
      No teams yet — run seed_db.py
    </div>
  );
}

function NavLink({
  href,
  active,
  indent,
  children,
}: {
  href: string;
  active: boolean;
  indent?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition-colors duration-150",
        indent && "ml-3",
        active
          ? "font-semibold text-[var(--series-1)] bg-[color-mix(in_srgb,var(--series-1)_12%,transparent)]"
          : "font-normal text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[color-mix(in_srgb,var(--text-secondary)_10%,transparent)]"
      )}
    >
      {children}
    </Link>
  );
}
