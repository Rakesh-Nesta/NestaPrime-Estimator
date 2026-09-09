import { useEffect, useState } from "react";
import {
  bulkUpdateSettings,
  createSettingVersion,
  downloadCompanyLogoBlob,
  getCompanyLogoMeta,
  listSettings,
  uploadCompanyLogo,
} from "./api";

export default function MasterSettings({ token, onBack }) {
  const [settings, setSettings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editKey, setEditKey] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [editReason, setEditReason] = useState("");

  const [bulkPrefix, setBulkPrefix] = useState("");
  const [bulkPercent, setBulkPercent] = useState("");
  const [bulkReason, setBulkReason] = useState("");

  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [newUnit, setNewUnit] = useState("");
  const [newReason, setNewReason] = useState("");

  const [logoMeta, setLogoMeta] = useState(null);
  const [logoPreviewUrl, setLogoPreviewUrl] = useState(null);
  const [logoError, setLogoError] = useState("");
  const [uploadingLogo, setUploadingLogo] = useState(false);

  function load() {
    return listSettings(token).then(setSettings);
  }

  function loadLogo() {
    return Promise.all([getCompanyLogoMeta(token), downloadCompanyLogoBlob(token)]).then(([meta, blob]) => {
      setLogoMeta(meta);
      setLogoPreviewUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return blob ? URL.createObjectURL(blob) : null;
      });
    });
  }

  useEffect(() => {
    load().finally(() => setLoading(false));
    loadLogo().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleLogoUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLogoError("");
    setUploadingLogo(true);
    try {
      await uploadCompanyLogo(token, file);
      await loadLogo();
    } catch (err) {
      setLogoError(err.message);
    } finally {
      setUploadingLogo(false);
      e.target.value = "";
    }
  }

  function startEdit(setting) {
    setEditKey(setting.key);
    setEditValue(setting.value);
    setEditReason("");
    setError("");
  }

  async function saveEdit() {
    setError("");
    try {
      await createSettingVersion(token, { key: editKey, value: editValue, reason: editReason || null });
      setEditKey(null);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleCreateNew(e) {
    e.preventDefault();
    setError("");
    try {
      await createSettingVersion(token, { key: newKey, value: newValue, unit: newUnit || null, reason: newReason || null });
      setNewKey("");
      setNewValue("");
      setNewUnit("");
      setNewReason("");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleBulkUpdate(e) {
    e.preventDefault();
    setError("");
    try {
      await bulkUpdateSettings(token, {
        key_prefix: bulkPrefix,
        percent_change: Number(bulkPercent),
        reason: bulkReason,
      });
      setBulkPrefix("");
      setBulkPercent("");
      setBulkReason("");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) {
    return <p className="text-center text-gray-500 mt-10">Loading Master Settings…</p>;
  }

  return (
    <div className="max-w-2xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Master Settings</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-blue-600 hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-gray-400 mt-1">
          Q.2: editing a setting creates a new version, effective from today by default — it never
          alters a document that already froze the old value. Director-only; PM is read-only.
        </p>
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      </div>

      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-1">Company logo</h3>
        <p className="text-xs text-gray-400 mb-3">
          Part O COMPANY.logo / R.0: "Logo (SVG/PNG) ... for PDF." Printed on every Estimate and Quotation PDF
          header (PNG only -- SVG downloads fine but can't be embedded in the PDF itself). Director-only.
        </p>
        <div className="flex items-center gap-4">
          <div className="w-20 h-20 border border-gray-200 rounded flex items-center justify-center bg-gray-50 overflow-hidden">
            {logoPreviewUrl ? (
              <img src={logoPreviewUrl} alt="Company logo" className="max-w-full max-h-full object-contain" />
            ) : (
              <span className="text-[10px] text-gray-400 text-center px-1">No logo uploaded</span>
            )}
          </div>
          <div className="text-sm">
            {logoMeta && (
              <p className="text-gray-600">
                {logoMeta.original_filename}{" "}
                <span className="text-xs text-gray-400">
                  ({logoMeta.content_type}, uploaded {new Date(logoMeta.uploaded_at).toLocaleDateString()})
                </span>
              </p>
            )}
            <label className="inline-block mt-1 text-xs bg-blue-600 text-white rounded px-3 py-1.5 cursor-pointer hover:bg-blue-700">
              {uploadingLogo ? "Uploading…" : logoMeta ? "Replace logo" : "Upload logo"}
              <input type="file" accept="image/png,image/svg+xml" onChange={handleLogoUpload} className="hidden" disabled={uploadingLogo} />
            </label>
            {logoError && <p className="text-xs text-red-600 mt-1">{logoError}</p>}
          </div>
        </div>
      </div>

      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Current settings ({settings.length})</h3>
        <div className="space-y-2">
          {settings.map((s) => (
            <div key={s.key} className="border border-gray-200 rounded px-3 py-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium">{s.key}</span>
                {editKey !== s.key && (
                  <button onClick={() => startEdit(s)} className="text-blue-600 hover:underline text-xs">
                    Edit
                  </button>
                )}
              </div>
              {editKey === s.key ? (
                <div className="mt-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      className="flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
                    />
                    <span className="text-xs text-gray-400">{s.unit}</span>
                  </div>
                  <input
                    type="text"
                    placeholder="Reason for change"
                    value={editReason}
                    onChange={(e) => setEditReason(e.target.value)}
                    className="w-full rounded border border-gray-300 px-2 py-1 text-xs"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={saveEdit}
                      className="bg-blue-600 text-white text-xs rounded px-3 py-1 hover:bg-blue-700"
                    >
                      Save new version
                    </button>
                    <button
                      onClick={() => setEditKey(null)}
                      className="text-xs text-gray-500 hover:underline"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-gray-600">
                  {s.value} {s.unit} <span className="text-xs text-gray-400">(effective {s.effective_from})</span>
                </p>
              )}
            </div>
          ))}
        </div>
      </div>

      <form onSubmit={handleCreateNew} className="bg-white shadow rounded-lg p-6 space-y-3">
        <h3 className="text-sm font-semibold text-gray-700">Add a new setting</h3>
        <p className="text-xs text-gray-400">
          Any key not yet listed above (e.g. warranty_years_school, payment_schedule_advance_percent_club,
          company_pan, company_gstin, company_bank_name, company_registered_office_city) -- create it once here,
          then edit it above like any other setting.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700">Key</label>
            <input
              type="text"
              required
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Value</label>
            <input
              type="text"
              required
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Unit (optional)</label>
            <input
              type="text"
              placeholder="e.g. %, years"
              value={newUnit}
              onChange={(e) => setNewUnit(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Reason (optional)</label>
            <input
              type="text"
              value={newReason}
              onChange={(e) => setNewReason(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
        </div>
        <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
          Create setting
        </button>
      </form>

      <form onSubmit={handleBulkUpdate} className="bg-white shadow rounded-lg p-6 space-y-3">
        <h3 className="text-sm font-semibold text-gray-700">Bulk update (Q.2 rule 5)</h3>
        <p className="text-xs text-gray-400">
          Apply a % change to every setting whose key starts with a prefix, e.g. "steel_" for +6%.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700">Key prefix</label>
            <input
              type="text"
              required
              value={bulkPrefix}
              onChange={(e) => setBulkPrefix(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">% change</label>
            <input
              type="number"
              step="any"
              required
              value={bulkPercent}
              onChange={(e) => setBulkPercent(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
        </div>
        <input
          type="text"
          required
          placeholder="Reason"
          value={bulkReason}
          onChange={(e) => setBulkReason(e.target.value)}
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700"
        >
          Apply bulk update
        </button>
      </form>
    </div>
  );
}
