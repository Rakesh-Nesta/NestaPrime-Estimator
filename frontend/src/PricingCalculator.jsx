import { useEffect, useState } from "react";
import { listMarginPolicies, priceQuote } from "./api";
import { CalculatorIcon, DocumentIcon, LockIcon, TargetIcon } from "./Icons";

const CLIENT_TYPES = [
  ["school", "School"],
  ["college", "College"],
  ["housing_society", "Housing Society"],
  ["corporate", "Corporate"],
  ["club", "Club"],
  ["government", "Government (Tender)"],
  ["individual", "Individual"],
];

const RULES = [
  {
    icon: CalculatorIcon,
    title: "1. Selling price formula",
    body: "Selling price = Cost ÷ (1 − target margin)",
  },
  {
    icon: DocumentIcon,
    title: "2. GST on subtotal",
    body: "GST is configured at 18% on the subtotal after discount.",
  },
  {
    icon: LockIcon,
    title: "3. Access restriction",
    body: "Cost and margin information is restricted to PM and Director. This application's displayed configuration, not a claim of universal tax law.",
  },
];

// Redesign (2026-09-27, Director's request): same screen, same data and the same server call -- a
// two-column layout (inputs beside a live breakdown, instead of the breakdown appearing below the form)
// plus a "Pricing rules" explainer row. Sidebar and header are untouched; only this screen's own content
// changed.
export default function PricingCalculator({ token, onBack }) {
  const [policies, setPolicies] = useState([]);
  const [cost, setCost] = useState("");
  const [clientType, setClientType] = useState("school");
  const [discountType, setDiscountType] = useState("none");
  const [discountValue, setDiscountValue] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listMarginPolicies(token)
      .then(setPolicies)
      .finally(() => setLoading(false));
  }, [token]);

  const policy = policies.find((p) => p.client_type === clientType);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    try {
      const body = {
        cost_incl_contingency: Number(cost),
        client_type: clientType,
      };
      if (discountType !== "none" && discountValue) {
        body.discount_type = discountType;
        body.discount_value = Number(discountValue);
      }
      const res = await priceQuote(token, body);
      setResult(res);
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading pricing…</p>;
  }

  const inputClass = "mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm";

  return (
    <div className="max-w-[1400px] mx-auto mt-6 mb-10 px-4 sm:px-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-text-secondary">Workspace / Tools &amp; Reports</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1 flex items-center gap-3 flex-wrap">
            Pricing Calculator
            <span className="text-[10px] uppercase tracking-wider bg-gold/10 border border-gold/40 text-gold rounded-full px-2.5 py-1 font-semibold">
              <LockIcon className="w-3 h-3 inline -mt-0.5 mr-1" /> PM &amp; Director only
            </span>
          </h2>
          <p className="text-sm text-text-secondary mt-1">Calculate selling prices using your configured margins and discounts.</p>
        </div>
        {onBack && (
          <button onClick={onBack} className="text-xs uppercase tracking-wider text-gold hover:text-gold-hover shrink-0">
            ← Back
          </button>
        )}
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        <form onSubmit={handleSubmit} className="bg-surface border border-border-dark rounded-lg p-5 space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">Pricing inputs</h3>
            <p className="text-xs text-text-secondary mt-0.5">Enter cost and client details to calculate the selling price.</p>
          </div>

          <div>
            <label className="block text-xs font-medium text-text-secondary">Cost including contingency (Rs)</label>
            <input
              type="number"
              required
              placeholder="Enter cost"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
              className={inputClass}
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-text-secondary">Client type</label>
            <select value={clientType} onChange={(e) => setClientType(e.target.value)} className={inputClass}>
              {CLIENT_TYPES.map(([val, label]) => (
                <option key={val} value={val}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          {policy && (
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-surface-raised border border-border-dark rounded-lg px-3 py-2.5">
                <p className="text-[10px] uppercase tracking-wide text-text-secondary flex items-center gap-1.5">
                  <CalculatorIcon className="w-3.5 h-3.5" /> Floor margin
                </p>
                <p className="text-lg font-heading font-bold text-gold mt-0.5">{policy.floor_margin_percent}%</p>
              </div>
              <div className="bg-surface-raised border border-border-dark rounded-lg px-3 py-2.5">
                <p className="text-[10px] uppercase tracking-wide text-text-secondary flex items-center gap-1.5">
                  <TargetIcon className="w-3.5 h-3.5" /> Target margin
                </p>
                <p className="text-lg font-heading font-bold text-gold mt-0.5">{policy.target_margin_percent}%</p>
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-text-secondary">Discount</label>
              <select value={discountType} onChange={(e) => setDiscountType(e.target.value)} className={inputClass}>
                <option value="none">None</option>
                <option value="percent">Percent</option>
                <option value="amount">Amount (Rs)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-text-secondary">Discount value</label>
              <input
                type="number"
                disabled={discountType === "none"}
                value={discountValue}
                onChange={(e) => setDiscountValue(e.target.value)}
                className={`${inputClass} disabled:opacity-50`}
              />
            </div>
          </div>
          <p className="text-xs text-text-secondary -mt-2">
            {discountType === "none" ? "No discount applied." : "Applied to the selling price before GST."}
          </p>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <button type="submit" className="w-full bg-gold text-base rounded py-2.5 text-sm font-semibold hover:bg-gold-hover">
            Calculate price
          </button>
        </form>

        <div className="bg-surface border border-border-dark rounded-lg p-5">
          <h3 className="text-sm font-semibold text-text-primary">Price breakdown</h3>
          <p className="text-xs text-text-secondary mt-0.5 mb-4">See the detailed calculation below.</p>

          {!result ? (
            <div className="text-center py-8 space-y-3">
              <div className="mx-auto w-16 h-16 rounded-lg border-2 border-gold/30 flex items-center justify-center">
                <CalculatorIcon className="w-8 h-8 text-gold" />
              </div>
              <p className="text-text-primary font-heading font-semibold">Ready to calculate</p>
              <p className="text-sm text-text-secondary">Enter a cost and select Calculate price to view the breakdown.</p>
            </div>
          ) : (
            <div className="space-y-2 text-sm">
              <Row label="Selling price before discount" value={result.selling_price_ex_gst} />
              <Row label="Discount" value={result.discount_amount} />
              <Row label="Subtotal after discount" value={result.selling_after_discount} />
              <Row label={`GST (${result.gst_rate_percent}%)`} value={result.gst_amount} />
              {result.below_floor && (
                <p className="text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1.5">
                  Below floor margin ({result.floor_margin_percent}%) -- Director approval required (K.1 step 10)
                </p>
              )}
              <div className="border-t border-border-dark pt-2 flex items-center justify-between">
                <span className="text-text-primary font-semibold">Total including GST</span>
                <span className="text-xl font-heading font-bold text-gold">
                  Rs {result.quotation_total.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              </div>
              <p className="text-[11px] text-text-secondary/70 pt-1">
                Target margin {result.target_margin_percent}% · Margin {result.margin_percent.toFixed(2)}% · Markup{" "}
                {result.markup_percent.toFixed(2)}%
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="bg-surface border border-border-dark rounded-lg p-5">
        <h3 className="text-sm font-semibold text-text-primary mb-1">Pricing rules</h3>
        <p className="text-xs text-text-secondary mb-4">This is your application&apos;s configured pricing logic.</p>
        <div className="grid sm:grid-cols-3 gap-4">
          {RULES.map((rule) => (
            <div key={rule.title} className="bg-surface-raised border border-border-dark rounded-lg p-4">
              <span className="w-9 h-9 rounded-full bg-gold/10 text-gold flex items-center justify-center mb-2">
                <rule.icon className="w-4 h-4" />
              </span>
              <p className="text-sm font-medium text-text-primary">{rule.title}</p>
              <p className="text-xs text-text-secondary mt-1">{rule.body}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }) {
  const formatted = typeof value === "number" ? `Rs ${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : value;
  return (
    <div className="flex items-center justify-between">
      <span className="text-text-secondary">{label}</span>
      <span className="text-text-primary">{formatted}</span>
    </div>
  );
}
