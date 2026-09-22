import { useEffect, useState } from "react";
import { getDashboard } from "./api";

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
// exact same real backend counts this screen already had; the other three
// (Open opportunities, Follow-ups due, Payments overdue) and the two panel
// placeholders below have no backend yet (Opportunities/Follow-ups/
// Payments are Phases 4/5/7) and deliberately show "--" with "Coming soon"
// rather than a fabricated "0" -- an unbuilt feature must never read as a
// real, empty one.
function ComingSoonTile({ label }) {
  return (
    <div className="text-left bg-surface border border-border-dark rounded-lg p-5 opacity-70">
      <p className="text-xs uppercase tracking-wide text-text-secondary flex items-center justify-between">
        {label}
        <span className="text-[10px] normal-case tracking-normal bg-surface-raised border border-border-dark rounded px-1.5 py-0.5">
          Soon
        </span>
      </p>
      <p className="text-2xl font-heading font-bold mt-2 text-text-secondary">--</p>
    </div>
  );
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

export default function Dashboard({ token, role, onOpenProject, onNewProject, onDrillDown }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getDashboard(token)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading Dashboard…</p>;
  }

  if (error) {
    return <p className="text-center text-red-400 mt-10">{error}</p>;
  }

  const { summary, recent_projects: recentProjects } = data;

  // "Pending quotations" carries cost/margin figures (K.3), so its
  // drill-down -- AllQuotations -- keeps the same Director-only gate it
  // already has everywhere else in the nav; every other role still sees
  // the count, just not a live link into it.
  const realTiles = [
    {
      label: "Pending quotations",
      value: summary.pending_quotations_count,
      target: role === "director" ? "quotations_admin" : null,
      preset: { statusGroup: "pending" },
    },
    { label: "Active projects", value: summary.open_projects_count, target: "projects_admin", preset: { status: "open" } },
  ];

  return (
    <div className="max-w-[1600px] mx-auto mt-8 mb-10 space-y-6 px-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-text-secondary">NestaPrime / Customer Relationships</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1">Business overview</h2>
        </div>
        <div className="flex items-center gap-2">
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

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        <ComingSoonTile label="Open opportunities" />
        <ComingSoonTile label="Follow-ups due" />
        {realTiles.map((tile) =>
          tile.target ? (
            <button
              key={tile.label}
              onClick={() => onDrillDown(tile.target, tile.preset)}
              className="text-left bg-surface border border-border-dark rounded-lg p-5 hover:border-gold hover:-translate-y-0.5 transition-all duration-250 ease-out"
            >
              <p className="text-xs uppercase tracking-wide text-text-secondary">{tile.label}</p>
              <p className="text-2xl font-heading font-bold mt-2 text-text-primary">{tile.value}</p>
            </button>
          ) : (
            <div key={tile.label} className="text-left bg-surface border border-border-dark rounded-lg p-5">
              <p className="text-xs uppercase tracking-wide text-text-secondary">{tile.label}</p>
              <p className="text-2xl font-heading font-bold mt-2 text-text-primary">{tile.value}</p>
            </div>
          )
        )}
        <ComingSoonTile label="Payments overdue" />
      </div>

      <div className="grid sm:grid-cols-2 gap-5">
        <ComingSoonPanel
          title="Orders & collections"
          description="Won order value vs. cash received, by month -- lands with Payments (Phase 7)."
        />
        <ComingSoonPanel
          title="Sales pipeline"
          description="Open opportunities by stage and value -- lands with Opportunities (Phase 5)."
        />
      </div>

      <div className="grid sm:grid-cols-3 gap-5">
        <div className="sm:col-span-2 bg-surface border border-border-dark rounded-lg p-5">
          <h3 className="font-heading font-semibold text-text-primary text-base mb-3">Recent projects</h3>
          {recentProjects.length === 0 ? (
            <p className="text-sm text-text-secondary">No projects yet -- create one to get started.</p>
          ) : (
            <ul className="divide-y divide-border-dark">
              {recentProjects.map((project) => (
                <li key={project.id}>
                  <button
                    onClick={() => onOpenProject(project.id)}
                    className="w-full text-left py-3 flex items-center justify-between hover:bg-surface-raised px-2 rounded hover:-translate-y-0.5 transition-all duration-250 ease-out"
                  >
                    <span>
                      <span className="font-medium text-text-primary font-mono text-sm">{project.project_no}</span>{" "}
                      <span className="text-text-secondary">
                        · {project.client_name} · {project.city}
                      </span>
                    </span>
                    <span className="text-sm text-gold">Open →</span>
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
        <ComingSoonPanel
          title="Your next moves"
          description="Overdue follow-ups and action items, with owner and due date -- lands with Follow-ups (Phase 4)."
        />
      </div>
    </div>
  );
}
