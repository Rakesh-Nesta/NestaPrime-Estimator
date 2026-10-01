import { useEffect, useState } from "react";
import { getProjectOverview } from "./api";

const WAITING_LABELS = { us: "Waiting on us", client: "Waiting on client", vendor: "Waiting on vendor" };
const WAITING_COLORS = {
  us: "bg-amber-500/10 text-amber-400",
  client: "bg-blue-500/10 text-blue-400",
  vendor: "bg-purple-500/10 text-purple-400",
};
const WAITING_ORDER = ["us", "client", "vendor"];

const PHASE_LABELS = { presales: "Pre-sales", confirmed: "Confirmed", abandoned: "Abandoned" };
const PHASE_COLORS = {
  presales: "bg-surface-raised text-text-secondary",
  confirmed: "bg-green-500/10 text-green-400",
  abandoned: "bg-red-500/10 text-red-400",
};

function screenNavigator({ onOpenDocuments, onOpenScope, onOpenSiteSurvey, onOpenFollowUps }) {
  return {
    documents: onOpenDocuments,
    scope: onOpenScope,
    site_survey: onOpenSiteSurvey,
    follow_ups: onOpenFollowUps,
  };
}

function PendingItemRow({ item, navigators }) {
  const go = navigators[item.screen];
  return (
    <div className="flex items-center justify-between gap-3 border border-border-dark rounded px-3 py-2 text-sm">
      <div className="min-w-0">
        <p className="text-text-primary truncate">{item.label}</p>
        {item.due_date && <p className="text-xs text-text-secondary">Due {item.due_date}</p>}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className={`text-xs rounded px-1.5 py-0.5 ${WAITING_COLORS[item.waiting_on] ?? "bg-surface-raised text-text-secondary"}`}>
          {WAITING_LABELS[item.waiting_on] ?? item.waiting_on}
        </span>
        {go && (
          <button onClick={go} className="text-xs text-gold hover:underline">
            Open &rarr;
          </button>
        )}
      </div>
    </div>
  );
}

const STAGE_EVIDENCE_ROLES = ["site_engineer", "pm", "director"];

export default function ProjectOverview({
  token, project, role, onOpenSports, onOpenScope, onOpenSiteSurvey, onOpenDocuments, onOpenFollowUps, onOpenStages,
}) {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    getProjectOverview(token, project.id)
      .then(setOverview)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token, project.id]);

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading overview…</p>;
  }
  if (error) {
    return <p className="max-w-3xl mx-auto mt-8 text-sm text-red-400">{error}</p>;
  }
  if (!overview) return null;

  const navigators = screenNavigator({ onOpenDocuments, onOpenScope, onOpenSiteSurvey, onOpenFollowUps });
  const itemsByWaiting = WAITING_ORDER.map((key) => ({
    key, items: overview.pending_items.filter((i) => i.waiting_on === key),
  })).filter((g) => g.items.length > 0);

  const readinessBlocking = overview.readiness
    ? [
        ...(!overview.readiness.client_identity_passed
          ? [{ key: "client_identity", label: `Missing client identity: ${overview.readiness.client_identity_missing.join(", ")}`, waivable: false }]
          : []),
        ...overview.readiness.checks.filter((c) => !c.passed),
      ]
    : [];

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Overview</h2>
            <p className="text-sm text-text-secondary">
              Project <span className="font-mono">{overview.project_no}</span> &middot; {overview.client_name} &middot; {overview.city}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs rounded px-2 py-1 ${PHASE_COLORS[overview.phase] ?? "bg-surface-raised text-text-secondary"}`}>
              {PHASE_LABELS[overview.phase] ?? overview.phase}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-1 mt-3 text-xs text-text-secondary">
          <span>Owner: {overview.owner_name ?? "Unassigned"}</span>
          {overview.opportunity_stage && <span>Opportunity stage: {overview.opportunity_stage}</span>}
        </div>
      </div>

      <div className="bg-surface shadow rounded-lg p-6 space-y-2">
        <h3 className="text-sm font-semibold text-text-secondary">Latest activity</h3>
        {!overview.activity_visible ? (
          <p className="text-sm text-text-secondary italic">Restricted to Director/Admin (same as the Audit Log screen).</p>
        ) : overview.latest_activity.length === 0 ? (
          <p className="text-sm text-text-secondary">No recent activity logged for this project.</p>
        ) : (
          <div className="space-y-1.5 text-xs">
            {overview.latest_activity.map((a, i) => (
              <div key={i} className="flex justify-between gap-3 text-text-secondary">
                <span>
                  <span className="text-text-primary">{a.user_name}</span> changed {a.document_type} {a.field}
                  {a.reason ? ` -- ${a.reason}` : ""}
                </span>
                <span className="shrink-0">{new Date(a.timestamp).toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-surface shadow rounded-lg p-6 space-y-3">
        <h3 className="text-sm font-semibold text-text-secondary">Pending work</h3>
        {!overview.document_chain_visible && (
          <p className="text-xs text-text-secondary italic">
            Cost Sheet/Estimate/Quotation status isn't shown for your role (same as the Documents screen) -- only
            follow-ups you're entitled to see appear below.
          </p>
        )}
        {overview.pending_items.length === 0 && (
          <p className="text-sm text-text-secondary">Nothing pending -- this project is caught up.</p>
        )}
        {itemsByWaiting.map(({ key, items }) => (
          <div key={key} className="space-y-1.5">
            <p className="text-xs uppercase tracking-wide text-text-secondary">{WAITING_LABELS[key]}</p>
            {items.map((item, i) => (
              <PendingItemRow key={i} item={item} navigators={navigators} />
            ))}
          </div>
        ))}
      </div>

      <div className="bg-surface shadow rounded-lg p-6 space-y-2">
        <h3 className="text-sm font-semibold text-text-secondary">Readiness gaps</h3>
        {!overview.readiness_visible ? (
          <p className="text-sm text-text-secondary italic">Restricted to Sales/PM/Director (same as the Documents readiness check).</p>
        ) : readinessBlocking.length === 0 ? (
          <p className="text-sm text-green-400">All readiness requirements are met.</p>
        ) : (
          <>
            <div className="space-y-1.5 text-sm">
              {readinessBlocking.map((c) => (
                <div key={c.key} className="flex items-center justify-between gap-3">
                  <span>{c.label}</span>
                  <span className={`text-xs rounded px-1.5 py-0.5 ${c.waivable === false ? "bg-red-500/10 text-red-400" : "bg-amber-500/10 text-amber-400"}`}>
                    {c.waivable === false ? "Not waivable" : c.pending_exception ? "Exception pending" : "Waivable"}
                  </span>
                </div>
              ))}
            </div>
            <button onClick={onOpenDocuments} className="text-xs text-gold hover:underline">
              Go to Documents to resolve &rarr;
            </button>
          </>
        )}
      </div>

      <div className={`bg-surface shadow rounded-lg p-6 space-y-2 ${overview.payment_visible && overview.payment_blocker ? "border border-red-500/30" : ""}`}>
        <h3 className={`text-sm font-semibold ${overview.payment_visible && overview.payment_blocker ? "text-red-400" : "text-text-secondary"}`}>
          Payment blocker
        </h3>
        {!overview.payment_visible ? (
          <p className="text-sm text-text-secondary italic">Restricted to PM/Director/CA &amp; Tax (same as the Payments screen).</p>
        ) : !overview.payment_blocker ? (
          <p className="text-sm text-green-400">No overdue payments on this project.</p>
        ) : (
          <p className="text-sm text-text-secondary">
            Rs {overview.payment_blocker.overdue_amount.toLocaleString()} overdue on this Work Order &middot; outstanding
            Rs {overview.payment_blocker.outstanding.toLocaleString()} of Rs {overview.payment_blocker.order_value.toLocaleString()}
            {overview.payment_blocker.next_due_date && ` -- next due ${overview.payment_blocker.next_due_date}`}
          </p>
        )}
      </div>

      <div className="bg-surface shadow rounded-lg p-6 space-y-2">
        <h3 className="text-sm font-semibold text-text-secondary">Vendor / price-request blockers</h3>
        <p className="text-sm text-text-secondary italic">
          {overview.vendor_price_requests.available ? "None." : overview.vendor_price_requests.reason}
        </p>
      </div>

      <div className="flex flex-wrap gap-4 text-sm">
        <button onClick={onOpenSports} className="text-gold hover:underline">Sport &rarr;</button>
        <button onClick={onOpenScope} className="text-gold hover:underline">Scope &rarr;</button>
        <button onClick={onOpenSiteSurvey} className="text-gold hover:underline">Site Survey &rarr;</button>
        <button onClick={onOpenDocuments} className="text-gold hover:underline">Documents &rarr;</button>
        {STAGE_EVIDENCE_ROLES.includes(role) && (
          <button onClick={onOpenStages} className="text-gold hover:underline">Stage Evidence &rarr;</button>
        )}
      </div>
    </div>
  );
}
