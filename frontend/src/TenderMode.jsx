import { useEffect, useState } from "react";
import AttachmentsPanel from "./AttachmentsPanel";
import {
  createTenderDetails,
  getTechnicalBidChecklist,
  getTenderDetails,
  netReceivable,
  performanceBgCost,
  updateTechnicalBidChecklistItem,
} from "./api";

const CHECKLIST_LABELS = {
  gst: "GST",
  pan: "PAN",
  turnover: "Turnover",
  past_work_certificates: "Past work certificates",
  iso: "ISO",
};

const emptyForm = {
  emd_amount: "",
  emd_validity_date: "",
  retention_percent: "5",
  performance_bg_percent: "4",
  dlp_months: "12",
  bid_due_date: "",
  pre_bid_meeting_date: "",
  opening_date: "",
};

export default function TenderMode({ token, project, onBack }) {
  const [details, setDetails] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [bgForm, setBgForm] = useState({ bg_amount: "", bank_charge_percent_pa: "1.5", contract_weeks: "", dlp_months: "12" });
  const [bgResult, setBgResult] = useState(null);

  const [receivableForm, setReceivableForm] = useState({ quotation_total: "", retention_percent: "5" });
  const [receivableResult, setReceivableResult] = useState(null);

  const [checklist, setChecklist] = useState([]);
  const [openChecklistDoc, setOpenChecklistDoc] = useState(null);

  useEffect(() => {
    getTenderDetails(token, project.id)
      .then(setDetails)
      .finally(() => setLoading(false));
    if (project.tender_mode) {
      getTechnicalBidChecklist(token, project.id).then(setChecklist).catch(() => {});
    }
  }, [token, project.id]);

  async function handleToggleChecklistItem(key, confirmed) {
    setError("");
    try {
      const updated = await updateTechnicalBidChecklistItem(token, project.id, key, confirmed);
      setChecklist((items) => items.map((i) => (i.key === key ? updated : i)));
    } catch (err) {
      setError(err.message);
    }
  }

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      const created = await createTenderDetails(token, project.id, {
        emd_amount: form.emd_amount ? Number(form.emd_amount) : null,
        emd_validity_date: form.emd_validity_date || null,
        retention_percent: Number(form.retention_percent),
        performance_bg_percent: Number(form.performance_bg_percent),
        dlp_months: Number(form.dlp_months),
        bid_due_date: form.bid_due_date || null,
        pre_bid_meeting_date: form.pre_bid_meeting_date || null,
        opening_date: form.opening_date || null,
      });
      setDetails(created);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleBgCalc(e) {
    e.preventDefault();
    try {
      const res = await performanceBgCost(token, {
        bg_amount: Number(bgForm.bg_amount),
        bank_charge_percent_pa: Number(bgForm.bank_charge_percent_pa),
        contract_weeks: Number(bgForm.contract_weeks),
        dlp_months: Number(bgForm.dlp_months),
      });
      setBgResult(res);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleReceivableCalc(e) {
    e.preventDefault();
    try {
      const res = await netReceivable(token, {
        quotation_total: Number(receivableForm.quotation_total),
        retention_percent: Number(receivableForm.retention_percent),
      });
      setReceivableResult(res);
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) {
    return <p className="text-center text-gray-500 mt-10">Loading tender details…</p>;
  }

  if (!project.tender_mode) {
    return (
      <div className="max-w-xl mx-auto mt-10 bg-white shadow rounded-lg p-8 text-center">
        <p className="text-gray-500">Tender Mode only applies to Government-client projects (Part L).</p>
        <button onClick={onBack} className="mt-4 text-sm text-blue-600 hover:underline">
          &larr; Back
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Tender Mode</h2>
            <p className="text-sm text-gray-500">
              Project <span className="font-mono">{project.project_no}</span>
            </p>
          </div>
          <button onClick={onBack} className="text-sm text-blue-600 hover:underline">
            &larr; Back to Scope Checklist
          </button>
        </div>
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      </div>

      {details ? (
        <div className="bg-white shadow rounded-lg p-6 space-y-2 text-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Tender Details</h3>
          <Row label="EMD amount" value={details.emd_amount ? `Rs ${details.emd_amount.toLocaleString()}` : "—"} />
          <Row label="EMD validity" value={details.emd_validity_date || "—"} />
          <Row label="Retention %" value={`${details.retention_percent}%`} />
          <Row label="Performance BG %" value={`${details.performance_bg_percent}%`} />
          <Row label="DLP" value={`${details.dlp_months} months`} />
          <Row label="Bid due date" value={details.bid_due_date || "—"} />
          <Row label="Pre-bid meeting" value={details.pre_bid_meeting_date || "—"} />
          <Row label="Opening date" value={details.opening_date || "—"} />
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="bg-white shadow rounded-lg p-6 space-y-3">
          <h3 className="text-sm font-semibold text-gray-700">Add tender details</h3>
          <div className="grid grid-cols-2 gap-3">
            <Num label="EMD amount (Rs)" value={form.emd_amount} onChange={(v) => set("emd_amount", v)} />
            <DateField label="EMD validity" value={form.emd_validity_date} onChange={(v) => set("emd_validity_date", v)} />
            <Num label="Retention %" value={form.retention_percent} onChange={(v) => set("retention_percent", v)} required />
            <Num label="Performance BG %" value={form.performance_bg_percent} onChange={(v) => set("performance_bg_percent", v)} required />
            <Num label="DLP (months)" value={form.dlp_months} onChange={(v) => set("dlp_months", v)} required />
            <DateField label="Bid due date" value={form.bid_due_date} onChange={(v) => set("bid_due_date", v)} />
            <DateField label="Pre-bid meeting" value={form.pre_bid_meeting_date} onChange={(v) => set("pre_bid_meeting_date", v)} />
            <DateField label="Opening date" value={form.opening_date} onChange={(v) => set("opening_date", v)} />
          </div>
          <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
            Save tender details
          </button>
        </form>
      )}

      <div className="bg-white shadow rounded-lg p-6 space-y-2">
        <h3 className="text-sm font-semibold text-gray-700">Technical bid checklist</h3>
        <p className="text-xs text-gray-400">
          Part L: "Technical bid checklist (GST, PAN, turnover, past work certificates, ISO)" -- the blueprint's
          complete item list. These are NestaPrime's own bidder-eligibility documents, not the client's.
        </p>
        {checklist.map((item) => (
          <div key={item.key} className="border border-gray-200 rounded px-3 py-2 text-sm space-y-1">
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={item.confirmed}
                  onChange={(e) => handleToggleChecklistItem(item.key, e.target.checked)}
                />
                <span>{CHECKLIST_LABELS[item.key]}</span>
              </label>
              <div className="flex items-center gap-2 text-xs">
                {item.confirmed && <span className="text-green-700">confirmed</span>}
                <button
                  onClick={() => setOpenChecklistDoc(openChecklistDoc === item.id ? null : item.id)}
                  className="text-blue-600 hover:underline"
                >
                  {openChecklistDoc === item.id ? "Hide document" : "Document"}
                </button>
              </div>
            </div>
            {openChecklistDoc === item.id && (
              <AttachmentsPanel token={token} docType="technical_bid_checklist_item" docId={item.id} />
            )}
          </div>
        ))}
      </div>

      <form onSubmit={handleBgCalc} className="bg-white shadow rounded-lg p-6 space-y-3">
        <h3 className="text-sm font-semibold text-gray-700">Performance BG cost calculator</h3>
        <div className="grid grid-cols-2 gap-3">
          <Num label="BG amount (Rs)" value={bgForm.bg_amount} onChange={(v) => setBgForm((f) => ({ ...f, bg_amount: v }))} required />
          <Num label="Bank charge % p.a." value={bgForm.bank_charge_percent_pa} onChange={(v) => setBgForm((f) => ({ ...f, bank_charge_percent_pa: v }))} required />
          <Num label="Contract weeks" value={bgForm.contract_weeks} onChange={(v) => setBgForm((f) => ({ ...f, contract_weeks: v }))} required />
          <Num label="DLP (months)" value={bgForm.dlp_months} onChange={(v) => setBgForm((f) => ({ ...f, dlp_months: v }))} required />
        </div>
        <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
          Calculate BG cost
        </button>
        {bgResult && (
          <div className="text-sm space-y-1 mt-2">
            <Row label="Contract months" value={bgResult.contract_months} />
            <Row label="BG cost" value={`Rs ${bgResult.bg_cost.toLocaleString(undefined, { maximumFractionDigits: 2 })}`} bold />
          </div>
        )}
      </form>

      <form onSubmit={handleReceivableCalc} className="bg-white shadow rounded-lg p-6 space-y-3">
        <h3 className="text-sm font-semibold text-gray-700">Net receivable calculator</h3>
        <div className="grid grid-cols-2 gap-3">
          <Num label="Quotation total (Rs)" value={receivableForm.quotation_total} onChange={(v) => setReceivableForm((f) => ({ ...f, quotation_total: v }))} required />
          <Num label="Retention %" value={receivableForm.retention_percent} onChange={(v) => setReceivableForm((f) => ({ ...f, retention_percent: v }))} required />
        </div>
        <button type="submit" className="bg-blue-600 text-white text-sm rounded px-4 py-2 hover:bg-blue-700">
          Calculate
        </button>
        {receivableResult && (
          <div className="text-sm space-y-1 mt-2">
            <Row label="Retention amount" value={`Rs ${receivableResult.retention_amount.toLocaleString()}`} />
            <Row label="Net receivable" value={`Rs ${receivableResult.net_receivable.toLocaleString()}`} bold />
          </div>
        )}
      </form>
    </div>
  );
}

function Row({ label, value, bold }) {
  return (
    <div className={`flex items-center justify-between ${bold ? "font-semibold" : ""}`}>
      <span className="text-gray-600">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function Num({ label, value, onChange, required }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      <input
        type="number"
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
      />
    </div>
  );
}

function DateField({ label, value, onChange }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
      />
    </div>
  );
}
