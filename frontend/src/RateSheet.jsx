import { useEffect, useState } from "react";
import { confirmRateItem, createRateItem, listLabourCategories, listRateItems } from "./api";

const emptyForm = {
  category: "",
  item_name: "",
  spec: "",
  unit: "",
  hsn_sac: "",
  rate: "",
  vendor: "",
  city_of_quote: "",
  labour_category_id: "",
};

export default function RateSheet({ token, onBack }) {
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function load() {
    return Promise.all([listRateItems(token), listLabourCategories(token)]).then(
      ([itemsRes, categoriesRes]) => {
        setItems(itemsRes);
        setCategories(categoriesRes);
      }
    );
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
        rate: Number(form.rate),
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

  if (loading) {
    return <p className="text-center text-gray-500 mt-10">Loading rate sheet…</p>;
  }

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Rate Sheet</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-blue-600 hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-gray-400 mt-1">
          Every entry starts as a Manual, unverified rate. A PM or Director confirming it
          promotes it to an AI (master) rate (J.1).
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white shadow rounded-lg p-6 space-y-3">
        <h3 className="text-sm font-semibold text-gray-700">Add a rate item</h3>
        <div className="grid grid-cols-2 gap-3">
          <Text label="Category" value={form.category} onChange={(v) => set("category", v)} required />
          <Text label="Item name" value={form.item_name} onChange={(v) => set("item_name", v)} required />
          <Text label="Spec" value={form.spec} onChange={(v) => set("spec", v)} />
          <Text label="Unit" value={form.unit} onChange={(v) => set("unit", v)} required />
          <Text label="HSN/SAC" value={form.hsn_sac} onChange={(v) => set("hsn_sac", v)} required />
          <Text label="Rate (Rs)" type="number" value={form.rate} onChange={(v) => set("rate", v)} required />
          <Text label="Vendor" value={form.vendor} onChange={(v) => set("vendor", v)} />
          <Text label="City of quote" value={form.city_of_quote} onChange={(v) => set("city_of_quote", v)} />
          <div className="col-span-2">
            <label className="block text-sm font-medium text-gray-700">Labour category</label>
            <select
              value={form.labour_category_id}
              onChange={(e) => set("labour_category_id", e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
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
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? "Saving…" : "Save as rate"}
        </button>
      </form>

      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Items ({items.length})</h3>
        <div className="space-y-2">
          {items.map((item) => (
            <div key={item.id} className="border border-gray-200 rounded px-3 py-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium">{item.item_name}</span>
                <span className="text-gray-500">
                  Rs {item.rate} / {item.unit}
                </span>
              </div>
              <p className="text-xs text-gray-500">
                {item.category} {item.spec && `· ${item.spec}`} · HSN/SAC {item.hsn_sac}
              </p>
              <div className="mt-1 flex items-center gap-2">
                {item.source === "ai" ? (
                  <span className="text-xs bg-green-50 text-green-700 rounded px-1.5 py-0.5">
                    AI · confirmed {item.confirmed_date}
                    {item.is_stale && " · stale (90+ days)"}
                  </span>
                ) : (
                  <span className="text-xs bg-gray-100 text-gray-600 rounded px-1.5 py-0.5">
                    Manual · Unverified
                  </span>
                )}
                {item.source === "manual" && (
                  <button
                    onClick={() => handleConfirm(item.id)}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    Confirm &rarr; AI rate
                  </button>
                )}
              </div>
            </div>
          ))}
          {items.length === 0 && <p className="text-sm text-gray-400">No rate items yet.</p>}
        </div>
      </div>
    </div>
  );
}

function Text({ label, value, onChange, type = "text", required }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      <input
        type={type}
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
      />
    </div>
  );
}
