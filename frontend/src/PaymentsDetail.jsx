import { useEffect, useState } from "react";
import {
  addWorkOrderPaymentEntry,
  createWorkOrderPaymentMilestone,
  deletePaymentMilestone,
  getWorkOrderPaymentSummary,
  listWorkOrderPaymentEntries,
  listWorkOrderPaymentMilestones,
  updatePaymentEntry,
  updatePaymentMilestone,
} from "./api";
import { formatRs } from "./money";

// Amendment 50 (Section 54): one Work Order's expected payments (milestones)
// and the payments received against them. Used by both the Payments screen
// (an expanded row) and the Work Order panel on Documents, so the two can
// never drift apart. Reconciliation only: every figure is entered by a person
// or derived by the API from what was entered -- nothing is estimated, and no
// schedule is guessed from the client's payment terms.
const STATUS_STYLE = {
  pending: "bg-surface-raised text-text-secondary",
  part_paid: "bg-gold/10 text-gold",
  paid: "bg-green-500/10 text-green-400",
};
const STATUS_LABEL = { pending: "Pending", part_paid: "Part paid", paid: "Paid" };

const inputClass = "rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5 text-xs w-full";
const labelClass = "block text-[11px] font-medium text-text-secondary";

const emptyMilestone = { name: "", amount_due: "", due_date: "", notes: "" };
const emptyReceipt = {
  milestone_name: "", amount_received: "", received_date: "", gst_tds_amount: "", notes: "", milestone_id: "",
};

function Field({ id, label, children }) {
  return (
    <div className="min-w-0">
      <label htmlFor={id} className={labelClass}>
        {label}
      </label>
      {children}
    </div>
  );
}

// showSummary: the Payments screen's own row already shows these four figures,
// so it turns the strip off; the Work Order panel on Documents keeps it.
export default function PaymentsDetail({
  token, workOrderId, canEdit, paymentTerms, onChanged, idPrefix = "pd", showSummary = true,
}) {
  const [milestones, setMilestones] = useState([]);
  const [entries, setEntries] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [error, setError] = useState("");
  const [showMilestoneForm, setShowMilestoneForm] = useState(false);
  const [showReceiptForm, setShowReceiptForm] = useState(false);
  const [milestoneForm, setMilestoneForm] = useState(emptyMilestone);
  const [receiptForm, setReceiptForm] = useState(emptyReceipt);
  const [editingMilestone, setEditingMilestone] = useState(null); // { id, ...draft }
  const [editingEntry, setEditingEntry] = useState(null); // { id, ...draft }

  async function load() {
    const [m, e, s] = await Promise.all([
      listWorkOrderPaymentMilestones(token, workOrderId),
      listWorkOrderPaymentEntries(token, workOrderId),
      getWorkOrderPaymentSummary(token, workOrderId),
    ]);
    setMilestones(m);
    setEntries(e);
    setSummary(s);
  }

  useEffect(() => {
    setLoading(true);
    setLoadFailed(false);
    load()
      .catch((err) => {
        setError(err.message);
        setLoadFailed(true);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, workOrderId]);

  // Run a write, then reload and tell the parent (which refreshes its totals).
  async function run(action) {
    setError("");
    try {
      await action();
      await load();
      if (onChanged) onChanged();
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    }
  }

  const milestoneName = Object.fromEntries(milestones.map((m) => [m.id, m.name]));

  async function submitMilestone(e) {
    e.preventDefault();
    const ok = await run(() =>
      createWorkOrderPaymentMilestone(token, workOrderId, {
        name: milestoneForm.name,
        amount_due: Number(milestoneForm.amount_due),
        due_date: milestoneForm.due_date,
        notes: milestoneForm.notes || null,
      })
    );
    if (ok) {
      setMilestoneForm(emptyMilestone);
      setShowMilestoneForm(false);
    }
  }

  async function saveMilestoneEdit(e) {
    e.preventDefault();
    const d = editingMilestone;
    const ok = await run(() =>
      updatePaymentMilestone(token, d.id, {
        name: d.name,
        amount_due: Number(d.amount_due),
        due_date: d.due_date,
        notes: d.notes || null,
      })
    );
    if (ok) setEditingMilestone(null);
  }

  async function removeMilestone(m) {
    if (!window.confirm(`Delete the milestone "${m.name}"? This is recorded in the audit log.`)) return;
    await run(() => deletePaymentMilestone(token, m.id));
  }

  // Picking a milestone with no description typed yet uses the milestone's own name.
  function receiptPayload(f) {
    const linked = f.milestone_id ? milestoneName[f.milestone_id] : "";
    return {
      milestone_name: f.milestone_name.trim() || linked || "",
      amount_received: Number(f.amount_received),
      received_date: f.received_date,
      gst_tds_amount: f.gst_tds_amount === "" ? null : Number(f.gst_tds_amount),
      notes: f.notes || null,
      milestone_id: f.milestone_id || null,
    };
  }

  async function submitReceipt(e) {
    e.preventDefault();
    const ok = await run(() => addWorkOrderPaymentEntry(token, workOrderId, receiptPayload(receiptForm)));
    if (ok) {
      setReceiptForm(emptyReceipt);
      setShowReceiptForm(false);
    }
  }

  async function saveReceiptEdit(e) {
    e.preventDefault();
    const d = editingEntry;
    const ok = await run(() => updatePaymentEntry(token, d.id, receiptPayload(d)));
    if (ok) setEditingEntry(null);
  }

  function milestoneOptions(includeBlank) {
    return (
      <>
        {includeBlank && <option value="">Not against a milestone</option>}
        {milestones.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name} (due {m.due_date})
          </option>
        ))}
      </>
    );
  }

  if (loading) return <p className="text-xs text-text-secondary">Loading payments…</p>;

  return (
    <div className="space-y-4 text-xs">
      {error && <p className="text-red-400">{error}</p>}

      {showSummary && summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            ["Order value", summary.order_value],
            ["Received", summary.total_received],
            ["TDS withheld", summary.total_tds],
            ["Outstanding", summary.outstanding],
          ].map(([label, value]) => (
            <div key={label} className="bg-surface-raised border border-border-dark rounded px-3 py-2">
              <p className="text-[10px] uppercase tracking-wide text-text-secondary">{label}</p>
              <p className="text-sm font-medium text-text-primary mt-0.5">{formatRs(value)}</p>
            </div>
          ))}
        </div>
      )}
      {showSummary && summary?.over_received && (
        <p className="text-gold">Received plus TDS is more than the order value (an advance or extra work).</p>
      )}

      {/* ---------------- Expected payments ---------------- */}
      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="font-semibold text-text-secondary">Expected payments</h4>
          {canEdit && (
            <button onClick={() => setShowMilestoneForm((v) => !v)} className="text-gold hover:underline">
              {showMilestoneForm ? "Close" : "+ Add milestone"}
            </button>
          )}
        </div>

        {canEdit && showMilestoneForm && (
          <form onSubmit={submitMilestone} className="space-y-2 border border-border-dark rounded p-3">
            {paymentTerms && (
              <p className="text-text-secondary">
                Client payment terms: <span className="text-text-primary">{paymentTerms}</span> -- a reminder only;
                enter the schedule yourself.
              </p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
              <Field id={`${idPrefix}-m-name`} label="Milestone">
                <input id={`${idPrefix}-m-name`} className={inputClass} required value={milestoneForm.name}
                  onChange={(e) => setMilestoneForm((f) => ({ ...f, name: e.target.value }))} />
              </Field>
              <Field id={`${idPrefix}-m-amount`} label="Amount due (Rs)">
                <input id={`${idPrefix}-m-amount`} className={inputClass} type="number" min="0.01" step="0.01" required
                  value={milestoneForm.amount_due}
                  onChange={(e) => setMilestoneForm((f) => ({ ...f, amount_due: e.target.value }))} />
              </Field>
              <Field id={`${idPrefix}-m-due`} label="Due date">
                <input id={`${idPrefix}-m-due`} className={inputClass} type="date" required value={milestoneForm.due_date}
                  onChange={(e) => setMilestoneForm((f) => ({ ...f, due_date: e.target.value }))} />
              </Field>
              <Field id={`${idPrefix}-m-notes`} label="Notes (optional)">
                <input id={`${idPrefix}-m-notes`} className={inputClass} value={milestoneForm.notes}
                  onChange={(e) => setMilestoneForm((f) => ({ ...f, notes: e.target.value }))} />
              </Field>
            </div>
            <button type="submit" className="bg-gold text-base rounded px-3 py-1.5 font-semibold hover:bg-gold-hover">
              Save milestone
            </button>
          </form>
        )}

        {milestones.length === 0 && !loadFailed && (
          <p className="text-text-secondary">
            No expected payments set. {canEdit ? "Add a milestone with an amount and a due date" : "None have been added"}
            {canEdit ? " to track when money is due." : "."}
          </p>
        )}

        {milestones.map((m) =>
          editingMilestone?.id === m.id ? (
            <form key={m.id} onSubmit={saveMilestoneEdit} className="space-y-2 border border-gold/40 rounded p-3">
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
                <Field id={`${idPrefix}-me-name`} label="Milestone">
                  <input id={`${idPrefix}-me-name`} className={inputClass} required value={editingMilestone.name}
                    onChange={(e) => setEditingMilestone((d) => ({ ...d, name: e.target.value }))} />
                </Field>
                <Field id={`${idPrefix}-me-amount`} label="Amount due (Rs)">
                  <input id={`${idPrefix}-me-amount`} className={inputClass} type="number" min="0.01" step="0.01" required
                    value={editingMilestone.amount_due}
                    onChange={(e) => setEditingMilestone((d) => ({ ...d, amount_due: e.target.value }))} />
                </Field>
                <Field id={`${idPrefix}-me-due`} label="Due date">
                  <input id={`${idPrefix}-me-due`} className={inputClass} type="date" required value={editingMilestone.due_date}
                    onChange={(e) => setEditingMilestone((d) => ({ ...d, due_date: e.target.value }))} />
                </Field>
                <Field id={`${idPrefix}-me-notes`} label="Notes (optional)">
                  <input id={`${idPrefix}-me-notes`} className={inputClass} value={editingMilestone.notes}
                    onChange={(e) => setEditingMilestone((d) => ({ ...d, notes: e.target.value }))} />
                </Field>
              </div>
              <div className="flex items-center gap-4">
                <button type="submit" className="bg-gold text-base rounded px-3 py-1.5 font-semibold hover:bg-gold-hover">
                  Save changes
                </button>
                <button type="button" onClick={() => setEditingMilestone(null)} className="text-text-secondary hover:text-text-primary">
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <div key={m.id} className="border border-border-dark rounded px-3 py-2 space-y-1">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <span className="min-w-0 break-words">
                  <span className="font-medium text-text-primary">{m.name}</span>{" "}
                  <span className={m.overdue ? "text-red-400" : "text-text-secondary"}>
                    · due {m.due_date}
                    {m.overdue && " (overdue)"}
                  </span>
                </span>
                <span className="flex items-center gap-2 shrink-0">
                  {m.overdue && (
                    <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-red-500/10 text-red-400">
                      Overdue
                    </span>
                  )}
                  <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${STATUS_STYLE[m.status]}`}>
                    {STATUS_LABEL[m.status]}
                  </span>
                </span>
              </div>
              <p className="text-text-secondary">
                Due {formatRs(m.amount_due)} · received {formatRs(m.received_amount)}
                {m.tds_amount > 0 && ` + TDS ${formatRs(m.tds_amount)}`} · outstanding{" "}
                <span className={m.overdue ? "text-red-400" : "text-text-primary"}>{formatRs(m.outstanding_amount)}</span>
                {m.notes && ` · ${m.notes}`}
              </p>
              {canEdit && (
                <div className="flex items-center gap-4">
                  <button
                    onClick={() =>
                      setEditingMilestone({
                        id: m.id, name: m.name, amount_due: String(m.amount_due), due_date: m.due_date, notes: m.notes || "",
                      })
                    }
                    className="text-gold hover:underline"
                  >
                    Edit
                  </button>
                  <button onClick={() => removeMilestone(m)} className="text-text-secondary hover:text-red-400">
                    Delete
                  </button>
                </div>
              )}
            </div>
          )
        )}
      </section>

      {/* ---------------- Payments received ---------------- */}
      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="font-semibold text-text-secondary">Payments received</h4>
          {canEdit && (
            <button onClick={() => setShowReceiptForm((v) => !v)} className="text-gold hover:underline">
              {showReceiptForm ? "Close" : "+ Record payment"}
            </button>
          )}
        </div>

        {canEdit && showReceiptForm && (
          <form onSubmit={submitReceipt} className="space-y-2 border border-border-dark rounded p-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <Field id={`${idPrefix}-r-milestone`} label="Against milestone (optional)">
                <select id={`${idPrefix}-r-milestone`} className={inputClass} value={receiptForm.milestone_id}
                  onChange={(e) => setReceiptForm((f) => ({ ...f, milestone_id: e.target.value }))}>
                  {milestoneOptions(true)}
                </select>
              </Field>
              <Field id={`${idPrefix}-r-name`} label="What was it for?">
                <input id={`${idPrefix}-r-name`} className={inputClass} value={receiptForm.milestone_name}
                  required={!receiptForm.milestone_id}
                  placeholder={receiptForm.milestone_id ? milestoneName[receiptForm.milestone_id] : ""}
                  onChange={(e) => setReceiptForm((f) => ({ ...f, milestone_name: e.target.value }))} />
              </Field>
              <Field id={`${idPrefix}-r-amount`} label="Amount received (Rs)">
                <input id={`${idPrefix}-r-amount`} className={inputClass} type="number" min="0.01" step="0.01" required
                  value={receiptForm.amount_received}
                  onChange={(e) => setReceiptForm((f) => ({ ...f, amount_received: e.target.value }))} />
              </Field>
              <Field id={`${idPrefix}-r-date`} label="Received on">
                <input id={`${idPrefix}-r-date`} className={inputClass} type="date" required
                  value={receiptForm.received_date}
                  onChange={(e) => setReceiptForm((f) => ({ ...f, received_date: e.target.value }))} />
              </Field>
              <Field id={`${idPrefix}-r-tds`} label="GST-TDS withheld (optional)">
                <input id={`${idPrefix}-r-tds`} className={inputClass} type="number" min="0" step="0.01"
                  value={receiptForm.gst_tds_amount}
                  onChange={(e) => setReceiptForm((f) => ({ ...f, gst_tds_amount: e.target.value }))} />
              </Field>
              <Field id={`${idPrefix}-r-notes`} label="Notes (optional)">
                <input id={`${idPrefix}-r-notes`} className={inputClass} value={receiptForm.notes}
                  onChange={(e) => setReceiptForm((f) => ({ ...f, notes: e.target.value }))} />
              </Field>
            </div>
            <button type="submit" className="bg-gold text-base rounded px-3 py-1.5 font-semibold hover:bg-gold-hover">
              Save payment
            </button>
          </form>
        )}

        {entries.length === 0 && !loadFailed && <p className="text-text-secondary">No payments recorded yet.</p>}

        {entries.map((en) =>
          editingEntry?.id === en.id ? (
            <form key={en.id} onSubmit={saveReceiptEdit} className="space-y-2 border border-gold/40 rounded p-3">
              <p className="text-text-secondary">
                Correcting a payment is recorded in the audit log with the old and new values.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <Field id={`${idPrefix}-re-milestone`} label="Against milestone">
                  <select id={`${idPrefix}-re-milestone`} className={inputClass} value={editingEntry.milestone_id}
                    onChange={(e) => setEditingEntry((d) => ({ ...d, milestone_id: e.target.value }))}>
                    {milestoneOptions(true)}
                  </select>
                </Field>
                <Field id={`${idPrefix}-re-name`} label="What was it for?">
                  <input id={`${idPrefix}-re-name`} className={inputClass} required value={editingEntry.milestone_name}
                    onChange={(e) => setEditingEntry((d) => ({ ...d, milestone_name: e.target.value }))} />
                </Field>
                <Field id={`${idPrefix}-re-amount`} label="Amount received (Rs)">
                  <input id={`${idPrefix}-re-amount`} className={inputClass} type="number" min="0.01" step="0.01" required
                    value={editingEntry.amount_received}
                    onChange={(e) => setEditingEntry((d) => ({ ...d, amount_received: e.target.value }))} />
                </Field>
                <Field id={`${idPrefix}-re-date`} label="Received on">
                  <input id={`${idPrefix}-re-date`} className={inputClass} type="date" required value={editingEntry.received_date}
                    onChange={(e) => setEditingEntry((d) => ({ ...d, received_date: e.target.value }))} />
                </Field>
                <Field id={`${idPrefix}-re-tds`} label="GST-TDS withheld">
                  <input id={`${idPrefix}-re-tds`} className={inputClass} type="number" min="0" step="0.01"
                    value={editingEntry.gst_tds_amount}
                    onChange={(e) => setEditingEntry((d) => ({ ...d, gst_tds_amount: e.target.value }))} />
                </Field>
                <Field id={`${idPrefix}-re-notes`} label="Notes">
                  <input id={`${idPrefix}-re-notes`} className={inputClass} value={editingEntry.notes}
                    onChange={(e) => setEditingEntry((d) => ({ ...d, notes: e.target.value }))} />
                </Field>
              </div>
              <div className="flex items-center gap-4">
                <button type="submit" className="bg-gold text-base rounded px-3 py-1.5 font-semibold hover:bg-gold-hover">
                  Save changes
                </button>
                <button type="button" onClick={() => setEditingEntry(null)} className="text-text-secondary hover:text-text-primary">
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <div key={en.id} className="border border-border-dark rounded px-3 py-2">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <span className="min-w-0 break-words">
                  <span className="text-text-primary">{en.milestone_name}</span>{" "}
                  <span className="text-text-secondary">
                    · {en.received_date}
                    {en.milestone_id && ` · against ${milestoneName[en.milestone_id] || "a milestone"}`}
                    {en.gst_tds_amount != null && ` · GST-TDS ${formatRs(en.gst_tds_amount)}`}
                    {en.notes && ` · ${en.notes}`}
                  </span>
                </span>
                <span className="font-medium text-text-primary shrink-0">{formatRs(en.amount_received)}</span>
              </div>
              {canEdit && (
                <button
                  onClick={() =>
                    setEditingEntry({
                      id: en.id,
                      milestone_name: en.milestone_name,
                      amount_received: String(en.amount_received),
                      received_date: en.received_date,
                      gst_tds_amount: en.gst_tds_amount == null ? "" : String(en.gst_tds_amount),
                      notes: en.notes || "",
                      milestone_id: en.milestone_id || "",
                    })
                  }
                  className="text-gold hover:underline mt-1"
                >
                  Edit
                </button>
              )}
            </div>
          )
        )}
      </section>
    </div>
  );
}
