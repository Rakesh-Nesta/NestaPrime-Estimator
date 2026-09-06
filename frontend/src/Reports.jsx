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
    return <p className="text-center text-gray-500 mt-10">Loading Reports…</p>;
  }

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Reports</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-blue-600 hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-gray-400 mt-1">
          T.2: every report is a computed snapshot, hashed for integrity. Re-running the same
          period creates a new report rather than editing the old one.
        </p>
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      </div>

      <form onSubmit={handleGenerate} className="bg-white shadow rounded-lg p-6 space-y-3">
        <h3 className="text-sm font-semibold text-gray-700">Generate a report</h3>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700">Type</label>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-2 py-2 text-sm"
            >
              <option value="pipeline">Quotation Pipeline</option>
              {canSeeMargin && <option value="margin">Margin Performance</option>}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Period from</label>
            <input
              type="date"
              required
              value={periodFrom}
              onChange={(e) => setPeriodFrom(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-2 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Period to</label>
            <input
              type="date"
              required
              value={periodTo}
              onChange={(e) => setPeriodTo(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-2 py-2 text-sm"
            />
          </div>
        </div>
        <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
          Generate
        </button>
      </form>

      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">History ({reports.length})</h3>
        {reports.length === 0 && <p className="text-sm text-gray-400">No reports generated yet.</p>}
        <div className="space-y-2">
          {reports.map((r) => (
            <div key={r.id} className="border border-gray-200 rounded px-3 py-2 text-sm">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium capitalize">{r.report_type}</span>{" "}
                  <span className="text-gray-500">
                    {r.period_from} → {r.period_to}
                  </span>{" "}
                  <span
                    className={`text-xs rounded px-2 py-0.5 ${
                      r.status === "released" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"
                    }`}
                  >
                    {r.status}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {r.status === "draft" && role === "director" && (
                    <button
                      onClick={() => handleRelease(r.id)}
                      className="text-xs bg-blue-600 text-white rounded px-2 py-1 hover:bg-blue-700"
                    >
                      Release
                    </button>
                  )}
                  <button
                    onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    {expandedId === r.id ? "Hide" : "View"}
                  </button>
                </div>
              </div>
              <p className="text-xs text-gray-400 mt-1">
                source: {r.source_tables} · hash {r.file_hash.slice(0, 12)}…
              </p>
              {expandedId === r.id && (
                <pre className="mt-2 bg-gray-50 rounded p-2 text-xs overflow-x-auto">
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
