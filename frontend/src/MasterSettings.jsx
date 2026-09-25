import { useEffect, useState } from "react";
import {
  bulkUpdateSettings,
  createMessageTemplate,
  createSettingVersion,
  downloadCompanyLogoBlob,
  exportSettingsBlob,
  getCompanyLogoMeta,
  getQuotationTemplateDefaults,
  importSettingsExcel,
  listAllQuotations,
  listFieldSettings,
  listMessageTemplates,
  listSettings,
  previewQuotationTemplateBlob,
  updateFieldSetting,
  updateMessageTemplate,
  uploadCompanyLogo,
} from "./api";
import MiniField from "./MiniField";

function downloadBlobAsFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// Amendment 51 (Section 55): Master Settings is now only the settings -- user
// management and the role view moved to the Director-only Team & Access screen.
// PM can read settings (GET /settings) but every write endpoint is Director-only,
// so for PM the write controls are simply not shown; the Director's screen is
// unchanged.
export default function MasterSettings({ token, onBack, currentUser }) {
  const readOnly = currentUser?.role !== "director";

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

  const [importResult, setImportResult] = useState(null);
  const [importingExcel, setImportingExcel] = useState(false);

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

  async function handleExportExcel() {
    setError("");
    try {
      const blob = await exportSettingsBlob(token);
      downloadBlobAsFile(blob, "master-settings.xlsx");
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleImportExcel(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    setImportResult(null);
    setImportingExcel(true);
    try {
      const result = await importSettingsExcel(token, file);
      setImportResult(result);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setImportingExcel(false);
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
    return <p className="text-center text-text-secondary mt-10">Loading Master Settings…</p>;
  }

  return (
    <div className="max-w-2xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Master Settings</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-text-secondary mt-1">
          {readOnly
            ? "You can view the settings; only the Director can change them."
            : "Q.2: editing a setting creates a new version, effective from today by default — it never alters a document that already froze the old value. Director-only; PM is read-only."}
        </p>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
      </div>

      <>
      <div className="bg-surface shadow rounded-lg p-6">
        <h3 className="text-sm font-semibold text-text-secondary mb-1">Company logo</h3>
        <p className="text-xs text-text-secondary mb-3">
          Part O COMPANY.logo / R.0: "Logo (SVG/PNG) ... for PDF." Printed on every Estimate and Quotation PDF
          header (PNG only -- SVG downloads fine but can't be embedded in the PDF itself). Director-only.
        </p>
        <div className="flex items-center gap-4">
          <div className="w-20 h-20 border border-border-dark rounded flex items-center justify-center bg-surface-raised overflow-hidden">
            {logoPreviewUrl ? (
              <img src={logoPreviewUrl} alt="Company logo" className="max-w-full max-h-full object-contain" />
            ) : (
              <span className="text-[10px] text-text-secondary text-center px-1">No logo uploaded</span>
            )}
          </div>
          <div className="text-sm">
            {logoMeta && (
              <p className="text-text-secondary">
                {logoMeta.original_filename}{" "}
                <span className="text-xs text-text-secondary">
                  ({logoMeta.content_type}, uploaded {new Date(logoMeta.uploaded_at).toLocaleDateString()})
                </span>
              </p>
            )}
            {!readOnly && (
              <label className="inline-block mt-1 text-xs bg-gold text-base rounded px-3 py-1.5 cursor-pointer hover:bg-gold-hover">
                {uploadingLogo ? "Uploading…" : logoMeta ? "Replace logo" : "Upload logo"}
                <input type="file" accept="image/png,image/svg+xml" onChange={handleLogoUpload} className="hidden" disabled={uploadingLogo} />
              </label>
            )}
            {logoError && <p className="text-xs text-red-400 mt-1">{logoError}</p>}
          </div>
        </div>
      </div>

      <CompanyDetailsCard token={token} readOnly={readOnly} />

      <div className="bg-surface shadow rounded-lg p-6">
        <h3 className="text-sm font-semibold text-text-secondary mb-1">Excel export / import</h3>
        <p className="text-xs text-text-secondary mb-3">
          Q.2 rule 6: "exportable to Excel and importable back, so NestaPrime can maintain its rate card in Excel if
          preferred." Re-importing an unchanged file is a safe no-op -- only rows whose Value actually differs from
          what's currently effective create a new version.
        </p>
        <div className="flex items-center gap-3">
          <button
            onClick={handleExportExcel}
            className="text-xs bg-surface-raised text-text-secondary rounded px-3 py-1.5 hover:bg-surface-raised"
          >
            Export to Excel
          </button>
          {!readOnly && (
            <label className="text-xs bg-gold text-base rounded px-3 py-1.5 cursor-pointer hover:bg-gold-hover">
              {importingExcel ? "Importing…" : "Import from Excel"}
              <input
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                onChange={handleImportExcel}
                className="hidden"
                disabled={importingExcel}
              />
            </label>
          )}
        </div>
        {importResult && (
          <div className="mt-3 text-xs bg-surface-raised border border-border-dark rounded p-3">
            <p className="text-text-secondary">
              <span className="font-medium">{importResult.created.length}</span> new version(s) created,{" "}
              <span className="font-medium">{importResult.unchanged}</span> row(s) unchanged (skipped)
              {importResult.errors.length > 0 && (
                <>
                  , <span className="font-medium text-red-400">{importResult.errors.length}</span> row error(s)
                </>
              )}
              .
            </p>
            {importResult.errors.length > 0 && (
              <ul className="mt-1 list-disc list-inside text-red-400">
                {importResult.errors.map((e) => (
                  <li key={e.row}>
                    Row {e.row}: {e.detail}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <QuotationTemplateCard token={token} readOnly={readOnly} />

      <MessageTemplatesCard token={token} readOnly={readOnly} />

      <FieldSettingsCard token={token} readOnly={readOnly} />

      <div className="bg-surface shadow rounded-lg p-6">
        <h3 className="text-sm font-semibold text-text-secondary mb-3">Current settings ({settings.length})</h3>
        <div className="space-y-2">
          {settings.map((s) => (
            <div key={s.key} className="border border-border-dark rounded px-3 py-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium">{s.key}</span>
                {!readOnly && editKey !== s.key && (
                  <button onClick={() => startEdit(s)} className="text-gold hover:underline text-xs">
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
                      className="flex-1 rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
                    />
                    <span className="text-xs text-text-secondary">{s.unit}</span>
                  </div>
                  <input
                    type="text"
                    placeholder="Reason for change"
                    value={editReason}
                    onChange={(e) => setEditReason(e.target.value)}
                    className="w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={saveEdit}
                      className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover"
                    >
                      Save new version
                    </button>
                    <button
                      onClick={() => setEditKey(null)}
                      className="text-xs text-text-secondary hover:underline"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-text-secondary">
                  {s.value} {s.unit} <span className="text-xs text-text-secondary">(effective {s.effective_from})</span>
                </p>
              )}
            </div>
          ))}
        </div>
      </div>

      {!readOnly && (
      <form onSubmit={handleCreateNew} className="bg-surface shadow rounded-lg p-6 space-y-3">
        <h3 className="text-sm font-semibold text-text-secondary">Add a new setting</h3>
        <p className="text-xs text-text-secondary">
          Any key not yet listed above (e.g. warranty_years_school, payment_schedule_advance_percent_club,
          company_pan, company_gstin, company_bank_name, company_registered_office_city) -- create it once here,
          then edit it above like any other setting.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-text-secondary">Key</label>
            <input
              type="text"
              required
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary">Value</label>
            <input
              type="text"
              required
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary">Unit (optional)</label>
            <input
              type="text"
              placeholder="e.g. %, years"
              value={newUnit}
              onChange={(e) => setNewUnit(e.target.value)}
              className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary">Reason (optional)</label>
            <input
              type="text"
              value={newReason}
              onChange={(e) => setNewReason(e.target.value)}
              className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
            />
          </div>
        </div>
        <button type="submit" className="bg-gold text-base text-sm rounded px-4 py-2 hover:bg-gold-hover">
          Create setting
        </button>
      </form>
      )}

      {!readOnly && (
      <form onSubmit={handleBulkUpdate} className="bg-surface shadow rounded-lg p-6 space-y-3">
        <h3 className="text-sm font-semibold text-text-secondary">Bulk update (Q.2 rule 5)</h3>
        <p className="text-xs text-text-secondary">
          Apply a % change to every setting whose key starts with a prefix, e.g. "steel_" for +6%.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-text-secondary">Key prefix</label>
            <input
              type="text"
              required
              value={bulkPrefix}
              onChange={(e) => setBulkPrefix(e.target.value)}
              className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary">% change</label>
            <input
              type="number"
              step="any"
              required
              value={bulkPercent}
              onChange={(e) => setBulkPercent(e.target.value)}
              className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
            />
          </div>
        </div>
        <input
          type="text"
          required
          placeholder="Reason"
          value={bulkReason}
          onChange={(e) => setBulkReason(e.target.value)}
          className="w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
        />
        <button
          type="submit"
          className="bg-gold text-base text-sm rounded px-4 py-2 hover:bg-gold-hover"
        >
          Apply bulk update
        </button>
      </form>
      )}
      </>
    </div>
  );
}

const DOC_TYPES = [
  "", "cost_sheet", "estimate", "quotation", "work_order", "technical_bid_checklist_item", "price_request", "site_survey",
];

function emptyTemplateForm() {
  return { document_type: "", channel: "email", name: "", subject: "", body: "", language: "en" };
}

const FIELD_LABELS = {
  soil_type: "Soil type",
  distance_km: "Distance from hub (km)",
  number_of_courts: "Number of courts",
  site_access: "Site access",
  power_available: "Power available",
  water_available: "Water available",
};
const FIELD_STATES = ["compulsory", "optional", "hidden"];

function FieldSettingsCard({ token, readOnly }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savingKey, setSavingKey] = useState(null);

  function load() {
    return listFieldSettings(token).then(setRows);
  }

  useEffect(() => {
    setLoading(true);
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleChange(fieldKey, state) {
    setError("");
    setSavingKey(fieldKey);
    try {
      await updateFieldSetting(token, fieldKey, state);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingKey(null);
    }
  }

  if (loading) return null;

  return (
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <h3 className="text-sm font-semibold text-text-secondary mb-1">Field settings</h3>
      <p className="text-xs text-text-secondary mb-2">
        Amendment 5 Phase 2: New Project Setup fields the Director can make Optional (a real "None" becomes
        selectable) or Hidden (removed from the form, uses its default) -- Compulsory matches today's behaviour and
        is the default for every field until changed here.
      </p>
      {error && <p className="text-xs text-red-400 mb-2">{error}</p>}
      <div className="space-y-2">
        {rows.map((r) => (
          <div key={r.field_key} className="flex items-center justify-between border border-border-dark rounded px-3 py-2 text-sm">
            <span>{FIELD_LABELS[r.field_key] || r.field_key}</span>
            {readOnly ? (
              <span className="text-text-secondary">{r.state.charAt(0).toUpperCase() + r.state.slice(1)}</span>
            ) : (
            <select
              value={r.state}
              disabled={savingKey === r.field_key}
              onChange={(e) => handleChange(r.field_key, e.target.value)}
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm disabled:opacity-50"
            >
              {FIELD_STATES.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

const COMPANY_DETAIL_FIELDS = [
  { key: "company_legal_name", label: "Legal name" },
  { key: "company_pan", label: "PAN" },
  { key: "company_gstin", label: "GSTIN" },
  { key: "company_registered_office_city", label: "Registered office city" },
  { key: "company_bank_name", label: "Bank name" },
  { key: "company_bank_account_name", label: "Bank account name" },
  { key: "company_bank_account_number", label: "Bank account number" },
  { key: "company_bank_ifsc", label: "Bank IFSC" },
  // Amendment 54: the cover letter's sign-off ("Yours faithfully, For <company>, <name>, <designation>").
  { key: "company_signatory_name", label: "Authorised signatory name" },
  { key: "company_signatory_designation", label: "Authorised signatory designation" },
];

function CompanyDetailsCard({ token, readOnly }) {
  const [values, setValues] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState("");

  function load() {
    return listSettings(token).then((rows) => {
      const next = {};
      for (const f of COMPANY_DETAIL_FIELDS) {
        const row = rows.find((r) => r.key === f.key);
        next[f.key] = row ? row.value : "";
      }
      setValues(next);
    });
  }

  useEffect(() => {
    setLoading(true);
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleSave() {
    setError("");
    setSavedMessage("");
    setSaving(true);
    try {
      await Promise.all(
        COMPANY_DETAIL_FIELDS.map((f) =>
          createSettingVersion(token, {
            key: f.key,
            value: values[f.key] || "",
            reason: "Edited via Master Settings (Section 14)",
          })
        )
      );
      await load();
      setSavedMessage("Saved -- these details now print on every Quotation PDF.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return null;

  return (
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <h3 className="text-sm font-semibold text-text-secondary mb-1">Company details</h3>
      <p className="text-xs text-text-secondary mb-2">
        {readOnly
          ? "These print on the Quotation PDF; the authorised signatory signs off its cover letter. A blank field is simply omitted from the PDF, never printed as placeholder text."
          : 'Part O COMPANY / Section 14: these already fed the Quotation PDF before this panel existed -- they just had to be set through the raw "Add a new setting" key/value form below. This is the same data, with real labels. The authorised signatory (Amendment 54) signs off the cover letter that prints when a Quotation has a cover note. A blank field is simply omitted from the PDF, never printed as placeholder text.'}
      </p>
      {error && <p className="text-xs text-red-400 mb-2">{error}</p>}
      {savedMessage && <p className="text-xs text-green-400 mb-2">{savedMessage}</p>}
      <div className="grid grid-cols-2 gap-3">
        {COMPANY_DETAIL_FIELDS.map((f) => (
          <div key={f.key}>
            <label className="block text-xs font-medium text-text-secondary mb-1">{f.label}</label>
            {readOnly ? (
              <p className="text-sm text-text-primary break-words">{values[f.key] || <span className="text-text-secondary">Not set</span>}</p>
            ) : (
              <input
                value={values[f.key] || ""}
                onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                className="w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5 text-sm"
              />
            )}
          </div>
        ))}
      </div>
      {!readOnly && (
        <button
          onClick={handleSave}
          disabled={saving}
          className="text-xs bg-gold text-base rounded px-3 py-1.5 hover:bg-gold-hover disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
      )}
    </div>
  );
}

function QuotationTemplateCard({ token, readOnly }) {
  const [termsText, setTermsText] = useState("");
  const [warrantyRows, setWarrantyRows] = useState([]);
  const [quotations, setQuotations] = useState([]);
  const [previewQuotationId, setPreviewQuotationId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState("");

  function load() {
    // The quotation list only feeds the Director's Preview picker (preview-pdf is
    // Director-only), so a read-only viewer does not fetch it.
    return Promise.all([getQuotationTemplateDefaults(token), readOnly ? [] : listAllQuotations(token)]).then(
      ([defaults, allQuotations]) => {
        setTermsText(defaults.terms.join("\n"));
        setWarrantyRows(defaults.warranty_table.map(([item, basis]) => ({ item, basis })));
        setQuotations(allQuotations);
        if (allQuotations.length > 0) setPreviewQuotationId(allQuotations[0].id);
      }
    );
  }

  useEffect(() => {
    setLoading(true);
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function currentTerms() {
    return termsText.split("\n").map((t) => t.trim()).filter(Boolean);
  }

  function currentWarrantyTable() {
    return warrantyRows.filter((r) => r.item.trim() && r.basis.trim()).map((r) => [r.item.trim(), r.basis.trim()]);
  }

  function updateWarrantyRow(index, field, value) {
    setWarrantyRows((rows) => rows.map((r, i) => (i === index ? { ...r, [field]: value } : r)));
  }

  function addWarrantyRow() {
    setWarrantyRows((rows) => [...rows, { item: "", basis: "" }]);
  }

  function removeWarrantyRow(index) {
    setWarrantyRows((rows) => rows.filter((_, i) => i !== index));
  }

  async function handlePreview() {
    setError("");
    setSavedMessage("");
    if (!previewQuotationId) {
      setError("No Quotation exists yet to preview against -- create one first.");
      return;
    }
    setPreviewing(true);
    try {
      const blob = await previewQuotationTemplateBlob(token, previewQuotationId, {
        terms: currentTerms(),
        warrantyTable: currentWarrantyTable(),
      });
      // window.open() after an await is routinely popup-blocked (the
      // user-activation gesture from the click has already expired by
      // the time the fetch resolves) -- downloading instead matches
      // every other generated PDF/export in this app and is never
      // blocked, since it's a plain anchor click, not a new window.
      downloadBlobAsFile(blob, "quotation-template-preview.pdf");
    } catch (err) {
      setError(err.message);
    } finally {
      setPreviewing(false);
    }
  }

  async function handleSave() {
    setError("");
    setSavedMessage("");
    setSaving(true);
    try {
      await createSettingVersion(token, {
        key: "quotation_terms_and_conditions",
        value: JSON.stringify(currentTerms()),
        reason: "Edited via Master Settings (Section 14)",
      });
      await createSettingVersion(token, {
        key: "quotation_warranty_table",
        value: JSON.stringify(currentWarrantyTable()),
        reason: "Edited via Master Settings (Section 14)",
      });
      await load();
      setSavedMessage("Saved -- new Quotation PDFs will use this wording from now on.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return null;

  return (
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <h3 className="text-sm font-semibold text-text-secondary mb-1">Quotation terms &amp; warranty</h3>
      <p className="text-xs text-text-secondary mb-2">
        Section 14: the Quotation PDF's own T&amp;C clauses and warranty table, Director-editable -- seeded below
        with today's actual wording, so nothing on the PDF changes until you save an edit here. Always preview
        before saving; a Quotation already sent is unaffected either way (each PDF is built live at download time).
      </p>
      {error && <p className="text-xs text-red-400 mb-2">{error}</p>}
      {savedMessage && <p className="text-xs text-green-400 mb-2">{savedMessage}</p>}

      <div>
        <label className="block text-xs font-medium text-text-secondary mb-1">Terms &amp; conditions (one per line)</label>
        <textarea
          value={termsText}
          onChange={(e) => setTermsText(e.target.value)}
          readOnly={readOnly}
          rows={8}
          className="w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm font-mono"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-text-secondary mb-1">Warranty table</label>
        <div className="space-y-1.5">
          {warrantyRows.map((row, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                value={row.item}
                onChange={(e) => updateWarrantyRow(i, "item", e.target.value)}
                readOnly={readOnly}
                placeholder="Item"
                className="flex-1 min-w-0 rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
              />
              <input
                value={row.basis}
                onChange={(e) => updateWarrantyRow(i, "basis", e.target.value)}
                readOnly={readOnly}
                placeholder="Basis"
                className="flex-1 min-w-0 rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
              />
              {!readOnly && (
                <button onClick={() => removeWarrantyRow(i)} className="text-xs text-red-400 hover:underline">
                  Remove
                </button>
              )}
            </div>
          ))}
        </div>
        {!readOnly && (
          <button onClick={addWarrantyRow} className="text-xs text-gold hover:underline mt-1.5">
            + Add row
          </button>
        )}
      </div>

      {!readOnly && (
      <div className="flex items-center gap-3 pt-1">
        <select
          value={previewQuotationId}
          onChange={(e) => setPreviewQuotationId(e.target.value)}
          className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5 text-xs flex-1"
        >
          {quotations.length === 0 && <option value="">No Quotations exist yet</option>}
          {quotations.map((q) => (
            <option key={q.id} value={q.id}>
              {q.document_no} -- {q.project_no} -- {q.client_name}
            </option>
          ))}
        </select>
        <button
          onClick={handlePreview}
          disabled={previewing || !previewQuotationId}
          className="text-xs bg-surface-raised text-gold border border-gold/40 rounded px-3 py-1.5 hover:bg-gold/10 disabled:opacity-50"
        >
          {previewing ? "Rendering…" : "Preview"}
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="text-xs bg-gold text-base rounded px-3 py-1.5 hover:bg-gold-hover disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
      </div>
      )}
    </div>
  );
}

function MessageTemplatesCard({ token, readOnly }) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [addForm, setAddForm] = useState(emptyTemplateForm());
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(null);

  function load() {
    return listMessageTemplates(token, { includeInactive: true }).then(setTemplates);
  }

  useEffect(() => {
    setLoading(true);
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    try {
      await createMessageTemplate(token, {
        document_type: addForm.document_type || null,
        channel: addForm.channel,
        name: addForm.name,
        subject: addForm.subject || null,
        body: addForm.body,
        language: addForm.language,
      });
      setAddForm(emptyTemplateForm());
      setAdding(false);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  function startEdit(t) {
    setEditingId(t.id);
    setEditForm({
      document_type: t.document_type || "", name: t.name, subject: t.subject || "", body: t.body,
      language: t.language, whatsapp_template_status: t.whatsapp_template_status || "",
    });
  }

  async function handleSaveEdit() {
    setError("");
    try {
      await updateMessageTemplate(token, editingId, {
        document_type: editForm.document_type || null,
        name: editForm.name,
        subject: editForm.subject || null,
        body: editForm.body,
        language: editForm.language,
        ...(editForm.whatsapp_template_status ? { whatsapp_template_status: editForm.whatsapp_template_status } : {}),
      });
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleActive(t) {
    setError("");
    try {
      await updateMessageTemplate(token, t.id, { is_active: !t.is_active });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) return null;

  return (
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <h3 className="text-sm font-semibold text-text-secondary mb-1">Message templates</h3>
      <p className="text-xs text-text-secondary mb-2">
        M.7.2 rule 6: "Director-managed library of message templates per document and channel." A WhatsApp
        template needs Meta's approval (through the provider, outside this app) before it can be used on a real
        send -- editing a submitted/approved template's wording resets it to draft, since Meta's approval is tied
        to specific text. Placeholders like {"{client_name}"} stay literal text for the sender to fill in -- no
        real provider is wired up in this build to render them.
      </p>
      {error && <p className="text-xs text-red-400 mb-2">{error}</p>}

      <div className="space-y-2">
        {templates.map((t) =>
          editingId === t.id ? (
            <div key={t.id} className="border border-gold bg-gold-muted rounded p-2 space-y-2 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <MiniField label="Name" value={editForm.name} onChange={(v) => setEditForm((f) => ({ ...f, name: v }))} />
                <div>
                  <label className="block text-xs text-text-secondary">Document type</label>
                  <select
                    value={editForm.document_type}
                    onChange={(e) => setEditForm((f) => ({ ...f, document_type: e.target.value }))}
                    className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
                  >
                    {DOC_TYPES.map((d) => (
                      <option key={d} value={d}>{d || "(any document type)"}</option>
                    ))}
                  </select>
                </div>
                <MiniField label="Subject" value={editForm.subject} onChange={(v) => setEditForm((f) => ({ ...f, subject: v }))} />
                <MiniField label="Language" value={editForm.language} onChange={(v) => setEditForm((f) => ({ ...f, language: v }))} />
                {t.channel === "whatsapp" && (
                  <div>
                    <label className="block text-xs text-text-secondary">WhatsApp status</label>
                    <select
                      value={editForm.whatsapp_template_status}
                      onChange={(e) => setEditForm((f) => ({ ...f, whatsapp_template_status: e.target.value }))}
                      className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
                    >
                      <option value="">(leave as-is)</option>
                      <option value="draft">draft</option>
                      <option value="submitted">submitted</option>
                      <option value="approved">approved</option>
                      <option value="rejected">rejected</option>
                    </select>
                  </div>
                )}
                <div className="col-span-2">
                  <label className="block text-xs text-text-secondary">Body</label>
                  <textarea
                    value={editForm.body}
                    onChange={(e) => setEditForm((f) => ({ ...f, body: e.target.value }))}
                    rows={3}
                    className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={handleSaveEdit} className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover">
                  Save
                </button>
                <button onClick={() => setEditingId(null)} className="text-xs text-text-secondary hover:underline">
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div
              key={t.id}
              className={`text-sm border rounded px-3 py-2 ${t.is_active ? "border-border-dark" : "border-border-dark bg-surface-raised opacity-60"}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span>
                  <span className="font-medium">{t.name}</span>{" "}
                  <span className="text-text-secondary text-xs">
                    ({t.channel}{t.document_type ? `, ${t.document_type}` : ""}, v{t.version}, {t.language})
                  </span>
                  {t.channel === "whatsapp" && (
                    <span
                      className={`ml-2 text-[10px] uppercase rounded px-1.5 py-0.5 ${
                        t.whatsapp_template_status === "approved"
                          ? "bg-green-500/15 text-green-400"
                          : t.whatsapp_template_status === "rejected"
                          ? "bg-red-500/15 text-red-400"
                          : "bg-amber-500/15 text-amber-400"
                      }`}
                    >
                      {t.whatsapp_template_status}
                    </span>
                  )}
                  {!t.is_active && <span className="text-text-secondary"> · inactive</span>}
                </span>
                {!readOnly && (
                  <div className="flex items-center gap-3 shrink-0">
                    <button onClick={() => startEdit(t)} className="text-gold hover:underline text-xs">
                      Edit
                    </button>
                    <button onClick={() => toggleActive(t)} className="text-text-secondary hover:underline text-xs">
                      {t.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </div>
                )}
              </div>
              {t.subject && <p className="text-xs text-text-secondary mt-1">Subject: {t.subject}</p>}
              <p className="text-xs text-text-secondary mt-0.5 whitespace-pre-wrap">{t.body}</p>
            </div>
          )
        )}
        {templates.length === 0 && !adding && (
          <p className="text-xs text-text-secondary">
            {readOnly ? "No message templates yet." : "No message templates yet -- add one below."}
          </p>
        )}
      </div>

      {readOnly ? null : adding ? (
        <form onSubmit={handleCreate} className="border border-green-500/30 bg-green-500/10 rounded p-2 space-y-2 text-sm">
          <div className="grid grid-cols-2 gap-2">
            <MiniField label="Name" value={addForm.name} onChange={(v) => setAddForm((f) => ({ ...f, name: v }))} required />
            <div>
              <label className="block text-xs text-text-secondary">Channel</label>
              <select
                value={addForm.channel}
                onChange={(e) => setAddForm((f) => ({ ...f, channel: e.target.value }))}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
              >
                <option value="email">email</option>
                <option value="whatsapp">whatsapp</option>
                <option value="telegram">telegram</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-text-secondary">Document type</label>
              <select
                value={addForm.document_type}
                onChange={(e) => setAddForm((f) => ({ ...f, document_type: e.target.value }))}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
              >
                {DOC_TYPES.map((d) => (
                  <option key={d} value={d}>{d || "(any document type)"}</option>
                ))}
              </select>
            </div>
            <MiniField label="Language" value={addForm.language} onChange={(v) => setAddForm((f) => ({ ...f, language: v }))} />
            <MiniField label="Subject" value={addForm.subject} onChange={(v) => setAddForm((f) => ({ ...f, subject: v }))} />
            <div className="col-span-2">
              <label className="block text-xs text-text-secondary">Body</label>
              <textarea
                required
                value={addForm.body}
                onChange={(e) => setAddForm((f) => ({ ...f, body: e.target.value }))}
                rows={3}
                placeholder="e.g. Hi {client_name}, your Quotation {quotation_number} for Rs {amount} is ready, valid {validity} days."
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="bg-green-600 text-white text-xs rounded px-3 py-1 hover:bg-green-700">
              Add template
            </button>
            <button
              type="button"
              onClick={() => {
                setAdding(false);
                setAddForm(emptyTemplateForm());
              }}
              className="text-xs text-text-secondary hover:underline"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button onClick={() => setAdding(true)} className="text-xs text-gold hover:underline">
          + Add template
        </button>
      )}
    </div>
  );
}
