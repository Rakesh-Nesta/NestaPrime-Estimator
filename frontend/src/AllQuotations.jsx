import { useEffect, useState } from "react";
import { downloadAllQuotationsCsvBlob, downloadQuotationPdfBlob, listAllQuotations } from "./api";
import AllEstimates from "./AllEstimates";
import { ClockIcon, DocumentIcon, FunnelIcon } from "./Icons";

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

const STAGE_PILL_STYLE = {
  draft: "bg-gold/10 text-gold",
  released: "bg-surface-raised text-text-secondary",
  sent: "bg-surface-raised text-text-secondary",
  won: "bg-green-500/10 text-green-400",
  lost: "bg-red-500/10 text-red-400",
  expired: "bg-red-500/10 text-red-400",
  superseded: "bg-surface-raised text-text-secondary",
};
const STAGE_DOT_STYLE = {
  draft: "bg-gold",
  released: "bg-text-secondary",
  sent: "bg-text-secondary",
  won: "bg-green-400",
  lost: "bg-red-400",
  expired: "bg-red-400",
  superseded: "bg-text-secondary",
};

// A revision number for the timeline -- the document number's own "-R<n>" suffix when it has one (every
// quotation created this way does), falling back to a positional count so nothing in an older or
// differently-numbered document ever throws.
function revisionLabel(documentNo, position) {
  const match = /-R(\d+)$/.exec(documentNo);
  return match ? `R${match[1]}` : `R${position}`;
}

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
//
// Redesign (2026-09-27, Director's request): same screen, same data and the same server calls -- the
// table gains row selection, which opens a read-only summary of that quotation and its revision history
// below it. Sidebar and header are untouched; only this screen's own content changed.
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
  // P1 acceptance fix (correction plan, 2026-09-30): see Opportunities.jsx's own comment on this
  // same pattern -- useState's initial value only applies on first mount, so landing here twice
  // without an intervening remount (App.jsx's screen key unchanged) needs this to actually reset.
  useEffect(() => {
    setStatusGroup(initialStatusGroup);
  }, [initialStatusGroup]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [autoSelectDone, setAutoSelectDone] = useState(false);
  const [revisionOrder, setRevisionOrder] = useState("newest");
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

  // The summary + revision-history panels read as part of the page, not an optional extra -- so the first
  // row is selected by default as soon as there is one. Once, not on every load: changing a filter must
  // not silently reselect something the user hasn't looked at.
  useEffect(() => {
    if (!autoSelectDone && selectedId === null && rows.length > 0) {
      setSelectedId(rows[0].id);
      setAutoSelectDone(true);
    }
  }, [rows, autoSelectDone, selectedId]);

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
  const selected = rows.find((r) => r.id === selectedId) || null;
  const revisions = selected
    ? rows
        .filter((r) => r.project_id === selected.project_id)
        .slice()
        .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
        .map((r, i) => ({ ...r, revisionLabel: revisionLabel(r.document_no, i + 1) }))
        .sort((a, b) =>
          revisionOrder === "newest" ? new Date(b.created_at) - new Date(a.created_at) : new Date(a.created_at) - new Date(b.created_at)
        )
    : [];

  const tiles = [
    {
      label: "Documents",
      value: rows.length,
      icon: DocumentIcon,
      accent: "border-l-gold",
      active: !status && !statusGroup,
      onClick: () => { setStatus(""); setStatusGroup(""); },
    },
    {
      label: "Draft",
      value: rows.filter((r) => r.status === "draft").length,
      icon: ClockIcon,
      accent: "border-l-gold",
      active: status === "draft",
      onClick: () => { setStatusGroup(""); setStatus(status === "draft" ? "" : "draft"); },
    },
    {
      label: "Lost",
      value: rows.filter((r) => r.status === "lost").length,
      icon: FunnelIcon,
      accent: "border-l-red-400",
      active: status === "lost",
      onClick: () => { setStatusGroup(""); setStatus(status === "lost" ? "" : "lost"); },
    },
  ];

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
    <div className="max-w-[1400px] mx-auto mt-6 mb-10 space-y-4 px-4 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-text-secondary">Workspace / Customer relationships</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1 flex items-center gap-2">
            <DocumentIcon className="w-6 h-6 text-gold" /> Quotations
          </h2>
          <p className="text-sm text-text-secondary mt-1">Manage quotations and estimates across your projects.</p>
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

      <div className="flex items-start gap-2 bg-gold/5 border border-gold/20 rounded-lg px-4 py-3 text-sm text-text-secondary">
        <span className="text-gold shrink-0">ℹ</span>
        <span>
          Open one to work on it -- a quotation is created from a project&apos;s Documents screen once the
          client approves an estimate.
        </span>
      </div>

      {tab === "quotations" && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {tiles.map((tile) => (
            <button
              key={tile.label}
              onClick={tile.onClick}
              className={`text-left bg-surface border border-border-dark ${tile.accent} border-l-4 rounded-lg p-4 hover:-translate-y-0.5 transition-all duration-250 ease-out ${
                tile.active ? "ring-1 ring-gold" : ""
              }`}
            >
              <p className="text-xs uppercase tracking-wide text-text-secondary flex items-center gap-1.5">
                <tile.icon className="w-3.5 h-3.5" />
                {tile.label}
              </p>
              <p className="text-2xl font-heading font-bold mt-1 text-text-primary">{tile.value}</p>
            </button>
          ))}
        </div>
      )}

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
            {t.label} {t.key === "quotations" && <span className="text-xs text-text-secondary">({rows.length})</span>}
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
                  <button
                    key={r.id}
                    onClick={() => setSelectedId(r.id)}
                    className={`w-full text-left bg-surface border rounded-lg px-4 py-3 text-sm space-y-1.5 ${
                      selectedId === r.id ? "border-gold" : "border-border-dark"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <span className="font-mono text-text-primary break-all">{r.document_no}</span>
                      <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full shrink-0 ${STAGE_PILL_STYLE[r.status]}`}>
                        {r.status}
                      </span>
                    </div>
                    <p className="text-text-primary break-words">{r.client_name}</p>
                    <p className="text-xs text-text-secondary break-words">
                      {r.project_no} · {r.sports.join(", ") || "—"}
                    </p>
                    <p className="text-sm">
                      Rs {Math.round(r.quotation_total).toLocaleString()}
                      {canSeeMargin && r.margin_percent != null && (
                        <span className="text-xs text-text-secondary"> · {r.margin_percent.toFixed(1)}% margin</span>
                      )}
                      {r.below_floor && <span className="text-xs text-red-400"> (below floor)</span>}
                    </p>
                    <p className="text-xs text-text-secondary pt-1">{new Date(r.created_at).toLocaleDateString()}</p>
                  </button>
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
                      <tr
                        key={r.id}
                        onClick={() => setSelectedId(r.id)}
                        className={`border-t cursor-pointer align-top hover:bg-surface-raised transition-colors duration-150 ${
                          selectedId === r.id ? "border-gold bg-gold/5" : "border-border-dark"
                        }`}
                      >
                        <td className="px-3 py-2 whitespace-nowrap">{r.document_no}</td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          {onOpenProject ? (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onOpenProject(r.project_id);
                              }}
                              className="text-gold hover:underline"
                            >
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
                          <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${STAGE_PILL_STYLE[r.status]}`}>
                            {r.status}
                          </span>
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
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDownloadPdf(r.id, r.document_no);
                            }}
                            className="text-gold hover:underline"
                          >
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

              {selected && (
                <div className="grid lg:grid-cols-[1fr_20rem] gap-5">
                  <div className="bg-surface border border-border-dark rounded-lg p-5">
                    <div className="flex items-start justify-between gap-2 mb-3">
                      <h3 className="text-sm font-semibold text-text-secondary">Selected quotation</h3>
                      <span className="flex items-center gap-1.5 text-xs text-text-secondary">
                        <DocumentIcon className="w-3.5 h-3.5" /> Quotation Document
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mb-3">
                      <span className="font-mono text-lg text-text-primary">{selected.document_no}</span>
                      <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${STAGE_PILL_STYLE[selected.status]}`}>
                        {selected.status}
                      </span>
                    </div>
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm mb-4">
                      <dt className="text-text-secondary">Project</dt>
                      <dd>
                        {onOpenProject ? (
                          <button onClick={() => onOpenProject(selected.project_id)} className="text-gold hover:underline">
                            {selected.project_no}
                          </button>
                        ) : (
                          selected.project_no
                        )}
                      </dd>
                      <dt className="text-text-secondary">Client</dt>
                      <dd className="text-text-primary">{selected.client_name}</dd>
                      <dt className="text-text-secondary">Sport</dt>
                      <dd className="text-text-primary">{selected.sports.join(", ") || "—"}</dd>
                      <dt className="text-text-secondary">Created</dt>
                      <dd className="text-text-primary">{new Date(selected.created_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}</dd>
                    </dl>
                    <div className="border-t border-border-dark pt-3 mb-4">
                      <p className="text-xs text-text-secondary">Total (including GST)</p>
                      <p className="text-2xl font-heading font-bold text-gold">
                        ₹{Math.round(selected.quotation_total).toLocaleString("en-IN")}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      {onOpenProject && (
                        <button
                          onClick={() => onOpenProject(selected.project_id)}
                          className="bg-gold text-base text-sm rounded px-4 py-2 font-semibold hover:bg-gold-hover"
                        >
                          🔗 Open document
                        </button>
                      )}
                      <button
                        onClick={() => handleDownloadPdf(selected.id, selected.document_no)}
                        className="border border-border-dark text-text-primary text-sm rounded px-4 py-2 hover:bg-surface-raised"
                      >
                        📄 View PDF
                      </button>
                    </div>
                  </div>

                  <div className="bg-surface border border-border-dark rounded-lg p-5">
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <h3 className="text-sm font-semibold text-text-primary">Revision history</h3>
                      <select
                        value={revisionOrder}
                        onChange={(e) => setRevisionOrder(e.target.value)}
                        className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs"
                        aria-label="Revision order"
                      >
                        <option value="newest">Newest first</option>
                        <option value="oldest">Oldest first</option>
                      </select>
                    </div>
                    <ul className="relative space-y-4">
                      {revisions.map((r, i) => (
                        <li key={r.id} className="relative pl-6">
                          {i < revisions.length - 1 && (
                            <span className="absolute left-[5px] top-4 bottom-[-1rem] w-px bg-border-dark" />
                          )}
                          <button
                            onClick={() => setSelectedId(r.id)}
                            className={`absolute left-0 top-1 w-2.5 h-2.5 rounded-full ${STAGE_DOT_STYLE[r.status]} ${
                              r.id === selected.id ? "ring-2 ring-gold ring-offset-2 ring-offset-surface" : ""
                            }`}
                            aria-label={`View ${r.revisionLabel}`}
                          />
                          <button onClick={() => setSelectedId(r.id)} className="text-left w-full">
                            <p className="flex items-center gap-2">
                              <span className={`text-sm font-medium ${r.id === selected.id ? "text-gold" : "text-text-primary"}`}>
                                {r.revisionLabel}
                              </span>
                              <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${STAGE_PILL_STYLE[r.status]}`}>
                                {r.status}
                              </span>
                            </p>
                            <p className="text-xs text-text-secondary mt-0.5">
                              ₹{Math.round(r.quotation_total).toLocaleString("en-IN")} ·{" "}
                              {new Date(r.created_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}
                            </p>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
