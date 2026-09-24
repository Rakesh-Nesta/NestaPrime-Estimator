import { useEffect, useRef, useState } from "react";
import { getDashboard, listClients, listOpportunities } from "./api";
import { CalendarIcon, ClockIcon, DocumentIcon, FolderIcon, FunnelIcon } from "./Icons";

// Small local duplicate of FollowUps.jsx's own due-date merge/sort (same
// pattern ClientsAdmin.jsx's STATUS_PILL_STYLE comment already documents)
// -- Clients (Amendment 43) and Opportunities (Amendment 44 Phase D) share
// one queue. Won/Lost Opportunities carry no date, so drop out naturally.
function dueFollowUps(clients, opportunities) {
  const today = new Date().toISOString().slice(0, 10);
  return [
    ...clients.map((c) => ({ id: c.id, kind: "client", name: c.name, next_follow_up_date: c.next_follow_up_date })),
    ...opportunities.map((o) => ({ id: o.id, kind: "opportunity", name: o.lead_name, next_follow_up_date: o.next_follow_up_date })),
  ]
    .filter((i) => i.next_follow_up_date)
    .sort((a, b) => a.next_follow_up_date.localeCompare(b.next_follow_up_date))
    .map((i) => ({
      ...i,
      status: i.next_follow_up_date < today ? "overdue" : i.next_follow_up_date === today ? "due" : "upcoming",
    }));
}

const PIPELINE_STAGES = [
  { key: "opportunities_new_count", label: "New" },
  { key: "opportunities_contacted_count", label: "Contacted" },
  { key: "opportunities_qualified_count", label: "Qualified" },
];

// Amendment 41 (Section 47): animates a KPI tile's arrival, real data only
// (Pending Quotations/Active Projects) -- never applied to a placeholder
// "--" tile. Respects prefers-reduced-motion by skipping straight to the
// final value.
function useCountUp(target) {
  const [value, setValue] = useState(0);
  const reduceMotion = useRef(
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );

  useEffect(() => {
    if (reduceMotion.current) {
      setValue(target);
      return;
    }
    let raf;
    const start = performance.now();
    const duration = 900;
    function step(now) {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setValue(Math.round(target * eased));
      if (p < 1) raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target]);

  return value;
}

// Amendment 4 (Annexure 2): "business-summary dashboard ... link back to
// dashboard from every section ... the app itself is the training." This
// is the post-login landing screen; onOpenProject resumes an existing
// project straight into its Documents stage (Cost Sheet/Estimate/
// Quotation), which is the concrete fix for the "no way to browse back
// into an existing project" gap found live during the 12 Sep validation run.
//
// Amendment 12 (Section 11): "which projects no Ans, then pending all are
// dead ... link all section with dashboard." Every tile below now drills
// through onDrillDown(target, preset) into a real screen instead of just
// showing a static count, and Recent Activity is gone -- the Director
// found it noise, not signal, in real usage.
//
// Amendment 36 (Section 42): "Overview" shell, shell-first per Director
// decision -- two tiles (Pending quotations, Active projects) reuse the
// exact same real backend counts this screen already had; Payments overdue
// and the "Orders & collections" panel have no backend yet (Payments is
// Phase 7) and deliberately show "--" with "Coming soon" rather than a
// fabricated "0" -- an unbuilt feature must never read as a real, empty
// one. Follow-ups due (tile) and Your next moves (panel) got real data in
// Amendment 43; Open opportunities (tile) and Sales pipeline (panel) in
// Amendment 44 Phase D.
function ComingSoonTile({ label, icon: IconComp }) {
  return (
    <div className="text-left bg-surface border border-border-dark rounded-lg p-5 opacity-70">
      <p className="text-xs uppercase tracking-wide text-text-secondary flex items-center justify-between">
        <span className="flex items-center gap-1.5">
          {IconComp && <IconComp className="w-3.5 h-3.5" />}
          {label}
        </span>
        <span className="text-[10px] normal-case tracking-normal bg-surface-raised border border-border-dark rounded px-1.5 py-0.5">
          Soon
        </span>
      </p>
      <p className="text-2xl font-heading font-bold mt-2 text-text-secondary">--</p>
    </div>
  );
}

function CountUpValue({ value }) {
  const animated = useCountUp(value);
  return <>{animated}</>;
}

function ComingSoonPanel({ title, description }) {
  return (
    <div className="bg-surface border border-border-dark rounded-lg p-5 opacity-70">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-heading font-semibold text-text-primary text-base">{title}</h3>
        <span className="text-[10px] uppercase tracking-wider bg-surface-raised border border-border-dark rounded px-1.5 py-0.5 text-text-secondary">
          Coming soon
        </span>
      </div>
      <p className="text-sm text-text-secondary">{description}</p>
    </div>
  );
}

// Amendment 43 (Section E step 4): "Your next moves" reuses the same
// GET /clients + dueFollowUps() filter FollowUps.jsx uses for the full
// screen, capped to a short preview -- same due/overdue set, not a
// separate computation.
const NEXT_MOVES_PREVIEW_LIMIT = 5;

// GET /clients (clients.py) is gated to sales/pm/director/procurement --
// narrower than Dashboard's own gate, which also admits site_engineer and
// ca_tax. Those two roles can see the real followups_due_count (it comes
// from GET /dashboard, which they can call) but not the per-client
// breakdown, same existing gap the "Leads & Clients" nav item already has
// for those roles. Fetched separately from the dashboard summary so a 403
// here never breaks the rest of the page.
const CAN_SEE_CLIENT_LIST = ["sales", "pm", "director", "procurement"];

export default function Dashboard({ token, role, onOpenProject, onNewProject, onDrillDown }) {
  const [data, setData] = useState(null);
  const [clients, setClients] = useState(null);
  const [opportunities, setOpportunities] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getDashboard(token)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    if (CAN_SEE_CLIENT_LIST.includes(role)) {
      listClients(token)
        .then(setClients)
        .catch(() => setClients(null));
      listOpportunities(token)
        .then(setOpportunities)
        .catch(() => setOpportunities(null));
    }
  }, [token, role]);

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading Dashboard…</p>;
  }

  if (error) {
    return <p className="text-center text-red-400 mt-10">{error}</p>;
  }

  const { summary, recent_projects: recentProjects } = data;
  const nextMoves = clients ? dueFollowUps(clients, opportunities || []).slice(0, NEXT_MOVES_PREVIEW_LIMIT) : null;

  // Amendment 49 (Section 53): the drill-down behind "Pending quotations" --
  // the Quotations screen -- is open to Sales, PM and Director (the API
  // withholds cost/margin from Sales), so the tile links for them; other
  // roles still see the count, just not a live link into it.
  const canSeeList = CAN_SEE_CLIENT_LIST.includes(role);
  const canSeeQuotations = ["sales", "pm", "director"].includes(role);
  const realTiles = [
    {
      label: "Open opportunities",
      value: summary.open_opportunities_count,
      target: canSeeList ? "opportunities" : null,
      preset: {},
      icon: FunnelIcon,
    },
    {
      label: "Pending quotations",
      value: summary.pending_quotations_count,
      target: canSeeQuotations ? "quotations_admin" : null,
      preset: { statusGroup: "pending" },
      icon: DocumentIcon,
    },
    {
      label: "Active projects",
      value: summary.open_projects_count,
      target: "projects_admin",
      preset: { status: "open" },
      icon: FolderIcon,
    },
    {
      label: "Follow-ups due",
      value: summary.followups_due_count,
      target: CAN_SEE_CLIENT_LIST.includes(role) ? "followups" : null,
      preset: {},
      icon: ClockIcon,
    },
  ];

  // Same mirrored-nav item set as Sidebar.jsx's primaryItems, minus Team &
  // Access (not shown in the CRM reference's own tab strip either) --
  // "Overview" is always the active one here since Dashboard only renders
  // on that screen; every other tab navigates away entirely.
  function quotationsTabClick() {
    onDrillDown("quotations_admin", {});
  }
  const tabs = [
    { key: "dashboard", label: "Overview", active: true },
    ...(canSeeList
      ? [
          { key: "clients_admin", label: "Leads & Clients", onClick: () => onDrillDown("clients_admin", {}) },
          { key: "opportunities", label: "Opportunities", onClick: () => onDrillDown("opportunities", {}) },
        ]
      : []),
    ...(canSeeQuotations ? [{ key: "quotations", label: "Quotations", onClick: quotationsTabClick }] : []),
    { key: "projects_admin", label: "Projects", onClick: () => onDrillDown("projects_admin", {}) },
    ...(["pm", "director", "ca_tax"].includes(role)
      ? [{ key: "payments", label: "Payments", onClick: () => onDrillDown("payments", {}) }]
      : []),
    ...(canSeeList ? [{ key: "followups", label: "Follow-ups", onClick: () => onDrillDown("followups", {}) }] : []),
  ];

  return (
    <div className="max-w-[1600px] mx-auto mt-6 mb-10 space-y-6 px-4 sm:px-6">
      <div className="rise" style={{ "--d": "0.05s" }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wide text-text-secondary">NestaPrime / Customer Relationships</p>
            <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1">Business overview.</h2>
            <p className="text-sm text-text-secondary mt-1">Every relationship. Every opportunity. One clear view.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => onDrillDown("reports", {})}
              title="Pinned for quick access"
              className="text-xs uppercase tracking-wider bg-surface border border-gold/40 text-gold hover:bg-gold/10 rounded px-4 py-2.5 font-semibold hover:-translate-y-0.5 transition-all duration-250 ease-out"
            >
              📌 Reports
            </button>
            <button
              onClick={onNewProject}
              className="text-xs uppercase tracking-wider bg-gold hover:bg-gold-hover text-base rounded px-4 py-2.5 font-semibold hover:-translate-y-0.5 transition-all duration-250 ease-out"
            >
              + New project
            </button>
          </div>
        </div>

        <div className="flex items-center gap-5 mt-4 border-b border-border-dark overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={tab.onClick}
              className={`text-sm pb-2.5 border-b-2 whitespace-nowrap transition-colors duration-200 ${
                tab.active
                  ? "text-gold border-gold font-medium"
                  : "text-text-secondary border-transparent hover:text-text-primary"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 rise" style={{ "--d": "0.12s" }}>
        {realTiles.map((tile) =>
          tile.target ? (
            <button
              key={tile.label}
              onClick={() => onDrillDown(tile.target, tile.preset)}
              className="text-left bg-surface border border-border-dark rounded-lg p-5 hover:border-gold hover:-translate-y-0.5 transition-all duration-250 ease-out"
            >
              <p className="text-xs uppercase tracking-wide text-text-secondary flex items-center gap-1.5">
                <tile.icon className="w-3.5 h-3.5" />
                {tile.label}
              </p>
              <p className="text-2xl font-heading font-bold mt-2 text-text-primary">
                <CountUpValue value={tile.value} />
              </p>
            </button>
          ) : (
            <div key={tile.label} className="text-left bg-surface border border-border-dark rounded-lg p-5">
              <p className="text-xs uppercase tracking-wide text-text-secondary flex items-center gap-1.5">
                <tile.icon className="w-3.5 h-3.5" />
                {tile.label}
              </p>
              <p className="text-2xl font-heading font-bold mt-2 text-text-primary">
                <CountUpValue value={tile.value} />
              </p>
            </div>
          )
        )}
        <ComingSoonTile label="Payments overdue" icon={CalendarIcon} />
      </div>

      <div className="grid lg:grid-cols-2 gap-5 rise" style={{ "--d": "0.2s" }}>
        <ComingSoonPanel
          title="Orders & collections"
          description="Won order value vs. cash received, by month -- arrives with Payments."
        />
        <div className="bg-surface border border-border-dark rounded-lg p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-heading font-semibold text-text-primary text-base">Sales pipeline</h3>
            {canSeeList && (
              <button
                onClick={() => onDrillDown("opportunities", {})}
                className="text-xs uppercase tracking-wider text-gold hover:text-gold-hover"
              >
                View all →
              </button>
            )}
          </div>
          {summary.open_opportunities_count === 0 ? (
            <p className="text-sm text-text-secondary">
              No open opportunities yet -- add an enquiry from Leads &amp; Clients.
            </p>
          ) : (
            <ul className="space-y-3">
              {PIPELINE_STAGES.map(({ key, label }) => {
                const n = summary[key];
                const pct = Math.round((n / summary.open_opportunities_count) * 100);
                return (
                  <li key={key}>
                    <div className="flex items-center justify-between text-xs text-text-secondary mb-1">
                      <span>{label}</span>
                      <span className="font-mono text-text-primary">
                        <CountUpValue value={n} />
                      </span>
                    </div>
                    <div className="h-1.5 rounded-full bg-surface-raised overflow-hidden">
                      <div className="h-full rounded-full bg-gold" style={{ width: `${pct}%` }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          <p className="text-[11px] text-text-secondary/70 mt-3">
            Counts only -- values appear once an estimate exists.
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-5 rise" style={{ "--d": "0.28s" }}>
        <div className="lg:col-span-2 bg-surface border border-border-dark rounded-lg p-5">
          <h3 className="font-heading font-semibold text-text-primary text-base mb-3">Recent projects</h3>
          {recentProjects.length === 0 ? (
            <p className="text-sm text-text-secondary">No projects yet -- create one to get started.</p>
          ) : (
            <ul className="divide-y divide-border-dark">
              {recentProjects.map((project) => (
                <li key={project.id}>
                  <button
                    onClick={() => onOpenProject(project.id)}
                    className="w-full text-left py-3 flex items-center justify-between gap-3 hover:bg-surface-raised px-2 rounded hover:-translate-y-0.5 transition-all duration-250 ease-out"
                  >
                    <span className="flex items-center gap-3 min-w-0">
                      <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-semibold text-gold bg-gold-muted border border-gold/30 rounded-full px-2 py-0.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-gold" />
                        Open
                      </span>
                      <span className="min-w-0 break-words">
                        <span className="font-medium text-text-primary font-mono text-sm">{project.project_no}</span>{" "}
                        <span className="text-text-secondary">
                          · {project.client_name} · {project.city}
                        </span>
                      </span>
                    </span>
                    <span className="text-sm text-gold shrink-0">Open →</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <button
            onClick={() => onDrillDown("projects_admin", {})}
            className="mt-3 text-xs uppercase tracking-wider text-gold hover:text-gold-hover"
          >
            View all projects →
          </button>
        </div>
        <div className="bg-surface border border-border-dark rounded-lg p-5">
          <h3 className="font-heading font-semibold text-text-primary text-base mb-3">Your next moves</h3>
          {nextMoves === null ? (
            <p className="text-sm text-text-secondary">Follow-up details aren't available for your role.</p>
          ) : nextMoves.length === 0 ? (
            <p className="text-sm text-text-secondary">No client follow-ups due right now.</p>
          ) : (
            <ul className="divide-y divide-border-dark">
              {nextMoves.map((c) => (
                <li key={`${c.kind}-${c.id}`} className="py-2 flex items-center justify-between gap-2">
                  <span className="text-sm text-text-primary truncate min-w-0">
                    {c.name}
                    {c.kind === "opportunity" && (
                      <span className="ml-2 text-[10px] uppercase tracking-wider text-text-secondary">lead</span>
                    )}
                  </span>
                  <span className={`text-xs shrink-0 ${c.status === "overdue" ? "text-red-400" : "text-text-secondary"}`}>
                    {c.next_follow_up_date}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {nextMoves !== null && (
            <button
              onClick={() => onDrillDown("followups", {})}
              className="mt-3 text-xs uppercase tracking-wider text-gold hover:text-gold-hover"
            >
              View all follow-ups →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
