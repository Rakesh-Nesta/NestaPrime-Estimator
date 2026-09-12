import { useEffect, useState } from "react";
import { downloadAuditLogCsvBlob, listAuditLog } from "./api";

function downloadBlobAsFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function AuditLogView({ token, onBack }) {
  const [entries, setEntries] = useState([]);
  const [documentType, setDocumentType] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    return listAuditLog(token, { documentType: documentType || undefined }).then(setEntries);
  }

  useEffect(() => {
    setLoading(true);
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, documentType]);

  async function handleExport() {
    setError("");
    try {
      const blob = await downloadAuditLogCsvBlob(token, { documentType: documentType || undefined });
      downloadBlobAsFile(blob, "audit_log.csv");
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading audit log…</p>;
  }

  return (
    <div className="max-w-4xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Audit Log</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-text-secondary mt-1">
          M.5: "change_log[] on every document: who, when, field, old → new, reason (for approvals, skips,
          waivers, discounts). Exportable for Director review." Also covers Settings changes (Q.2 rule 7).
          Director-only.
        </p>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
        <div className="flex items-center gap-2 mt-3">
          <select
            value={documentType}
            onChange={(e) => setDocumentType(e.target.value)}
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
          >
            <option value="">All document types</option>
            <option value="estimate">Estimate (waivers)</option>
            <option value="estimate_option">Estimate option (approvals)</option>
            <option value="quotation">Quotation (discounts/releases)</option>
            <option value="skip_request">Skip request</option>
            <option value="price_request">Vendor price request</option>
            <option value="site_survey">Site survey</option>
            <option value="setting">Master Setting</option>
          </select>
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
              <th className="text-left px-3 py-2">Timestamp</th>
              <th className="text-left px-3 py-2">Role</th>
              <th className="text-left px-3 py-2">Document type</th>
              <th className="text-left px-3 py-2">Field</th>
              <th className="text-left px-3 py-2">Old → New</th>
              <th className="text-left px-3 py-2">Reason</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-t border-border-dark">
                <td className="px-3 py-2 whitespace-nowrap">{new Date(e.timestamp).toLocaleString()}</td>
                <td className="px-3 py-2">{e.role}</td>
                <td className="px-3 py-2">{e.document_type}</td>
                <td className="px-3 py-2">{e.field}</td>
                <td className="px-3 py-2">
                  {e.old_value ?? "—"} → {e.new_value ?? "—"}
                </td>
                <td className="px-3 py-2">{e.reason ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {entries.length === 0 && <p className="text-sm text-text-secondary text-center py-6">No entries yet.</p>}
      </div>
    </div>
  );
}
