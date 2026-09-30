import { useEffect, useState } from "react";
import { getProject, listClients, listPayments } from "./api";
import { AlertIcon, BankIcon, CalendarIcon, DocumentIcon, PieIcon, RupeeIcon } from "./Icons";
import { formatRs } from "./money";
import PaymentsDetail from "./PaymentsDetail";

// Amendment 50 (Section 54): the Payments header. One row per Work Order --
// what the order is worth, what has been received, what the payer withheld as
// TDS, what is still outstanding, and what is overdue against the due dates a
// person entered. Reconciliation only: figures are entered or derived by the
// API, nothing is estimated, and "overdue" exists only where a due date was
// entered. PM and Director can change things; CA/Tax sees everything read-only.
const TABS = [
  { key: "all", label: "All" },
  { key: "overdue", label: "Overdue" },
];

const WO_STATUS_LABEL = { awarded: "Awarded", in_progress: "In progress", completed: "Completed" };

const CARD_STYLE = {
  "Order value": { icon: DocumentIcon, tone: "bg-gold/10 text-gold" },
  Received: { icon: RupeeIcon, tone: "bg-green-500/10 text-green-400" },
  "TDS withheld": { icon: BankIcon, tone: "bg-blue-500/10 text-blue-400" },
  Outstanding: { icon: PieIcon, tone: "bg-amber-500/10 text-amber-400" },
  Overdue: { icon: AlertIcon, tone: "bg-red-500/10 text-red-400" },
};

export default function Payments({ token, role, initialFilter = "", onOpenProject, onOpenProjects, onBack }) {
  const [rows, setRows] = useState([]);
  const [tab, setTab] = useState(initialFilter === "overdue" ? "overdue" : "all");
  // P1 acceptance fix (correction plan, 2026-09-30): see Opportunities.jsx's own comment on this
  // same pattern -- useState's initial value only applies on first mount, so landing here twice
  // without an intervening remount (App.jsx's screen key unchanged) needs this to actually reset.
  useEffect(() => {
    setTab(initialFilter === "overdue" ? "overdue" : "all");
  }, [initialFilter]);
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState(null);
  const [terms, setTerms] = useState({}); // work_order_id -> client's payment terms text
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [loadFailed, setLoadFailed] = useState(false);

  const canEdit = ["pm", "director"].includes(role);

  function load() {
    return listPayments(token).then(setRows);
  }

  useEffect(() => {
    load()
      .catch((err) => {
        setError(err.message);
        setLoadFailed(true);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // The client's payment terms are shown beside "Add milestone" as a reminder
  // only. The list row does not carry them, so look them up when a row opens
  // (writers only -- CA/Tax cannot add milestones and cannot read clients).
  async function toggleRow(row) {
    if (expandedId === row.work_order_id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(row.work_order_id);
    if (!canEdit || terms[row.work_order_id] !== undefined) return;
    try {
      const project = await getProject(token, row.project_id);
      const clients = await listClients(token);
      const client = clients.find((c) => c.id === project.client_id);
      setTerms((t) => ({ ...t, [row.work_order_id]: client?.payment_terms || null }));
    } catch {
      setTerms((t) => ({ ...t, [row.work_order_id]: null }));
    }
  }

  const needle = search.trim().toLowerCase();
  const searched = needle
    ? rows.filter((r) => r.project_no.toLowerCase().includes(needle) || r.client_name.toLowerCase().includes(needle))
    : rows;
  const overdueRows = searched.filter((r) => r.overdue);
  const visible = tab === "overdue" ? overdueRows : searched;
  const tabCount = { all: searched.length, overdue: overdueRows.length };

  const sum = (field) => visible.reduce((total, r) => total + r[field], 0);
  const cards = [
    ["Order value", sum("order_value")],
    ["Received", sum("total_received")],
    ["TDS withheld", sum("total_tds")],
    ["Outstanding", sum("outstanding")],
    ["Overdue", sum("overdue_amount")],
  ];

  if (loading) return <p className="text-center text-text-secondary mt-10">Loading payments…</p>;

  return (
    <div className="max-w-[1000px] mx-auto mt-6 mb-10 space-y-4 px-4 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-text-secondary">NestaPrime / Customer Relationships</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1 flex items-center gap-2">
            <CalendarIcon className="w-6 h-6 text-gold" /> Payments
          </h2>
          <p className="text-sm text-text-secondary mt-1">
            Track Work Order values, receipts and outstanding balances.
            {!canEdit && " You have read-only access."}
          </p>
        </div>
        {onBack && (
          <button onClick={onBack} className="text-xs uppercase tracking-wider text-gold hover:text-gold-hover shrink-0">
            ← Back
          </button>
        )}
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {cards.map(([label, value]) => {
          const style = CARD_STYLE[label];
          return (
            <div key={label} className="bg-surface border border-border-dark rounded-lg px-4 py-3 flex items-center gap-3">
              <span className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${style.tone}`}>
                <style.icon className="w-4 h-4" />
              </span>
              <div className="min-w-0">
                <p className="text-[10px] uppercase tracking-wide text-text-secondary truncate">{label}</p>
                <p className={`text-base font-heading font-bold ${label === "Overdue" && value > 0 ? "text-red-400" : "text-text-primary"}`}>
                  {formatRs(value)}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex items-start gap-2 bg-gold/5 border border-gold/20 rounded-lg px-4 py-3 text-sm text-text-secondary">
        <span className="text-gold shrink-0">ℹ</span>
        <span>Amounts and due dates reflect your team&apos;s entries. No estimated values.</span>
      </div>

      <div className="flex items-center gap-5 border-b border-border-dark">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`text-sm pb-2.5 border-b-2 whitespace-nowrap transition-colors duration-200 ${
              tab === t.key
                ? "text-gold border-gold font-medium"
                : "text-text-secondary border-transparent hover:text-text-primary"
            }`}
          >
            {t.label} <span className="text-xs text-text-secondary">({tabCount[t.key]})</span>
          </button>
        ))}
      </div>

      <input
        id="payments-search"
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search by project or client"
        aria-label="Search payments"
        className="w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
      />

      <div className="space-y-3">
        {visible.map((r) => (
          <div key={r.work_order_id} className="bg-surface border border-border-dark rounded-lg px-4 py-3 text-sm space-y-2">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <span className="min-w-0 break-words">
                {onOpenProject ? (
                  <button onClick={() => onOpenProject(r.project_id)} className="font-mono text-gold hover:underline">
                    {r.project_no}
                  </button>
                ) : (
                  <span className="font-mono">{r.project_no}</span>
                )}{" "}
                <span className="font-medium text-text-primary">{r.client_name}</span>
              </span>
              <span className="flex items-center gap-2 shrink-0">
                {r.overdue && (
                  <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-red-500/10 text-red-400">
                    Overdue
                  </span>
                )}
                <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-surface-raised text-text-secondary">
                  {WO_STATUS_LABEL[r.work_order_status] || r.work_order_status}
                </span>
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1 text-xs">
              {[
                ["Order value", r.order_value],
                ["Received", r.total_received],
                ["TDS withheld", r.total_tds],
                ["Outstanding", r.outstanding],
              ].map(([label, value]) => (
                <p key={label} className="text-text-secondary">
                  {label} <span className="block text-sm text-text-primary">{formatRs(value)}</span>
                </p>
              ))}
            </div>

            <p className={`text-xs ${r.overdue ? "text-red-400" : "text-text-secondary"}`}>
              {r.milestone_count === 0
                ? "No expected payments set -- nothing can be overdue until a milestone has a due date."
                : `${r.milestone_count} milestone${r.milestone_count === 1 ? "" : "s"}` +
                  (r.next_due_date ? ` · next due ${r.next_due_date}` : " · all paid") +
                  (r.overdue ? ` · ${formatRs(r.overdue_amount)} overdue` : "")}
              {r.over_received && " · received more than the order value"}
            </p>

            <button onClick={() => toggleRow(r)} className="text-xs text-gold hover:underline">
              {expandedId === r.work_order_id ? "▾ Hide milestones & payments" : "▸ Milestones & payments"}
            </button>

            {expandedId === r.work_order_id && (
              <div className="border-t border-border-dark pt-3">
                <PaymentsDetail
                  token={token}
                  workOrderId={r.work_order_id}
                  canEdit={canEdit}
                  paymentTerms={terms[r.work_order_id]}
                  onChanged={load}
                  idPrefix={`wo-${r.work_order_id}`}
                  showSummary={false}
                />
              </div>
            )}
          </div>
        ))}
        {visible.length === 0 && !loadFailed && (needle || tab === "overdue") && (
          <p className="text-sm text-text-secondary bg-surface border border-border-dark rounded-lg p-5">
            {needle
              ? "Nothing matches that search."
              : "No Work Order has an unpaid milestone past its due date. (A Work Order with no milestones has no due dates to be overdue against.)"}
          </p>
        )}
        {visible.length === 0 && !loadFailed && !needle && tab === "all" && (
          <div className="bg-surface border border-border-dark rounded-lg p-10 text-center space-y-4">
            <div className="mx-auto w-16 h-16 rounded-full bg-gold/10 flex items-center justify-center relative">
              <DocumentIcon className="w-8 h-8 text-gold" />
              <span className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-gold flex items-center justify-center">
                <RupeeIcon className="w-3.5 h-3.5 text-base" />
              </span>
            </div>
            <div>
              <p className="text-text-primary font-heading font-bold text-lg">No Work Orders yet.</p>
              <p className="text-sm text-text-secondary mt-1">
                Create a Work Order from a Won quotation on the project&apos;s Documents screen.
              </p>
            </div>
            {onOpenProjects && (
              <button
                onClick={onOpenProjects}
                className="bg-gold text-base text-sm rounded px-5 py-2.5 font-semibold hover:bg-gold-hover"
              >
                View projects →
              </button>
            )}

            <div className="border-t border-border-dark pt-6 mt-6 grid sm:grid-cols-3 gap-6 text-left">
              <p className="sm:col-span-3 text-sm font-semibold text-text-primary text-center -mt-2 mb-1">
                Start tracking payments
              </p>
              {[
                { n: 1, title: "Open your project", body: "Go to the project where you have a Won quotation." },
                { n: 2, title: "Go to Documents", body: "Open the project's Documents screen." },
                { n: 3, title: "Create a Work Order", body: "Create a Work Order from a Won quotation." },
              ].map((step) => (
                <div key={step.n} className="flex items-start gap-3">
                  <span className="w-7 h-7 rounded-full border border-gold/50 text-gold text-xs font-semibold flex items-center justify-center shrink-0">
                    {step.n}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-text-primary">{step.title}</p>
                    <p className="text-xs text-text-secondary mt-0.5">{step.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
