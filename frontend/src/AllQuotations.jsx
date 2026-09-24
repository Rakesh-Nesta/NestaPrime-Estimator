import { useEffect, useState } from "react";
import { downloadAllQuotationsCsvBlob, downloadQuotationPdfBlob, listAllQuotations } from "./api";
import AllEstimates from "./AllEstimates";
import { DocumentIcon } from "./Icons";

function downloadBlobAsFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

const STATUS_OPTIONS = ["draft", "released", "sent", "won", "lost", "expired", "superseded"];

const TABS = [
  { key: "quotations", label: "Quotations" },
  { key: "estimates", label: "Estimates" },
];

// Amendment 6b (Section 9): "admin reviews all quotations." Cross-project
// browse, filterable by status/date range with a client-side project/client
// search on top -- backend filters (status, date_from, date_to) match what
// GET /quotations accepts; project_id/client_id filtering is also
// backend-supported but this screen exposes it as a simple text search over
// the already-loaded rows rather than a separate project/client picker.
// Amendment 12 (Section 11): "Pending Quotation" / "Old Quotation" nav
// shortcuts land here with an initialStatusGroup preset instead of a single
// status -- an explicit status pick in the dropdown still wins over it,
// matching the backend's own status_group precedence rule.
//
// Amendment 49 (Section 53): this is now the Quotations header for Sales,
// PM and Director (it was Director-only). The API withholds cost/margin/
// below-floor from Sales (K.3), so Sales gets no margin column -- not a blank
// one. Estimates sits beside it as a sibling tab, a row from a Won
// Opportunity names its lead, and only the Director gets the CSV export (it
// dumps cost/margin).
export default function AllQuotations({
  token,
  role,
  initialStatusGroup = "",
  onOpenProject,
  onOpenOpportunities,
  onNewProject,
  onBack,
}) {
  const [tab, setTab] = useState("quotations");
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("");
  const [statusGroup, setStatusGroup] = useState(initialStatusGroup);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [loadFailed, setLoadFailed] = useState(false);

  const canSeeMargin = role !== "sales";
  const canExport = role === "director";

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
    setLoadFailed(false);
    setError("");
    load()
      .catch((err) => {
        setError(err.message);
        setLoadFailed(true);
      })
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

  const inputClass = "rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm";

  function leadLine(r) {
    if (!r.lead_name) return null;
    return (
      <span className="text-xs text-text-secondary">
        From lead: <span className="text-text-primary">{r.lead_name}</span>
        {onOpenOpportunities && (
          <>
            {" "}
            <button onClick={onOpenOpportunities} className="text-gold hover:underline">
              Open in Opportunities →
            </button>
          </>
        )}
      </span>
    );
  }

  return (
    <div className="max-w-[1000px] mx-auto mt-6 mb-10 space-y-4 px-4 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-text-secondary">NestaPrime / Customer Relationships</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1 flex items-center gap-2">
            <DocumentIcon className="w-6 h-6 text-gold" /> Quotations
          </h2>
          <p className="text-sm text-text-secondary mt-1">
            Every quotation and estimate across every project, newest first. Open one to work on it -- a
            quotation is created from a project&apos;s Documents screen once the client approves an estimate.
          </p>
        </div>
        <div className="flex items-center gap-4 shrink-0">
          {onNewProject && (
            <button
              onClick={onNewProject}
              className="bg-gold text-base text-sm rounded px-4 py-2 font-semibold hover:bg-gold-hover"
            >
              + New project
            </button>
          )}
          {onBack && (
            <button onClick={onBack} className="text-xs uppercase tracking-wider text-gold hover:text-gold-hover">
              ← Back
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center gap-5 border-b border-border-dark">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`text-sm pb-2.5 border-b-2 whitespace-nowrap transition-colors duration-200 ${
              tab === t.key
                ? "text-gold border-gold font-medium"
                : "text-text-secondary border-transparent hover:text-text-primary"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "estimates" ? (
        <AllEstimates token={token} onOpenProject={onOpenProject} embedded />
      ) : (
        <>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex flex-wrap items-center gap-2">
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
              className={inputClass}
              aria-label="Status"
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
              className={inputClass}
              aria-label="Created from"
            />
            <span className="text-text-secondary text-sm">to</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className={inputClass}
              aria-label="Created to"
            />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search project or client…"
              className={`${inputClass} flex-1 min-w-[180px]`}
            />
            {canExport && (
              <button onClick={handleExport} className="bg-gold text-base text-sm rounded px-4 py-2 hover:bg-gold-hover">
                Export CSV
              </button>
            )}
          </div>

          {loading ? (
            <p className="text-center text-text-secondary mt-6">Loading quotations…</p>
          ) : (
            <>
              {/* Phones: stacked cards, so nothing needs sideways scrolling. */}
              <div className="space-y-3 sm:hidden">
                {visibleRows.map((r) => (
                  <div key={r.id} className="bg-surface border border-border-dark rounded-lg px-4 py-3 text-sm space-y-1.5">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <span className="font-mono text-text-primary break-all">{r.document_no}</span>
                      <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-gold/10 text-gold shrink-0">
                        {r.status}
                      </span>
                    </div>
                    <p className="text-text-primary break-words">{r.client_name}</p>
                    <p className="text-xs text-text-secondary break-words">
                      {onOpenProject ? (
                        <button onClick={() => onOpenProject(r.project_id)} className="text-gold hover:underline">
                          {r.project_no}
                        </button>
                      ) : (
                        r.project_no
                      )}
                      {" · "}
                      {r.sports.join(", ") || "—"}
                    </p>
                    <p className="text-sm">
                      Rs {Math.round(r.quotation_total).toLocaleString()}
                      {canSeeMargin && r.margin_percent != null && (
                        <span className="text-xs text-text-secondary"> · {r.margin_percent.toFixed(1)}% margin</span>
                      )}
                      {r.below_floor && <span className="text-xs text-red-400"> (below floor)</span>}
                    </p>
                    {leadLine(r)}
                    <div className="flex items-center justify-between text-xs text-text-secondary pt-1">
                      <span>{new Date(r.created_at).toLocaleDateString()}</span>
                      <button onClick={() => handleDownloadPdf(r.id, r.document_no)} className="text-gold hover:underline">
                        PDF
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="hidden sm:block bg-surface border border-border-dark rounded-lg overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-surface-raised text-text-secondary">
                    <tr>
                      <th className="text-left px-3 py-2">Document No.</th>
                      <th className="text-left px-3 py-2">Project</th>
                      <th className="text-left px-3 py-2">Client</th>
                      <th className="text-left px-3 py-2">Sport(s)</th>
                      <th className="text-left px-3 py-2">Status</th>
                      <th className="text-right px-3 py-2">Total (incl. GST)</th>
                      {canSeeMargin && <th className="text-right px-3 py-2">Margin %</th>}
                      <th className="text-left px-3 py-2">Created</th>
                      <th className="text-left px-3 py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleRows.map((r) => (
                      <tr key={r.id} className="border-t border-border-dark align-top">
                        <td className="px-3 py-2 whitespace-nowrap">{r.document_no}</td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          {onOpenProject ? (
                            <button onClick={() => onOpenProject(r.project_id)} className="text-gold hover:underline">
                              {r.project_no}
                            </button>
                          ) : (
                            r.project_no
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {r.client_name}
                          {r.lead_name && <div className="mt-0.5">{leadLine(r)}</div>}
                        </td>
                        <td className="px-3 py-2">{r.sports.join(", ") || "—"}</td>
                        <td className="px-3 py-2">
                          {r.status}
                          {r.below_floor && <span className="text-red-400"> (below floor)</span>}
                        </td>
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          Rs {Math.round(r.quotation_total).toLocaleString()}
                        </td>
                        {canSeeMargin && (
                          <td className="px-3 py-2 text-right">
                            {r.margin_percent != null ? `${r.margin_percent.toFixed(1)}%` : "—"}
                          </td>
                        )}
                        <td className="px-3 py-2 whitespace-nowrap">{new Date(r.created_at).toLocaleDateString()}</td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <button onClick={() => handleDownloadPdf(r.id, r.document_no)} className="text-gold hover:underline">
                            PDF
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {visibleRows.length === 0 && !loadFailed && (
                <p className="text-sm text-text-secondary bg-surface border border-border-dark rounded-lg p-5 text-center">
                  No quotations match these filters.
                </p>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
