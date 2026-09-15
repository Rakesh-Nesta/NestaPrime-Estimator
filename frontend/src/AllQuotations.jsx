import { useEffect, useState } from "react";
import { downloadAllQuotationsCsvBlob, downloadQuotationPdfBlob, listAllQuotations } from "./api";

function downloadBlobAsFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

const STATUS_OPTIONS = ["draft", "released", "sent", "won", "lost", "expired", "superseded"];

// Amendment 6b (Section 9): "admin reviews all quotations." Director-only
// cross-project browse, filterable by status/date range with a client-side
// project/client search on top -- backend filters (status, date_from,
// date_to) match what GET /quotations accepts; project_id/client_id
// filtering is also backend-supported but this screen exposes it as a
// simple text search over the already-loaded rows rather than a separate
// project/client picker, since a Director scanning "everything right now"
// is the primary use case, not a saved per-project filter.
// Amendment 12 (Section 11): "Pending Quotation" / "Old Quotation" nav
// shortcuts land here with an initialStatusGroup preset instead of a
// single status -- an explicit status pick in the dropdown still wins
// over it, matching the backend's own status_group precedence rule.
export default function AllQuotations({ token, initialStatusGroup = "", onOpenProject, onBack }) {
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("");
  const [statusGroup, setStatusGroup] = useState(initialStatusGroup);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    return listAllQuotations(token, {
      status: status || undefined,
      statusGroup: statusGroup || undefined,
      dateFrom: dateFrom || undefined,
      dateTo: dateTo || undefined,
    }).then(setRows);
  }

  useEffect(() => {
    setLoading(true);
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, status, statusGroup, dateFrom, dateTo]);

  async function handleExport() {
    setError("");
    try {
      const blob = await downloadAllQuotationsCsvBlob(token, {
        status: status || undefined,
        statusGroup: statusGroup || undefined,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
      });
      downloadBlobAsFile(blob, "all_quotations.csv");
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDownloadPdf(quotationId, documentNo) {
    setError("");
    try {
      const blob = await downloadQuotationPdfBlob(token, quotationId);
      downloadBlobAsFile(blob, `${documentNo}.pdf`);
    } catch (err) {
      setError(err.message);
    }
  }

  const needle = search.trim().toLowerCase();
  const visibleRows = needle
    ? rows.filter(
        (r) => r.project_no.toLowerCase().includes(needle) || r.client_name.toLowerCase().includes(needle)
      )
    : rows;

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading quotations…</p>;
  }

  return (
    <div className="max-w-5xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">All Quotations</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-text-secondary mt-1">
          Amendment 6b: every quotation across every project, newest first. Director-only, matching the
          Margin Performance report's own cost/margin gate.
        </p>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
        <div className="flex flex-wrap items-center gap-2 mt-3">
          <div className="flex items-center gap-1.5 text-xs">
            {[
              { key: "", label: "All" },
              { key: "pending", label: "Pending" },
              { key: "old", label: "Old" },
            ].map((g) => (
              <button
                key={g.key}
                onClick={() => {
                  setStatus("");
                  setStatusGroup(g.key);
                }}
                className={`uppercase tracking-wide px-2.5 py-1.5 rounded-full hover:-translate-y-0.5 transition-all duration-250 ease-out ${
                  statusGroup === g.key ? "bg-gold text-base font-semibold" : "bg-surface-raised text-text-secondary"
                }`}
              >
                {g.label}
              </button>
            ))}
          </div>
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setStatusGroup("");
            }}
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
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
            aria-label="Created from"
          />
          <span className="text-text-secondary text-sm">to</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
            aria-label="Created to"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search project or client…"
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm flex-1 min-w-[180px]"
          />
          <button
            onClick={handleExport}
            className="bg-gold text-base text-sm rounded px-4 py-2 hover:bg-gold-hover"
          >
            Export CSV
          </button>
        </div>
      </div>

      <div className="bg-surface shadow rounded-lg overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-surface-raised text-text-secondary">
            <tr>
              <th className="text-left px-3 py-2">Document No.</th>
              <th className="text-left px-3 py-2">Project</th>
              <th className="text-left px-3 py-2">Client</th>
              <th className="text-left px-3 py-2">Sport(s)</th>
              <th className="text-left px-3 py-2">Status</th>
              <th className="text-right px-3 py-2">Total (incl. GST)</th>
              <th className="text-right px-3 py-2">Margin %</th>
              <th className="text-left px-3 py-2">Created</th>
              <th className="text-left px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((r) => (
              <tr key={r.id} className="border-t border-border-dark">
                <td className="px-3 py-2 whitespace-nowrap">{r.document_no}</td>
                <td className="px-3 py-2">
                  {onOpenProject ? (
                    <button onClick={() => onOpenProject(r.project_id)} className="text-gold hover:underline">
                      {r.project_no}
                    </button>
                  ) : (
                    r.project_no
                  )}
                </td>
                <td className="px-3 py-2">{r.client_name}</td>
                <td className="px-3 py-2">{r.sports.join(", ") || "—"}</td>
                <td className="px-3 py-2">
                  {r.status}
                  {r.below_floor && <span className="text-red-400"> (below floor)</span>}
                </td>
                <td className="px-3 py-2 text-right whitespace-nowrap">Rs {Math.round(r.quotation_total).toLocaleString()}</td>
                <td className="px-3 py-2 text-right">{r.margin_percent.toFixed(1)}%</td>
                <td className="px-3 py-2 whitespace-nowrap">{new Date(r.created_at).toLocaleDateString()}</td>
                <td className="px-3 py-2 whitespace-nowrap">
                  <button
                    onClick={() => handleDownloadPdf(r.id, r.document_no)}
                    className="text-gold hover:underline"
                  >
                    PDF
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {visibleRows.length === 0 && <p className="text-sm text-text-secondary text-center py-6">No quotations match these filters.</p>}
      </div>
    </div>
  );
}
