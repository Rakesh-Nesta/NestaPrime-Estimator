import { useEffect, useState } from "react";
import { listProjects } from "./api";

const STATUS_OPTIONS = [
  { value: "", label: "All projects" },
  { value: "open", label: "Open" },
  { value: "won", label: "Won" },
  { value: "lost", label: "Lost" },
];

// Amendment 12 (Section 11): the Dashboard's "Open Projects" tile had no
// screen behind it -- only a 5-row "Recent projects" list. This is that
// screen: every project, filterable by open/won/lost (matching
// dashboard.py's own status vocabulary), with a client-side search on top
// of the backend's own project_no/client_name search.
export default function AllProjects({ token, initialStatus = "", onOpenProject, onBack }) {
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState(initialStatus);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    listProjects(token, { status: status || undefined })
      .then(setRows)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token, status]);

  const needle = search.trim().toLowerCase();
  const visibleRows = needle
    ? rows.filter(
        (r) => r.project_no.toLowerCase().includes(needle) || r.client_name.toLowerCase().includes(needle)
      )
    : rows;

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading projects…</p>;
  }

  return (
    <div className="max-w-4xl mx-auto mt-8 mb-10 space-y-6 px-4">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">All Projects</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
        <div className="flex flex-wrap items-center gap-2 mt-3">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search project or client…"
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm flex-1 min-w-[180px]"
          />
        </div>
      </div>

      <div className="bg-surface shadow rounded-lg divide-y divide-border-dark">
        {visibleRows.map((p) => (
          <button
            key={p.id}
            onClick={() => onOpenProject(p.id)}
            className="w-full text-left px-4 py-3 flex items-center justify-between hover:bg-surface-raised hover:-translate-y-0.5 transition-all duration-250 ease-out"
          >
            <span className="text-sm">
              <span className="font-medium text-text-primary font-mono">{p.project_no}</span>{" "}
              <span className="text-text-secondary">
                · {p.client_name} · {p.city}
              </span>
            </span>
            <span className="flex items-center gap-3">
              <StatusPill status={p.status} />
              <span className="text-sm text-gold">Open →</span>
            </span>
          </button>
        ))}
        {visibleRows.length === 0 && (
          <p className="text-sm text-text-secondary text-center py-6">No projects match these filters.</p>
        )}
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const styles = {
    open: "bg-gold/10 text-gold",
    won: "bg-green-500/10 text-green-400",
    lost: "bg-red-500/10 text-red-400",
  };
  return (
    <span className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full ${styles[status] || ""}`}>
      {status}
    </span>
  );
}
