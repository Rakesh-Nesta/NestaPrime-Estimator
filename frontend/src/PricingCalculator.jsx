import { useEffect, useState } from "react";
import { listMarginPolicies, priceQuote } from "./api";

const CLIENT_TYPES = [
  ["school", "School"],
  ["college", "College"],
  ["housing_society", "Housing Society"],
  ["corporate", "Corporate"],
  ["club", "Club"],
  ["government", "Government (Tender)"],
  ["individual", "Individual"],
];

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
    return <p className="text-center text-gray-500 mt-10">Loading pricing…</p>;
  }

  return (
    <div className="max-w-xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Pricing Calculator</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-blue-600 hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-gray-400 mt-1">
          K.1 steps 7-12: Selling = Cost / (1 - target margin); GST is a flat 18% on the
          subtotal after discount (K.4). Cost, contingency, markup and margin are PM/Director
          only (K.3) — Sales never sees this screen.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white shadow rounded-lg p-6 space-y-3">
        <div>
          <label className="block text-sm font-medium text-gray-700">Cost incl. contingency (Rs)</label>
          <input
            type="number"
            required
            value={cost}
            onChange={(e) => setCost(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Client type</label>
          <select
            value={clientType}
            onChange={(e) => setClientType(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
          >
            {CLIENT_TYPES.map(([val, label]) => (
              <option key={val} value={val}>{label}</option>
            ))}
          </select>
          {policy && (
            <p className="text-xs text-gray-400 mt-1">
              Floor {policy.floor_margin_percent}% · Target {policy.target_margin_percent}%
            </p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700">Discount</label>
            <select
              value={discountType}
              onChange={(e) => setDiscountType(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="none">None</option>
              <option value="percent">Percent</option>
              <option value="amount">Amount (Rs)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Value</label>
            <input
              type="number"
              disabled={discountType === "none"}
              value={discountValue}
              onChange={(e) => setDiscountValue(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-50"
            />
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          className="w-full bg-blue-600 text-white rounded py-2 text-sm font-medium hover:bg-blue-700"
        >
          Calculate
        </button>
      </form>

      {result && (
        <div className="bg-white shadow rounded-lg p-6 space-y-2 text-sm">
          <Row label="Cost incl. contingency" value={result.cost_incl_contingency} />
          <Row label="Target margin" value={`${result.target_margin_percent}%`} />
          <Row label="Selling price (ex-GST)" value={result.selling_price_ex_gst} />
          <Row label="Discount" value={result.discount_amount} />
          <Row label="Selling after discount" value={result.selling_after_discount} bold />
          <Row label="Margin %" value={`${result.margin_percent.toFixed(2)}%`} />
          <Row label="Markup %" value={`${result.markup_percent.toFixed(2)}%`} />
          {result.below_floor && (
            <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">
              Below floor margin ({result.floor_margin_percent}%) — Director approval required (K.1 step 10)
            </p>
          )}
          <Row label={`GST (${result.gst_rate_percent}% flat)`} value={result.gst_amount} />
          <Row label="Quotation total" value={result.quotation_total} bold big />
        </div>
      )}
    </div>
  );
}

function Row({ label, value, bold, big }) {
  const formatted = typeof value === "number" ? `Rs ${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : value;
  return (
    <div className={`flex items-center justify-between ${bold ? "font-semibold" : ""} ${big ? "text-base" : ""}`}>
      <span className="text-gray-600">{label}</span>
      <span>{formatted}</span>
    </div>
  );
}
