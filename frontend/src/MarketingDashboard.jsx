import { useEffect, useState } from "react";
import { getMarketingDashboard } from "./api";

// P3 contract (revision 4), Section 9: Phase A's aggregate-only dashboard -- counts by source, QUERY_TYPE and
// date bucket, plus a CURRENT-STAGE SNAPSHOT of the Opportunities imported in the selected period (that count is
// the explicit denominator). Not a historical conversion funnel (that would need stage-change history from
// audit_log, not built). Counts and rates only -- never individual buyer fields, never raw payload.
//
// Choices the contract leaves open are explicit here and echoed by the API: which date defines the cohort, the
// bucket size, and the calendar (IST days).

// Today's date as an IST calendar date (YYYY-MM-DD) -- the dashboard's calendar -- not the browser's UTC date.
function istDate(offsetDays = 0) {
  const d = new Date(Date.now() + offsetDays * 86400000);
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(d);
}

const STAGE_LABELS = { new: "New", contacted: "Contacted", qualified: "Qualified", won: "Won", lost: "Lost" };
const BASIS_LABELS = {
  enquiry_time: "Enquiry date (when the buyer enquired)",
  received_at: "Import date (when we received the lead)",
};
const BUCKET_LABELS = { day: "Day", week: "Week (Mon-Sun)", month: "Month" };

function Section({ title, children }) {
  return (
    <div className="bg-surface shadow rounded-lg p-6 space-y-2">
      <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
      {children}
    </div>
  );
}

function CountRows({ entries, empty }) {
  if (entries.length === 0) return <p className="text-sm text-text-secondary">{empty}</p>;
  return entries.map(([label, count]) => (
    <div key={label} className="flex items-center justify-between text-sm border-b border-border-dark last:border-0 py-1.5">
      <span className="text-text-secondary">{label}</span>
      <span className="text-text-primary font-medium">{count}</span>
    </div>
  ));
}

export default function MarketingDashboard({ token }) {
  const [periodStart, setPeriodStart] = useState(istDate(-30));
  const [periodEnd, setPeriodEnd] = useState(istDate(0));
  const [basis, setBasis] = useState("enquiry_time");
  const [bucket, setBucket] = useState("day");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    if (periodEnd < periodStart) {
      setError("The end date must not be before the start date.");
      return;
    }
    setLoading(true);
    setError("");
    getMarketingDashboard(token, { periodStart, periodEnd, basis, bucket })
      .then(setData)
      .catch((err) => {
        setData(null);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const maxBucket = data ? Math.max(1, ...data.by_date_bucket.map((b) => b.count)) : 1;
  const fieldClass = "block mt-1 bg-surface-raised border border-border-dark rounded px-2 py-1 text-sm";

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6 space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">Marketing -- IndiaMART leads</h2>
          <p className="text-sm text-text-secondary">
            Leads for the selected period, grouped by the date you choose, and where the Opportunities they produced are
            sitting <em>today</em>. This is a snapshot of current stages, not a historical conversion rate over time.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-text-secondary">
            From
            <input type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} className={fieldClass} />
          </label>
          <label className="text-xs text-text-secondary">
            To
            <input type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} className={fieldClass} />
          </label>
          <label className="text-xs text-text-secondary">
            Group leads by
            <select value={basis} onChange={(e) => setBasis(e.target.value)} className={fieldClass}>
              {Object.entries(BASIS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label className="text-xs text-text-secondary">
            Bucket
            <select value={bucket} onChange={(e) => setBucket(e.target.value)} className={fieldClass}>
              {Object.entries(BUCKET_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <button onClick={load} className="text-xs rounded px-3 py-1.5 bg-gold text-base font-medium hover:bg-gold/90">
            Refresh
          </button>
        </div>
        {error && <p className="text-sm text-red-400" role="alert">{error}</p>}
      </div>

      {loading && <p className="text-sm text-text-secondary">Loading…</p>}

      {!loading && data && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-surface shadow rounded-lg p-6">
              <p className="text-[10px] uppercase tracking-wider text-text-secondary/70">Leads received</p>
              <p className="text-2xl font-heading font-semibold text-text-primary mt-1" data-testid="received-total">
                {data.received_total}
              </p>
              <p className="text-xs text-text-secondary mt-1">Every lead in the period, whatever its status.</p>
            </div>
            <div className="bg-surface shadow rounded-lg p-6">
              <p className="text-[10px] uppercase tracking-wider text-text-secondary/70">Opportunities imported</p>
              <p className="text-2xl font-heading font-semibold text-text-primary mt-1" data-testid="imported-total">
                {data.imported_total}
              </p>
              <p className="text-xs text-text-secondary mt-1">The denominator for the stage percentages below.</p>
            </div>
          </div>
          <p className="text-xs text-text-secondary">
            Grouped by {BASIS_LABELS[data.cohort_basis] || data.cohort_basis}. {data.timezone}.
            {data.excluded_missing_enquiry_time > 0 &&
              ` ${data.excluded_missing_enquiry_time} lead${data.excluded_missing_enquiry_time === 1 ? "" : "s"} received in this period ${
                data.excluded_missing_enquiry_time === 1 ? "has" : "have"
              } no enquiry date and ${data.excluded_missing_enquiry_time === 1 ? "is" : "are"} not counted here; group by import date to include ${
                data.excluded_missing_enquiry_time === 1 ? "it" : "them"
              }.`}
          </p>

          <Section title="By source">
            <CountRows entries={Object.entries(data.by_source)} empty="No leads in this period." />
          </Section>

          <Section title="By enquiry type">
            <CountRows entries={Object.entries(data.by_query_type)} empty="No enquiries in this period." />
            {data.by_query_type.unknown > 0 && (
              <p className="text-xs text-text-secondary">
                "unknown" are leads whose type has not been recorded yet (not processed, or the type was missing).
              </p>
            )}
          </Section>

          <Section title={`By ${bucket}`}>
            {data.received_total === 0 ? (
              <p className="text-sm text-text-secondary">No leads in this period.</p>
            ) : (
              <div className="max-h-72 overflow-y-auto space-y-1" data-testid="bucket-rows">
                {data.by_date_bucket.map((b) => (
                  <div key={b.bucket_start} className="flex items-center gap-3 text-xs">
                    <span className="w-28 shrink-0 text-text-secondary">{b.label}</span>
                    <div className="flex-1 h-3 bg-surface-raised rounded overflow-hidden">
                      <div className="h-3 bg-gold/70" style={{ width: `${(b.count / maxBucket) * 100}%` }} />
                    </div>
                    <span className="w-8 text-right text-text-primary font-medium">{b.count}</span>
                  </div>
                ))}
              </div>
            )}
          </Section>

          <Section title="Current stage (as of today)">
            {data.current_stage_distribution.length === 0 ? (
              <p className="text-sm text-text-secondary">No Opportunities were imported in this period.</p>
            ) : (
              <>
                {data.current_stage_distribution.map((s) => (
                  <div
                    key={s.stage}
                    className="flex items-center justify-between text-sm border-b border-border-dark last:border-0 py-1.5"
                  >
                    <span className="text-text-secondary">{STAGE_LABELS[s.stage] || s.stage}</span>
                    <span className="text-text-primary font-medium">
                      {s.count} ({Math.round(s.rate * 100)}%)
                    </span>
                  </div>
                ))}
                <p className="text-xs text-text-secondary">Percentages are of the {data.imported_total} Opportunities imported.</p>
              </>
            )}
          </Section>
        </>
      )}
    </div>
  );
}
