import { useEffect, useState } from "react";
import { listAllEstimates } from "./api";

const STATUS_OPTIONS = ["draft", "sent", "won", "lost", "expired", "superseded"];

// Amendment 12 (Section 11): the Dashboard's "Pending Estimates" tile had
// no screen behind it -- only the count. Cross-project, searchable,
// status-filterable, matching AllQuotations.jsx's own shape.
// Amendment 49 (Section 53): also rendered as the "Estimates" tab of the
// Quotations screen. `embedded` drops this screen's own title card and page
// width -- the parent supplies the header -- and everything else (filters,
// list, row behaviour) is the same list, unchanged.
export default function AllEstimates({ token, initialStatus = "", onOpenProject, onBack, embedded = false }) {
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState(initialStatus);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    setLoading(true);
    listAllEstimates(token, { status: status || undefined })
      .then(setRows)
      .catch((err) => {
        setError(err.message);
        setLoadFailed(true);
      })
      .finally(() => setLoading(false));
  }, [token, status]);

  const needle = search.trim().toLowerCase();
  const visibleRows = needle
    ? rows.filter(
        (r) => r.project_no.toLowerCase().includes(needle) || r.client_name.toLowerCase().includes(needle)
      )
    : rows;

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading estimates…</p>;
  }

  return (
    <div className={embedded ? "space-y-4" : "max-w-4xl mx-auto mt-8 mb-10 space-y-6 px-4"}>
      <div className={embedded ? "" : "bg-surface shadow rounded-lg p-6"}>
        {!embedded && (
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-text-primary">All Estimates</h2>
            {onBack && (
              <button onClick={onBack} className="text-sm text-gold hover:underline">
                &larr; Back
              </button>
            )}
          </div>
        )}
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
        <div className={`flex flex-wrap items-center gap-2 ${embedded ? "" : "mt-3"}`}>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
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
        {visibleRows.map((e) => (
          <button
            key={e.id}
            onClick={() => onOpenProject(e.project_id)}
            className="w-full text-left px-4 py-3 flex items-center justify-between hover:bg-surface-raised hover:-translate-y-0.5 transition-all duration-250 ease-out"
          >
            <span className="text-sm">
              <span className="font-medium text-text-primary font-mono">{e.document_no}</span>{" "}
              <span className="text-text-secondary">
                · {e.project_no} · {e.client_name}
              </span>
            </span>
            <span className="flex items-center gap-3">
              <span className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full bg-gold/10 text-gold">
                {e.status}
              </span>
              <span className="text-sm text-gold">Open →</span>
            </span>
          </button>
        ))}
        {visibleRows.length === 0 && !loadFailed && (
          <p className="text-sm text-text-secondary text-center py-6">No estimates match these filters.</p>
        )}
      </div>
    </div>
  );
}
