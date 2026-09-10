import { useEffect, useState } from "react";
import AttachmentsPanel from "./AttachmentsPanel";
import ClientSignatoriesPanel from "./ClientSignatoriesPanel";
import CostSheetBuilder from "./CostSheetBuilder";
import MessagesPanel from "./MessagesPanel";
import {
  addCostSheetLine,
  addWorkOrderPaymentEntry,
  approveSkipRequest,
  createCostSheet,
  createEstimate,
  createQuotation,
  createSkipRequest,
  createWorkOrder,
  downloadEstimatePdfBlob,
  downloadQuotationPdfBlob,
  getL1View,
  getWorkOrder,
  listCostSheetLines,
  listCostSheets,
  listEstimates,
  listProjectSports,
  listQuotations,
  listSkipRequests,
  listSports,
  listWorkOrderPaymentEntries,
  markQuotationLost,
  markQuotationWon,
  rebaseEstimate,
  rejectCostSheet,
  rejectQuotation,
  releaseQuotation,
  reviseCostSheet,
  reviseEstimate,
  reviseQuotation,
  sendEstimate,
  sendQuotation,
  updateCostSheetLine,
  updateEstimateOptionClientStatus,
  updateWorkOrderStatus,
  verifyCostSheet,
} from "./api";

function downloadBlobAsFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// M.3: "Every approval step has a Reject -> Rework path with a reason
// category ... and a note; the document returns to Draft."
const REJECT_REASON_CATEGORIES = [
  { value: "wrong_quantities", label: "Wrong quantities" },
  { value: "rate_not_confirmed", label: "Rate not confirmed" },
  { value: "margin", label: "Margin" },
  { value: "scope_unclear", label: "Scope unclear" },
  { value: "evidence_missing", label: "Evidence missing" },
  { value: "other", label: "Other" },
];

function RejectForm({ onSubmit, onCancel }) {
  const [reasonCategory, setReasonCategory] = useState(REJECT_REASON_CATEGORIES[0].value);
  const [note, setNote] = useState("");

  return (
    <div className="border border-red-200 bg-red-50 rounded p-2 space-y-2 text-xs">
      <div className="flex items-center gap-2">
        <select
          value={reasonCategory}
          onChange={(e) => setReasonCategory(e.target.value)}
          className="rounded border border-gray-300 px-2 py-1"
        >
          {REJECT_REASON_CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="flex-1 rounded border border-gray-300 px-2 py-1"
        />
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={() => onSubmit(reasonCategory, note)}
          disabled={!note.trim()}
          className="bg-red-600 text-white rounded px-2 py-1 hover:bg-red-700 disabled:opacity-50"
        >
          Confirm reject
        </button>
        <button onClick={onCancel} className="text-gray-500 hover:underline">
          Cancel
        </button>
      </div>
    </div>
  );
}

export default function Documents({ token, project, role, onBack }) {
  const [projectSports, setProjectSports] = useState([]);
  const [sports, setSports] = useState([]);
  const [costSheets, setCostSheets] = useState([]);
  const [estimates, setEstimates] = useState([]);
  const [quotations, setQuotations] = useState([]);
  const [skipRequests, setSkipRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [builderCostSheet, setBuilderCostSheet] = useState(null);

  function load() {
    return Promise.all([
      listProjectSports(token, project.id),
      listSports(token),
      listCostSheets(token, project.id).catch(() => []),
      listEstimates(token, project.id).catch(() => []),
      listQuotations(token, project.id).catch(() => []),
      listSkipRequests(token, project.id).catch(() => []),
    ]).then(([ps, s, cs, est, quo, skip]) => {
      setProjectSports(ps);
      setSports(s);
      setCostSheets(cs);
      setEstimates(est);
      setQuotations(quo);
      setSkipRequests(skip);
    });
  }

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [token, project.id]);

  function withErrorHandling(fn) {
    return async (...args) => {
      setError("");
      try {
        await fn(...args);
        await load();
      } catch (err) {
        setError(err.message);
      }
    };
  }

  const activeCostSheet = costSheets.find((c) => c.status !== "superseded");
  const sportsById = Object.fromEntries(sports.map((s) => [s.id, s]));

  if (loading) {
    return <p className="text-center text-gray-500 mt-10">Loading documents…</p>;
  }

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Documents</h2>
            <p className="text-sm text-gray-500">
              Project <span className="font-mono">{project.project_no}</span>
            </p>
          </div>
          <button onClick={onBack} className="text-sm text-blue-600 hover:underline">
            &larr; Back
          </button>
        </div>
        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
      </div>

      {builderCostSheet ? (
        <CostSheetBuilder
          token={token}
          costSheet={builderCostSheet}
          projectType={project.project_type}
          tenderMode={project.tender_mode}
          projectSports={projectSports}
          sports={sports}
          onBack={() => {
            setBuilderCostSheet(null);
            load();
          }}
          onCostSheetUpdated={(updated) => {
            setBuilderCostSheet(updated);
            load();
          }}
        />
      ) : (
        <>
          <ClientSignatoriesPanel token={token} clientId={project.client_id} />

          <CostSheetPanel
            token={token}
            project={project}
            role={role}
            costSheets={costSheets}
            skipRequests={skipRequests}
            onAction={withErrorHandling}
            onBuild={setBuilderCostSheet}
          />

          <EstimatePanel
            token={token}
            project={project}
            role={role}
            activeCostSheet={activeCostSheet}
            projectSports={projectSports}
            sportsById={sportsById}
            estimates={estimates}
            onAction={withErrorHandling}
          />

          <QuotationPanel
            token={token}
            project={project}
            role={role}
            estimates={estimates}
            quotations={quotations}
            onAction={withErrorHandling}
          />
        </>
      )}
    </div>
  );
}

function RateBlindLinesPanel({ token, costSheetId, role, onChanged }) {
  const [lines, setLines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ work_package: "civil", category: "", item_name: "", unit: "", quantity: "" });
  const [rateDrafts, setRateDrafts] = useState({});
  const isSales = role === "sales";

  function load() {
    return listCostSheetLines(token, costSheetId).then(setLines);
  }

  useEffect(() => {
    setLoading(true);
    load().catch((err) => setError(err.message)).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, costSheetId]);

  async function handlePropose() {
    setError("");
    try {
      await addCostSheetLine(token, costSheetId, { ...form, quantity: Number(form.quantity) });
      setForm({ work_package: "civil", category: "", item_name: "", unit: "", quantity: "" });
      await load();
      if (onChanged) await onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSetRate(lineId) {
    setError("");
    try {
      await updateCostSheetLine(token, costSheetId, lineId, { rate: Number(rateDrafts[lineId]) });
      setRateDrafts((d) => ({ ...d, [lineId]: "" }));
      await load();
      if (onChanged) await onChanged();
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) return <p className="text-xs text-gray-400">Loading lines…</p>;

  return (
    <div className="border border-dashed border-gray-300 rounded p-3 space-y-2 bg-gray-50 text-xs">
      <p className="font-semibold text-gray-600">
        Cost Sheet lines (K.3 Rate-blind mode) {isSales && "-- rates are hidden from you by design"}
      </p>
      {error && <p className="text-red-600">{error}</p>}
      {lines.map((l) => (
        <div key={l.id} className="flex flex-wrap items-center justify-between gap-2 bg-white rounded px-2 py-1 border border-gray-200">
          <span>
            {l.category} · {l.item_name} · {l.quantity} {l.unit}
            {l.pending && <span className="text-amber-700"> · pending PM rate</span>}
            {!isSales && !l.pending && <span className="text-gray-500"> · Rs {l.rate}/unit = Rs {l.amount.toLocaleString()}</span>}
          </span>
          {!isSales && l.pending && (
            <div className="flex items-center gap-1">
              <input
                type="number" placeholder="Rate"
                value={rateDrafts[l.id] || ""}
                onChange={(e) => setRateDrafts((d) => ({ ...d, [l.id]: e.target.value }))}
                className="border border-gray-300 rounded px-1 py-0.5 w-20"
              />
              <button onClick={() => handleSetRate(l.id)} disabled={!rateDrafts[l.id]} className="text-blue-600 hover:underline disabled:opacity-50">
                Set rate
              </button>
            </div>
          )}
        </div>
      ))}
      {lines.length === 0 && <p className="text-gray-400">No lines proposed yet.</p>}

      {isSales && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <select value={form.work_package} onChange={(e) => setForm((f) => ({ ...f, work_package: e.target.value }))} className="border border-gray-300 rounded px-2 py-1">
            <option value="civil">Civil</option>
            <option value="structure">Structure</option>
            <option value="flooring">Flooring</option>
            <option value="electrical">Electrical</option>
            <option value="pool">Pool</option>
            <option value="hvac">HVAC</option>
            <option value="accessories">Accessories</option>
            <option value="scope">Scope</option>
            <option value="services">Services</option>
          </select>
          <input placeholder="Category" value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} className="border border-gray-300 rounded px-2 py-1 w-24" />
          <input placeholder="Item" value={form.item_name} onChange={(e) => setForm((f) => ({ ...f, item_name: e.target.value }))} className="border border-gray-300 rounded px-2 py-1 flex-1 min-w-[120px]" />
          <input placeholder="Unit" value={form.unit} onChange={(e) => setForm((f) => ({ ...f, unit: e.target.value }))} className="border border-gray-300 rounded px-2 py-1 w-16" />
          <input type="number" placeholder="Qty" value={form.quantity} onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))} className="border border-gray-300 rounded px-2 py-1 w-20" />
          <button
            onClick={handlePropose}
            disabled={!form.category || !form.item_name || !form.unit || !form.quantity}
            className="bg-blue-600 text-white rounded px-3 py-1.5 hover:bg-blue-700 disabled:opacity-50"
          >
            Propose line
          </button>
        </div>
      )}
    </div>
  );
}

function CostSheetPanel({ token, project, role, costSheets, skipRequests, onAction, onBuild }) {
  const [costTotal, setCostTotal] = useState("");
  const [openAttachmentsFor, setOpenAttachmentsFor] = useState(null);
  const [openMessagesFor, setOpenMessagesFor] = useState(null);
  const [skipReason, setSkipReason] = useState("");
  const [approveCostTotal, setApproveCostTotal] = useState("");
  const [rejectFormFor, setRejectFormFor] = useState(null);
  const [openLinesFor, setOpenLinesFor] = useState(null);
  const active = costSheets.find((c) => c.status !== "superseded");
  const pendingSkipRequest = skipRequests.find((r) => r.status === "pending");
  const canApproveSkip = role === "pm" || role === "director";
  const canReject = role === "pm" || role === "director";
  const canSeeLines = role === "sales" || role === "pm" || role === "director";

  const handleCreate = onAction(async () => {
    await createCostSheet(token, project.id, { cost_total: Number(costTotal) });
    setCostTotal("");
  });
  const handleCreateEmpty = onAction(async () => {
    const created = await createCostSheet(token, project.id, {});
    onBuild(created);
  });
  const handleVerify = onAction(async (id) => verifyCostSheet(token, id));
  const handleReject = onAction(async (id, reasonCategory, note) => {
    await rejectCostSheet(token, id, { reason_category: reasonCategory, note });
    setRejectFormFor(null);
  });
  const handleRevise = onAction(async (id) => {
    await reviseCostSheet(token, id, { cost_total: Number(costTotal) });
    setCostTotal("");
  });
  const handleRequestSkip = onAction(async () => {
    await createSkipRequest(token, project.id, { stage_skipped: "cost_sheet", reason: skipReason });
    setSkipReason("");
  });
  const handleApproveSkip = onAction(async (id) => {
    await approveSkipRequest(token, id, { cost_total: Number(approveCostTotal) });
    setApproveCostTotal("");
  });

  return (
    <div className="bg-white shadow rounded-lg p-6 space-y-3">
      <h3 className="text-sm font-semibold text-gray-700">Cost Sheet (M.1 stage 1)</h3>
      {costSheets.map((cs) => (
        <div key={cs.id} className="border border-gray-200 rounded px-3 py-2 text-sm space-y-2">
          <div className="flex items-center justify-between">
            <span>
              {cs.document_no}
              {cs.cost_total != null && <> · Rs {cs.cost_total.toLocaleString()}</>} ·{" "}
              <StatusBadge status={cs.status} />
              {cs.auto_generated && <span className="text-amber-700 text-xs"> · skip-generated</span>}
              {cs.sla_breached && (
                <span className="text-red-700 text-xs bg-red-50 rounded px-1.5 py-0.5 ml-1">
                  SLA breached (M.3) -- awaiting verification
                </span>
              )}
            </span>
            <div className="flex items-center gap-3">
              {role !== "sales" && (cs.status === "draft" || cs.status === "unverified") && (
                <>
                  <button onClick={() => onBuild(cs)} className="text-xs text-blue-600 hover:underline">
                    Build from take-off
                  </button>
                  <button onClick={() => handleVerify(cs.id)} className="text-xs text-blue-600 hover:underline">
                    Verify
                  </button>
                </>
              )}
              {canReject && (cs.status === "verified" || cs.status === "unverified") && (
                <button
                  onClick={() => setRejectFormFor(rejectFormFor === cs.id ? null : cs.id)}
                  className="text-xs text-red-600 hover:underline"
                >
                  Reject
                </button>
              )}
              <button
                onClick={() => setOpenAttachmentsFor(openAttachmentsFor === cs.id ? null : cs.id)}
                className="text-xs text-gray-500 hover:underline"
              >
                {openAttachmentsFor === cs.id ? "Hide attachments" : "Attachments"}
              </button>
              <button
                onClick={() => setOpenMessagesFor(openMessagesFor === cs.id ? null : cs.id)}
                className="text-xs text-gray-500 hover:underline"
              >
                {openMessagesFor === cs.id ? "Hide messages" : "Messages"}
              </button>
              {canSeeLines && (cs.status === "draft" || cs.status === "unverified") && (
                <button
                  onClick={() => setOpenLinesFor(openLinesFor === cs.id ? null : cs.id)}
                  className="text-xs text-gray-500 hover:underline"
                >
                  {openLinesFor === cs.id ? "Hide lines" : "Lines"}
                </button>
              )}
            </div>
          </div>
          {rejectFormFor === cs.id && (
            <RejectForm
              onSubmit={(reasonCategory, note) => handleReject(cs.id, reasonCategory, note)}
              onCancel={() => setRejectFormFor(null)}
            />
          )}
          {openAttachmentsFor === cs.id && <AttachmentsPanel token={token} docType="cost_sheet" docId={cs.id} />}
          {openMessagesFor === cs.id && <MessagesPanel token={token} docType="cost_sheet" docId={cs.id} />}
          {openLinesFor === cs.id && <RateBlindLinesPanel token={token} costSheetId={cs.id} role={role} />}
        </div>
      ))}
      {role !== "sales" && (
        <div className="flex items-center gap-2">
          <input
            type="number"
            placeholder="Cost incl. contingency (Rs)"
            value={costTotal}
            onChange={(e) => setCostTotal(e.target.value)}
            className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm"
          />
          {active && active.status === "verified" ? (
            <button
              onClick={() => handleRevise(active.id)}
              className="bg-blue-600 text-white text-xs rounded px-3 py-2 hover:bg-blue-700"
            >
              Revise (new R+1)
            </button>
          ) : (
            <button
              onClick={handleCreate}
              disabled={!!active}
              className="bg-blue-600 text-white text-xs rounded px-3 py-2 hover:bg-blue-700 disabled:opacity-50"
            >
              Create Cost Sheet
            </button>
          )}
        </div>
      )}
      {role !== "sales" && !active && (
        <button
          onClick={handleCreateEmpty}
          className="w-full text-xs text-blue-600 hover:underline text-center py-1"
        >
          …or start an empty Cost Sheet and build it up from Structures/Base/Flooring/etc. take-offs
        </button>
      )}

      {!active && !pendingSkipRequest && (
        <div className="border-t border-gray-200 pt-3 space-y-2">
          <p className="text-xs font-semibold text-gray-600">
            Or: request to skip this stage (M.2 rule 3)
          </p>
          <p className="text-[11px] text-gray-400">
            "Sales cannot skip alone" -- a PM or Director must approve before the Estimate stage can be created
            on an auto-generated (Unverified) Cost Sheet.
          </p>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Reason (e.g. client wants a quotation directly)"
              value={skipReason}
              onChange={(e) => setSkipReason(e.target.value)}
              className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <button
              onClick={handleRequestSkip}
              disabled={!skipReason}
              className="bg-gray-600 text-white text-xs rounded px-3 py-2 hover:bg-gray-700 disabled:opacity-50"
            >
              Request skip
            </button>
          </div>
        </div>
      )}

      {pendingSkipRequest && (
        <div className="border-t border-amber-200 bg-amber-50 rounded p-3 space-y-2 text-sm">
          <p className="font-semibold text-amber-800">Skip request pending</p>
          <p className="text-xs text-gray-600">"{pendingSkipRequest.reason}"</p>
          {canApproveSkip ? (
            <div className="flex items-center gap-2">
              <input
                type="number"
                placeholder="Ballpark cost total (Rs)"
                value={approveCostTotal}
                onChange={(e) => setApproveCostTotal(e.target.value)}
                className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm"
              />
              <button
                onClick={() => handleApproveSkip(pendingSkipRequest.id)}
                disabled={!approveCostTotal}
                className="bg-green-600 text-white text-xs rounded px-3 py-2 hover:bg-green-700 disabled:opacity-50"
              >
                Approve &amp; auto-generate
              </button>
            </div>
          ) : (
            <p className="text-xs text-gray-500">Waiting for PM or Director approval.</p>
          )}
        </div>
      )}
    </div>
  );
}

function EstimatePanel({ token, project, role, activeCostSheet, projectSports, sportsById, estimates, onAction }) {
  const [optionForm, setOptionForm] = useState({ project_sport_id: "", package: "standard", cost_for_option: "" });
  const [openAttachmentsFor, setOpenAttachmentsFor] = useState(null);
  const [openMessagesFor, setOpenMessagesFor] = useState(null);
  const [openOptionAttachmentsFor, setOpenOptionAttachmentsFor] = useState(null);
  const [waiverReasons, setWaiverReasons] = useState({});
  const [rejectionReasons, setRejectionReasons] = useState({});
  const [pdfError, setPdfError] = useState("");
  const [openReviseFor, setOpenReviseFor] = useState(null);
  const [reviseDrafts, setReviseDrafts] = useState({}); // estimateId -> { costs: {optionId: value}, refresh_pricing }
  const canWaive = role === "pm" || role === "director";
  const canRevise = role === "pm" || role === "director";

  async function handleDownloadPdf(estimate) {
    setPdfError("");
    try {
      const blob = await downloadEstimatePdfBlob(token, estimate.id);
      downloadBlobAsFile(blob, `${estimate.document_no}.pdf`);
    } catch (err) {
      setPdfError(err.message);
    }
  }
  const sportNameByProjectSportId = Object.fromEntries(
    projectSports.map((ps) => [ps.id, sportsById[ps.sport_id]?.name ?? ps.sport_id])
  );

  const handleCreate = onAction(async () => {
    await createEstimate(token, project.id, {
      options: [
        {
          project_sport_id: optionForm.project_sport_id,
          package: optionForm.package,
          cost_for_option: Number(optionForm.cost_for_option),
        },
      ],
    });
    setOptionForm({ project_sport_id: "", package: "standard", cost_for_option: "" });
  });
  const handleSend = onAction(async (id) => sendEstimate(token, id));
  const handleRebase = onAction(async (id) => rebaseEstimate(token, id));
  const handleRevise = onAction(async (estimateId, options, refreshPricing) => {
    await reviseEstimate(token, estimateId, { options, refresh_pricing: refreshPricing });
    setOpenReviseFor(null);
  });
  const handleClientStatus = onAction(async (estimateId, optionId, client_status, waiveEvidenceReason, rejectionReason) =>
    updateEstimateOptionClientStatus(token, estimateId, optionId, {
      client_status,
      ...(waiveEvidenceReason ? { waive_evidence_reason: waiveEvidenceReason } : {}),
      ...(rejectionReason ? { rejection_reason: rejectionReason } : {}),
    })
  );

  return (
    <div className="bg-white shadow rounded-lg p-6 space-y-3">
      <h3 className="text-sm font-semibold text-gray-700">Estimate (M.1 stage 2)</h3>
      {pdfError && <p className="text-xs text-red-600">{pdfError}</p>}

      {estimates.map((est) => (
        <div key={est.id} className="border border-gray-200 rounded px-3 py-2 text-sm space-y-2">
          <div className="flex items-center justify-between">
            <span>
              {est.document_no} · <StatusBadge status={est.status} /> · client:{" "}
              <StatusBadge status={est.client_status} />
              {est.cost_basis_rebase_required && (
                <span className="text-red-700 text-xs"> · cost basis changed — rebase required</span>
              )}
            </span>
            <div className="flex items-center gap-3">
              {est.cost_basis_rebase_required && (
                <button onClick={() => handleRebase(est.id)} className="text-xs text-red-600 hover:underline">
                  Rebase
                </button>
              )}
              {est.status === "draft" && (
                <button onClick={() => handleSend(est.id)} className="text-xs text-blue-600 hover:underline">
                  Send
                </button>
              )}
              {est.status === "sent" && canRevise && (
                <button
                  onClick={() => {
                    if (openReviseFor === est.id) {
                      setOpenReviseFor(null);
                      return;
                    }
                    setReviseDrafts((d) => ({
                      ...d,
                      [est.id]: {
                        costs: Object.fromEntries(est.options.map((o) => [o.id, o.cost_for_option])),
                        refresh_pricing: false,
                      },
                    }));
                    setOpenReviseFor(est.id);
                  }}
                  className="text-xs text-blue-600 hover:underline"
                >
                  {openReviseFor === est.id ? "Cancel revise" : "Revise"}
                </button>
              )}
              <button onClick={() => handleDownloadPdf(est)} className="text-xs text-blue-600 hover:underline">
                Download PDF
              </button>
              <button
                onClick={() => setOpenAttachmentsFor(openAttachmentsFor === est.id ? null : est.id)}
                className="text-xs text-gray-500 hover:underline"
              >
                {openAttachmentsFor === est.id ? "Hide attachments" : "Attachments"}
              </button>
              <button
                onClick={() => setOpenMessagesFor(openMessagesFor === est.id ? null : est.id)}
                className="text-xs text-gray-500 hover:underline"
              >
                {openMessagesFor === est.id ? "Hide messages" : "Messages"}
              </button>
            </div>
          </div>
          {openAttachmentsFor === est.id && <AttachmentsPanel token={token} docType="estimate" docId={est.id} />}
          {openMessagesFor === est.id && <MessagesPanel token={token} docType="estimate" docId={est.id} />}
          {openReviseFor === est.id && (
            <div className="bg-amber-50 border border-amber-200 rounded px-3 py-2 space-y-2 text-xs">
              <p className="text-amber-800">
                M.2 rule 4: a priced-content change to a Sent Estimate creates a new revision (EST-…-R
                {est.revision_major + 1}) and needs fresh client approval.
              </p>
              {est.options.map((opt) => (
                <div key={opt.id} className="flex items-center gap-2">
                  <span className="w-40 truncate">
                    {sportNameByProjectSportId[opt.project_sport_id] ?? opt.project_sport_id} ({opt.package})
                  </span>
                  <span>Cost for option (Rs)</span>
                  <input
                    type="number"
                    value={reviseDrafts[est.id]?.costs[opt.id] ?? opt.cost_for_option}
                    onChange={(e) =>
                      setReviseDrafts((d) => ({
                        ...d,
                        [est.id]: { ...d[est.id], costs: { ...d[est.id]?.costs, [opt.id]: Number(e.target.value) } },
                      }))
                    }
                    className="w-32 rounded border border-gray-300 px-1 py-0.5"
                  />
                </div>
              ))}
              <label className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={reviseDrafts[est.id]?.refresh_pricing ?? false}
                  onChange={(e) =>
                    setReviseDrafts((d) => ({ ...d, [est.id]: { ...d[est.id], refresh_pricing: e.target.checked } }))
                  }
                />
                Refresh pricing from current settings (otherwise unchanged options keep their frozen price)
              </label>
              <button
                onClick={() =>
                  handleRevise(
                    est.id,
                    est.options.map((opt) => ({
                      project_sport_id: opt.project_sport_id,
                      package: opt.package,
                      cost_for_option: reviseDrafts[est.id]?.costs[opt.id] ?? opt.cost_for_option,
                    })),
                    reviseDrafts[est.id]?.refresh_pricing ?? false
                  )
                }
                className="bg-blue-600 text-white rounded px-3 py-1 hover:bg-blue-700"
              >
                Create revision
              </button>
            </div>
          )}
          {est.options.map((opt) => (
            <div key={opt.id} className="space-y-1">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs bg-gray-50 rounded px-2 py-1">
                <span>
                  {sportNameByProjectSportId[opt.project_sport_id] ?? opt.project_sport_id} ({opt.package}): Rs{" "}
                  {opt.price_low.toLocaleString()} - Rs {opt.price_high.toLocaleString()} incl. GST ·{" "}
                  <StatusBadge status={opt.client_status} />
                  {opt.rejection_reason && (
                    <span className="text-gray-500"> ({opt.rejection_reason})</span>
                  )}
                </span>
                <div className="flex items-center gap-1">
                  {canWaive && (
                    <input
                      type="text"
                      placeholder="waiver reason (PM/Director)"
                      value={waiverReasons[opt.id] || ""}
                      onChange={(e) => setWaiverReasons((w) => ({ ...w, [opt.id]: e.target.value }))}
                      className="text-xs border border-gray-300 rounded px-1 py-0.5 w-40"
                    />
                  )}
                  <button
                    onClick={() => handleClientStatus(est.id, opt.id, "approved", waiverReasons[opt.id])}
                    className="text-green-700 hover:underline"
                  >
                    Approve
                  </button>
                  <select
                    value={rejectionReasons[opt.id] || ""}
                    onChange={(e) => setRejectionReasons((r) => ({ ...r, [opt.id]: e.target.value }))}
                    className="text-xs border border-gray-300 rounded px-1 py-0.5"
                  >
                    <option value="">reason (for reject)…</option>
                    <option value="price">Price</option>
                    <option value="scope">Scope</option>
                    <option value="timing">Timing</option>
                    <option value="competitor">Competitor</option>
                    <option value="other">Other</option>
                  </select>
                  <button
                    onClick={() => handleClientStatus(est.id, opt.id, "rejected", null, rejectionReasons[opt.id])}
                    disabled={!rejectionReasons[opt.id]}
                    className="text-red-700 hover:underline disabled:text-gray-300 disabled:cursor-not-allowed"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => setOpenOptionAttachmentsFor(openOptionAttachmentsFor === opt.id ? null : opt.id)}
                    className="text-gray-500 hover:underline"
                  >
                    {openOptionAttachmentsFor === opt.id ? "Hide photo" : "Product photo"}
                  </button>
                </div>
              </div>
              {openOptionAttachmentsFor === opt.id && (
                <AttachmentsPanel token={token} docType="estimate_option" docId={opt.id} />
              )}
            </div>
          ))}
        </div>
      ))}

      {activeCostSheet?.status === "verified" || activeCostSheet?.status === "unverified" ? (
        <div className="space-y-2">
          {activeCostSheet?.status === "unverified" && (
            <p className="text-[11px] text-amber-700 bg-amber-50 rounded px-2 py-1">
              This Cost Sheet is Unverified (skip-generated, M.2 rule 3) -- the resulting Quotation will need
              Director release and can't be marked Won until it's Verified.
            </p>
          )}
          <select
            value={optionForm.project_sport_id}
            onChange={(e) => setOptionForm((f) => ({ ...f, project_sport_id: e.target.value }))}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">Select a sport…</option>
            {projectSports.map((ps) => (
              <option key={ps.id} value={ps.id}>
                {sportsById[ps.sport_id]?.name ?? ps.sport_id}
              </option>
            ))}
          </select>
          <div className="flex items-center gap-2">
            <select
              value={optionForm.package}
              onChange={(e) => setOptionForm((f) => ({ ...f, package: e.target.value }))}
              className="rounded border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="budget">Budget</option>
              <option value="standard">Standard</option>
              <option value="premium">Premium</option>
            </select>
            <input
              type="number"
              placeholder="Cost for this option (Rs)"
              value={optionForm.cost_for_option}
              onChange={(e) => setOptionForm((f) => ({ ...f, cost_for_option: e.target.value }))}
              className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <button
              onClick={handleCreate}
              disabled={!optionForm.project_sport_id || !optionForm.cost_for_option}
              className="bg-blue-600 text-white text-xs rounded px-3 py-2 hover:bg-blue-700 disabled:opacity-50"
            >
              Create Estimate
            </button>
          </div>
        </div>
      ) : (
        <p className="text-xs text-gray-400">Requires a Verified cost sheet (M.2 rule 1).</p>
      )}
    </div>
  );
}

function QuotationPanel({ token, project, role, estimates, quotations, onAction }) {
  const [selectedEstimateId, setSelectedEstimateId] = useState("");
  const [discountValue, setDiscountValue] = useState("");
  const [gstMode, setGstMode] = useState("exclusive");
  const [openAttachmentsFor, setOpenAttachmentsFor] = useState(null);
  const [openMessagesFor, setOpenMessagesFor] = useState(null);
  const [waiverReasons, setWaiverReasons] = useState({});
  const [pdfError, setPdfError] = useState("");
  const [rejectFormFor, setRejectFormFor] = useState(null);
  const [openReviseFor, setOpenReviseFor] = useState(null);
  const [reviseDrafts, setReviseDrafts] = useState({}); // quotationId -> { discount_value, refresh_pricing, gst_mode }
  const [openL1For, setOpenL1For] = useState(null);
  const [l1Views, setL1Views] = useState({}); // quotationId -> L1ViewOut
  const [l1Error, setL1Error] = useState("");
  const canWaive = role === "pm" || role === "director";
  const canReject = role === "pm" || role === "director";
  const canRevise = role === "pm" || role === "director";

  async function toggleL1View(quotationId) {
    if (openL1For === quotationId) {
      setOpenL1For(null);
      return;
    }
    setL1Error("");
    setOpenL1For(quotationId);
    try {
      const view = await getL1View(token, quotationId);
      setL1Views((v) => ({ ...v, [quotationId]: view }));
    } catch (err) {
      setL1Views((v) => ({ ...v, [quotationId]: null }));
      setL1Error(err.message);
    }
  }

  async function handleDownloadPdf(quotation) {
    setPdfError("");
    try {
      const blob = await downloadQuotationPdfBlob(token, quotation.id);
      downloadBlobAsFile(blob, `${quotation.document_no}.pdf`);
    } catch (err) {
      setPdfError(err.message);
    }
  }

  const approvableOptions = estimates.flatMap((est) =>
    est.options
      .filter((o) => o.client_status === "approved" || o.client_status === "demand_received")
      .map((o) => ({ ...o, estimateId: est.id }))
  );

  const handleCreate = onAction(async () => {
    const options = estimates.find((e) => e.id === selectedEstimateId)?.options ?? [];
    const includedIds = options
      .filter((o) => o.client_status === "approved" || o.client_status === "demand_received")
      .map((o) => o.id);
    await createQuotation(token, project.id, {
      estimate_id: selectedEstimateId,
      included_option_ids: includedIds,
      ...(discountValue ? { discount_type: "amount", discount_value: Number(discountValue) } : {}),
      ...(project.tender_mode ? { gst_mode: gstMode } : {}),
    });
    setDiscountValue("");
  });
  const handleRelease = onAction(async (id) => releaseQuotation(token, id));
  const handleSend = onAction(async (id) => sendQuotation(token, id));
  const handleWon = onAction(async (id, waiveEvidenceReason) =>
    markQuotationWon(token, id, { reason: "Client accepted", waiveEvidenceReason })
  );
  const handleLost = onAction(async (id) => markQuotationLost(token, id, "Client declined"));
  const handleReject = onAction(async (id, reasonCategory, note) => {
    await rejectQuotation(token, id, { reason_category: reasonCategory, note });
    setRejectFormFor(null);
  });
  const handleRevise = onAction(async (quotation) => {
    const draft = reviseDrafts[quotation.id] || {};
    // The API can revise onto any option set; this form keeps whatever
    // is currently Client approved / demand received on the linked
    // Estimate (the common case) rather than exposing a full line
    // editor here -- changing which sports a Quotation covers still
    // needs a fresh /quotations POST today.
    const estimate = estimates.find((e) => e.id === quotation.estimate_id);
    const includedIds = (estimate?.options ?? [])
      .filter((o) => o.client_status === "approved" || o.client_status === "demand_received")
      .map((o) => o.id);
    await reviseQuotation(token, quotation.id, {
      included_option_ids: includedIds,
      discount_type: draft.discount_value ? "amount" : null,
      discount_value: Number(draft.discount_value || 0),
      refresh_pricing: draft.refresh_pricing ?? false,
      ...(project.tender_mode && draft.gst_mode ? { gst_mode: draft.gst_mode } : {}),
    });
    setOpenReviseFor(null);
  });

  return (
    <div className="bg-white shadow rounded-lg p-6 space-y-3">
      <h3 className="text-sm font-semibold text-gray-700">Quotation (M.1 stage 3)</h3>
      {pdfError && <p className="text-xs text-red-600">{pdfError}</p>}

      {quotations.map((q) => (
        <div key={q.id} className="border border-gray-200 rounded px-3 py-2 text-sm space-y-2">
          <div className="flex items-center justify-between">
            <span>
              {q.document_no} · <StatusBadge status={q.status} />
              {q.below_floor && <span className="text-amber-700"> · below floor</span>}
              {q.cost_basis_rebase_required && (
                <span className="text-red-700"> · cost basis changed — rebase the Estimate</span>
              )}
              {q.sla_breached && (
                <span className="text-red-700 text-xs bg-red-50 rounded px-1.5 py-0.5 ml-1">
                  SLA breached (M.3) -- awaiting release
                </span>
              )}
              {q.gst_mode === "inclusive" && (
                <span className="text-blue-700 text-xs bg-blue-50 rounded px-1.5 py-0.5 ml-1">
                  GST inclusive (Part L)
                </span>
              )}
            </span>
            <span className="font-semibold">Rs {q.quotation_total.toLocaleString()}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {q.status === "draft" && (
              <button onClick={() => handleRelease(q.id)} className="text-blue-600 hover:underline">
                Release
              </button>
            )}
            <button onClick={() => handleDownloadPdf(q)} className="text-blue-600 hover:underline">
              Download PDF
            </button>
            {q.status === "released" && (
              <button onClick={() => handleSend(q.id)} className="text-blue-600 hover:underline">
                Send
              </button>
            )}
            {q.status === "sent" && (
              <>
                {canWaive && (
                  <input
                    type="text"
                    placeholder="waiver reason (PM/Director)"
                    value={waiverReasons[q.id] || ""}
                    onChange={(e) => setWaiverReasons((w) => ({ ...w, [q.id]: e.target.value }))}
                    className="text-xs border border-gray-300 rounded px-1 py-0.5 w-40"
                  />
                )}
                <button onClick={() => handleWon(q.id, waiverReasons[q.id])} className="text-green-700 hover:underline">
                  Mark Won
                </button>
                <button onClick={() => handleLost(q.id)} className="text-red-700 hover:underline">
                  Mark Lost
                </button>
              </>
            )}
            {canReject && (q.status === "released" || q.status === "sent") && (
              <button
                onClick={() => setRejectFormFor(rejectFormFor === q.id ? null : q.id)}
                className="text-red-600 hover:underline"
              >
                Reject
              </button>
            )}
            {canRevise && (q.status === "released" || q.status === "sent") && (
              <button
                onClick={() => {
                  if (openReviseFor === q.id) {
                    setOpenReviseFor(null);
                    return;
                  }
                  setReviseDrafts((d) => ({
                    ...d,
                    [q.id]: { discount_value: q.discount_value || "", refresh_pricing: false, gst_mode: q.gst_mode },
                  }));
                  setOpenReviseFor(q.id);
                }}
                className="text-blue-600 hover:underline"
              >
                {openReviseFor === q.id ? "Cancel revise" : "Revise"}
              </button>
            )}
            <button
              onClick={() => setOpenAttachmentsFor(openAttachmentsFor === q.id ? null : q.id)}
              className="text-gray-500 hover:underline"
            >
              {openAttachmentsFor === q.id ? "Hide attachments" : "Attachments"}
            </button>
            <button
              onClick={() => setOpenMessagesFor(openMessagesFor === q.id ? null : q.id)}
              className="text-gray-500 hover:underline"
            >
              {openMessagesFor === q.id ? "Hide messages" : "Messages"}
            </button>
            {project.tender_mode && (
              <button onClick={() => toggleL1View(q.id)} className="text-amber-700 hover:underline">
                {openL1For === q.id ? "Hide L1 view" : "L1 view (live)"}
              </button>
            )}
          </div>
          {l1Error && openL1For === q.id && <p className="text-xs text-red-600">{l1Error}</p>}
          {openL1For === q.id && l1Views[q.id] && (
            <div className="bg-amber-50 border border-amber-200 rounded px-3 py-2 text-xs space-y-1">
              <p className="text-amber-800 font-medium">
                {l1Views[q.id].is_l1 === null
                  ? "No competitor bids on file yet -- add some in Tender Mode to see a live L1 comparison."
                  : l1Views[q.id].is_l1
                  ? `We're L1 (lowest), rank 1 of ${l1Views[q.id].competitor_bids.length + 1}.`
                  : `Not L1 -- rank ${l1Views[q.id].rank} of ${l1Views[q.id].competitor_bids.length + 1}.`}
              </p>
              <p>Our price: Rs {l1Views[q.id].our_price.toLocaleString()}</p>
              {l1Views[q.id].margin_percent !== null && <p>Margin at this price: {l1Views[q.id].margin_percent}%</p>}
              {l1Views[q.id].lowest_competitor_amount !== null && (
                <p>Lowest known competitor: Rs {l1Views[q.id].lowest_competitor_amount.toLocaleString()}</p>
              )}
              {l1Views[q.id].competitor_bids.length > 0 && (
                <ul className="list-disc list-inside text-gray-600">
                  {l1Views[q.id].competitor_bids.map((b) => (
                    <li key={b.id}>
                      {b.bidder_name}: Rs {b.amount.toLocaleString()}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {rejectFormFor === q.id && (
            <RejectForm
              onSubmit={(reasonCategory, note) => handleReject(q.id, reasonCategory, note)}
              onCancel={() => setRejectFormFor(null)}
            />
          )}
          {openReviseFor === q.id && (
            <div className="bg-amber-50 border border-amber-200 rounded px-3 py-2 space-y-2 text-xs">
              <p className="text-amber-800">
                M.2 rule 4:{" "}
                {q.status === "sent"
                  ? `this creates a new revision (NPQ-…-R${q.revision_major + 1}) -- the Sent copy stays frozen as what the client saw.`
                  : "this updates the Draft in place -- nothing has reached the client yet."}
                {" "}Keeps the currently Client-approved sports; changing which sports are covered still needs a new Quotation.
              </p>
              <div className="flex items-center gap-2">
                <span>Discount (Rs)</span>
                <input
                  type="number"
                  value={reviseDrafts[q.id]?.discount_value ?? ""}
                  onChange={(e) =>
                    setReviseDrafts((d) => ({ ...d, [q.id]: { ...d[q.id], discount_value: e.target.value } }))
                  }
                  className="w-28 rounded border border-gray-300 px-1 py-0.5"
                />
              </div>
              {project.tender_mode && (
                <div className="flex items-center gap-2">
                  <span>GST basis (Part L)</span>
                  <select
                    value={reviseDrafts[q.id]?.gst_mode ?? q.gst_mode}
                    onChange={(e) =>
                      setReviseDrafts((d) => ({ ...d, [q.id]: { ...d[q.id], gst_mode: e.target.value } }))
                    }
                    className="rounded border border-gray-300 px-1 py-0.5"
                  >
                    <option value="exclusive">Exclusive</option>
                    <option value="inclusive">Inclusive</option>
                  </select>
                </div>
              )}
              <label className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={reviseDrafts[q.id]?.refresh_pricing ?? false}
                  onChange={(e) =>
                    setReviseDrafts((d) => ({ ...d, [q.id]: { ...d[q.id], refresh_pricing: e.target.checked } }))
                  }
                />
                Refresh pricing from current settings (otherwise unchanged figures stay frozen)
              </label>
              <button
                onClick={() => handleRevise(q)}
                className="bg-blue-600 text-white rounded px-3 py-1 hover:bg-blue-700"
              >
                Create revision
              </button>
            </div>
          )}
          {openAttachmentsFor === q.id && <AttachmentsPanel token={token} docType="quotation" docId={q.id} />}
          {openMessagesFor === q.id && <MessagesPanel token={token} docType="quotation" docId={q.id} />}
          {q.status === "won" && role !== "sales" && <WorkOrderPanel token={token} quotationId={q.id} />}
        </div>
      ))}

      {approvableOptions.length > 0 ? (
        <div className="flex items-center gap-2">
          <select
            value={selectedEstimateId}
            onChange={(e) => setSelectedEstimateId(e.target.value)}
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">Select estimate…</option>
            {estimates.map((est) => (
              <option key={est.id} value={est.id}>
                {est.document_no}
              </option>
            ))}
          </select>
          <input
            type="number"
            placeholder="Discount (Rs, optional)"
            value={discountValue}
            onChange={(e) => setDiscountValue(e.target.value)}
            className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm"
          />
          {project.tender_mode && (
            <select
              value={gstMode}
              onChange={(e) => setGstMode(e.target.value)}
              title="Part L: Inclusive/exclusive GST toggle"
              className="rounded border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="exclusive">GST exclusive</option>
              <option value="inclusive">GST inclusive</option>
            </select>
          )}
          <button
            onClick={handleCreate}
            disabled={!selectedEstimateId}
            className="bg-blue-600 text-white text-xs rounded px-3 py-2 hover:bg-blue-700 disabled:opacity-50"
          >
            Create Quotation
          </button>
        </div>
      ) : (
        <p className="text-xs text-gray-400">
          Requires at least one Client-approved or demand-received estimate option (M.2 rule 2).
        </p>
      )}
    </div>
  );
}

const WORK_ORDER_NEXT_STATUS = { awarded: "in_progress", in_progress: "completed" };
const WORK_ORDER_STATUS_LABEL = { awarded: "Awarded", in_progress: "In progress", completed: "Completed" };

function WorkOrderPanel({ token, quotationId }) {
  const [workOrder, setWorkOrder] = useState(null);
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAttachments, setShowAttachments] = useState(false);
  const [entryForm, setEntryForm] = useState({ milestone_name: "", amount_received: "", received_date: "", gst_tds_amount: "", notes: "" });

  function load() {
    return getWorkOrder(token, quotationId).then((wo) => {
      setWorkOrder(wo);
      return wo ? listWorkOrderPaymentEntries(token, wo.id) : [];
    });
  }

  useEffect(() => {
    setLoading(true);
    load()
      .then(setEntries)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, quotationId]);

  async function refresh() {
    setError("");
    try {
      setEntries(await load());
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleCreate() {
    setError("");
    try {
      await createWorkOrder(token, quotationId);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleAdvanceStatus() {
    setError("");
    try {
      await updateWorkOrderStatus(token, workOrder.id, WORK_ORDER_NEXT_STATUS[workOrder.status]);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleAddEntry(e) {
    e.preventDefault();
    setError("");
    try {
      await addWorkOrderPaymentEntry(token, workOrder.id, {
        milestone_name: entryForm.milestone_name,
        amount_received: Number(entryForm.amount_received),
        received_date: entryForm.received_date,
        gst_tds_amount: entryForm.gst_tds_amount ? Number(entryForm.gst_tds_amount) : null,
        notes: entryForm.notes || null,
      });
      setEntryForm({ milestone_name: "", amount_received: "", received_date: "", gst_tds_amount: "", notes: "" });
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) {
    return <p className="text-xs text-gray-400">Loading work order…</p>;
  }

  return (
    <div className="border-t border-gray-200 pt-2 mt-1 space-y-2">
      <p className="text-xs font-semibold text-gray-600">Work Order &amp; Actuals (M.1 stage 4)</p>
      {error && <p className="text-xs text-red-600">{error}</p>}

      {!workOrder ? (
        <button onClick={handleCreate} className="bg-green-600 text-white text-xs rounded px-3 py-1.5 hover:bg-green-700">
          Create Work Order
        </button>
      ) : (
        <div className="space-y-2 text-xs">
          <div className="flex items-center gap-2">
            <StatusBadge status={workOrder.status} />
            <span className="text-gray-400">
              Awarded {new Date(workOrder.awarded_at).toLocaleDateString()}
            </span>
            {WORK_ORDER_NEXT_STATUS[workOrder.status] && (
              <button onClick={handleAdvanceStatus} className="text-blue-600 hover:underline">
                Move to {WORK_ORDER_STATUS_LABEL[WORK_ORDER_NEXT_STATUS[workOrder.status]]}
              </button>
            )}
            <button onClick={() => setShowAttachments((s) => !s)} className="text-gray-500 hover:underline">
              {showAttachments ? "Hide work order document" : "Work order document"}
            </button>
          </div>
          {showAttachments && <AttachmentsPanel token={token} docType="work_order" docId={workOrder.id} />}

          <div className="space-y-1">
            <p className="font-semibold text-gray-600">
              Payment reconciliation (not a blueprint RA-bill schema -- a lightweight milestone/amount/date log)
            </p>
            {entries.length === 0 && <p className="text-gray-400">No payments recorded yet.</p>}
            {entries.map((e) => (
              <div key={e.id} className="flex items-center justify-between border border-gray-100 rounded px-2 py-1">
                <span>
                  {e.milestone_name} · {e.received_date} {e.notes && `· ${e.notes}`}
                  {e.gst_tds_amount != null && ` · GST-TDS Rs ${e.gst_tds_amount.toLocaleString()}`}
                </span>
                <span className="font-medium">Rs {e.amount_received.toLocaleString()}</span>
              </div>
            ))}
            <form onSubmit={handleAddEntry} className="flex flex-wrap items-center gap-1">
              <input
                type="text"
                placeholder="Milestone"
                value={entryForm.milestone_name}
                onChange={(e) => setEntryForm((f) => ({ ...f, milestone_name: e.target.value }))}
                className="border border-gray-300 rounded px-1.5 py-1 w-28"
                required
              />
              <input
                type="number"
                placeholder="Amount"
                value={entryForm.amount_received}
                onChange={(e) => setEntryForm((f) => ({ ...f, amount_received: e.target.value }))}
                className="border border-gray-300 rounded px-1.5 py-1 w-24"
                required
              />
              <input
                type="date"
                value={entryForm.received_date}
                onChange={(e) => setEntryForm((f) => ({ ...f, received_date: e.target.value }))}
                className="border border-gray-300 rounded px-1.5 py-1"
                required
              />
              <input
                type="number"
                placeholder="GST-TDS (optional)"
                value={entryForm.gst_tds_amount}
                onChange={(e) => setEntryForm((f) => ({ ...f, gst_tds_amount: e.target.value }))}
                className="border border-gray-300 rounded px-1.5 py-1 w-32"
              />
              <input
                type="text"
                placeholder="Notes (optional)"
                value={entryForm.notes}
                onChange={(e) => setEntryForm((f) => ({ ...f, notes: e.target.value }))}
                className="border border-gray-300 rounded px-1.5 py-1 w-32"
              />
              <button type="submit" className="bg-blue-600 text-white rounded px-2 py-1 hover:bg-blue-700">
                Add
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }) {
  const colors = {
    draft: "bg-gray-100 text-gray-600",
    pending: "bg-gray-100 text-gray-600",
    verified: "bg-green-50 text-green-700",
    approved: "bg-green-50 text-green-700",
    won: "bg-green-50 text-green-700",
    released: "bg-blue-50 text-blue-700",
    sent: "bg-blue-50 text-blue-700",
    superseded: "bg-gray-100 text-gray-400",
    rejected: "bg-red-50 text-red-700",
    lost: "bg-red-50 text-red-700",
    expired: "bg-red-50 text-red-700",
    demand_received: "bg-amber-50 text-amber-700",
  };
  return (
    <span className={`text-xs rounded px-1.5 py-0.5 ${colors[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}
