import { useEffect, useState } from "react";
import { getMarketingDashboard } from "./api";

// P3 contract (revision 4), Section 9: Phase A's aggregate-only dashboard -- a CURRENT-STAGE
// SNAPSHOT grouped by import cohort, not a true historical conversion funnel (that would need
// Opportunity stage-change history from audit_log, not built this release). Counts and rates
// only -- never individual buyer fields, never raw payload, never full Opportunity rows.

function isoDate(d) {
  return d.toISOString().slice(0, 10);
}

const STAGE_LABELS = { new: "New", contacted: "Contacted", qualified: "Qualified", won: "Won", lost: "Lost" };

export default function MarketingDashboard({ token }) {
  const today = new Date();
  const monthAgo = new Date(today);
  monthAgo.setDate(monthAgo.getDate() - 30);

  const [periodStart, setPeriodStart] = useState(isoDate(monthAgo));
  const [periodEnd, setPeriodEnd] = useState(isoDate(today));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    setLoading(true);
    setError("");
    getMarketingDashboard(token, { periodStart, periodEnd })
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6 space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">Marketing -- IndiaMART leads</h2>
          <p className="text-sm text-text-secondary">
            Current-stage snapshot for leads imported in the selected period, by their own enquiry date. Not a
            historical conversion rate over time -- that would need a separate, not-yet-built report.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-text-secondary">
            From
            <input
              type="date"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              className="block mt-1 bg-surface-raised border border-border-dark rounded px-2 py-1 text-sm"
            />
          </label>
          <label className="text-xs text-text-secondary">
            To
            <input
              type="date"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              className="block mt-1 bg-surface-raised border border-border-dark rounded px-2 py-1 text-sm"
            />
          </label>
          <button
            onClick={load}
            className="text-xs rounded px-3 py-1.5 bg-gold text-base font-medium hover:bg-gold/90"
          >
            Refresh
          </button>
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
      </div>

      {loading && <p className="text-sm text-text-secondary">Loading…</p>}

      {!loading && data && (
        <>
          <div className="bg-surface shadow rounded-lg p-6">
            <p className="text-[10px] uppercase tracking-wider text-text-secondary/70">Imported in period</p>
            <p className="text-2xl font-heading font-semibold text-text-primary mt-1">{data.imported_total}</p>
          </div>

          <div className="bg-surface shadow rounded-lg p-6 space-y-2">
            <h3 className="text-sm font-semibold text-text-primary">By enquiry type</h3>
            {Object.keys(data.by_query_type).length === 0 && (
              <p className="text-sm text-text-secondary">No enquiries in this period.</p>
            )}
            {Object.entries(data.by_query_type).map(([type, count]) => (
              <div key={type} className="flex items-center justify-between text-sm border-b border-border-dark last:border-0 py-1.5">
                <span className="text-text-secondary">{type}</span>
                <span className="text-text-primary font-medium">{count}</span>
              </div>
            ))}
          </div>

          <div className="bg-surface shadow rounded-lg p-6 space-y-2">
            <h3 className="text-sm font-semibold text-text-primary">Current stage (as of today)</h3>
            {data.current_stage_distribution.length === 0 && (
              <p className="text-sm text-text-secondary">No linked Opportunities in this period yet.</p>
            )}
            {data.current_stage_distribution.map((s) => (
              <div key={s.stage} className="flex items-center justify-between text-sm border-b border-border-dark last:border-0 py-1.5">
                <span className="text-text-secondary">{STAGE_LABELS[s.stage] || s.stage}</span>
                <span className="text-text-primary font-medium">
                  {s.count}
                  {data.imported_total > 0 ? ` (${Math.round((s.count / data.imported_total) * 100)}%)` : ""}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
