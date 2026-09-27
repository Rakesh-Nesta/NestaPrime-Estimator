import { useEffect, useState } from "react";
import { createProduct, createVendor, deleteProduct, listProducts, listVendors, updateVendor } from "./api";
import { DocumentIcon, SearchIcon, UsersIcon } from "./Icons";

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
  const [search, setSearch] = useState("");

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

  const needle = search.trim().toLowerCase();
  const visibleVendors = needle
    ? vendors.filter((v) => v.name.toLowerCase().includes(needle) || (v.vendor_code || "").toLowerCase().includes(needle))
    : vendors;

  return (
    <div className="max-w-[1400px] mx-auto mt-6 mb-10 px-4 sm:px-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-text-secondary">Workspace / Tools &amp; Reports</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1 flex items-center gap-2">
            <UsersIcon className="w-6 h-6 text-gold" /> Vendor Master
          </h2>
          <p className="text-sm text-text-secondary mt-1">Manage vendor details, codes and product catalogues.</p>
        </div>
        {onBack && (
          <button onClick={onBack} className="text-xs uppercase tracking-wider text-gold hover:text-gold-hover shrink-0">
            ← Back
          </button>
        )}
      </div>

      <div className="flex items-start gap-2 bg-gold/5 border border-gold/20 rounded-lg px-4 py-3 text-sm text-text-secondary">
        <span className="text-gold shrink-0">ℹ</span>
        <span>Catalogue prices are approximate. Use Rate Sheet or Price Requests for confirmed pricing.</span>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="grid lg:grid-cols-[1fr_22rem] gap-5">
        <div className="bg-surface border border-border-dark rounded-lg p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-text-primary">Vendors ({visibleVendors.length})</h3>
          </div>
          <div className="relative mb-4">
            <SearchIcon className="w-3.5 h-3.5 text-text-secondary absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by vendor name or code"
              className="w-full rounded border border-border-dark bg-surface-raised text-text-primary pl-8 pr-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-2">
            {visibleVendors.map((v) => (
              <VendorRow
                key={v.id}
                token={token}
                vendor={v}
                expanded={expandedId === v.id}
                onToggleExpand={() => setExpandedId(expandedId === v.id ? null : v.id)}
                onChanged={load}
              />
            ))}
            {visibleVendors.length === 0 && (
              <p className="text-sm text-text-secondary">{vendors.length === 0 ? "No vendors yet." : "Nothing matches that search."}</p>
            )}
          </div>

          <div className="mt-5 border-t border-border-dark pt-4 flex items-start gap-3">
            <span className="w-9 h-9 rounded-lg bg-gold/10 text-gold flex items-center justify-center shrink-0">
              <DocumentIcon className="w-4 h-4" />
            </span>
            <div>
              <p className="text-sm font-medium text-text-primary">Product catalogues</p>
              <p className="text-xs text-text-secondary mt-0.5">
                Open a vendor to browse their own products and indicative prices.
              </p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="bg-surface border border-border-dark rounded-lg p-5 space-y-4 h-fit lg:sticky lg:top-4">
          <h3 className="text-sm font-semibold text-text-primary">Add a vendor</h3>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-secondary">Business details</p>
            <div className="grid grid-cols-2 gap-3">
              <Text label="Name" value={form.name} onChange={(v) => set("name", v)} required />
              <Text label="Vendor code" value={form.vendor_code} onChange={(v) => set("vendor_code", v)} />
              <Text label="City" value={form.city} onChange={(v) => set("city", v)} />
              <Text label="Category" value={form.category} onChange={(v) => set("category", v)} />
            </div>
          </div>

          <div className="space-y-3 border-t border-border-dark pt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-secondary">Contact details</p>
            <div className="grid grid-cols-2 gap-3">
              <Text label="Contact name" value={form.contact_name} onChange={(v) => set("contact_name", v)} />
              <Text label="Phone" value={form.phone} onChange={(v) => set("phone", v)} />
            </div>
            <Text label="Email" value={form.email} onChange={(v) => set("email", v)} />
          </div>

          <div className="space-y-3 border-t border-border-dark pt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-secondary">Billing details</p>
            <Text label="GSTIN" value={form.gstin} onChange={(v) => set("gstin", v)} />
            <Text label="Payment terms" value={form.payment_terms} onChange={(v) => set("payment_terms", v)} />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-gold text-base text-sm rounded px-4 py-2 font-semibold hover:bg-gold-hover disabled:opacity-50"
          >
            {submitting ? "Saving…" : "Save vendor"}
          </button>
        </form>
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
          {expanded ? "Hide products" : "View products →"}
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
