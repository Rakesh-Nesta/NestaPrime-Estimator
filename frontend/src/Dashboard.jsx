import { useEffect, useState } from "react";
import { getDashboard } from "./api";

function formatMoney(value) {
  return `Rs ${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatWhen(iso) {
  return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

// Amendment 4 (Annexure 2): "business-summary dashboard ... link back to
// dashboard from every section ... the app itself is the training." This
// is the post-login landing screen; onOpenProject resumes an existing
// project straight into its Documents stage (Cost Sheet/Estimate/
// Quotation), which is the concrete fix for the "no way to browse back
// into an existing project" gap found live during the 12 Sep validation run.
export default function Dashboard({ token, role, onOpenProject, onNewProject }) {
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
    return <p className="text-center text-gray-500 mt-10">Loading Dashboard…</p>;
  }

  if (error) {
    return <p className="text-center text-red-600 mt-10">{error}</p>;
  }

  const { summary, recent_projects: recentProjects, recent_activity: recentActivity } = data;

  const tiles = [
    { label: "Open projects", value: summary.open_projects_count },
    { label: "Pending estimates", value: summary.pending_estimates_count },
    { label: "Pending quotations", value: summary.pending_quotations_count },
    { label: "Overdue clients", value: summary.overdue_clients_count },
    { label: "Won this month", value: formatMoney(summary.won_this_month_total) },
  ];

  return (
    <div className="max-w-4xl mx-auto mt-8 mb-10 space-y-6 px-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">Dashboard</h2>
        <button
          onClick={onNewProject}
          className="text-sm bg-blue-600 text-white rounded px-3 py-1.5 font-medium hover:bg-blue-700"
        >
          + New project
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {tiles.map((tile) => (
          <div key={tile.label} className="bg-white shadow rounded-lg p-4">
            <p className="text-xs text-gray-500">{tile.label}</p>
            <p className="text-lg font-semibold text-gray-900 mt-1">{tile.value}</p>
          </div>
        ))}
      </div>

      <div className="bg-white shadow rounded-lg p-4">
        <h3 className="font-medium text-gray-900 mb-3">Recent projects</h3>
        {recentProjects.length === 0 ? (
          <p className="text-sm text-gray-500">No projects yet -- create one to get started.</p>
        ) : (
          <ul className="divide-y">
            {recentProjects.map((project) => (
              <li key={project.id}>
                <button
                  onClick={() => onOpenProject(project.id)}
                  className="w-full text-left py-2.5 flex items-center justify-between hover:bg-gray-50 px-1 rounded"
                >
                  <span>
                    <span className="font-medium text-gray-900">{project.project_no}</span>{" "}
                    <span className="text-gray-500">
                      · {project.client_name} · {project.city}
                    </span>
                  </span>
                  <span className="text-sm text-blue-600">Open →</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {role === "director" && recentActivity && (
        <div className="bg-white shadow rounded-lg p-4">
          <h3 className="font-medium text-gray-900 mb-3">Recent activity</h3>
          {recentActivity.length === 0 ? (
            <p className="text-sm text-gray-500">Nothing logged yet.</p>
          ) : (
            <ul className="divide-y text-sm">
              {recentActivity.map((entry) => (
                <li key={entry.id} className="py-2 text-gray-600">
                  <span className="text-gray-400">{formatWhen(entry.timestamp)}</span> — {entry.role}{" "}
                  {entry.document_type} <span className="font-medium">{entry.field}</span>
                  {entry.old_value || entry.new_value ? (
                    <>
                      : {entry.old_value ?? "—"} → {entry.new_value ?? "—"}
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
