import { useEffect, useState } from "react";
import { bulkUpdateSettings, createSettingVersion, listSettings } from "./api";

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

  function load() {
    return listSettings(token).then(setSettings);
  }

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [token]);

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
