import { CalendarIcon } from "./Icons";
import { formatRs, formatRsWhole } from "./money";

// Amendment 50 Part C (Section 54): the Overview's payments tile and panel, for
// the roles that can open the Payments header. The API sends `payments` only to
// pm / director / ca_tax (everyone else gets null and the Overview shows neither
// -- not a "Coming soon"). Every figure is derived by the API from milestones
// and receipts a person entered; nothing here is estimated.

export function PaymentsOverdueTile({ payments, onOpen }) {
  const tracked = payments.tracked_milestones_count > 0;
  const overdueWord = payments.overdue_count === 1 ? "Work Order" : "Work Orders";
  return (
    <button
      onClick={onOpen}
      className="text-left bg-surface border border-border-dark rounded-lg p-5 hover:border-gold hover:-translate-y-0.5 transition-all duration-250 ease-out"
    >
      <p className="text-xs uppercase tracking-wide text-text-secondary flex items-center gap-1.5">
        <CalendarIcon className="w-3.5 h-3.5" />
        Payments overdue
      </p>
      {/* "--", never 0, until someone has entered a due date: a zero would read as
          "nothing is late" when really nothing is being tracked. */}
      <p
        className={`text-xl font-heading font-bold mt-2 break-words ${
          tracked && payments.overdue_amount > 0 ? "text-red-400" : "text-text-primary"
        }`}
      >
        {tracked ? formatRsWhole(payments.overdue_amount) : "--"}
      </p>
      <p className="text-xs text-text-secondary mt-1">
        {!tracked
          ? "No due dates set"
          : payments.overdue_count > 0
            ? `${payments.overdue_count} ${overdueWord} overdue`
            : "Nothing overdue"}
      </p>
    </button>
  );
}

function monthLabel(key) {
  const [year, month] = key.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleString("en-IN", { month: "short", year: "2-digit" });
}

export function CollectionsPanel({ payments, onOpen }) {
  const { months } = payments;
  const max = Math.max(...months.flatMap((m) => [m.awarded_value, m.cash_received]), 0);
  const totals = [
    ["Awarded Work Orders", payments.awarded_value_total],
    ["Cash received", payments.cash_received_total],
    ["TDS withheld", payments.tds_total],
    ["Outstanding", payments.outstanding_total],
  ];
  return (
    <div className="bg-surface border border-border-dark rounded-lg p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-heading font-semibold text-text-primary text-base">Orders &amp; collections</h3>
        <button onClick={onOpen} className="text-xs uppercase tracking-wider text-gold hover:text-gold-hover">
          View all →
        </button>
      </div>
      {payments.work_orders_count === 0 ? (
        <p className="text-sm text-text-secondary">
          No Work Orders yet -- a Work Order is created from a Won quotation on the project&apos;s Documents screen.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2 mb-4">
            {totals.map(([label, value]) => (
              <p key={label} className="text-xs text-text-secondary min-w-0">
                {label}
                <span className="block text-sm text-text-primary break-words">{formatRs(value)}</span>
              </p>
            ))}
          </div>
          {max === 0 ? (
            <p className="text-sm text-text-secondary">Nothing awarded or received in the last six months.</p>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-4 text-[11px] text-text-secondary mb-2">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-sm bg-gold" /> Awarded Work Orders
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-sm bg-green-500" /> Cash received
                </span>
              </div>
              <ul className="space-y-2">
                {months.map((m) => (
                  <li key={m.month} className="flex items-center gap-3">
                    <span className="w-14 shrink-0 text-xs text-text-secondary">{monthLabel(m.month)}</span>
                    <div className="flex-1 min-w-0 space-y-1">
                      <div
                        className="h-2 rounded-sm bg-gold"
                        style={{ width: `${(m.awarded_value / max) * 100}%` }}
                        title={`Awarded ${formatRs(m.awarded_value)}`}
                      />
                      <div
                        className="h-2 rounded-sm bg-green-500"
                        style={{ width: `${(m.cash_received / max) * 100}%` }}
                        title={`Received ${formatRs(m.cash_received)}`}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
          <p className="text-[11px] text-text-secondary mt-3">
            Work Orders are counted by award date and cash by the date it was received. A Won quotation with no Work
            Order yet is not counted.
          </p>
        </>
      )}
    </div>
  );
}
