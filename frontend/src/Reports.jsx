import { useEffect, useState } from "react";
import { exportReportBlob, exportReportPdfBlob, generateReport, listReports, releaseReport, summarizeReport } from "./api";

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

export default function Reports({ token, role, onBack }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState(null);
  const [summaries, setSummaries] = useState({}); // reportId -> text
  const [summarizingId, setSummarizingId] = useState(null);
  const [summaryError, setSummaryError] = useState("");

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

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Reports</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-text-secondary mt-1">
          T.2: every report is a computed snapshot, hashed for integrity. Re-running the same
          period creates a new report rather than editing the old one.
        </p>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
      </div>

      <form onSubmit={handleGenerate} className="bg-surface shadow rounded-lg p-6 space-y-3">
        <h3 className="text-sm font-semibold text-text-secondary">Generate a report</h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-text-secondary">Type</label>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
              className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
            >
              <option value="pipeline">Quotation Pipeline</option>
              {canSeeMargin && <option value="margin">Margin Performance</option>}
              {canSeeOverrideSummary && <option value="override_summary">Override Summary (monthly)</option>}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary">Period</label>
            <select
              value={periodPreset}
              onChange={(e) => handlePresetChange(e.target.value)}
              className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
            >
              {Object.entries(PERIOD_PRESETS).map(([key, { label }]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-text-secondary">Period from</label>
            <input
              type="date"
              required
              value={periodFrom}
              onChange={(e) => {
                setPeriodFrom(e.target.value);
                setPeriodPreset("custom");
              }}
              className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary">Period to</label>
            <input
              type="date"
              required
              value={periodTo}
              onChange={(e) => {
                setPeriodTo(e.target.value);
                setPeriodPreset("custom");
              }}
              className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
            />
          </div>
        </div>
        <button type="submit" className="bg-gold text-base text-sm rounded px-4 py-2 hover:bg-gold-hover">
          Generate
        </button>
      </form>

      <div className="bg-surface shadow rounded-lg p-6">
        <h3 className="text-sm font-semibold text-text-secondary mb-3">History ({reports.length})</h3>
        {reports.length === 0 && <p className="text-sm text-text-secondary">No reports generated yet.</p>}
        <div className="space-y-2">
          {reports.map((r) => (
            <div key={r.id} className="border border-border-dark rounded px-3 py-2 text-sm">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium capitalize">{r.report_type.replace(/_/g, " ")}</span>{" "}
                  <span className="text-text-secondary">
                    {r.period_from} → {r.period_to}
                  </span>{" "}
                  <span
                    className={`text-xs rounded px-2 py-0.5 ${
                      r.status === "released" ? "bg-green-500/15 text-green-400" : "bg-amber-500/15 text-amber-400"
                    }`}
                  >
                    {r.status}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {r.status === "draft" && role === "director" && (
                    <button
                      onClick={() => handleRelease(r.id)}
                      className="text-xs bg-gold text-base rounded px-2 py-1 hover:bg-gold-hover"
                    >
                      Release
                    </button>
                  )}
                  <button
                    onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                    className="text-xs text-gold hover:underline"
                  >
                    {expandedId === r.id ? "Hide" : "View"}
                  </button>
                </div>
              </div>
              <p className="text-xs text-text-secondary mt-1">
                source: {r.source_tables} · hash {r.file_hash.slice(0, 12)}…
              </p>
              {expandedId === r.id && (
                <>
                  <div className="mt-2 flex items-center gap-2">
                    <button
                      onClick={() => handleSummarize(r.id)}
                      disabled={summarizingId === r.id}
                      className="text-xs bg-surface-raised text-gold border border-gold/40 rounded px-2 py-1 hover:bg-gold/10 hover:-translate-y-0.5 transition-all duration-250 ease-out disabled:opacity-50"
                    >
                      {summarizingId === r.id
                        ? "Summarizing…"
                        : summaries[r.id]
                        ? "Regenerate summary"
                        : "Generate summary"}
                    </button>
                    <button
                      onClick={() => handleExportExcel(r)}
                      className="text-xs bg-gold text-base rounded px-2 py-1 hover:bg-gold-hover hover:-translate-y-0.5 transition-all duration-250 ease-out"
                    >
                      Download Excel
                    </button>
                    <button
                      onClick={() => handleExportPdf(r)}
                      className="text-xs bg-gold text-base rounded px-2 py-1 hover:bg-gold-hover hover:-translate-y-0.5 transition-all duration-250 ease-out"
                    >
                      Download PDF
                    </button>
                  </div>
                  {summaryError && <p className="text-xs text-red-400 mt-1">{summaryError}</p>}
                  {summaries[r.id] && (
                    <p className="mt-2 bg-gold/5 border border-gold/20 rounded p-2 text-xs text-text-primary">
                      {summaries[r.id]}
                    </p>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
