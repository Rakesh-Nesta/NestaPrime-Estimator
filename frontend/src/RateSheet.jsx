import { useEffect, useState } from "react";
import {
  bulkMarkRateItems,
  bulkUpdateRateItems,
  confirmRateItem,
  createRateItem,
  exportRateItemsBlob,
  getRateHistory,
  importRateItemsExcel,
  listLabourCategories,
  listRateItems,
  listVendors,
  syncDraftLinesToMasterRate,
  updateRateItem,
  updateRateValue,
} from "./api";
import SelectWithOther from "./SelectWithOther";

function downloadBlobAsFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

const emptyForm = {
  category: "",
  item_name: "",
  spec: "",
  unit: "",
  hsn_sac: "",
  rate: "",
  gst_percent: "",
  vendor: "",
  city_of_quote: "",
  labour_category_id: "",
};

export default function RateSheet({ token, onBack }) {
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [vendorNames, setVendorNames] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [importingExcel, setImportingExcel] = useState(false);
  const [importResult, setImportResult] = useState(null);

  function load() {
    return Promise.all([
      listRateItems(token),
      listLabourCategories(token),
      // Amendment 7: Rate Sheet's vendor field is now a real picker sourced
      // from the Vendor master. site_engineer can see Rate Sheet but not
      // Vendors (PROCUREMENT_ROLES) -- a 403 here just falls back to the
      // Others-only free-text mode SelectWithOther already supports.
      listVendors(token).catch(() => []),
    ]).then(([itemsRes, categoriesRes, vendorsRes]) => {
      setItems(itemsRes);
      setCategories(categoriesRes);
      setVendorNames(vendorsRes.map((v) => v.name));
    });
  }

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [token]);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await createRateItem(token, {
        category: form.category,
        item_name: form.item_name,
        spec: form.spec || null,
        unit: form.unit,
        hsn_sac: form.hsn_sac,
        // Amendment 11 Part A: a blank rate creates an "awaiting rate" item
        // -- a real catalog entry with no defensible Rs/unit figure yet,
        // never a fabricated number.
        rate: form.rate === "" ? null : Number(form.rate),
        gst_percent: form.gst_percent === "" ? null : Number(form.gst_percent),
        vendor: form.vendor || null,
        city_of_quote: form.city_of_quote || null,
        labour_category_id: form.labour_category_id || null,
      });
      setForm(emptyForm);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirm(itemId) {
    setError("");
    try {
      await confirmRateItem(token, itemId);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleToggleWatch(item) {
    setError("");
    try {
      await updateRateItem(token, item.id, { is_commodity_watched: !item.is_commodity_watched });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleExportExcel() {
    setError("");
    try {
      const blob = await exportRateItemsBlob(token);
      downloadBlobAsFile(blob, "rate-sheet.xlsx");
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
      const result = await importRateItemsExcel(token, file);
      setImportResult(result);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setImportingExcel(false);
      e.target.value = "";
    }
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading rate sheet…</p>;
  }

  // Amendment 5's dropdown "Others" rule, scoped to a genuine reference
  // list (not a business-logic enum): category names already in use on
  // the Rate Sheet, so a new item picks an existing one -- keeping the
  // sheet tidy instead of "Civil" vs "civil work" vs "Civil Works" drift
  // -- with Others still open for a genuinely new category.
  const existingCategories = [...new Set(items.map((i) => i.category))].sort();

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Rate Sheet</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-text-secondary mt-1">
          Every entry starts as a Manual, unverified rate. A PM or Director confirming it
          promotes it to an AI (master) rate (J.1).
        </p>
      </div>

      <div className="bg-surface shadow rounded-lg p-6">
        <h3 className="text-sm font-semibold text-text-secondary mb-1">Excel export / import</h3>
        <p className="text-xs text-text-secondary mb-3">
          P.2 Phase 1b: "Excel rate import" -- so NestaPrime can maintain its rate card in Excel and
          upload it. Re-importing an unchanged file is a safe no-op; a changed rate on an existing item
          goes through the same rate-history mechanics as editing it here. New items always start
          Manual/unverified, same as adding one below -- an Excel file can never promote a rate to AI.
        </p>
        <div className="flex items-center gap-3">
          <button
            onClick={handleExportExcel}
            className="text-xs bg-surface-raised text-text-secondary rounded px-3 py-1.5 hover:bg-surface-raised"
          >
            Export to Excel
          </button>
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
        </div>
        {importResult && (
          <div className="mt-3 text-xs bg-surface-raised border border-border-dark rounded p-3">
            <p className="text-text-secondary">
              <span className="font-medium">{importResult.created.length}</span> new item(s) created,{" "}
              <span className="font-medium">{importResult.updated.length}</span> item(s) updated,{" "}
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

      <form onSubmit={handleSubmit} className="bg-surface shadow rounded-lg p-6 space-y-3">
        <h3 className="text-sm font-semibold text-text-secondary">Add a rate item</h3>
        <div className="grid grid-cols-2 gap-3">
          <SelectWithOther
            label="Category"
            value={form.category}
            onChange={(v) => set("category", v)}
            options={existingCategories}
            required
          />
          <Text label="Item name" value={form.item_name} onChange={(v) => set("item_name", v)} required />
          <Text label="Spec" value={form.spec} onChange={(v) => set("spec", v)} />
          <Text label="Unit" value={form.unit} onChange={(v) => set("unit", v)} required />
          <Text label="HSN/SAC" value={form.hsn_sac} onChange={(v) => set("hsn_sac", v)} required />
          <Text
            label="Rate (Rs, blank = awaiting rate)"
            type="number"
            value={form.rate}
            onChange={(v) => set("rate", v)}
          />
          <Text
            label="GST % (blank = global default)"
            type="number"
            value={form.gst_percent}
            onChange={(v) => set("gst_percent", v)}
          />
          <SelectWithOther label="Vendor" value={form.vendor} onChange={(v) => set("vendor", v)} options={vendorNames} />
          <Text label="City of quote" value={form.city_of_quote} onChange={(v) => set("city_of_quote", v)} />
          <div className="col-span-2">
            <label className="block text-sm font-medium text-text-secondary">Labour category</label>
            <select
              value={form.labour_category_id}
              onChange={(e) => set("labour_category_id", e.target.value)}
              className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
            >
              <option value="">None (uses blended fallback %)</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.default_percent}%)
                </option>
              ))}
            </select>
          </div>
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="bg-gold text-base text-sm rounded px-4 py-2 hover:bg-gold-hover disabled:opacity-50"
        >
          {submitting ? "Saving…" : "Save as rate"}
        </button>
      </form>

      <BulkActionsPanel token={token} categories={existingCategories} onChanged={load} />

      <div className="bg-surface shadow rounded-lg p-6">
        <h3 className="text-sm font-semibold text-text-secondary mb-3">Items ({items.length})</h3>
        <div className="space-y-2">
          {items.map((item) => (
            <RateItemRow
              key={item.id}
              token={token}
              item={item}
              onConfirm={() => handleConfirm(item.id)}
              onToggleWatch={() => handleToggleWatch(item)}
              onChanged={load}
            />
          ))}
          {items.length === 0 && <p className="text-sm text-text-secondary">No rate items yet.</p>}
        </div>
      </div>
    </div>
  );
}

function BulkActionsPanel({ token, categories, onChanged }) {
  const [markCategory, setMarkCategory] = useState("");
  const [markBusy, setMarkBusy] = useState(false);
  const [markError, setMarkError] = useState("");
  const [markResult, setMarkResult] = useState("");

  const [pctCategory, setPctCategory] = useState("");
  const [pctChange, setPctChange] = useState("");
  const [pctReason, setPctReason] = useState("");
  const [pctBusy, setPctBusy] = useState(false);
  const [pctError, setPctError] = useState("");
  const [pctResult, setPctResult] = useState(null);

  async function handleMark(source) {
    setMarkError("");
    setMarkResult("");
    setMarkBusy(true);
    try {
      const res = await bulkMarkRateItems(token, { source, category: markCategory || null });
      setMarkResult(
        `${res.updated_count} item(s) marked ${source === "ai" ? "AI (confirmed)" : "Manual"}${
          markCategory ? ` in "${markCategory}"` : ""
        }.`
      );
      await onChanged();
    } catch (err) {
      setMarkError(err.message);
    } finally {
      setMarkBusy(false);
    }
  }

  async function handlePercentUpdate(e) {
    e.preventDefault();
    setPctError("");
    setPctResult(null);
    setPctBusy(true);
    try {
      const res = await bulkUpdateRateItems(token, {
        category: pctCategory,
        percent_change: Number(pctChange),
        reason: pctReason,
      });
      setPctResult(res);
      setPctChange("");
      setPctReason("");
      await onChanged();
    } catch (err) {
      setPctError(err.message);
    } finally {
      setPctBusy(false);
    }
  }

  return (
    <div className="bg-surface shadow rounded-lg p-6 space-y-4">
      <h3 className="text-sm font-semibold text-text-secondary">Bulk actions (J.1)</h3>

      <div>
        <p className="text-xs text-text-secondary mb-1">
          Mark all items (or just one category) AI/Manual in one action -- the multi-item version of the per-row
          Confirm button and its reverse.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={markCategory}
            onChange={(e) => setMarkCategory(e.target.value)}
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs"
          >
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <button
            onClick={() => handleMark("ai")}
            disabled={markBusy}
            className="text-xs bg-green-600 text-white rounded px-3 py-1 hover:bg-green-700 disabled:opacity-50"
          >
            Mark all AI
          </button>
          <button
            onClick={() => handleMark("manual")}
            disabled={markBusy}
            className="text-xs bg-surface-raised text-text-primary rounded px-3 py-1 hover:bg-border-dark disabled:opacity-50"
          >
            Mark all Manual
          </button>
        </div>
        {markError && <p className="text-xs text-red-400 mt-1">{markError}</p>}
        {markResult && <p className="text-xs text-green-400 mt-1">{markResult}</p>}
      </div>

      <div className="border-t border-border-dark pt-3">
        <p className="text-xs text-text-secondary mb-1">
          Apply a % change to a whole category (e.g. "Steel +6%") with one effective date -- Q.2 rule 5's Master
          Settings bulk-update, for the rate sheet itself.
        </p>
        <form onSubmit={handlePercentUpdate} className="flex flex-wrap items-center gap-2">
          <select
            value={pctCategory}
            onChange={(e) => setPctCategory(e.target.value)}
            required
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs"
          >
            <option value="" disabled>
              Select category…
            </option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <input
            type="number"
            step="0.1"
            required
            value={pctChange}
            onChange={(e) => setPctChange(e.target.value)}
            placeholder="% change, e.g. 6"
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs w-32"
          />
          <input
            required
            value={pctReason}
            onChange={(e) => setPctReason(e.target.value)}
            placeholder="Reason"
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs flex-1 min-w-[10rem]"
          />
          <button
            type="submit"
            disabled={pctBusy}
            className="text-xs bg-gold text-base rounded px-3 py-1 hover:bg-gold-hover disabled:opacity-50"
          >
            {pctBusy ? "Applying…" : "Apply to category"}
          </button>
        </form>
        {pctError && <p className="text-xs text-red-400 mt-1">{pctError}</p>}
        {pctResult && (
          <p className="text-xs text-green-400 mt-1">
            {pctResult.updated_count} item(s) updated.
            {pctResult.items.some((i) => i.commodity_alert?.triggered) &&
              " Commodity alert triggered on one or more watched items -- open each item's history to review."}
          </p>
        )}
      </div>
    </div>
  );
}

function RateItemRow({ token, item, onConfirm, onToggleWatch, onChanged }) {
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState(null);
  const [showUpdateForm, setShowUpdateForm] = useState(false);
  const [newRate, setNewRate] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [alert, setAlert] = useState(null);
  const [syncing, setSyncing] = useState(false);

  async function toggleHistory() {
    setError("");
    if (!showHistory && history === null) {
      try {
        setHistory(await getRateHistory(token, item.id));
      } catch (err) {
        setError(err.message);
        return;
      }
    }
    setShowHistory((v) => !v);
  }

  async function handleUpdateRate(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const res = await updateRateValue(token, item.id, { rate: Number(newRate), reason });
      setAlert(res.commodity_alert);
      setNewRate("");
      setReason("");
      setShowUpdateForm(false);
      setHistory(null);
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleSync() {
    setError("");
    setSyncing(true);
    try {
      const res = await syncDraftLinesToMasterRate(token, item.id);
      setAlert(null);
      window.alert(`Synced ${res.updated_line_count} line(s) across ${res.updated_cost_sheet_ids.length} draft cost sheet(s).`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="border border-border-dark rounded px-3 py-2 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-medium">
          {item.item_name}
          {item.is_commodity_watched && <span className="ml-1 text-amber-400" title="Commodity watched">★</span>}
        </span>
        <span className="text-text-secondary">
          {item.rate != null ? (
            <>
              Rs {item.rate} / {item.unit}
            </>
          ) : (
            <span className="text-amber-400">Awaiting rate</span>
          )}
        </span>
      </div>
      <p className="text-xs text-text-secondary">
        {item.category} {item.spec && `· ${item.spec}`} · HSN/SAC {item.hsn_sac} · GST{" "}
        {item.gst_percent != null ? `${item.gst_percent}% (override)` : "default"}
      </p>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        {item.source === "ai" ? (
          <span className="text-xs bg-green-500/10 text-green-400 rounded px-1.5 py-0.5">
            AI · confirmed {item.confirmed_date}
            {item.is_stale && " · stale (90+ days)"}
          </span>
        ) : (
          <span className="text-xs bg-surface-raised text-text-secondary rounded px-1.5 py-0.5">Manual · Unverified</span>
        )}
        {item.source === "manual" && item.rate != null && (
          <button onClick={onConfirm} className="text-xs text-gold hover:underline">
            Confirm &rarr; AI rate
          </button>
        )}
        {item.source === "manual" && item.rate == null && (
          <span className="text-xs text-text-secondary italic">Enter a rate below to confirm</span>
        )}
        <button onClick={onToggleWatch} className="text-xs text-amber-400 hover:underline">
          {item.is_commodity_watched ? "Unwatch (commodity alert)" : "Watch (commodity alert)"}
        </button>
        <button onClick={() => setShowUpdateForm((v) => !v)} className="text-xs text-gold hover:underline">
          {showUpdateForm ? "Cancel" : "Update rate"}
        </button>
        <button onClick={toggleHistory} className="text-xs text-text-secondary hover:underline">
          {showHistory ? "Hide history" : "History"}
        </button>
      </div>

      {error && <p className="text-xs text-red-400 mt-1">{error}</p>}

      {showUpdateForm && (
        <form onSubmit={handleUpdateRate} className="mt-2 flex flex-wrap items-center gap-2 bg-surface-raised rounded p-2">
          <input
            type="number"
            step="0.01"
            required
            value={newRate}
            onChange={(e) => setNewRate(e.target.value)}
            placeholder="New rate"
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs w-28"
          />
          <input
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason for change"
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs flex-1 min-w-[10rem]"
          />
          <button
            type="submit"
            disabled={saving}
            className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save new rate"}
          </button>
        </form>
      )}

      {alert && alert.triggered && (
        <div className="mt-2 bg-amber-500/10 border border-amber-500/30 rounded p-2 text-xs space-y-1">
          <p className="font-semibold text-amber-400">
            Commodity alert: {alert.percent_move > 0 ? "+" : ""}
            {alert.percent_move}% (Rs {alert.previous_rate} &rarr; Rs {alert.new_rate}, threshold &plusmn;
            {alert.threshold_percent}%)
          </p>
          {alert.draft_cost_sheets.length > 0 && (
            <p>
              {alert.draft_cost_sheets.length} draft cost sheet(s) use this rate and can be synced:{" "}
              <button onClick={handleSync} disabled={syncing} className="text-gold-hover hover:underline disabled:opacity-50">
                {syncing ? "Syncing…" : "Sync draft lines now"}
              </button>
            </p>
          )}
          {alert.verified_cost_sheets.length > 0 && (
            <p className="text-text-secondary">
              {alert.verified_cost_sheets.length} verified cost sheet(s) also use this rate -- their figures are
              frozen (M.2 rule 5) and won't be touched.
            </p>
          )}
        </div>
      )}

      {showHistory && history && (
        <div className="mt-2 border-t border-border-dark pt-2 space-y-1">
          {history.map((h) => (
            <p key={h.id} className="text-xs text-text-secondary">
              Rs {h.rate} · {h.effective_from} &rarr; {h.effective_to || "current"}
              {h.reason && ` · ${h.reason}`}
            </p>
          ))}
          {history.length === 0 && <p className="text-xs text-text-secondary">No history.</p>}
        </div>
      )}
    </div>
  );
}

function Text({ label, value, onChange, type = "text", required }) {
  return (
    <div>
      <label className="block text-sm font-medium text-text-secondary">{label}</label>
      <input
        type={type}
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
      />
    </div>
  );
}
