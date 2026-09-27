import { Fragment, useEffect, useState } from "react";
import { exportReportBlob, exportReportPdfBlob, generateReport, listReports, releaseReport, summarizeReport } from "./api";
import { DocumentIcon, GridIcon, SearchIcon, ShieldIcon } from "./Icons";

function downloadBlobAsFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// Builds the date string from the Date object's own LOCAL fields --
// .toISOString() converts to UTC first, which silently shifts the date
// back a day whenever the browser's timezone is ahead of UTC (e.g. IST).
// That bug predates this preset feature (the old startOfMonthIso used
// toISOString the same way) but presets computing the wrong boundary
// defeats their whole point, so it's fixed here rather than carried over.
function toIso(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function todayIso() {
  return toIso(new Date());
}

function startOfMonthIso() {
  const d = new Date();
  return toIso(new Date(d.getFullYear(), d.getMonth(), 1));
}

function startOfWeekIso() {
  // Monday as the week start (matches how the team's own work week runs).
  const d = new Date();
  const day = d.getDay(); // 0=Sun..6=Sat
  const diffToMonday = day === 0 ? -6 : 1 - day;
  return toIso(new Date(d.getFullYear(), d.getMonth(), d.getDate() + diffToMonday));
}

function startOfYearIso() {
  const d = new Date();
  return toIso(new Date(d.getFullYear(), 0, 1));
}

// Amendment 6c: "reports for daily / weekly / monthly / full-year / custom ranges" --
// custom already worked (period_from/period_to are free-form on the existing
// generate endpoint); these presets just compute the two dates so a user doesn't
// have to pick calendar boundaries by hand every time. Custom keeps today's
// manual date-pickers as the fallback.
const PERIOD_PRESETS = {
  today: { label: "Today", from: todayIso },
  this_week: { label: "This Week", from: startOfWeekIso },
  this_month: { label: "This Month", from: startOfMonthIso },
  this_year: { label: "This Year", from: startOfYearIso },
  custom: { label: "Custom", from: null },
};

const REPORT_TYPE_LABEL = {
  pipeline: "Quotation Pipeline",
  margin: "Margin Performance",
  override_summary: "Override Summary",
};

// Redesign (2026-09-27, Director's request): same screen, same data and the same server calls -- a
// two-column "Generate a report" form beside a plain-language "Your report access" summary (derived from
// the same role checks the generate form already enforced, nothing new granted), and a searchable history
// table instead of a flat expanding list. Sidebar and header are untouched; only this screen's own content
// changed.
export default function Reports({ token, role, onBack }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState(null);
  const [summaries, setSummaries] = useState({}); // reportId -> text
  const [summarizingId, setSummarizingId] = useState(null);
  const [summaryError, setSummaryError] = useState("");
  const [search, setSearch] = useState("");

  const [reportType, setReportType] = useState("pipeline");
  const [periodPreset, setPeriodPreset] = useState("this_month");
  const [periodFrom, setPeriodFrom] = useState(startOfMonthIso());
  const [periodTo, setPeriodTo] = useState(todayIso());

  function handlePresetChange(preset) {
    setPeriodPreset(preset);
    const config = PERIOD_PRESETS[preset];
    if (config.from) {
      setPeriodFrom(config.from());
      setPeriodTo(todayIso());
    }
  }

  const canSeeMargin = role === "pm" || role === "director";
  const canSeeOverrideSummary = role === "director";
  const accessRows = [
    { key: "pipeline", label: "Quotation Pipeline", ok: true, note: "Available for you." },
    { key: "margin", label: "Margin Performance", ok: canSeeMargin, note: canSeeMargin ? "Available for you." : "Restricted to PM and Director." },
    {
      key: "override_summary",
      label: "Override Summary",
      ok: canSeeOverrideSummary,
      note: canSeeOverrideSummary ? "Available for you." : "Restricted to PM and Director.",
    },
  ];

  function load() {
    return listReports(token).then(setReports);
  }

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [token]);

  async function handleGenerate(e) {
    e.preventDefault();
    setError("");
    try {
      await generateReport(token, { report_type: reportType, period_from: periodFrom, period_to: periodTo });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRelease(reportId) {
    setError("");
    try {
      await releaseReport(token, reportId);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleExportExcel(report) {
    setError("");
    try {
      const blob = await exportReportBlob(token, report.id);
      downloadBlobAsFile(blob, `${report.report_type}_${report.period_from}_${report.period_to}.xlsx`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleExportPdf(report) {
    setError("");
    try {
      const blob = await exportReportPdfBlob(token, report.id);
      downloadBlobAsFile(blob, `${report.report_type}_${report.period_from}_${report.period_to}.pdf`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSummarize(reportId) {
    setSummaryError("");
    setSummarizingId(reportId);
    try {
      const { summary } = await summarizeReport(token, reportId);
      setSummaries((s) => ({ ...s, [reportId]: summary }));
    } catch (err) {
      setSummaryError(err.message);
    } finally {
      setSummarizingId(null);
    }
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading Reports…</p>;
  }

  const needle = search.trim().toLowerCase();
  const visibleReports = reports.filter(
    (r) =>
      !needle ||
      (REPORT_TYPE_LABEL[r.report_type] || r.report_type).toLowerCase().includes(needle) ||
      r.status.toLowerCase().includes(needle) ||
      r.source_tables.toLowerCase().includes(needle)
  );

  return (
    <div className="max-w-[1400px] mx-auto mt-6 mb-10 px-4 sm:px-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-text-secondary">Workspace / Tools &amp; Reports</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1">Reports</h2>
          <p className="text-sm text-text-secondary mt-1">Generate reports and revisit saved snapshots.</p>
        </div>
        {onBack && (
          <button onClick={onBack} className="text-xs uppercase tracking-wider text-gold hover:text-gold-hover shrink-0">
            ← Back
          </button>
        )}
      </div>

      <div className="flex items-start gap-2 bg-gold/5 border border-gold/20 rounded-lg px-4 py-3 text-sm text-text-secondary">
        <span className="text-gold shrink-0">ℹ</span>
        <span>Every report is a saved snapshot. Running the same period again creates a new report and keeps the previous one.</span>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="grid lg:grid-cols-[1fr_20rem] gap-5">
        <form onSubmit={handleGenerate} className="bg-surface border border-border-dark rounded-lg p-5 space-y-3">
          <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
            <DocumentIcon className="w-4 h-4 text-gold" /> Generate a report
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-text-secondary">Type</label>
              <select
                value={reportType}
                onChange={(e) => setReportType(e.target.value)}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2.5 py-2 text-sm"
              >
                <option value="pipeline">Quotation Pipeline</option>
                {canSeeMargin && <option value="margin">Margin Performance</option>}
                {canSeeOverrideSummary && <option value="override_summary">Override Summary (monthly)</option>}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-text-secondary">Period</label>
              <select
                value={periodPreset}
                onChange={(e) => handlePresetChange(e.target.value)}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2.5 py-2 text-sm"
              >
                {Object.entries(PERIOD_PRESETS).map(([key, { label }]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-text-secondary">Period from</label>
              <input
                type="date"
                required
                value={periodFrom}
                onChange={(e) => {
                  setPeriodFrom(e.target.value);
                  setPeriodPreset("custom");
                }}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2.5 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-secondary">Period to</label>
              <input
                type="date"
                required
                value={periodTo}
                onChange={(e) => {
                  setPeriodTo(e.target.value);
                  setPeriodPreset("custom");
                }}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2.5 py-2 text-sm"
              />
            </div>
          </div>
          <button type="submit" className="bg-gold text-base text-sm rounded px-4 py-2 font-semibold hover:bg-gold-hover">
            Generate report
          </button>
        </form>

        <div className="bg-surface border border-border-dark rounded-lg p-5">
          <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2 mb-3">
            <ShieldIcon className="w-4 h-4 text-gold" /> Your report access
          </h3>
          <ul className="space-y-3">
            {accessRows.map((row) => (
              <li key={row.key} className="flex items-start gap-2">
                <span className={`mt-0.5 shrink-0 ${row.ok ? "text-green-400" : "text-text-secondary"}`}>
                  {row.ok ? "✓" : "🔒"}
                </span>
                <span className="min-w-0">
                  <span className={`block text-sm font-medium ${row.ok ? "text-text-primary" : "text-text-secondary"}`}>
                    {row.label}
                  </span>
                  <span className="block text-xs text-text-secondary">{row.note}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="bg-surface border border-border-dark rounded-lg p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
            <GridIcon className="w-4 h-4 text-gold" /> Report history
            <span className="text-[10px] bg-surface-raised text-text-secondary rounded-full w-5 h-5 flex items-center justify-center">
              {reports.length}
            </span>
          </h3>
          <div className="relative">
            <SearchIcon className="w-3.5 h-3.5 text-text-secondary absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search reports"
              className="rounded border border-border-dark bg-surface-raised text-text-primary pl-7 pr-2 py-1.5 text-xs w-48"
            />
          </div>
        </div>

        {reports.length === 0 ? (
          <p className="text-sm text-text-secondary">No reports generated yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-text-secondary border-b border-border-dark">
                <tr>
                  <th className="text-left px-3 py-2">Report</th>
                  <th className="text-left px-3 py-2">Period</th>
                  <th className="text-left px-3 py-2">Status</th>
                  <th className="text-left px-3 py-2">Source</th>
                  <th className="text-left px-3 py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {visibleReports.map((r) => (
                  <Fragment key={r.id}>
                    <tr className="border-t border-border-dark align-top">
                      <td className="px-3 py-2.5">
                        <span className="inline-flex items-center gap-1.5 text-text-primary capitalize">
                          <DocumentIcon className="w-3.5 h-3.5 text-gold shrink-0" />
                          {(REPORT_TYPE_LABEL[r.report_type] || r.report_type.replace(/_/g, " "))}
                        </span>
                        <button
                          onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                          className="block text-[11px] text-gold hover:underline mt-0.5 pl-5"
                        >
                          {expandedId === r.id ? "︿ Hide details" : "› Snapshot details"}
                        </button>
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap text-text-secondary">
                        {r.period_from} – {r.period_to}
                      </td>
                      <td className="px-3 py-2.5">
                        <span
                          className={`text-[10px] uppercase tracking-wider rounded-full px-2 py-0.5 ${
                            r.status === "released" ? "bg-green-500/15 text-green-400" : "bg-amber-500/15 text-amber-400"
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-text-secondary whitespace-nowrap">{r.source_tables}</td>
                      <td className="px-3 py-2.5 whitespace-nowrap">
                        <button
                          onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                          className="text-gold hover:underline"
                        >
                          View report →
                        </button>
                      </td>
                    </tr>
                    {expandedId === r.id && (
                      <tr className="border-t border-border-dark bg-surface-raised/40">
                        <td colSpan={5} className="px-3 py-3">
                          <p className="text-text-secondary mb-2">hash {r.file_hash.slice(0, 20)}…</p>
                          <div className="flex flex-wrap items-center gap-2">
                            {r.status === "draft" && role === "director" && (
                              <button
                                onClick={() => handleRelease(r.id)}
                                className="bg-gold text-base rounded px-2.5 py-1.5 font-medium hover:bg-gold-hover"
                              >
                                Release
                              </button>
                            )}
                            <button
                              onClick={() => handleSummarize(r.id)}
                              disabled={summarizingId === r.id}
                              className="bg-surface-raised text-gold border border-gold/40 rounded px-2.5 py-1.5 hover:bg-gold/10 hover:-translate-y-0.5 transition-all duration-250 ease-out disabled:opacity-50"
                            >
                              {summarizingId === r.id ? "Summarizing…" : summaries[r.id] ? "Regenerate summary" : "Generate summary"}
                            </button>
                            <button
                              onClick={() => handleExportExcel(r)}
                              className="bg-gold text-base rounded px-2.5 py-1.5 hover:bg-gold-hover hover:-translate-y-0.5 transition-all duration-250 ease-out"
                            >
                              Download Excel
                            </button>
                            <button
                              onClick={() => handleExportPdf(r)}
                              className="bg-gold text-base rounded px-2.5 py-1.5 hover:bg-gold-hover hover:-translate-y-0.5 transition-all duration-250 ease-out"
                            >
                              Download PDF
                            </button>
                          </div>
                          {summaryError && <p className="text-red-400 mt-2">{summaryError}</p>}
                          {summaries[r.id] && (
                            <p className="mt-2 bg-gold/5 border border-gold/20 rounded p-2 text-text-primary">
                              {summaries[r.id]}
                            </p>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {reports.length > 0 && visibleReports.length === 0 && (
          <p className="text-sm text-text-secondary text-center py-4">No reports match that search.</p>
        )}
        <p className="text-[11px] text-text-secondary mt-3">Showing {visibleReports.length} saved report{visibleReports.length === 1 ? "" : "s"}.</p>
      </div>
    </div>
  );
}
