import { useEffect, useState } from "react";
import {
  cancelPurchaseOrder,
  createPurchaseOrder,
  createVendor,
  issuePurchaseOrder,
  listPurchaseOrders,
  listVendors,
  receivePurchaseOrder,
} from "./api";

const STATUS_COLORS = {
  draft: "bg-surface-raised text-text-secondary",
  issued: "bg-gold-muted text-gold-hover",
  partially_received: "bg-amber-500/10 text-amber-400",
  received: "bg-green-500/10 text-green-400",
  cancelled: "bg-red-500/10 text-red-400",
};

function StatusBadge({ status }) {
  return <span className={`text-xs rounded px-1.5 py-0.5 ${STATUS_COLORS[status] ?? "bg-surface-raised"}`}>{status}</span>;
}

export default function PurchaseOrdersPanel({ token, costSheetId, consumptionRows, onChanged }) {
  const [vendors, setVendors] = useState([]);
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showNewVendor, setShowNewVendor] = useState(false);
  const [newVendor, setNewVendor] = useState({ name: "", city: "", phone: "" });

  const [vendorId, setVendorId] = useState("");
  const [deliveryDate, setDeliveryDate] = useState("");
  const [ewayBillNo, setEwayBillNo] = useState("");
  const [selectedLineIds, setSelectedLineIds] = useState({});
  const [lineOverrides, setLineOverrides] = useState({}); // id -> { quantity, rate }

  const [receiveInputs, setReceiveInputs] = useState({}); // po_line_id -> qty

  const availableRows = (consumptionRows ?? []).filter((r) => !r.po_no);

  function load() {
    return Promise.all([listVendors(token), listPurchaseOrders(token, costSheetId)]).then(([v, po]) => {
      setVendors(v);
      setPurchaseOrders(po);
    });
  }

  useEffect(() => {
    setLoading(true);
    load().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, costSheetId]);

  async function refresh() {
    setError("");
    try {
      await load();
      onChanged?.();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleCreateVendor() {
    setError("");
    try {
      const created = await createVendor(token, newVendor);
      setNewVendor({ name: "", city: "", phone: "" });
      setShowNewVendor(false);
      setVendorId(created.id);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  function toggleLine(row) {
    setSelectedLineIds((s) => ({ ...s, [row.id]: !s[row.id] }));
    if (!lineOverrides[row.id]) {
      setLineOverrides((o) => ({ ...o, [row.id]: { quantity: String(row.order_qty), rate: String(row.rate) } }));
    }
  }

  function updateOverride(rowId, field, value) {
    setLineOverrides((o) => ({ ...o, [rowId]: { ...o[rowId], [field]: value } }));
  }

  async function handleRaisePO() {
    setError("");
    const lines = Object.keys(selectedLineIds)
      .filter((id) => selectedLineIds[id])
      .map((id) => ({
        cost_sheet_line_id: id,
        quantity: Number(lineOverrides[id]?.quantity),
        rate: Number(lineOverrides[id]?.rate),
      }));
    if (!vendorId || lines.length === 0) return;
    try {
      await createPurchaseOrder(token, costSheetId, {
        vendor_id: vendorId,
        lines,
        delivery_date: deliveryDate || undefined,
        eway_bill_no: ewayBillNo || undefined,
      });
      setSelectedLineIds({});
      setLineOverrides({});
      setDeliveryDate("");
      setEwayBillNo("");
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleIssue(poId) {
    setError("");
    try {
      await issuePurchaseOrder(token, poId);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleCancel(poId) {
    setError("");
    try {
      await cancelPurchaseOrder(token, poId);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleReceive(poId, lineId) {
    setError("");
    const qty = Number(receiveInputs[lineId]);
    if (Number.isNaN(qty)) return;
    try {
      await receivePurchaseOrder(token, poId, { lines: [{ line_id: lineId, received_qty: qty }] });
      setReceiveInputs((r) => ({ ...r, [lineId]: "" }));
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) return <p className="text-xs text-text-secondary">Loading purchase orders…</p>;

  return (
    <div className="border border-border-dark rounded p-3 space-y-3">
      <p className="text-xs font-semibold text-text-secondary">Purchase Orders (Part O)</p>
      {error && <p className="text-xs text-red-400">{error}</p>}

      {purchaseOrders.length === 0 && <p className="text-xs text-text-secondary">No purchase orders raised yet.</p>}
      {purchaseOrders.map((po) => (
        <div key={po.id} className="border border-border-dark rounded p-2 space-y-1.5 bg-surface-raised">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <span>
              <span className="font-medium">{po.po_no}</span> · {po.vendor_name} · <StatusBadge status={po.status} />
              {po.delivery_date && <span className="text-text-secondary"> · delivery {po.delivery_date}</span>}
              {po.eway_bill_no && <span className="text-text-secondary"> · e-way {po.eway_bill_no}</span>}
            </span>
            <div className="flex items-center gap-2">
              {po.status === "draft" && (
                <button onClick={() => handleIssue(po.id)} className="text-gold hover:underline">
                  Issue
                </button>
              )}
              {po.status !== "received" && po.status !== "cancelled" && (
                <button onClick={() => handleCancel(po.id)} className="text-red-400 hover:underline">
                  Cancel
                </button>
              )}
            </div>
          </div>
          {po.lines.map((line) => (
            <div key={line.id} className="flex flex-wrap items-center justify-between gap-2 text-xs bg-surface rounded px-2 py-1">
              <span>
                {line.item_name} · {line.quantity} {line.unit} x Rs {line.rate} = Rs {line.amount.toLocaleString()} ·
                received {line.received_qty} · balance {line.balance_qty}
              </span>
              {(po.status === "issued" || po.status === "partially_received") && (
                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    value={receiveInputs[line.id] ?? ""}
                    onChange={(e) => setReceiveInputs((r) => ({ ...r, [line.id]: e.target.value }))}
                    placeholder="received qty"
                    className="w-24 text-xs border border-border-dark bg-surface-raised text-text-primary rounded px-1 py-0.5"
                  />
                  <button onClick={() => handleReceive(po.id, line.id)} className="text-green-400 hover:underline">
                    Record receipt
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      ))}

      <div className="border-t border-border-dark pt-3 space-y-2">
        <p className="text-xs font-medium text-text-secondary">Raise a new purchase order</p>

        <div className="flex items-center gap-2">
          <select
            value={vendorId}
            onChange={(e) => setVendorId(e.target.value)}
            className="flex-1 rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs"
          >
            <option value="">Select a vendor…</option>
            {vendors.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
          <button type="button" onClick={() => setShowNewVendor((s) => !s)} className="text-xs text-gold hover:underline">
            {showNewVendor ? "Cancel" : "+ New vendor"}
          </button>
        </div>

        {showNewVendor && (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newVendor.name}
              onChange={(e) => setNewVendor((v) => ({ ...v, name: e.target.value }))}
              placeholder="Vendor name"
              className="flex-1 text-xs border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1"
            />
            <input
              type="text"
              value={newVendor.city}
              onChange={(e) => setNewVendor((v) => ({ ...v, city: e.target.value }))}
              placeholder="City"
              className="w-28 text-xs border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1"
            />
            <input
              type="text"
              value={newVendor.phone}
              onChange={(e) => setNewVendor((v) => ({ ...v, phone: e.target.value }))}
              placeholder="Phone"
              className="w-32 text-xs border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1"
            />
            <button
              type="button"
              onClick={handleCreateVendor}
              disabled={!newVendor.name}
              className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover disabled:opacity-50"
            >
              Add
            </button>
          </div>
        )}

        {availableRows.length === 0 ? (
          <p className="text-xs text-text-secondary">
            Every Cost Sheet line already has an open PO, or there are no lines yet.
          </p>
        ) : (
          <div className="space-y-1">
            {availableRows.map((row) => (
              <div key={row.id} className="grid grid-cols-12 gap-2 items-center text-xs">
                <label className="col-span-5 flex items-center gap-1">
                  <input type="checkbox" checked={!!selectedLineIds[row.id]} onChange={() => toggleLine(row)} />
                  {row.item_name} ({row.unit})
                </label>
                <input
                  type="number"
                  disabled={!selectedLineIds[row.id]}
                  value={lineOverrides[row.id]?.quantity ?? ""}
                  onChange={(e) => updateOverride(row.id, "quantity", e.target.value)}
                  placeholder="Qty"
                  className="col-span-3 text-xs border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1 disabled:bg-surface-raised"
                />
                <input
                  type="number"
                  disabled={!selectedLineIds[row.id]}
                  value={lineOverrides[row.id]?.rate ?? ""}
                  onChange={(e) => updateOverride(row.id, "rate", e.target.value)}
                  placeholder="Rs/unit"
                  className="col-span-4 text-xs border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1 disabled:bg-surface-raised"
                />
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center gap-2">
          <input
            type="date"
            value={deliveryDate}
            onChange={(e) => setDeliveryDate(e.target.value)}
            className="text-xs border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1"
          />
          <input
            type="text"
            value={ewayBillNo}
            onChange={(e) => setEwayBillNo(e.target.value)}
            placeholder="E-way bill no. (optional)"
            className="flex-1 text-xs border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1"
          />
          <button
            type="button"
            onClick={handleRaisePO}
            disabled={!vendorId || !Object.values(selectedLineIds).some(Boolean)}
            className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover disabled:opacity-50"
          >
            Raise PO
          </button>
        </div>
      </div>
    </div>
  );
}
