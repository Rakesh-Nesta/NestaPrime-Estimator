import { useEffect, useState } from "react";
import {
  closePriceRequest,
  createPriceRequest,
  createVendor,
  createVendorReply,
  listPriceRequests,
  listRateItems,
  listVendorReplies,
  listVendors,
  updateVendor,
  useVendorReply,
} from "./api";

const CHANNELS = [
  { value: "whatsapp", label: "WhatsApp" },
  { value: "email", label: "Email" },
];

function StatusBadge({ status }) {
  const styles = {
    open: "bg-surface-raised text-text-secondary",
    replied: "bg-gold-muted text-gold-hover",
    closed: "bg-green-500/10 text-green-400",
  };
  return (
    <span className={`text-xs rounded px-2 py-0.5 ${styles[status] || "bg-surface-raised text-text-secondary"}`}>{status}</span>
  );
}

function VendorsPanel({ token, vendors, onChanged }) {
  const [form, setForm] = useState({ name: "", phone: "", email: "", whatsapp_opt_in: false, email_opt_in: true });
  const [error, setError] = useState("");

  async function handleCreate() {
    setError("");
    try {
      await createVendor(token, form);
      setForm({ name: "", phone: "", email: "", whatsapp_opt_in: false, email_opt_in: true });
      await onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleOptIn(vendorId, field, value) {
    setError("");
    try {
      await updateVendor(token, vendorId, { [field]: value });
      await onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <h3 className="text-sm font-semibold text-text-secondary">Vendors</h3>
      <p className="text-xs text-text-secondary">
        M.7.2 rule 5: WhatsApp only to opted-in numbers; email is opt-out by default.
      </p>
      {error && <p className="text-xs text-red-400">{error}</p>}
      {vendors.map((v) => (
        <div key={v.id} className="flex flex-wrap items-center justify-between gap-2 border border-border-dark rounded px-3 py-2 text-sm">
          <span>
            <span className="font-medium">{v.name}</span>{" "}
            <span className="text-xs text-text-secondary">{v.phone || "no phone"} · {v.email || "no email"}</span>
          </span>
          <div className="flex items-center gap-3 text-xs">
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={v.whatsapp_opt_in}
                onChange={(e) => toggleOptIn(v.id, "whatsapp_opt_in", e.target.checked)}
              />
              WhatsApp opt-in
            </label>
            <label className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={v.email_opt_in}
                onChange={(e) => toggleOptIn(v.id, "email_opt_in", e.target.checked)}
              />
              Email opt-in
            </label>
          </div>
        </div>
      ))}
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text" placeholder="Vendor name" value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
        />
        <input
          type="text" placeholder="Phone" value={form.phone}
          onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
          className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm w-32"
        />
        <input
          type="email" placeholder="Email" value={form.email}
          onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
          className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm w-40"
        />
        <button
          onClick={handleCreate}
          disabled={!form.name}
          className="bg-gold text-white text-xs rounded px-3 py-1.5 hover:bg-gold-hover disabled:opacity-50"
        >
          Add vendor
        </button>
      </div>
    </div>
  );
}

function RepliesPanel({ token, priceRequestId, item, vendors, onChanged }) {
  const [replies, setReplies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [replyForm, setReplyForm] = useState({
    vendor_id: "", raw_reply_text: "", parsed_rate: "", parsed_unit: "", parsed_gst_basis: "", parsed_validity_days: "",
  });
  const [lineIdByReply, setLineIdByReply] = useState({});

  function load() {
    return listVendorReplies(token, priceRequestId, item.id).then(setReplies);
  }

  useEffect(() => {
    setLoading(true);
    load().catch((err) => setError(err.message)).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [priceRequestId, item.id]);

  async function handleCaptureReply() {
    setError("");
    try {
      await createVendorReply(token, priceRequestId, item.id, {
        vendor_id: replyForm.vendor_id,
        raw_reply_text: replyForm.raw_reply_text,
        parsed_rate: replyForm.parsed_rate ? Number(replyForm.parsed_rate) : null,
        parsed_unit: replyForm.parsed_unit || null,
        parsed_gst_basis: replyForm.parsed_gst_basis || null,
        parsed_validity_days: replyForm.parsed_validity_days ? Number(replyForm.parsed_validity_days) : null,
      });
      setReplyForm({ vendor_id: "", raw_reply_text: "", parsed_rate: "", parsed_unit: "", parsed_gst_basis: "", parsed_validity_days: "" });
      await load();
      await onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleUse(replyId, applyTo) {
    setError("");
    try {
      await useVendorReply(token, replyId, {
        apply_to: applyTo,
        cost_sheet_line_id: applyTo !== "master" ? lineIdByReply[replyId] || null : null,
      });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) return <p className="text-xs text-text-secondary">Loading replies…</p>;

  return (
    <div className="bg-surface-raised rounded p-3 space-y-2 text-xs">
      {error && <p className="text-red-400">{error}</p>}
      {replies.map((r) => (
        <div key={r.id} className="border border-border-dark bg-surface rounded px-2 py-2 space-y-1">
          <div className="flex items-center justify-between">
            <span className="font-medium">{r.vendor_name}</span>
            <span>
              {r.parsed_rate != null ? `Rs ${r.parsed_rate}${r.parsed_unit ? "/" + r.parsed_unit : ""}` : "no rate parsed"}
              {r.parsed_gst_basis && ` · ${r.parsed_gst_basis}`}
              {r.parsed_validity_days != null && ` · valid ${r.parsed_validity_days}d`}
              {r.vendor_reliability_score != null && ` · reliability ${r.vendor_reliability_score}`}
            </span>
          </div>
          <p className="text-text-secondary italic">"{r.raw_reply_text}"</p>
          {r.confirmed ? (
            <p className="text-green-400">Used ({r.applied_as})</p>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => handleUse(r.id, "master")}
                disabled={r.parsed_rate == null}
                className="bg-gold text-white rounded px-2 py-1 hover:bg-gold-hover disabled:opacity-50"
              >
                Use for master rate
              </button>
              <input
                type="text" placeholder="Cost sheet line id"
                value={lineIdByReply[r.id] || ""}
                onChange={(e) => setLineIdByReply((m) => ({ ...m, [r.id]: e.target.value }))}
                className="border border-border-dark bg-surface-raised text-text-primary rounded px-1 py-1 w-40"
              />
              <button
                onClick={() => handleUse(r.id, "cost_sheet_line")}
                disabled={r.parsed_rate == null || !lineIdByReply[r.id]}
                className="bg-surface-raised text-white rounded px-2 py-1 hover:bg-surface-raised disabled:opacity-50"
              >
                Use for this line
              </button>
            </div>
          )}
        </div>
      ))}
      {replies.length === 0 && <p className="text-text-secondary">No replies captured yet.</p>}

      <div className="border-t border-border-dark pt-2 space-y-1">
        <p className="font-semibold text-text-secondary">Capture a vendor reply</p>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={replyForm.vendor_id}
            onChange={(e) => setReplyForm((f) => ({ ...f, vendor_id: e.target.value }))}
            className="border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1"
          >
            <option value="">Vendor…</option>
            {vendors.map((v) => (
              <option key={v.id} value={v.id}>{v.name}</option>
            ))}
          </select>
          <input
            type="text" placeholder='e.g. "Rs 68/kg ex-GST, valid 15 days"'
            value={replyForm.raw_reply_text}
            onChange={(e) => setReplyForm((f) => ({ ...f, raw_reply_text: e.target.value }))}
            className="flex-1 min-w-[220px] border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="number" placeholder="Rate (override)" value={replyForm.parsed_rate}
            onChange={(e) => setReplyForm((f) => ({ ...f, parsed_rate: e.target.value }))}
            className="border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1 w-32"
          />
          <input
            type="text" placeholder="Unit" value={replyForm.parsed_unit}
            onChange={(e) => setReplyForm((f) => ({ ...f, parsed_unit: e.target.value }))}
            className="border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1 w-20"
          />
          <select
            value={replyForm.parsed_gst_basis}
            onChange={(e) => setReplyForm((f) => ({ ...f, parsed_gst_basis: e.target.value }))}
            className="border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1"
          >
            <option value="">GST basis…</option>
            <option value="inclusive">Inclusive</option>
            <option value="exclusive">Exclusive</option>
          </select>
          <input
            type="number" placeholder="Validity days" value={replyForm.parsed_validity_days}
            onChange={(e) => setReplyForm((f) => ({ ...f, parsed_validity_days: e.target.value }))}
            className="border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1 w-28"
          />
          <button
            onClick={handleCaptureReply}
            disabled={!replyForm.vendor_id || !replyForm.raw_reply_text}
            className="bg-gold text-white rounded px-3 py-1.5 hover:bg-gold-hover disabled:opacity-50"
          >
            Capture reply
          </button>
        </div>
        <p className="text-text-secondary">
          Fields left blank are auto-proposed from the reply text (rate/unit/GST basis/validity) -- override any of
          them before capturing.
        </p>
      </div>
    </div>
  );
}

function NewPriceRequestForm({ token, rateItems, vendors, onCreated }) {
  const [items, setItems] = useState([{ rate_item_id: "", quantity_band: "" }]);
  const [vendorIds, setVendorIds] = useState(new Set());
  const [channels, setChannels] = useState(new Set(["whatsapp", "email"]));
  const [requiredBy, setRequiredBy] = useState("");
  const [validityDays, setValidityDays] = useState("");
  const [error, setError] = useState("");

  function updateItem(index, field, value) {
    setItems((rows) => rows.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  }

  function toggleSet(setter, current, value) {
    const next = new Set(current);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    setter(next);
  }

  async function handleSubmit() {
    setError("");
    try {
      await createPriceRequest(token, {
        items: items.filter((i) => i.rate_item_id).map((i) => ({ rate_item_id: i.rate_item_id, quantity_band: i.quantity_band || null })),
        vendor_ids: [...vendorIds],
        channels: [...channels],
        required_by: requiredBy || null,
        requested_validity_days: validityDays ? Number(validityDays) : null,
      });
      setItems([{ rate_item_id: "", quantity_band: "" }]);
      setVendorIds(new Set());
      setRequiredBy("");
      setValidityDays("");
      await onCreated();
    } catch (err) {
      setError(err.message);
    }
  }

  const canSubmit = items.some((i) => i.rate_item_id) && vendorIds.size > 0 && channels.size > 0;

  return (
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <h3 className="text-sm font-semibold text-text-secondary">Request a price update (M.7.3)</h3>
      {error && <p className="text-xs text-red-400">{error}</p>}

      <div className="space-y-2">
        <p className="text-xs font-medium text-text-secondary">Items</p>
        {items.map((row, i) => (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <select
              value={row.rate_item_id}
              onChange={(e) => updateItem(i, "rate_item_id", e.target.value)}
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm min-w-[220px]"
            >
              <option value="">Select rate item…</option>
              {rateItems.map((ri) => (
                <option key={ri.id} value={ri.id}>{ri.category} -- {ri.item_name} ({ri.unit})</option>
              ))}
            </select>
            <input
              type="text" placeholder="Quantity band (e.g. 100-500 kg)" value={row.quantity_band}
              onChange={(e) => updateItem(i, "quantity_band", e.target.value)}
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
            />
          </div>
        ))}
        <button
          onClick={() => setItems((rows) => [...rows, { rate_item_id: "", quantity_band: "" }])}
          className="text-xs text-gold hover:underline"
        >
          + Add another item
        </button>
      </div>

      <div>
        <p className="text-xs font-medium text-text-secondary mb-1">Vendors</p>
        <div className="flex flex-wrap gap-3">
          {vendors.map((v) => (
            <label key={v.id} className="flex items-center gap-1 text-xs">
              <input type="checkbox" checked={vendorIds.has(v.id)} onChange={() => toggleSet(setVendorIds, vendorIds, v.id)} />
              {v.name}
            </label>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-3">
          {CHANNELS.map((c) => (
            <label key={c.value} className="flex items-center gap-1 text-xs">
              <input type="checkbox" checked={channels.has(c.value)} onChange={() => toggleSet(setChannels, channels, c.value)} />
              {c.label}
            </label>
          ))}
        </div>
        <input
          type="date" value={requiredBy} onChange={(e) => setRequiredBy(e.target.value)}
          className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
          title="Required by"
        />
        <input
          type="number" placeholder="Requested validity (days)" value={validityDays}
          onChange={(e) => setValidityDays(e.target.value)}
          className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm w-44"
        />
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="bg-gold text-white text-sm rounded px-4 py-2 hover:bg-gold-hover disabled:opacity-50"
        >
          Send price update request
        </button>
      </div>
    </div>
  );
}

export default function PriceRequests({ token, onBack }) {
  const [priceRequests, setPriceRequests] = useState([]);
  const [rateItems, setRateItems] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [expandedItem, setExpandedItem] = useState(null); // { requestId, itemId }

  function load() {
    return Promise.all([
      listPriceRequests(token, { overdueOnly }),
      listRateItems(token),
      listVendors(token),
    ]).then(([pr, ri, v]) => {
      setPriceRequests(pr);
      setRateItems(ri);
      setVendors(v);
    });
  }

  useEffect(() => {
    setLoading(true);
    load().catch((err) => setError(err.message)).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, overdueOnly]);

  async function handleClose(id) {
    setError("");
    try {
      await closePriceRequest(token, id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) return <p className="text-center text-text-secondary mt-10">Loading price requests…</p>;

  return (
    <div className="max-w-4xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Vendor Price-Update Requests</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-text-secondary mt-1">
          M.7.3: ask vendors for a current price, capture their reply, and use it to update the master rate or a
          Cost Sheet line. No real WhatsApp/email provider is wired up (the blueprint marks the BSP choice as
          "[confirm]") -- sends are recorded, replies are logged from what the vendor actually said.
        </p>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
      </div>

      <VendorsPanel token={token} vendors={vendors} onChanged={load} />
      <NewPriceRequestForm token={token} rateItems={rateItems} vendors={vendors} onCreated={load} />

      <div className="bg-surface shadow rounded-lg p-6 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-secondary">Requests</h3>
          <label className="flex items-center gap-1 text-xs text-text-secondary">
            <input type="checkbox" checked={overdueOnly} onChange={(e) => setOverdueOnly(e.target.checked)} />
            Overdue only
          </label>
        </div>
        {priceRequests.map((pr) => (
          <div key={pr.id} className="border border-border-dark rounded px-3 py-2 text-sm space-y-2">
            <div className="flex items-center justify-between">
              <span>
                <StatusBadge status={pr.status} />
                {pr.reminder_due && <span className="text-amber-400 text-xs ml-2">reminder due</span>}
                {pr.required_by && <span className="text-xs text-text-secondary ml-2">required by {pr.required_by}</span>}
              </span>
              {pr.status !== "closed" && (
                <button onClick={() => handleClose(pr.id)} className="text-xs text-text-secondary hover:underline">
                  Close
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              {pr.vendors.map((v) => (
                <span
                  key={v.id}
                  className={`rounded px-2 py-0.5 ${v.replied ? "bg-green-500/10 text-green-400" : v.reminder_due ? "bg-amber-500/10 text-amber-400" : "bg-surface-raised text-text-secondary"}`}
                >
                  {v.vendor_name}{v.replied ? " · replied" : v.reminder_due ? " · no reply" : ""}
                </span>
              ))}
            </div>
            <div className="space-y-1">
              {pr.items.map((item) => (
                <div key={item.id}>
                  <button
                    onClick={() =>
                      setExpandedItem(
                        expandedItem?.requestId === pr.id && expandedItem?.itemId === item.id
                          ? null
                          : { requestId: pr.id, itemId: item.id }
                      )
                    }
                    className="text-xs text-gold hover:underline"
                  >
                    {item.category} -- {item.item_name} {item.quantity_band ? `(${item.quantity_band})` : ""}
                    {expandedItem?.requestId === pr.id && expandedItem?.itemId === item.id ? " (hide replies)" : " (view replies)"}
                  </button>
                  {expandedItem?.requestId === pr.id && expandedItem?.itemId === item.id && (
                    <RepliesPanel token={token} priceRequestId={pr.id} item={item} vendors={vendors} onChanged={load} />
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
        {priceRequests.length === 0 && <p className="text-sm text-text-secondary text-center py-6">No price requests yet.</p>}
      </div>
    </div>
  );
}
