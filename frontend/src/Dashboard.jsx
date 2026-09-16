import { useEffect, useState } from "react";
import { getDashboard } from "./api";

function formatMoney(value) {
  return `Rs ${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
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
  const tiles = [
    { label: "Open projects", value: summary.open_projects_count, target: "projects_admin", preset: { status: "open" } },
    { label: "Pending estimates", value: summary.pending_estimates_count, target: "estimates_admin", preset: { status: "sent" } },
    {
      label: "Pending quotations",
      value: summary.pending_quotations_count,
      target: role === "director" ? "quotations_admin" : null,
      preset: { statusGroup: "pending" },
    },
    { label: "Overdue clients", value: summary.overdue_clients_count, target: "clients_admin", preset: {} },
    { label: "Won this month", value: formatMoney(summary.won_this_month_total), target: "projects_admin", preset: { status: "won" }, accent: true },
  ];

  return (
    <div className="max-w-4xl mx-auto mt-8 mb-10 space-y-6 px-4">
      <div className="flex items-center justify-between">
        <h2 className="font-heading font-bold text-text-primary text-lg">Dashboard</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onDrillDown("reports", {})}
            title="Pinned for quick access"
            className="text-xs uppercase tracking-wider bg-surface border border-gold/40 text-gold hover:bg-gold/10 rounded px-4 py-2 font-semibold hover:-translate-y-0.5 transition-all duration-250 ease-out"
          >
            📌 Reports
          </button>
          <button
            onClick={onNewProject}
            className="text-xs uppercase tracking-wider bg-gold hover:bg-gold-hover text-base rounded px-4 py-2 font-semibold hover:-translate-y-0.5 transition-all duration-250 ease-out"
          >
            + New project
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {tiles.map((tile) =>
          tile.target ? (
            <button
              key={tile.label}
              onClick={() => onDrillDown(tile.target, tile.preset)}
              className="text-left bg-surface border border-border-dark rounded-lg p-4 hover:border-gold hover:-translate-y-0.5 transition-all duration-250 ease-out"
            >
              <p className="text-xs uppercase tracking-wide text-text-secondary">{tile.label}</p>
              <p className={`text-lg font-heading font-semibold mt-1 ${tile.accent ? "text-gold" : "text-text-primary"}`}>
                {tile.value}
              </p>
            </button>
          ) : (
            <div key={tile.label} className="text-left bg-surface border border-border-dark rounded-lg p-4">
              <p className="text-xs uppercase tracking-wide text-text-secondary">{tile.label}</p>
              <p className={`text-lg font-heading font-semibold mt-1 ${tile.accent ? "text-gold" : "text-text-primary"}`}>
                {tile.value}
              </p>
            </div>
          )
        )}
      </div>

      <div className="bg-surface border border-border-dark rounded-lg p-4">
        <h3 className="font-heading font-semibold text-text-primary mb-3">Recent projects</h3>
        {recentProjects.length === 0 ? (
          <p className="text-sm text-text-secondary">No projects yet -- create one to get started.</p>
        ) : (
          <ul className="divide-y divide-border-dark">
            {recentProjects.map((project) => (
              <li key={project.id}>
                <button
                  onClick={() => onOpenProject(project.id)}
                  className="w-full text-left py-2.5 flex items-center justify-between hover:bg-surface-raised px-1 rounded hover:-translate-y-0.5 transition-all duration-250 ease-out"
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
    </div>
  );
}
