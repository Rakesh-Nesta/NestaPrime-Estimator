import { useEffect, useState } from "react";
import { createProduct, createVendor, deleteProduct, listProducts, listVendors, updateVendor } from "./api";

const emptyVendorForm = {
  name: "",
  vendor_code: "",
  city: "",
  category: "",
  contact_name: "",
  phone: "",
  email: "",
  gstin: "",
  payment_terms: "",
};

const emptyProductForm = { name: "", spec: "", unit: "", approx_price: "", category: "", notes: "" };

export default function VendorsAdmin({ token, onBack }) {
  const [vendors, setVendors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState(emptyVendorForm);
  const [submitting, setSubmitting] = useState(false);
  const [expandedId, setExpandedId] = useState(null);

  function load() {
    return listVendors(token).then(setVendors);
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
      await createVendor(token, {
        name: form.name,
        vendor_code: form.vendor_code || null,
        city: form.city || null,
        category: form.category || null,
        contact_name: form.contact_name || null,
        phone: form.phone || null,
        email: form.email || null,
        gstin: form.gstin || null,
        payment_terms: form.payment_terms || null,
      });
      setForm(emptyVendorForm);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading vendors…</p>;
  }

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Vendors</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-text-secondary mt-1">
          Amendment 7: vendor master with vendor codes, plus each vendor's own product catalog
          (approximate pricing, not a locked quote — see Rate Sheet / RFQ for that).
        </p>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
      </div>

      <form onSubmit={handleSubmit} className="bg-surface shadow rounded-lg p-6 space-y-3">
        <h3 className="text-sm font-semibold text-text-secondary">Add a vendor</h3>
        <div className="grid grid-cols-2 gap-3">
          <Text label="Name" value={form.name} onChange={(v) => set("name", v)} required />
          <Text label="Vendor code" value={form.vendor_code} onChange={(v) => set("vendor_code", v)} />
          <Text label="City" value={form.city} onChange={(v) => set("city", v)} />
          <Text label="Category" value={form.category} onChange={(v) => set("category", v)} />
          <Text label="Contact name" value={form.contact_name} onChange={(v) => set("contact_name", v)} />
          <Text label="Phone" value={form.phone} onChange={(v) => set("phone", v)} />
          <Text label="Email" value={form.email} onChange={(v) => set("email", v)} />
          <Text label="GSTIN" value={form.gstin} onChange={(v) => set("gstin", v)} />
          <Text label="Payment terms" value={form.payment_terms} onChange={(v) => set("payment_terms", v)} />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="bg-gold text-base text-sm rounded px-4 py-2 hover:bg-gold-hover disabled:opacity-50"
        >
          {submitting ? "Saving…" : "Save vendor"}
        </button>
      </form>

      <div className="bg-surface shadow rounded-lg p-6">
        <h3 className="text-sm font-semibold text-text-secondary mb-3">Vendors ({vendors.length})</h3>
        <div className="space-y-2">
          {vendors.map((v) => (
            <VendorRow
              key={v.id}
              token={token}
              vendor={v}
              expanded={expandedId === v.id}
              onToggleExpand={() => setExpandedId(expandedId === v.id ? null : v.id)}
              onChanged={load}
            />
          ))}
          {vendors.length === 0 && <p className="text-sm text-text-secondary">No vendors yet.</p>}
        </div>
      </div>
    </div>
  );
}

function VendorRow({ token, vendor, expanded, onToggleExpand, onChanged }) {
  const [products, setProducts] = useState([]);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState(emptyProductForm);
  const [submitting, setSubmitting] = useState(false);
  const [editingCode, setEditingCode] = useState(false);
  const [codeDraft, setCodeDraft] = useState(vendor.vendor_code || "");

  function loadProducts() {
    setLoadingProducts(true);
    return listProducts(token, vendor.id)
      .then(setProducts)
      .catch((err) => setError(err.message))
      .finally(() => setLoadingProducts(false));
  }

  useEffect(() => {
    if (expanded) loadProducts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded]);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleAddProduct(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await createProduct(token, vendor.id, {
        name: form.name,
        spec: form.spec || null,
        unit: form.unit || null,
        approx_price: form.approx_price === "" ? null : Number(form.approx_price),
        category: form.category || null,
        notes: form.notes || null,
      });
      setForm(emptyProductForm);
      await loadProducts();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeleteProduct(productId) {
    setError("");
    try {
      await deleteProduct(token, productId);
      await loadProducts();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSaveCode() {
    setError("");
    try {
      await updateVendor(token, vendor.id, { vendor_code: codeDraft || null });
      setEditingCode(false);
      await onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="border border-border-dark rounded px-3 py-2 text-sm">
      <div className="flex items-center justify-between">
        <div>
          <span className="font-medium">{vendor.name}</span>{" "}
          {editingCode ? (
            <span className="inline-flex items-center gap-1 ml-1">
              <input
                value={codeDraft}
                onChange={(e) => setCodeDraft(e.target.value)}
                className="w-24 rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-0.5 text-xs"
              />
              <button onClick={handleSaveCode} className="text-xs text-gold hover:underline">
                Save
              </button>
            </span>
          ) : (
            <button
              onClick={() => setEditingCode(true)}
              className="text-xs text-text-secondary hover:text-gold ml-1"
            >
              {vendor.vendor_code ? `(${vendor.vendor_code})` : "(set code)"}
            </button>
          )}
          {vendor.city && <span className="text-xs text-text-secondary ml-2">· {vendor.city}</span>}
          {vendor.category && <span className="text-xs text-text-secondary ml-1">· {vendor.category}</span>}
        </div>
        <button onClick={onToggleExpand} className="text-xs text-gold hover:underline">
          {expanded ? "Hide products" : "Products"}
        </button>
      </div>

      {expanded && (
        <div className="mt-3 border-t border-border-dark pt-3 space-y-3">
          {error && <p className="text-xs text-red-400">{error}</p>}
          {loadingProducts ? (
            <p className="text-xs text-text-secondary">Loading products…</p>
          ) : (
            <div className="space-y-1">
              {products.map((p) => (
                <div key={p.id} className="flex items-center justify-between bg-surface-raised rounded px-2 py-1.5">
                  <span className="text-xs">
                    <span className="font-medium">{p.name}</span>
                    {p.spec && <span className="text-text-secondary"> · {p.spec}</span>}
                    {p.approx_price != null && (
                      <span className="text-text-secondary"> · ~Rs {p.approx_price}{p.unit ? ` / ${p.unit}` : ""}</span>
                    )}
                  </span>
                  <button
                    onClick={() => handleDeleteProduct(p.id)}
                    className="text-xs text-red-400 hover:underline"
                  >
                    Remove
                  </button>
                </div>
              ))}
              {products.length === 0 && (
                <p className="text-xs text-text-secondary">No products under this vendor yet.</p>
              )}
            </div>
          )}

          <form onSubmit={handleAddProduct} className="grid grid-cols-3 gap-2">
            <Text label="Product name" value={form.name} onChange={(v) => set("name", v)} required small />
            <Text label="Spec" value={form.spec} onChange={(v) => set("spec", v)} small />
            <Text label="Unit" value={form.unit} onChange={(v) => set("unit", v)} small />
            <Text
              label="Approx price (Rs)"
              type="number"
              value={form.approx_price}
              onChange={(v) => set("approx_price", v)}
              small
            />
            <Text label="Category" value={form.category} onChange={(v) => set("category", v)} small />
            <div className="flex items-end">
              <button
                type="submit"
                disabled={submitting}
                className="text-xs bg-gold text-base rounded px-3 py-1.5 hover:bg-gold-hover disabled:opacity-50"
              >
                Add product
              </button>
            </div>
          </form>
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
