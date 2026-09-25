import { useEffect, useState } from "react";
import AttachmentsPanel from "./AttachmentsPanel";
import PaymentsDetail from "./PaymentsDetail";
import ClientSignatoriesPanel from "./ClientSignatoriesPanel";
import CostSheetBuilder from "./CostSheetBuilder";
import CoverNotePanel from "./CoverNotePanel";
import MessagesPanel from "./MessagesPanel";
import {
  addCostSheetLine,
  addEstimateOption,
  addEstimateOptionAddon,
  approveSkipRequest,
  createCostSheet,
  createEstimate,
  createFastTrackQuotation,
  createQuotation,
  createSkipRequest,
  createWorkOrder,
  downloadEstimatePdfBlob,
  downloadQuotationPdfBlob,
  getL1View,
  getWorkOrder,
  listCostSheetLines,
  listCostSheets,
  listEstimateOptionAddons,
  listEstimates,
  listProjectSports,
  listQuotations,
  listSkipRequests,
  listSports,
  listSuggestedAddonsForProject,
  markQuotationLost,
  markQuotationWon,
  rebaseEstimate,
  rejectCostSheet,
  rejectQuotation,
  releaseQuotation,
  removeEstimateOption,
  removeEstimateOptionAddon,
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
    <div className="border border-red-500/30 bg-red-500/10 rounded p-2 space-y-2 text-xs">
      <div className="flex items-center gap-2">
        <select
          value={reasonCategory}
          onChange={(e) => setReasonCategory(e.target.value)}
          className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1"
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
          className="flex-1 rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1"
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
        <button onClick={onCancel} className="text-text-secondary hover:underline">
          Cancel
        </button>
      </div>
    </div>
  );
}

export default function Documents({ token, project, role, onBack, onOpenPayments }) {
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
    return <p className="text-center text-text-secondary mt-10">Loading documents…</p>;
  }

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Documents</h2>
            <p className="text-sm text-text-secondary">
              Project <span className="font-mono">{project.project_no}</span>
            </p>
          </div>
          <button onClick={onBack} className="text-sm text-gold hover:underline">
            &larr; Back
          </button>
        </div>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
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
            estimates={estimates}
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
            quotations={quotations}
            onAction={withErrorHandling}
          />

          <QuotationPanel
            token={token}
            project={project}
            role={role}
            estimates={estimates}
            quotations={quotations}
            activeCostSheet={activeCostSheet}
            sportNames={Object.fromEntries(
              projectSports.map((ps) => [ps.id, sportsById[ps.sport_id]?.name ?? ps.sport_id])
            )}
            onAction={withErrorHandling}
            onOpenPayments={onOpenPayments}
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

  if (loading) return <p className="text-xs text-text-secondary">Loading lines…</p>;

  return (
    <div className="border border-dashed border-border-dark bg-surface-raised text-text-primary rounded p-3 space-y-2 bg-surface-raised text-xs">
      <p className="font-semibold text-text-secondary">
        Cost Sheet lines (K.3 Rate-blind mode) {isSales && "-- rates are hidden from you by design"}
      </p>
      {error && <p className="text-red-400">{error}</p>}
      {lines.map((l) => (
        <div key={l.id} className="flex flex-wrap items-center justify-between gap-2 bg-surface rounded px-2 py-1 border border-border-dark">
          <span>
            {l.category} · {l.item_name} · {l.quantity} {l.unit}
            {l.pending && <span className="text-amber-400"> · pending PM rate</span>}
            {!isSales && !l.pending && <span className="text-text-secondary"> · Rs {l.rate}/unit = Rs {l.amount.toLocaleString()}</span>}
          </span>
          {!isSales && l.pending && (
            <div className="flex items-center gap-1">
              <input
                type="number" placeholder="Rate"
                value={rateDrafts[l.id] || ""}
                onChange={(e) => setRateDrafts((d) => ({ ...d, [l.id]: e.target.value }))}
                className="border border-border-dark bg-surface-raised text-text-primary rounded px-1 py-0.5 w-20"
              />
              <button onClick={() => handleSetRate(l.id)} disabled={!rateDrafts[l.id]} className="text-gold hover:underline disabled:opacity-50">
                Set rate
              </button>
            </div>
          )}
        </div>
      ))}
      {lines.length === 0 && <p className="text-text-secondary">No lines proposed yet.</p>}

      {isSales && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <select value={form.work_package} onChange={(e) => setForm((f) => ({ ...f, work_package: e.target.value }))} className="border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1">
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
          <input placeholder="Category" value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} className="border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1 w-24" />
          <input placeholder="Item" value={form.item_name} onChange={(e) => setForm((f) => ({ ...f, item_name: e.target.value }))} className="border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1 flex-1 min-w-[120px]" />
          <input placeholder="Unit" value={form.unit} onChange={(e) => setForm((f) => ({ ...f, unit: e.target.value }))} className="border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1 w-16" />
          <input type="number" placeholder="Qty" value={form.quantity} onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))} className="border border-border-dark bg-surface-raised text-text-primary rounded px-2 py-1 w-20" />
          <button
            onClick={handlePropose}
            disabled={!form.category || !form.item_name || !form.unit || !form.quantity}
            className="bg-gold text-base rounded px-3 py-1.5 hover:bg-gold-hover disabled:opacity-50"
          >
            Propose line
          </button>
        </div>
      )}
    </div>
  );
}

function CostSheetPanel({ token, project, role, costSheets, skipRequests, estimates, onAction, onBuild }) {
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
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <h3 className="text-sm font-semibold text-text-secondary">Cost Sheet (M.1 stage 1)</h3>
      <StageHint text={costSheetHint(costSheets, skipRequests, estimates)} />
      {costSheets.map((cs) => (
        <div key={cs.id} className="border border-border-dark rounded px-3 py-2 text-sm space-y-2">
          <div className="flex items-center justify-between">
            <span>
              {cs.document_no}
              {cs.cost_total != null && <> · Rs {cs.cost_total.toLocaleString()}</>} ·{" "}
              <StatusBadge status={cs.status} />
              {cs.auto_generated && <span className="text-amber-400 text-xs"> · skip-generated</span>}
              {cs.sla_breached && (
                <span className="text-red-400 text-xs bg-red-500/10 rounded px-1.5 py-0.5 ml-1">
                  SLA breached (M.3) -- awaiting verification
                </span>
              )}
            </span>
            <div className="flex items-center gap-3">
              {role !== "sales" && (cs.status === "draft" || cs.status === "unverified") && (
                <>
                  <button onClick={() => onBuild(cs)} className="text-xs text-gold hover:underline">
                    Build from take-off
                  </button>
                  <button onClick={() => handleVerify(cs.id)} className="text-xs text-gold hover:underline">
                    Verify
                  </button>
                </>
              )}
              {canReject && (cs.status === "verified" || cs.status === "unverified") && (
                <button
                  onClick={() => setRejectFormFor(rejectFormFor === cs.id ? null : cs.id)}
                  className="text-xs text-red-400 hover:underline"
                >
                  Reject
                </button>
              )}
              <button
                onClick={() => setOpenAttachmentsFor(openAttachmentsFor === cs.id ? null : cs.id)}
                className="text-xs text-text-secondary hover:underline"
              >
                {openAttachmentsFor === cs.id ? "Hide attachments" : "Attachments"}
              </button>
              <button
                onClick={() => setOpenMessagesFor(openMessagesFor === cs.id ? null : cs.id)}
                className="text-xs text-text-secondary hover:underline"
              >
                {openMessagesFor === cs.id ? "Hide messages" : "Messages"}
              </button>
              {canSeeLines && (cs.status === "draft" || cs.status === "unverified") && (
                <button
                  onClick={() => setOpenLinesFor(openLinesFor === cs.id ? null : cs.id)}
                  className="text-xs text-text-secondary hover:underline"
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
      {/* Amendment 38 (Section 44): this one input/button pair does two jobs --
          "Create Cost Sheet" when none exists, and "Revise (new R+1)" for a
          Verified one. It used to stay on screen for a Draft/Unverified sheet
          too, as a live-looking input over a permanently greyed-out button.
          It now renders only when it can act, so the Revise flow is untouched
          (spec item 2) and the dead state is gone. */}
      {role !== "sales" && (!active || active.status === "verified") && (
        <div className="flex items-center gap-2">
          <input
            type="number"
            placeholder="Cost incl. contingency (Rs)"
            value={costTotal}
            onChange={(e) => setCostTotal(e.target.value)}
            className="flex-1 rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
          />
          {active ? (
            <button
              onClick={() => handleRevise(active.id)}
              className="bg-gold text-base text-xs rounded px-3 py-2 hover:bg-gold-hover"
            >
              Revise (new R+1)
            </button>
          ) : (
            <button
              onClick={handleCreate}
              className="bg-gold text-base text-xs rounded px-3 py-2 hover:bg-gold-hover"
            >
              Create Cost Sheet
            </button>
          )}
        </div>
      )}
      {role !== "sales" && !active && (
        <button
          onClick={handleCreateEmpty}
          className="w-full text-xs text-gold hover:underline text-center py-1"
        >
          …or start an empty Cost Sheet and build it up from Structures/Base/Flooring/etc. take-offs
        </button>
      )}

      {!active && !pendingSkipRequest && (
        <div className="border-t border-border-dark pt-3 space-y-2">
          <p className="text-xs font-semibold text-text-secondary">
            Or: request to skip this stage (M.2 rule 3)
          </p>
          <p className="text-[11px] text-text-secondary">
            "Sales cannot skip alone" -- a PM or Director must approve before the Estimate stage can be created
            on an auto-generated (Unverified) Cost Sheet.
          </p>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Reason (e.g. client wants a quotation directly)"
              value={skipReason}
              onChange={(e) => setSkipReason(e.target.value)}
              className="flex-1 rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
            />
            <button
              onClick={handleRequestSkip}
              disabled={!skipReason}
              className="bg-surface-raised text-text-primary text-xs rounded px-3 py-2 hover:bg-border-dark disabled:opacity-50"
            >
              Request skip
            </button>
          </div>
        </div>
      )}

      {pendingSkipRequest && (
        <div className="border-t border-amber-500/30 bg-amber-500/10 rounded p-3 space-y-2 text-sm">
          <p className="font-semibold text-amber-400">Skip request pending</p>
          <p className="text-xs text-text-secondary">"{pendingSkipRequest.reason}"</p>
          {canApproveSkip ? (
            <div className="flex items-center gap-2">
              <input
                type="number"
                placeholder="Ballpark cost total (Rs)"
                value={approveCostTotal}
                onChange={(e) => setApproveCostTotal(e.target.value)}
                className="flex-1 rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
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
            <p className="text-xs text-text-secondary">Waiting for PM or Director approval.</p>
          )}
        </div>
      )}
    </div>
  );
}

const PACKAGE_LABELS = { budget: "Budget", standard: "Standard", premium: "Premium" };

// One sport / package / cost row -- used by Create Estimate (one per sport) and by "+ Add sport option".
function OptionRowFields({ row, projectSports, sportsById, onChange, idPrefix, onRemove }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        id={`${idPrefix}-sport`}
        aria-label="Sport"
        value={row.project_sport_id}
        onChange={(e) => onChange({ project_sport_id: e.target.value })}
        className="flex-1 min-w-[10rem] rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
      >
        <option value="">Select a sport…</option>
        {projectSports.map((ps) => (
          <option key={ps.id} value={ps.id}>
            {sportsById[ps.sport_id]?.name ?? ps.sport_id}
          </option>
        ))}
      </select>
      <select
        id={`${idPrefix}-package`}
        aria-label="Package"
        value={row.package}
        onChange={(e) => onChange({ package: e.target.value })}
        className="rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
      >
        {Object.entries(PACKAGE_LABELS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <input
        id={`${idPrefix}-cost`}
        aria-label="Cost for this option (Rs)"
        type="number"
        placeholder="Cost for this option (Rs)"
        value={row.cost_for_option}
        onChange={(e) => onChange({ cost_for_option: e.target.value })}
        className="flex-1 min-w-[10rem] rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
      />
      {onRemove && (
        <button onClick={onRemove} className="text-xs text-red-400 hover:underline">
          Remove
        </button>
      )}
    </div>
  );
}

function emptyOptionRow() {
  return { project_sport_id: "", package: "standard", cost_for_option: "" };
}

// Amendment 57 (Section 60): the rows of a new Estimate. Returns why the rows can't be submitted yet
// (empty string when they can): every row needs a sport and a cost, and the same sport with the same
// package twice is refused by the API -- a different package of one sport is an alternative.
function optionRowsProblem(rows) {
  const seen = new Set();
  for (const row of rows) {
    if (!row.project_sport_id || !(Number(row.cost_for_option) > 0)) return "Choose a sport and enter a cost for every option.";
    const key = `${row.project_sport_id}:${row.package}`;
    if (seen.has(key)) return "The same sport and package appears twice -- change one package or remove a row.";
    seen.add(key);
  }
  return "";
}

function formatRs(value) {
  return `Rs ${Math.round(value).toLocaleString("en-IN")}`;
}

function EstimatePanel({ token, project, role, activeCostSheet, projectSports, sportsById, estimates, quotations, onAction }) {
  const [optionRows, setOptionRows] = useState([emptyOptionRow()]);
  const [addOptionFor, setAddOptionFor] = useState(null); // estimateId whose "add sport option" form is open
  const [addOptionRow, setAddOptionRow] = useState(emptyOptionRow());
  const [openAttachmentsFor, setOpenAttachmentsFor] = useState(null);
  const [openMessagesFor, setOpenMessagesFor] = useState(null);
  const [openOptionAttachmentsFor, setOpenOptionAttachmentsFor] = useState(null);
  const [openOptionAddonsFor, setOpenOptionAddonsFor] = useState(null);
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

  const updateOptionRow = (index, patch) =>
    setOptionRows((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  const optionRowsTotal = optionRows.reduce((sum, row) => sum + (Number(row.cost_for_option) || 0), 0);
  const optionRowsSportCount = new Set(optionRows.map((row) => row.project_sport_id).filter(Boolean)).size;
  const rowsProblem = optionRowsProblem(optionRows);
  // A sport listed with two packages means the rows are alternatives, so their sum is not what the
  // job costs -- only compare with the Cost Sheet when every sport appears once.
  const rowsAreAlternatives = optionRowsSportCount < optionRows.filter((row) => row.project_sport_id).length;
  const costSheetTotal = activeCostSheet?.cost_total;
  const totalDiffers =
    !rowsAreAlternatives && optionRows.length > 1 && costSheetTotal != null && Math.abs(optionRowsTotal - costSheetTotal) >= 1;

  const handleCreate = onAction(async () => {
    await createEstimate(token, project.id, {
      options: optionRows.map((row) => ({
        project_sport_id: row.project_sport_id,
        package: row.package,
        cost_for_option: Number(row.cost_for_option),
      })),
    });
    setOptionRows([emptyOptionRow()]);
  });
  const handleAddOption = onAction(async (estimateId) => {
    await addEstimateOption(token, estimateId, {
      project_sport_id: addOptionRow.project_sport_id,
      package: addOptionRow.package,
      cost_for_option: Number(addOptionRow.cost_for_option),
    });
    setAddOptionFor(null);
    setAddOptionRow(emptyOptionRow());
  });
  const handleRemoveOption = onAction(async (estimateId, optionId) => removeEstimateOption(token, estimateId, optionId));
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
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <h3 className="text-sm font-semibold text-text-secondary">Estimate (M.1 stage 2)</h3>
      <StageHint text={estimateHint(activeCostSheet, estimates, quotations)} />
      {pdfError && <p className="text-xs text-red-400">{pdfError}</p>}

      {estimates.map((est) => (
        <div key={est.id} className="border border-border-dark rounded px-3 py-2 text-sm space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span>
              {est.document_no} · <StatusBadge status={est.status} /> · client:{" "}
              <StatusBadge status={est.client_status} />
              {est.cost_basis_rebase_required && (
                <span className="text-red-400 text-xs"> · cost basis changed — rebase required</span>
              )}
            </span>
            <div className="flex flex-wrap items-center gap-3">
              {est.cost_basis_rebase_required && (
                <button onClick={() => handleRebase(est.id)} className="text-xs text-red-400 hover:underline">
                  Rebase
                </button>
              )}
              {est.status === "draft" && canRevise && (
                <button
                  onClick={() => {
                    setAddOptionRow(emptyOptionRow());
                    setAddOptionFor(addOptionFor === est.id ? null : est.id);
                  }}
                  className="text-xs text-gold hover:underline"
                >
                  {addOptionFor === est.id ? "Cancel add" : "+ Add sport option"}
                </button>
              )}
              {est.status === "draft" && (
                <button onClick={() => handleSend(est.id)} className="text-xs text-gold hover:underline">
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
                  className="text-xs text-gold hover:underline"
                >
                  {openReviseFor === est.id ? "Cancel revise" : "Revise"}
                </button>
              )}
              <button onClick={() => handleDownloadPdf(est)} className="text-xs text-gold hover:underline">
                Download PDF
              </button>
              <button
                onClick={() => setOpenAttachmentsFor(openAttachmentsFor === est.id ? null : est.id)}
                className="text-xs text-text-secondary hover:underline"
              >
                {openAttachmentsFor === est.id ? "Hide attachments" : "Attachments"}
              </button>
              <button
                onClick={() => setOpenMessagesFor(openMessagesFor === est.id ? null : est.id)}
                className="text-xs text-text-secondary hover:underline"
              >
                {openMessagesFor === est.id ? "Hide messages" : "Messages"}
              </button>
            </div>
          </div>
          {openAttachmentsFor === est.id && <AttachmentsPanel token={token} docType="estimate" docId={est.id} />}
          {openMessagesFor === est.id && <MessagesPanel token={token} docType="estimate" docId={est.id} />}
          {addOptionFor === est.id && (
            <div className="bg-surface-raised rounded px-3 py-2 space-y-2 text-xs">
              <p className="text-text-secondary">
                Add another sport (or another package of a sport) to this Draft Estimate. Once it is sent, changes
                need a revision.
              </p>
              <OptionRowFields
                row={addOptionRow}
                projectSports={projectSports}
                sportsById={sportsById}
                onChange={(patch) => setAddOptionRow((r) => ({ ...r, ...patch }))}
                idPrefix={`add-${est.id}`}
              />
              <button
                onClick={() => handleAddOption(est.id)}
                disabled={
                  !addOptionRow.project_sport_id ||
                  !(Number(addOptionRow.cost_for_option) > 0) ||
                  est.options.some(
                    (o) => o.project_sport_id === addOptionRow.project_sport_id && o.package === addOptionRow.package
                  )
                }
                className="bg-gold text-base text-xs rounded px-3 py-1.5 hover:bg-gold-hover disabled:opacity-50"
              >
                Add option
              </button>
              {est.options.some(
                (o) => o.project_sport_id === addOptionRow.project_sport_id && o.package === addOptionRow.package
              ) && (
                <p className="text-amber-400">
                  That sport and package is already on this Estimate -- pick another package.
                </p>
              )}
            </div>
          )}
          {openReviseFor === est.id && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded px-3 py-2 space-y-2 text-xs">
              <p className="text-amber-400">
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
                    className="w-32 rounded border border-border-dark bg-surface-raised text-text-primary px-1 py-0.5"
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
                className="bg-gold text-base rounded px-3 py-1 hover:bg-gold-hover"
              >
                Create revision
              </button>
            </div>
          )}
          {est.options.map((opt) => (
            <div key={opt.id} className="space-y-1">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs bg-surface-raised rounded px-2 py-1">
                <span>
                  {sportNameByProjectSportId[opt.project_sport_id] ?? opt.project_sport_id} ({opt.package}): Rs{" "}
                  {opt.price_low.toLocaleString()} - Rs {opt.price_high.toLocaleString()} incl. GST ·{" "}
                  <StatusBadge status={opt.client_status} />
                  {opt.rejection_reason && (
                    <span className="text-text-secondary"> ({opt.rejection_reason})</span>
                  )}
                </span>
                <div className="flex flex-wrap items-center gap-1">
                  {canWaive && (
                    <input
                      type="text"
                      placeholder="waiver reason (PM/Director)"
                      value={waiverReasons[opt.id] || ""}
                      onChange={(e) => setWaiverReasons((w) => ({ ...w, [opt.id]: e.target.value }))}
                      className="text-xs border border-border-dark bg-surface-raised text-text-primary rounded px-1 py-0.5 w-40"
                    />
                  )}
                  <button
                    onClick={() => handleClientStatus(est.id, opt.id, "approved", waiverReasons[opt.id])}
                    className="text-green-400 hover:underline"
                  >
                    Approve
                  </button>
                  <select
                    value={rejectionReasons[opt.id] || ""}
                    onChange={(e) => setRejectionReasons((r) => ({ ...r, [opt.id]: e.target.value }))}
                    className="text-xs border border-border-dark bg-surface-raised text-text-primary rounded px-1 py-0.5"
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
                    className="text-red-400 hover:underline disabled:text-text-secondary disabled:cursor-not-allowed"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => setOpenOptionAttachmentsFor(openOptionAttachmentsFor === opt.id ? null : opt.id)}
                    className="text-text-secondary hover:underline"
                  >
                    {openOptionAttachmentsFor === opt.id ? "Hide photo" : "Product photo"}
                  </button>
                  <button
                    onClick={() => setOpenOptionAddonsFor(openOptionAddonsFor === opt.id ? null : opt.id)}
                    className="text-text-secondary hover:underline"
                  >
                    {openOptionAddonsFor === opt.id ? "Hide add-ons" : "Add-ons"}
                  </button>
                  {canRevise && est.status === "draft" && est.options.length > 1 && opt.client_status === "pending" && (
                    <button
                      onClick={() => handleRemoveOption(est.id, opt.id)}
                      className="text-red-400 hover:underline"
                      title="Remove this sport option from the Draft Estimate"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>
              {openOptionAttachmentsFor === opt.id && (
                <AttachmentsPanel token={token} docType="estimate_option" docId={opt.id} />
              )}
              {openOptionAddonsFor === opt.id && (
                <OptionAddons token={token} projectId={project.id} optionId={opt.id} />
              )}
            </div>
          ))}
        </div>
      ))}

      {activeCostSheet?.status === "verified" || activeCostSheet?.status === "unverified" ? (
        <div className="space-y-2">
          {activeCostSheet?.status === "unverified" && (
            <p className="text-[11px] text-amber-400 bg-amber-500/10 rounded px-2 py-1">
              This Cost Sheet is Unverified (skip-generated, M.2 rule 3) -- the resulting Quotation will need
              Director release and can't be marked Won until it's Verified.
            </p>
          )}
          {canRevise ? (
            <>
              <p className="text-xs text-text-secondary">
                One Estimate can cover several sports. Add a row for each sport; use two rows of the same sport for
                alternative packages the client compares.
              </p>
              {optionRows.map((row, index) => (
                <div key={index} className="space-y-1">
                  <OptionRowFields
                    row={row}
                    projectSports={projectSports}
                    sportsById={sportsById}
                    onChange={(patch) => updateOptionRow(index, patch)}
                    idPrefix={`new-${index}`}
                    onRemove={optionRows.length > 1 ? () => setOptionRows((rows) => rows.filter((_, i) => i !== index)) : null}
                  />
                </div>
              ))}
              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={() => setOptionRows((rows) => [...rows, emptyOptionRow()])}
                  className="text-xs text-gold hover:underline"
                >
                  + Add another sport
                </button>
                {optionRows.length > 1 && (
                  <span className="text-xs text-text-secondary">Options total {formatRs(optionRowsTotal)}</span>
                )}
              </div>
              {totalDiffers && (
                <p className="text-[11px] text-amber-400 bg-amber-500/10 rounded px-2 py-1">
                  The options add up to {formatRs(optionRowsTotal)}, but the active Cost Sheet is {formatRs(costSheetTotal)}.
                  You can still create the Estimate.
                </p>
              )}
              {optionRows.length > 1 && rowsProblem && <p className="text-[11px] text-amber-400">{rowsProblem}</p>}
              <button
                onClick={handleCreate}
                disabled={Boolean(rowsProblem)}
                className="bg-gold text-base text-xs rounded px-3 py-2 hover:bg-gold-hover disabled:opacity-50"
              >
                Create Estimate
              </button>
            </>
          ) : (
            <p className="text-xs text-text-secondary">Only a PM or Director creates an Estimate (it carries costs).</p>
          )}
        </div>
      ) : (
        <p className="text-xs text-text-secondary">Requires a Verified cost sheet (M.2 rule 1).</p>
      )}
    </div>
  );
}

// Amendment 3 (Section 7): "Complete Your Facility" -- up to 5 sport-matched
// suggestions, one-tap add, a separate "Optional add-ons" subtotal (never
// folded into the option's own price range -- that range stays exactly what
// M.1 already computes). K.3: cost/margin come back null for Sales; the
// selling price is still shown so the persuasion tool still works for them.
function OptionAddons({ token, projectId, optionId }) {
  const [suggestions, setSuggestions] = useState([]);
  const [added, setAdded] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  function load() {
    return Promise.all([
      listSuggestedAddonsForProject(token, projectId),
      listEstimateOptionAddons(token, optionId),
    ]).then(([s, a]) => {
      setSuggestions(s);
      setAdded(a);
    });
  }

  useEffect(() => {
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, optionId]);

  const addedAddonIds = new Set(added.map((row) => row.addon_id));
  const addonsSubtotal = added.reduce((sum, row) => sum + row.selling_price, 0);

  async function handleAdd(addonId) {
    setError("");
    setBusyId(addonId);
    try {
      await addEstimateOptionAddon(token, optionId, addonId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function handleRemove(rowId) {
    setError("");
    setBusyId(rowId);
    try {
      await removeEstimateOptionAddon(token, rowId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  if (loading) {
    return <p className="text-xs text-text-secondary px-2 py-1">Loading add-ons…</p>;
  }

  return (
    <div className="bg-surface-raised rounded px-2 py-2 text-xs space-y-2">
      {error && <p className="text-red-400">{error}</p>}

      {added.length > 0 && (
        <div className="space-y-1">
          <p className="font-medium text-text-secondary">Optional add-ons on this option</p>
          {added.map((row) => (
            <div key={row.id} className="flex items-center justify-between bg-surface rounded px-2 py-1">
              <span>
                {row.name}
                {row.unit ? ` (${row.unit})` : ""} · Rs {Math.round(row.selling_price).toLocaleString()}
              </span>
              <button
                onClick={() => handleRemove(row.id)}
                disabled={busyId === row.id}
                className="text-red-400 hover:underline disabled:opacity-50"
              >
                Remove
              </button>
            </div>
          ))}
          <p className="text-text-secondary">
            Add-ons subtotal: Rs {Math.round(addonsSubtotal).toLocaleString()} (shown separately, not folded into
            the price range above)
          </p>
        </div>
      )}

      <div className="space-y-1">
        <p className="font-medium text-text-secondary">Suggested for this project</p>
        {suggestions.filter((s) => !addedAddonIds.has(s.id)).length === 0 ? (
          <p className="text-text-secondary">
            {suggestions.length === 0 ? "No matching add-ons in the catalog yet." : "All suggestions already added."}
          </p>
        ) : (
          suggestions
            .filter((s) => !addedAddonIds.has(s.id))
            .map((s) => (
              <div key={s.id} className="flex items-center justify-between bg-surface rounded px-2 py-1">
                <span>
                  {s.name}
                  {s.unit ? ` (${s.unit})` : ""} · Rs {Math.round(s.selling_price).toLocaleString()}
                  {s.description && <span className="text-text-secondary"> — {s.description}</span>}
                </span>
                <button
                  onClick={() => handleAdd(s.id)}
                  disabled={busyId === s.id}
                  className="text-gold hover:underline disabled:opacity-50"
                >
                  + Add
                </button>
              </div>
            ))
        )}
      </div>
    </div>
  );
}

function QuotationPanel({ token, project, role, estimates, quotations, activeCostSheet, sportNames, onAction, onOpenPayments }) {
  const [selectedEstimateId, setSelectedEstimateId] = useState("");
  const [packageChoice, setPackageChoice] = useState({}); // project_sport_id -> option id (only needed when a sport has several approved packages)
  const [discountValue, setDiscountValue] = useState("");
  const [gstMode, setGstMode] = useState("exclusive");
  const [fastTrackPackage, setFastTrackPackage] = useState("standard");
  const [openAttachmentsFor, setOpenAttachmentsFor] = useState(null);
  const [openMessagesFor, setOpenMessagesFor] = useState(null);
  const [openCoverNoteFor, setOpenCoverNoteFor] = useState(null);
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

  // Amendment 57 (Section 60): a Quotation carries one package per sport. Group the approved options of
  // the chosen Estimate by sport; a sport with a single approved package is included as is, one with
  // several needs a choice.
  const sportGroups = [];
  for (const o of estimates.find((e) => e.id === selectedEstimateId)?.options ?? []) {
    if (o.client_status !== "approved" && o.client_status !== "demand_received") continue;
    let group = sportGroups.find((g) => g.projectSportId === o.project_sport_id);
    if (!group) {
      group = { projectSportId: o.project_sport_id, options: [] };
      sportGroups.push(group);
    }
    group.options.push(o);
  }
  const chosenOptions = sportGroups.map((g) =>
    g.options.length === 1 ? g.options[0] : g.options.find((o) => o.id === packageChoice[g.projectSportId])
  );
  const allSportsChosen = sportGroups.length > 0 && chosenOptions.every(Boolean);

  const handleCreate = onAction(async () => {
    await createQuotation(token, project.id, {
      estimate_id: selectedEstimateId,
      included_option_ids: chosenOptions.map((o) => o.id),
      ...(discountValue ? { discount_type: "amount", discount_value: Number(discountValue) } : {}),
      ...(project.tender_mode ? { gst_mode: gstMode } : {}),
    });
    setDiscountValue("");
    setPackageChoice({});
  });
  const handleFastTrack = onAction(async () => {
    await createFastTrackQuotation(token, project.id, {
      cost_sheet_id: activeCostSheet.id,
      package: fastTrackPackage,
    });
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
  const handleCoverNoteSaved = onAction(async () => {});
  const handleRevise = onAction(async (quotation) => {
    const draft = reviseDrafts[quotation.id] || {};
    // The API can revise onto any option set; this form keeps the options this Quotation already
    // includes (those still Client approved / demand received) rather than exposing a full line
    // editor here -- changing which sports a Quotation covers still needs a fresh /quotations POST.
    // (Amendment 57: not "every approved option of the Estimate" -- that would put two packages of
    // one sport in.)
    const estimate = estimates.find((e) => e.id === quotation.estimate_id);
    const includedIds = (estimate?.options ?? [])
      .filter(
        (o) =>
          quotation.included_option_ids.includes(o.id) &&
          (o.client_status === "approved" || o.client_status === "demand_received")
      )
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
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <h3 className="text-sm font-semibold text-text-secondary">Quotation (M.1 stage 3)</h3>
      <StageHint
        text={quotationHint(
          estimates,
          quotations,
          ["resurfacing", "repair"].includes(project.project_type) && activeCostSheet?.status === "verified"
        )}
      />
      {pdfError && <p className="text-xs text-red-400">{pdfError}</p>}

      {quotations.map((q) => (
        <div key={q.id} className="border border-border-dark rounded px-3 py-2 text-sm space-y-2">
          <div className="flex items-center justify-between">
            <span>
              {q.document_no} · <StatusBadge status={q.status} />
              {q.below_floor && <span className="text-amber-400"> · below floor</span>}
              {q.cost_basis_rebase_required && (
                <span className="text-red-400"> · cost basis changed — rebase the Estimate</span>
              )}
              {q.sla_breached && (
                <span className="text-red-400 text-xs bg-red-500/10 rounded px-1.5 py-0.5 ml-1">
                  SLA breached (M.3) -- awaiting release
                </span>
              )}
              {q.gst_mode === "inclusive" && (
                <span className="text-gold-hover text-xs bg-gold-muted rounded px-1.5 py-0.5 ml-1">
                  GST inclusive (Part L)
                </span>
              )}
              {q.fast_track_flag && (
                <span
                  className="text-amber-400 text-xs bg-amber-500/10 rounded px-1.5 py-0.5 ml-1"
                  title="Small-job fast-track (M.2 rule 8): created directly from a Cost Sheet under standing PM pre-approval"
                >
                  Fast-track (M.2 rule 8)
                </span>
              )}
            </span>
            <span className="font-semibold">Rs {q.quotation_total.toLocaleString()}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {q.status === "draft" && (
              <button onClick={() => handleRelease(q.id)} className="text-gold hover:underline">
                Release
              </button>
            )}
            <button onClick={() => handleDownloadPdf(q)} className="text-gold hover:underline">
              Download PDF
            </button>
            {q.status === "released" && (
              <button onClick={() => handleSend(q.id)} className="text-gold hover:underline">
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
                    className="text-xs border border-border-dark bg-surface-raised text-text-primary rounded px-1 py-0.5 w-40"
                  />
                )}
                <button onClick={() => handleWon(q.id, waiverReasons[q.id])} className="text-green-400 hover:underline">
                  Mark Won
                </button>
                <button onClick={() => handleLost(q.id)} className="text-red-400 hover:underline">
                  Mark Lost
                </button>
              </>
            )}
            {canReject && (q.status === "released" || q.status === "sent") && (
              <button
                onClick={() => setRejectFormFor(rejectFormFor === q.id ? null : q.id)}
                className="text-red-400 hover:underline"
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
                className="text-gold hover:underline"
              >
                {openReviseFor === q.id ? "Cancel revise" : "Revise"}
              </button>
            )}
            <button
              onClick={() => setOpenCoverNoteFor(openCoverNoteFor === q.id ? null : q.id)}
              className="text-text-secondary hover:underline"
            >
              {openCoverNoteFor === q.id ? "Hide cover note" : "Cover Note"}
            </button>
            <button
              onClick={() => setOpenAttachmentsFor(openAttachmentsFor === q.id ? null : q.id)}
              className="text-text-secondary hover:underline"
            >
              {openAttachmentsFor === q.id ? "Hide attachments" : "Attachments"}
            </button>
            <button
              onClick={() => setOpenMessagesFor(openMessagesFor === q.id ? null : q.id)}
              className="text-text-secondary hover:underline"
            >
              {openMessagesFor === q.id ? "Hide messages" : "Messages"}
            </button>
            {project.tender_mode && (
              <button onClick={() => toggleL1View(q.id)} className="text-amber-400 hover:underline">
                {openL1For === q.id ? "Hide L1 view" : "L1 view (live)"}
              </button>
            )}
          </div>
          {l1Error && openL1For === q.id && <p className="text-xs text-red-400">{l1Error}</p>}
          {openL1For === q.id && l1Views[q.id] && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded px-3 py-2 text-xs space-y-1">
              <p className="text-amber-400 font-medium">
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
                <ul className="list-disc list-inside text-text-secondary">
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
            <div className="bg-amber-500/10 border border-amber-500/30 rounded px-3 py-2 space-y-2 text-xs">
              <p className="text-amber-400">
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
                  className="w-28 rounded border border-border-dark bg-surface-raised text-text-primary px-1 py-0.5"
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
                    className="rounded border border-border-dark bg-surface-raised text-text-primary px-1 py-0.5"
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
                className="bg-gold text-base rounded px-3 py-1 hover:bg-gold-hover"
              >
                Create revision
              </button>
            </div>
          )}
          {openCoverNoteFor === q.id && (
            <CoverNotePanel token={token} quotation={q} onSaved={handleCoverNoteSaved} />
          )}
          {openAttachmentsFor === q.id && <AttachmentsPanel token={token} docType="quotation" docId={q.id} />}
          {openMessagesFor === q.id && <MessagesPanel token={token} docType="quotation" docId={q.id} />}
          {q.status === "won" && role !== "sales" && (
            <WorkOrderPanel
              token={token}
              quotationId={q.id}
              canEditPayments={["pm", "director"].includes(role)}
              onOpenPayments={["pm", "director"].includes(role) ? onOpenPayments : undefined}
            />
          )}
        </div>
      ))}

      {approvableOptions.length > 0 ? (
        <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selectedEstimateId}
            onChange={(e) => {
              setSelectedEstimateId(e.target.value);
              setPackageChoice({});
            }}
            className="rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
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
            className="flex-1 rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
          />
          {project.tender_mode && (
            <select
              value={gstMode}
              onChange={(e) => setGstMode(e.target.value)}
              title="Part L: Inclusive/exclusive GST toggle"
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
            >
              <option value="exclusive">GST exclusive</option>
              <option value="inclusive">GST inclusive</option>
            </select>
          )}
          <button
            onClick={handleCreate}
            disabled={!selectedEstimateId || !allSportsChosen}
            className="bg-gold text-base text-xs rounded px-3 py-2 hover:bg-gold-hover disabled:opacity-50"
          >
            Create Quotation
          </button>
        </div>
        {selectedEstimateId && sportGroups.length > 0 && (
          <div className="text-xs space-y-1 bg-surface-raised rounded px-3 py-2">
            <p className="text-text-secondary">
              This quotation will include{" "}
              {sportGroups.length === 1 ? "this sport" : `these ${sportGroups.length} sports`}:
            </p>
            {sportGroups.map((g) => {
              const name = sportNames?.[g.projectSportId] ?? g.projectSportId;
              if (g.options.length === 1) {
                const o = g.options[0];
                return (
                  <p key={g.projectSportId}>
                    {name} ({PACKAGE_LABELS[o.package] ?? o.package}) · {formatRs(o.price_low)} - {formatRs(o.price_high)} incl. GST
                  </p>
                );
              }
              return (
                <fieldset key={g.projectSportId} className="space-y-1">
                  <legend className="text-amber-400">{name}: the client approved more than one package -- choose one</legend>
                  {g.options.map((o) => (
                    <label key={o.id} className="flex items-center gap-2">
                      <input
                        type="radio"
                        name={`package-${g.projectSportId}`}
                        checked={packageChoice[g.projectSportId] === o.id}
                        onChange={() => setPackageChoice((c) => ({ ...c, [g.projectSportId]: o.id }))}
                      />
                      {PACKAGE_LABELS[o.package] ?? o.package} · {formatRs(o.price_low)} - {formatRs(o.price_high)} incl. GST
                    </label>
                  ))}
                </fieldset>
              );
            })}
          </div>
        )}
        </div>
      ) : (
        <p className="text-xs text-text-secondary">
          Requires at least one Client-approved or demand-received estimate option (M.2 rule 2).
        </p>
      )}

      {["resurfacing", "repair"].includes(project.project_type) &&
        (role === "pm" || role === "director") &&
        activeCostSheet &&
        activeCostSheet.status === "verified" && (
          <div className="border-t pt-3 mt-1 flex items-center gap-2">
            <span className="text-xs text-text-secondary" title="M.2 rule 8">
              Fast-track ({activeCostSheet.document_no}) →
            </span>
            <select
              value={fastTrackPackage}
              onChange={(e) => setFastTrackPackage(e.target.value)}
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
            >
              <option value="budget">Budget</option>
              <option value="standard">Standard</option>
              <option value="premium">Premium</option>
            </select>
            <button
              onClick={handleFastTrack}
              title="Small-job fast-track (M.2 rule 8): Cost Sheet -> Quotation directly, under a standing PM pre-approval, for Resurfacing/Repair jobs below the Director-set limit."
              className="bg-amber-600 text-white text-xs rounded px-3 py-2 hover:bg-amber-700"
            >
              Fast-track to Quotation
            </button>
          </div>
        )}
    </div>
  );
}

const WORK_ORDER_NEXT_STATUS = { awarded: "in_progress", in_progress: "completed" };
const WORK_ORDER_STATUS_LABEL = { awarded: "Awarded", in_progress: "In progress", completed: "Completed" };

function WorkOrderPanel({ token, quotationId, canEditPayments, onOpenPayments }) {
  const [workOrder, setWorkOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAttachments, setShowAttachments] = useState(false);

  function load() {
    return getWorkOrder(token, quotationId).then(setWorkOrder);
  }

  useEffect(() => {
    setLoading(true);
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, quotationId]);

  async function refresh() {
    setError("");
    try {
      await load();
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

  if (loading) {
    return <p className="text-xs text-text-secondary">Loading work order…</p>;
  }

  return (
    <div className="border-t border-border-dark pt-2 mt-1 space-y-2">
      <p className="text-xs font-semibold text-text-secondary">Work Order &amp; Actuals (M.1 stage 4)</p>
      {error && <p className="text-xs text-red-400">{error}</p>}

      {!workOrder ? (
        <button onClick={handleCreate} className="bg-green-600 text-white text-xs rounded px-3 py-1.5 hover:bg-green-700">
          Create Work Order
        </button>
      ) : (
        <div className="space-y-2 text-xs">
          <div className="flex items-center gap-2">
            <StatusBadge status={workOrder.status} />
            <span className="text-text-secondary">
              Awarded {new Date(workOrder.awarded_at).toLocaleDateString()}
            </span>
            {WORK_ORDER_NEXT_STATUS[workOrder.status] && (
              <button onClick={handleAdvanceStatus} className="text-gold hover:underline">
                Move to {WORK_ORDER_STATUS_LABEL[WORK_ORDER_NEXT_STATUS[workOrder.status]]}
              </button>
            )}
            <button onClick={() => setShowAttachments((s) => !s)} className="text-text-secondary hover:underline">
              {showAttachments ? "Hide work order document" : "Work order document"}
            </button>
          </div>
          {showAttachments && <AttachmentsPanel token={token} docType="work_order" docId={workOrder.id} />}

          <div className="space-y-2 border-t border-border-dark pt-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold text-text-secondary">Payments</p>
              {onOpenPayments && (
                <button onClick={onOpenPayments} className="text-gold hover:underline">
                  Open in Payments →
                </button>
              )}
            </div>
            <PaymentsDetail
              token={token}
              workOrderId={workOrder.id}
              canEdit={canEditPayments}
              idPrefix={`wo-panel-${workOrder.id}`}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// Amendment 40 (Section 46): a plain-language "what's next" line under each
// stage header, computed purely from the status data each panel already
// holds -- no new endpoint, no new field, visible to every role. Never
// contradicts the badge next to it: every branch keys off the same status
// values the badges print, and a state with no honest hint returns null
// rather than guessing.
function costSheetHint(costSheets, skipRequests, estimates) {
  const active = costSheets.find((c) => c.status !== "superseded");
  if (!active) {
    if (skipRequests.some((r) => r.status === "pending")) {
      return "Skip requested -- awaiting PM/Director approval.";
    }
    return "Awaiting PM/Director to build the Cost Sheet.";
  }
  // Once an Estimate exists the next move has moved on to the Estimate stage.
  const hasEstimate = estimates.some((e) => e.status !== "superseded");
  if (active.status === "verified") {
    return hasEstimate ? "Verified -- the Estimate is below." : "Ready -- an Estimate can now be created.";
  }
  // A skip-generated Cost Sheet is Unverified but already permits the next
  // stage (M.1 rule 3) -- the hint must not say otherwise.
  if (active.status === "unverified") {
    return hasEstimate
      ? "Skip-generated -- awaiting PM/Director to verify."
      : "Skip-generated -- awaiting PM/Director to verify; an Estimate can already be created.";
  }
  if (active.status === "draft") return "Awaiting PM/Director to verify.";
  return null;
}

function estimateHint(activeCostSheet, estimates, quotations) {
  // Once a Quotation exists the "a Quotation can now be created" lines below
  // would be stale -- the next move has moved on to the Quotation stage.
  const hasQuotation = quotations.some((q) => q.status !== "superseded");
  const live = estimates.filter((e) => e.status !== "superseded");
  if (live.length === 0) {
    return activeCostSheet?.status === "verified" || activeCostSheet?.status === "unverified"
      ? "Awaiting PM/Director to create the Estimate."
      : "Waiting on a verified Cost Sheet before an Estimate can be created.";
  }
  if (live.some((e) => e.client_status === "approved")) {
    return hasQuotation ? "Client approved -- see the Quotation below." : "Client approved -- a Quotation can now be created.";
  }
  if (live.some((e) => e.client_status === "demand_received")) {
    return hasQuotation
      ? "Client asked for a Quotation -- see the Quotation below."
      : "Client has asked for a Quotation -- one can now be created.";
  }
  // Rejected is checked before draft/sent so the hint never contradicts the
  // "rejected" badge shown on the same Estimate.
  if (live.some((e) => e.client_status === "rejected")) return "Client rejected this Estimate.";
  if (live.some((e) => e.status === "sent" && e.client_status === "pending")) return "Awaiting client response.";
  if (live.some((e) => e.status === "draft")) return "Awaiting send to client.";
  if (live.every((e) => e.status === "expired")) return "Estimate expired -- create a new one.";
  return null;
}

function quotationHint(estimates, quotations, canFastTrack) {
  const live = quotations.filter((q) => q.status !== "superseded");
  if (live.length === 0) {
    const hasApprovedOption = estimates.some((e) =>
      e.options.some((o) => o.client_status === "approved" || o.client_status === "demand_received")
    );
    if (hasApprovedOption) return "Awaiting PM/Director to create the Quotation.";
    return canFastTrack
      ? "Waiting on a client-approved Estimate -- or PM/Director can Fast-track this small job from the Cost Sheet."
      : "Waiting on a client-approved Estimate before a Quotation can be created.";
  }
  if (live.some((q) => q.status === "won")) return "Won -- Work Order can be created.";
  if (live.some((q) => q.status === "sent")) return "Awaiting client decision.";
  if (live.some((q) => q.status === "released")) return "Ready to send to client.";
  if (live.some((q) => q.status === "draft")) return "Awaiting release.";
  if (live.some((q) => q.status === "lost")) return "Lost -- a new Quotation can be raised to re-bid.";
  if (live.every((q) => q.status === "expired")) return "Quotation expired -- raise a new one.";
  return null;
}

function StageHint({ text }) {
  if (!text) return null;
  return (
    <p className="text-xs text-text-secondary -mt-1">
      <span className="text-gold font-medium">What&apos;s next:</span> {text}
    </p>
  );
}

function StatusBadge({ status }) {
  const colors = {
    draft: "bg-surface-raised text-text-secondary",
    pending: "bg-surface-raised text-text-secondary",
    verified: "bg-green-500/10 text-green-400",
    approved: "bg-green-500/10 text-green-400",
    won: "bg-green-500/10 text-green-400",
    released: "bg-gold-muted text-gold-hover",
    sent: "bg-gold-muted text-gold-hover",
    superseded: "bg-surface-raised text-text-secondary",
    rejected: "bg-red-500/10 text-red-400",
    lost: "bg-red-500/10 text-red-400",
    expired: "bg-red-500/10 text-red-400",
    demand_received: "bg-amber-500/10 text-amber-400",
  };
  return (
    <span className={`text-xs rounded px-1.5 py-0.5 ${colors[status] ?? "bg-surface-raised text-text-secondary"}`}>
      {status}
    </span>
  );
}
