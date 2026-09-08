import { useEffect, useState } from "react";
import AttachmentsPanel from "./AttachmentsPanel";
import ClientSignatoriesPanel from "./ClientSignatoriesPanel";
import CostSheetBuilder from "./CostSheetBuilder";
import MessagesPanel from "./MessagesPanel";
import {
  createCostSheet,
  createEstimate,
  createQuotation,
  downloadEstimatePdfBlob,
  downloadQuotationPdfBlob,
  listCostSheets,
  listEstimates,
  listProjectSports,
  listQuotations,
  listSports,
  markQuotationLost,
  markQuotationWon,
  releaseQuotation,
  reviseCostSheet,
  sendEstimate,
  sendQuotation,
  updateEstimateOptionClientStatus,
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

export default function Documents({ token, project, role, onBack }) {
  const [projectSports, setProjectSports] = useState([]);
  const [sports, setSports] = useState([]);
  const [costSheets, setCostSheets] = useState([]);
  const [estimates, setEstimates] = useState([]);
  const [quotations, setQuotations] = useState([]);
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
    ]).then(([ps, s, cs, est, quo]) => {
      setProjectSports(ps);
      setSports(s);
      setCostSheets(cs);
      setEstimates(est);
      setQuotations(quo);
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
            costSheets={costSheets}
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

function CostSheetPanel({ token, project, costSheets, onAction, onBuild }) {
  const [costTotal, setCostTotal] = useState("");
  const [openAttachmentsFor, setOpenAttachmentsFor] = useState(null);
  const [openMessagesFor, setOpenMessagesFor] = useState(null);
  const active = costSheets.find((c) => c.status !== "superseded");

  const handleCreate = onAction(async () => {
    await createCostSheet(token, project.id, { cost_total: Number(costTotal) });
    setCostTotal("");
  });
  const handleCreateEmpty = onAction(async () => {
    const created = await createCostSheet(token, project.id, {});
    onBuild(created);
  });
  const handleVerify = onAction(async (id) => verifyCostSheet(token, id));
  const handleRevise = onAction(async (id) => {
    await reviseCostSheet(token, id, { cost_total: Number(costTotal) });
    setCostTotal("");
  });

  return (
    <div className="bg-white shadow rounded-lg p-6 space-y-3">
      <h3 className="text-sm font-semibold text-gray-700">Cost Sheet (M.1 stage 1)</h3>
      {costSheets.map((cs) => (
        <div key={cs.id} className="border border-gray-200 rounded px-3 py-2 text-sm space-y-2">
          <div className="flex items-center justify-between">
            <span>
              {cs.document_no} · Rs {cs.cost_total.toLocaleString()} ·{" "}
              <StatusBadge status={cs.status} />
            </span>
            <div className="flex items-center gap-3">
              {cs.status === "draft" && (
                <>
                  <button onClick={() => onBuild(cs)} className="text-xs text-blue-600 hover:underline">
                    Build from take-off
                  </button>
                  <button onClick={() => handleVerify(cs.id)} className="text-xs text-blue-600 hover:underline">
                    Verify
                  </button>
                </>
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
            </div>
          </div>
          {openAttachmentsFor === cs.id && <AttachmentsPanel token={token} docType="cost_sheet" docId={cs.id} />}
          {openMessagesFor === cs.id && <MessagesPanel token={token} docType="cost_sheet" docId={cs.id} />}
        </div>
      ))}
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
      {!active && (
        <button
          onClick={handleCreateEmpty}
          className="w-full text-xs text-blue-600 hover:underline text-center py-1"
        >
          …or start an empty Cost Sheet and build it up from Structures/Base/Flooring/etc. take-offs
        </button>
      )}
    </div>
  );
}

function EstimatePanel({ token, project, role, activeCostSheet, projectSports, sportsById, estimates, onAction }) {
  const [optionForm, setOptionForm] = useState({ project_sport_id: "", package: "standard", cost_for_option: "" });
  const [openAttachmentsFor, setOpenAttachmentsFor] = useState(null);
  const [openMessagesFor, setOpenMessagesFor] = useState(null);
  const [waiverReasons, setWaiverReasons] = useState({});
  const [pdfError, setPdfError] = useState("");
  const canWaive = role === "pm" || role === "director";

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
  const handleClientStatus = onAction(async (estimateId, optionId, client_status, waiveEvidenceReason) =>
    updateEstimateOptionClientStatus(token, estimateId, optionId, {
      client_status,
      ...(waiveEvidenceReason ? { waive_evidence_reason: waiveEvidenceReason } : {}),
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
            </span>
            <div className="flex items-center gap-3">
              {est.status === "draft" && (
                <button onClick={() => handleSend(est.id)} className="text-xs text-blue-600 hover:underline">
                  Send
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
          {est.options.map((opt) => (
            <div key={opt.id} className="flex flex-wrap items-center justify-between gap-2 text-xs bg-gray-50 rounded px-2 py-1">
              <span>
                {sportNameByProjectSportId[opt.project_sport_id] ?? opt.project_sport_id} ({opt.package}): Rs{" "}
                {opt.price_low.toLocaleString()} - Rs {opt.price_high.toLocaleString()} incl. GST ·{" "}
                <StatusBadge status={opt.client_status} />
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
                <button onClick={() => handleClientStatus(est.id, opt.id, "rejected")} className="text-red-700 hover:underline">
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      ))}

      {activeCostSheet?.status === "verified" ? (
        <div className="space-y-2">
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
  const [openAttachmentsFor, setOpenAttachmentsFor] = useState(null);
  const [openMessagesFor, setOpenMessagesFor] = useState(null);
  const [waiverReasons, setWaiverReasons] = useState({});
  const [pdfError, setPdfError] = useState("");
  const canWaive = role === "pm" || role === "director";

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
    });
    setDiscountValue("");
  });
  const handleRelease = onAction(async (id) => releaseQuotation(token, id));
  const handleSend = onAction(async (id) => sendQuotation(token, id));
  const handleWon = onAction(async (id, waiveEvidenceReason) =>
    markQuotationWon(token, id, { reason: "Client accepted", waiveEvidenceReason })
  );
  const handleLost = onAction(async (id) => markQuotationLost(token, id, "Client declined"));

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
          </div>
          {openAttachmentsFor === q.id && <AttachmentsPanel token={token} docType="quotation" docId={q.id} />}
          {openMessagesFor === q.id && <MessagesPanel token={token} docType="quotation" docId={q.id} />}
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
    demand_received: "bg-amber-50 text-amber-700",
  };
  return (
    <span className={`text-xs rounded px-1.5 py-0.5 ${colors[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}
