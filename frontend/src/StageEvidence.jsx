import { useEffect, useState } from "react";
import AttachmentsPanel from "./AttachmentsPanel";
import { listProjectStages, reviewStage, submitStage } from "./api";

const PHASE_LABELS = {
  site_prep: "Site Preparation",
  sub_base: "Sub-Base",
  flooring: "Flooring",
  structure_fixtures: "Structure & Fixtures",
  lighting: "Lighting",
  accessories_finishing: "Accessories & Finishing",
};

const STATUS_COLORS = {
  not_started: "bg-surface-raised text-text-secondary",
  in_progress: "bg-gold-muted text-gold-hover",
  evidence_submitted: "bg-amber-500/10 text-amber-400",
  rejected: "bg-red-500/10 text-red-400",
  reviewed: "bg-green-500/10 text-green-400",
};

const STATUS_LABELS = {
  not_started: "Not started",
  in_progress: "In progress",
  evidence_submitted: "Submitted for review",
  rejected: "Rejected",
  reviewed: "Reviewed",
};

const SUBMIT_ROLES = ["site_engineer", "pm", "director"];
const REVIEW_ROLES = ["pm", "director"];

function StatusPill({ status }) {
  return (
    <span className={`text-xs rounded px-2 py-1 ${STATUS_COLORS[status] ?? "bg-surface-raised text-text-secondary"}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function StageCard({ token, stage, role, onChanged }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");

  const canSubmit = SUBMIT_ROLES.includes(role) && ["in_progress", "rejected"].includes(stage.status);
  const canReview = REVIEW_ROLES.includes(role) && stage.status === "evidence_submitted";

  async function doSubmit() {
    setError("");
    setBusy(true);
    try {
      await submitStage(token, stage.id);
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function doApprove() {
    setError("");
    setBusy(true);
    try {
      await reviewStage(token, stage.id, { action: "approve" });
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function doReject() {
    if (!rejectionReason.trim()) {
      setError("A rejection reason is required.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      await reviewStage(token, stage.id, { action: "reject", rejectionReason });
      setRejecting(false);
      setRejectionReason("");
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-surface shadow rounded-lg p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">{PHASE_LABELS[stage.phase] ?? stage.phase}</h3>
          {stage.started_at && (
            <p className="text-xs text-text-secondary">Started {new Date(stage.started_at).toLocaleDateString()}</p>
          )}
        </div>
        <StatusPill status={stage.status} />
      </div>

      {stage.status === "rejected" && stage.rejection_reason && (
        <p className="text-xs text-red-400 bg-red-500/5 rounded px-2 py-1">Rejected: {stage.rejection_reason}</p>
      )}
      {error && <p className="text-xs text-red-400">{error}</p>}

      <AttachmentsPanel token={token} docType="project_stage" docId={stage.id} role={role} onUploaded={onChanged} />

      <div className="flex flex-wrap items-center gap-2">
        {canSubmit && (
          <button
            onClick={doSubmit}
            disabled={busy}
            className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover disabled:opacity-50"
          >
            {busy ? "Submitting…" : "Mark ready for review"}
          </button>
        )}
        {canReview && !rejecting && (
          <>
            <button
              onClick={doApprove}
              disabled={busy}
              className="text-xs text-green-400 hover:underline disabled:opacity-50"
            >
              Approve
            </button>
            <button onClick={() => setRejecting(true)} className="text-xs text-red-400 hover:underline">
              Reject
            </button>
          </>
        )}
        {canReview && rejecting && (
          <div className="flex items-center gap-2 flex-1 min-w-[16rem]">
            <input
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="Reason for rejection (required)"
              className="flex-1 rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs"
            />
            <button onClick={doReject} disabled={busy} className="text-xs text-red-400 hover:underline disabled:opacity-50">
              Confirm reject
            </button>
            <button
              onClick={() => {
                setRejecting(false);
                setRejectionReason("");
                setError("");
              }}
              className="text-xs text-text-secondary hover:underline"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/** P4 contract v7, Section 3: stage evidence capture. Six fixed construction phases per
 * project, each with its own evidence, submit/review state machine. Gated site_engineer/pm/
 * director at the route level (navAccess.js) -- review itself is pm/director only, enforced
 * again here and by the backend independently. */
export default function StageEvidence({ token, project, role, onBack }) {
  const [stages, setStages] = useState(null);
  const [error, setError] = useState("");

  function load() {
    return listProjectStages(token, project.id)
      .then((rows) => setStages([...rows].sort((a, b) => a.phase.localeCompare(b.phase))))
      .catch((err) => setError(err.message));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, project.id]);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">Stage Evidence</h2>
          <p className="text-sm text-text-secondary">
            Project <span className="font-mono">{project.project_no}</span> — construction stage photos and sign-off.
          </p>
        </div>
        {onBack && (
          <button onClick={onBack} className="text-xs text-text-secondary hover:underline">
            ← Back
          </button>
        )}
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {!stages && !error && <p className="text-sm text-text-secondary">Loading stages…</p>}
      {stages && (
        <div className="space-y-4">
          {stages.map((stage) => (
            <StageCard key={stage.id} token={token} stage={stage} role={role} onChanged={load} />
          ))}
        </div>
      )}
    </div>
  );
}
