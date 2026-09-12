import { useEffect, useState } from "react";
import { generateReport, listReports, releaseReport } from "./api";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function startOfMonthIso() {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}

export default function Reports({ token, role, onBack }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState(null);

  const [reportType, setReportType] = useState("pipeline");
  const [periodFrom, setPeriodFrom] = useState(startOfMonthIso());
  const [periodTo, setPeriodTo] = useState(todayIso());

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
        <div className="grid grid-cols-3 gap-3">
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
            <label className="block text-sm font-medium text-text-secondary">Period from</label>
            <input
              type="date"
              required
              value={periodFrom}
              onChange={(e) => setPeriodFrom(e.target.value)}
              className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary">Period to</label>
            <input
              type="date"
              required
              value={periodTo}
              onChange={(e) => setPeriodTo(e.target.value)}
              className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
            />
          </div>
        </div>
        <button type="submit" className="bg-gold text-white text-sm rounded px-4 py-2 hover:bg-gold-hover">
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
                      className="text-xs bg-gold text-white rounded px-2 py-1 hover:bg-gold-hover"
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
                <pre className="mt-2 bg-surface-raised rounded p-2 text-xs overflow-x-auto">
                  {JSON.stringify(r.content, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
