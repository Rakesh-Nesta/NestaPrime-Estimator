import { useEffect, useState } from "react";
import {
  createCrossSellAddon,
  listCrossSellAddons,
  listSports,
  setCrossSellAddonSports,
  updateCrossSellAddon,
} from "./api";

const CATEGORIES = ["lighting", "fencing", "seating", "amc", "other"];

const emptyForm = {
  name: "",
  category: "fencing",
  description: "",
  cost: "",
  unit: "",
  margin_percent: "",
  all_sports: false,
};

export default function CrossSellAdmin({ token, onBack }) {
  const [addons, setAddons] = useState([]);
  const [sports, setSports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [expandedId, setExpandedId] = useState(null);

  function load() {
    return Promise.all([listCrossSellAddons(token), listSports(token)]).then(([a, s]) => {
      setAddons(a);
      setSports(s);
    });
  }

  useEffect(() => {
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await createCrossSellAddon(token, {
        name: form.name,
        category: form.category,
        description: form.description || null,
        cost: form.cost === "" ? null : Number(form.cost),
        unit: form.unit || null,
        margin_percent: form.margin_percent === "" ? null : Number(form.margin_percent),
        all_sports: form.all_sports,
      });
      setForm(emptyForm);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading cross-sell add-ons…</p>;
  }

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Cross-Sell Add-ons</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-text-secondary mt-1">
          Amendment 3: "Complete Your Facility" -- add-ons suggested at the Estimate step,
          matched to a project's selected sports (or all sports, e.g. AMC). An add-on can't go
          active until it has both a cost and a margin -- until then it's a real, sport-tagged
          catalog row that just never shows up as a suggestion.
        </p>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
      </div>

      <form onSubmit={handleSubmit} className="bg-surface shadow rounded-lg p-6 space-y-3">
        <h3 className="text-sm font-semibold text-text-secondary">Add a catalog entry</h3>
        <div className="grid grid-cols-2 gap-3">
          <Text label="Name" value={form.name} onChange={(v) => set("name", v)} required />
          <Select
            label="Category"
            value={form.category}
            onChange={(v) => set("category", v)}
            options={CATEGORIES}
          />
          <Text label="Description" value={form.description} onChange={(v) => set("description", v)} />
          <Text label="Unit (e.g. sqft, rft)" value={form.unit} onChange={(v) => set("unit", v)} />
          <Text label="Cost (Rs)" type="number" value={form.cost} onChange={(v) => set("cost", v)} />
          <Text
            label="Margin %"
            type="number"
            value={form.margin_percent}
            onChange={(v) => set("margin_percent", v)}
          />
          <label className="flex items-center gap-2 text-sm text-text-secondary mt-6">
            <input
              type="checkbox"
              checked={form.all_sports}
              onChange={(e) => set("all_sports", e.target.checked)}
            />
            Suggest for all sports (skip sport tagging)
          </label>
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="bg-gold text-base text-sm rounded px-4 py-2 hover:bg-gold-hover disabled:opacity-50"
        >
          {submitting ? "Saving…" : "Save add-on"}
        </button>
      </form>

      <div className="bg-surface shadow rounded-lg p-6">
        <h3 className="text-sm font-semibold text-text-secondary mb-3">Catalog ({addons.length})</h3>
        <div className="space-y-2">
          {addons.map((a) => (
            <AddonRow
              key={a.id}
              token={token}
              addon={a}
              sports={sports}
              expanded={expandedId === a.id}
              onToggleExpand={() => setExpandedId(expandedId === a.id ? null : a.id)}
              onChanged={load}
            />
          ))}
          {addons.length === 0 && <p className="text-sm text-text-secondary">No cross-sell add-ons yet.</p>}
        </div>
      </div>
    </div>
  );
}

function AddonRow({ token, addon, sports, expanded, onToggleExpand, onChanged }) {
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [costDraft, setCostDraft] = useState(addon.cost ?? "");
  const [marginDraft, setMarginDraft] = useState(addon.margin_percent ?? "");
  const [selectedSportIds, setSelectedSportIds] = useState(addon.sport_ids || []);

  const canActivate = addon.cost != null && addon.margin_percent != null;

  async function handleSavePricing() {
    setError("");
    setSaving(true);
    try {
      await updateCrossSellAddon(token, addon.id, {
        cost: costDraft === "" ? null : Number(costDraft),
        margin_percent: marginDraft === "" ? null : Number(marginDraft),
      });
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive() {
    setError("");
    setSaving(true);
    try {
      await updateCrossSellAddon(token, addon.id, { is_active: !addon.is_active });
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function toggleSport(sportId) {
    setSelectedSportIds((ids) =>
      ids.includes(sportId) ? ids.filter((id) => id !== sportId) : [...ids, sportId]
    );
  }

  async function handleSaveSports() {
    setError("");
    setSaving(true);
    try {
      await setCrossSellAddonSports(token, addon.id, selectedSportIds);
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="border border-border-dark rounded px-3 py-2 text-sm">
      <div className="flex items-center justify-between">
        <div>
          <span className="font-medium">{addon.name}</span>{" "}
          <span className="text-xs text-text-secondary">· {addon.category}</span>
          {addon.selling_price != null && (
            <span className="text-xs text-text-secondary ml-1">
              · Rs {Math.round(addon.selling_price)}
              {addon.unit ? ` / ${addon.unit}` : ""}
            </span>
          )}
          <span
            className={`text-xs ml-2 px-1.5 py-0.5 rounded ${
              addon.is_active ? "bg-emerald-900/40 text-emerald-400" : "bg-surface-raised text-text-secondary"
            }`}
          >
            {addon.is_active ? "Active" : "Inactive"}
          </span>
          {addon.all_sports && <span className="text-xs text-text-secondary ml-1">· all sports</span>}
        </div>
        <button onClick={onToggleExpand} className="text-xs text-gold hover:underline">
          {expanded ? "Hide" : "Edit"}
        </button>
      </div>

      {expanded && (
        <div className="mt-3 border-t border-border-dark pt-3 space-y-3">
          {error && <p className="text-xs text-red-400">{error}</p>}

          <div className="grid grid-cols-3 gap-2 items-end">
            <Text label="Cost (Rs)" type="number" value={costDraft} onChange={setCostDraft} small />
            <Text label="Margin %" type="number" value={marginDraft} onChange={setMarginDraft} small />
            <button
              onClick={handleSavePricing}
              disabled={saving}
              className="text-xs bg-gold text-base rounded px-3 py-1.5 hover:bg-gold-hover disabled:opacity-50"
            >
              Save pricing
            </button>
          </div>

          <button
            onClick={handleToggleActive}
            disabled={saving || (!addon.is_active && !canActivate)}
            title={!addon.is_active && !canActivate ? "Needs both cost and margin before it can go active" : undefined}
            className="text-xs bg-surface-raised text-text-primary border border-border-dark rounded px-3 py-1.5 hover:bg-border-dark disabled:opacity-50"
          >
            {addon.is_active ? "Deactivate" : "Activate"}
          </button>

          {!addon.all_sports && (
            <div>
              <p className="text-xs font-medium text-text-secondary mb-1">Suggested for sports</p>
              <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto">
                {sports.map((sport) => (
                  <label key={sport.id} className="flex items-center gap-1 text-xs bg-surface-raised rounded px-2 py-1">
                    <input
                      type="checkbox"
                      checked={selectedSportIds.includes(sport.id)}
                      onChange={() => toggleSport(sport.id)}
                    />
                    {sport.name}
                  </label>
                ))}
              </div>
              <button
                onClick={handleSaveSports}
                disabled={saving}
                className="mt-2 text-xs bg-gold text-base rounded px-3 py-1.5 hover:bg-gold-hover disabled:opacity-50"
              >
                Save sport tags
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Text({ label, value, onChange, type = "text", required = false, small = false }) {
  return (
    <div>
      <label className={`block font-medium text-text-secondary ${small ? "text-xs" : "text-sm"}`}>{label}</label>
      <input
        type={type}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className={`mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 ${
          small ? "py-1 text-xs" : "py-2 text-sm"
        }`}
      />
    </div>
  );
}

function Select({ label, value, onChange, options }) {
  return (
    <div>
      <label className="block text-sm font-medium text-text-secondary">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </div>
  );
}
