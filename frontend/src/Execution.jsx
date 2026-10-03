import { useCallback, useEffect, useState } from "react";
import AttachmentsPanel from "./AttachmentsPanel";
import {
  addProjectTeamMember, authorizeExecution, clientSignAgreement, createAgreementDraft, createMilestone,
  createSiteIssue, createTask, createWorkOrder, executeAgreement, getCurrentAgreement, getExecutionReadiness,
  getExecutionContext, getWorkOrder, listAgreementRevisions, listAttachments, listClientSignatories, listExecutionAuthorizations,
  listMilestones, listProjectTeam, listSiteIssues, listTasks, listUsers, removeProjectTeamMember,
  supersedeAgreement, updateMilestone, updateSiteIssue, updateTask, voidAgreement,
} from "./api";

const MANAGE_ROLES = ["pm", "director"];
const TEAM_ROLES = ["pm", "director", "site_engineer", "procurement"];
const ROLE_LABELS = { pm: "Project Manager", director: "Director", site_engineer: "Site Engineer", procurement: "Procurement" };
const NO_WON_MESSAGE = "No Won quotation yet -- the Agreement and Work Order steps start once a quotation is Won.";

const INPUT = "w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm";
const BTN = "bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover disabled:opacity-50";
const LINK_BTN = "text-xs text-gold hover:underline disabled:opacity-50";
const DANGER_BTN = "text-xs text-red-400 hover:underline disabled:opacity-50";
const FIELD_LABEL = "block text-xs text-text-secondary space-y-1";

const AGREEMENT_STATUS = {
  drafted: { label: "Drafted", color: "bg-surface-raised text-text-secondary" },
  client_signed: { label: "Client signed", color: "bg-amber-500/10 text-amber-400" },
  executed: { label: "Executed", color: "bg-green-500/10 text-green-400" },
  superseded: { label: "Superseded", color: "bg-surface-raised text-text-secondary" },
  voided: { label: "Voided", color: "bg-red-500/10 text-red-400" },
  legacy_adopted: { label: "Legacy (pre-P5 placeholder)", color: "bg-blue-500/10 text-blue-400" },
};
const WORK_STATUS = {
  not_started: { label: "Not started", color: "bg-surface-raised text-text-secondary" },
  in_progress: { label: "In progress", color: "bg-gold-muted text-gold-hover" },
  done: { label: "Done", color: "bg-green-500/10 text-green-400" },
};
const ISSUE_STATUS = {
  open: { label: "Open", color: "bg-red-500/10 text-red-400" },
  in_review: { label: "In review", color: "bg-amber-500/10 text-amber-400" },
  resolved: { label: "Resolved", color: "bg-green-500/10 text-green-400" },
};
const SEVERITY_COLORS = {
  low: "bg-surface-raised text-text-secondary",
  medium: "bg-amber-500/10 text-amber-400",
  high: "bg-red-500/10 text-red-400",
};

function Pill({ map, status }) {
  const entry = map[status] ?? { label: status, color: "bg-surface-raised text-text-secondary" };
  return <span className={`text-xs rounded px-2 py-0.5 whitespace-nowrap ${entry.color}`}>{entry.label}</span>;
}

function fmtDate(value) {
  if (!value) return "--";
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) || value.length <= 10 ? value : `${value}Z`);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString();
}

function fmtDateTime(value) {
  if (!value) return "--";
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString();
}

function isNotOnTeam(message) {
  return /not on this project'?s team/i.test(message || "");
}

function Card({ title, subtitle, children }) {
  return (
    <section className="bg-surface shadow rounded-lg p-4 sm:p-6 space-y-3">
      <div>
        <h3 className="text-base font-semibold text-text-primary">{title}</h3>
        {subtitle && <p className="text-xs text-text-secondary">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function SectionError({ message }) {
  if (!message) return null;
  if (isNotOnTeam(message)) {
    return (
      <p className="text-sm text-text-secondary bg-surface-raised rounded px-3 py-2">
        You are not on this project&apos;s team, so this section is not available to you. Ask a Project Manager or
        Director to add you to the team.
      </p>
    );
  }
  return <p className="text-sm text-red-400">{message}</p>;
}

function ReasonForm({ label, confirmLabel, busy, onSubmit, onCancel }) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  function submit(e) {
    e.preventDefault();
    if (!reason.trim()) {
      setError("A reason is required.");
      return;
    }
    setError("");
    onSubmit(reason.trim());
  }
  return (
    <form onSubmit={submit} className="space-y-2 border border-border-dark rounded p-3">
      <label className={FIELD_LABEL}>
        {label}
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} className={INPUT} />
      </label>
      {error && <p className="text-xs text-red-400">{error}</p>}
      <div className="flex flex-wrap gap-3">
        <button type="submit" disabled={busy} className={BTN}>{confirmLabel}</button>
        <button type="button" onClick={onCancel} className="text-xs text-text-secondary hover:underline">Cancel</button>
      </div>
    </form>
  );
}

/* ------------------------------------------------------------------ Readiness */

function ReadinessCard({ token, quotation, projectNo, workOrderExists, canManage, role, version, onChanged }) {
  const [readiness, setReadiness] = useState(null);
  const [auths, setAuths] = useState([]);
  const [workOrder, setWorkOrder] = useState(null);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const qid = quotation?.id;
  const canSeeReadiness = MANAGE_ROLES.includes(role);

  useEffect(() => {
    if (!qid) return;
    let cancelled = false;
    setError("");
    const jobs = [];
    if (canSeeReadiness) {
      jobs.push(getWorkOrder(token, qid).then((wo) => !cancelled && setWorkOrder(wo)));
      jobs.push(getExecutionReadiness(token, qid).then((r) => !cancelled && setReadiness(r)));
      jobs.push(listExecutionAuthorizations(token, qid).then((a) => !cancelled && setAuths(a)));
    }
    Promise.all(jobs).catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [token, qid, version, canSeeReadiness]);

  async function run(fn) {
    setActionError("");
    setBusy(true);
    try {
      await fn();
      onChanged();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!qid) {
    return (
      <Card title="Start readiness">
        <p className="text-sm text-text-secondary">{NO_WON_MESSAGE}</p>
      </Card>
    );
  }

  const teamCount = readiness
    ? (Array.isArray(readiness.eligible_site_engineers)
      ? readiness.eligible_site_engineers.length
      : Number(readiness.eligible_site_engineers) || 0)
    : 0;
  const teamOk = teamCount > 0;
  const agreementOk = !!readiness?.agreement_executed;
  const authorized = !!readiness?.authorization_valid;
  const currentAuthorization = auths.find((a) => a.status === "authorized");
  const blockers = readiness?.blockers ?? [];

  const checks = readiness
    ? [
      { key: "agreement", ok: agreementOk, label: "Agreement executed", detail: `Status: ${readiness.agreement_status ?? "no agreement"}` },
      { key: "team", ok: teamOk, label: "Active Site Engineer on the project team", detail: `${teamCount} eligible` },
      { key: "auth", ok: authorized, label: "Execution authorized", detail: authorized ? "Valid authorization on record" : "Not authorized yet" },
    ]
    : [];

  return (
    <Card title="Start readiness" subtitle={`Quotation ${quotation.document_no ?? quotation.id} -- everything needed before a Work Order can be created.`}>
      <SectionError message={error} />
      {!canSeeReadiness && (
        <p className="text-sm text-text-secondary">Readiness details are visible to the Project Manager and Director.</p>
      )}
      {canSeeReadiness && !readiness && !error && <p className="text-sm text-text-secondary">Loading readiness…</p>}
      {readiness && (
        <>
          <ul className="space-y-1">
            {checks.map((c) => (
              <li key={c.key} className="flex items-start gap-2 text-sm">
                <span className={c.ok ? "text-green-400" : "text-red-400"} aria-hidden="true">{c.ok ? "✔" : "✖"}</span>
                <span className="text-text-primary">
                  {c.label} <span className="sr-only">{c.ok ? "(done)" : "(not done)"}</span>
                  <span className="block text-xs text-text-secondary">{c.detail}</span>
                </span>
              </li>
            ))}
          </ul>
          {blockers.length > 0 && (
            <div className="bg-amber-500/5 border border-amber-500/30 rounded px-3 py-2">
              <p className="text-xs font-semibold text-amber-400">Blockers</p>
              <ul className="list-disc pl-5 text-xs text-amber-400 space-y-0.5">
                {blockers.map((b, i) => <li key={i}>{b}</li>)}
              </ul>
            </div>
          )}
        </>
      )}
      {actionError && <p className="text-sm text-red-400">{actionError}</p>}
      {canManage && readiness && (
        <div className="flex flex-wrap items-center gap-3">
          {authorized ? (
            <p className="text-sm text-green-400" role="status">
              <span aria-hidden="true">&#10003; </span>Execution authorized
              {currentAuthorization?.authorized_at && (
                <span className="text-text-secondary"> on {new Date(currentAuthorization.authorized_at).toLocaleString()}</span>
              )}
            </p>
          ) : (
            <button
              type="button"
              disabled={busy || !(agreementOk && teamOk)}
              onClick={() => run(() => authorizeExecution(token, qid))}
              className={BTN}
            >
              Authorize execution
            </button>
          )}
          {!authorized && !(agreementOk && teamOk) && (
            <span className="text-xs text-text-secondary">Needs an executed agreement and an active Site Engineer.</span>
          )}
        </div>
      )}

      <div className="border-t border-border-dark pt-3 space-y-2">
        <h4 className="text-sm font-semibold text-text-primary">Work Order</h4>
        {workOrder ? (
          <p className="text-sm text-text-primary">
            Work Order for project <span className="font-mono">{projectNo}</span>
            {quotation?.document_no && <> &middot; quotation <span className="font-mono">{quotation.document_no}</span></>} &middot;{" "}
            <span className="text-text-secondary">{String(workOrder.status ?? "").replace("_", " ")}</span>
            {workOrder.awarded_at && <span className="text-text-secondary"> &middot; since {new Date(workOrder.awarded_at).toLocaleDateString()}</span>}
            <span className="block text-xs text-text-secondary">
              Work Orders carry no separate number in NestaPrime; they are identified by their project and quotation.
              Manage status and payments from the Documents tab.
            </span>
          </p>
        ) : !canSeeReadiness ? (
          <p className="text-xs text-text-secondary">
            {workOrderExists ? "A Work Order has been created for this quotation." : "No Work Order yet."}
          </p>
        ) : (
          <>
            <p className="text-xs text-text-secondary">No Work Order yet.</p>
            {canManage && (
              <button
                type="button"
                disabled={busy || (readiness ? blockers.length > 0 : false)}
                onClick={() => run(async () => { setWorkOrder(await createWorkOrder(token, qid)); })}
                className={BTN}
              >
                Create Work Order
              </button>
            )}
          </>
        )}
      </div>

      {canSeeReadiness && (
        <details className="text-xs">
          <summary className="cursor-pointer text-text-secondary">Authorization history ({auths.length})</summary>
          <ul className="mt-2 space-y-1">
            {auths.length === 0 && <li className="text-text-secondary">None yet.</li>}
            {auths.map((a) => (
              <li key={a.id} className="border border-border-dark rounded px-2 py-1">
                <span className={a.status === "authorized" ? "text-green-400" : "text-red-400"}>{a.status}</span>
                {" "}&middot; {fmtDateTime(a.authorized_at ?? a.created_at)}
                {a.status === "invalidated" && a.invalidated_reason && (
                  <span className="block text-text-secondary">Invalidated: {a.invalidated_reason}</span>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ Agreement */

function AgreementCard({ token, project, quotation, role, canManage, version, onChanged }) {
  const isDirector = role === "director";
  const [current, setCurrent] = useState(null);
  const [revisions, setRevisions] = useState([]);
  const [signatories, setSignatories] = useState([]);
  const [attachments, setAttachments] = useState([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState(null); // "void" | "supersede"
  const [signForm, setSignForm] = useState({ signatoryId: "", signedOn: "", attachmentId: "" });
  const qid = quotation?.id;
  const agreementId = current?.id;

  const loadAttachments = useCallback(() => {
    if (!agreementId) return Promise.resolve();
    return listAttachments(token, "agreement", agreementId).then(setAttachments).catch(() => setAttachments([]));
  }, [token, agreementId]);

  useEffect(() => {
    if (!qid) return;
    let cancelled = false;
    setError("");
    Promise.all([getCurrentAgreement(token, qid), listAgreementRevisions(token, qid)])
      .then(([cur, revs]) => {
        if (cancelled) return;
        setCurrent(cur);
        setRevisions(revs);
        setLoaded(true);
      })
      .catch((err) => { if (!cancelled) { setError(err.message); setLoaded(true); } });
    return () => { cancelled = true; };
  }, [token, qid, version]);

  useEffect(() => { loadAttachments(); }, [loadAttachments, version]);

  useEffect(() => {
    if (!canManage || !project.client_id) return;
    listClientSignatories(token, project.client_id)
      .then((rows) => setSignatories(rows.filter((s) => s.is_active !== false)))
      .catch(() => setSignatories([]));
  }, [token, project.client_id, canManage]);

  async function run(fn) {
    setError("");
    setBusy(true);
    try {
      await fn();
      setMode(null);
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function submitSign(e) {
    e.preventDefault();
    if (!signForm.signatoryId || !signForm.signedOn || !signForm.attachmentId) {
      setError("Choose the client signatory, the signing date and the uploaded signed copy.");
      return;
    }
    run(() => clientSignAgreement(token, current.id, {
      clientSignatoryId: signForm.signatoryId,
      signedOn: signForm.signedOn,
      attachmentId: signForm.attachmentId,
    }));
  }

  if (!qid) {
    return (
      <Card title="Agreement">
        <p className="text-sm text-text-secondary">{NO_WON_MESSAGE}</p>
      </Card>
    );
  }

  const status = current?.status;
  const signedCopies = attachments.filter((a) => a.tag === "signed_document");
  const canSign = canManage && status === "drafted";
  const canExecute = isDirector && status === "client_signed";
  const canVoid = isDirector && ["drafted", "client_signed", "executed"].includes(status);
  const canSupersede = isDirector && ["client_signed", "executed"].includes(status);

  return (
    <Card title="Agreement" subtitle="Signed agreement for the Won quotation: client signature first, then Nesta Prime executes it.">
      <SectionError message={error} />
      {!loaded && !error && <p className="text-sm text-text-secondary">Loading agreement…</p>}

      {loaded && !current && (
        <div className="space-y-2">
          <p className="text-sm text-text-secondary">No agreement has been drafted for this quotation yet.</p>
          {canManage && (
            <button type="button" disabled={busy} className={BTN} onClick={() => run(() => createAgreementDraft(token, qid))}>
              Create agreement draft
            </button>
          )}
        </div>
      )}

      {current && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Pill map={AGREEMENT_STATUS} status={status} />
            <span className="text-xs text-text-secondary">Agreement #{current.id}</span>
          </div>

          {status === "legacy_adopted" && (
            <p className="text-xs text-blue-400 bg-blue-500/5 rounded px-3 py-2">
              This is a pre-P5 placeholder record adopted from an older project. It is not a signed agreement and does
              not satisfy the execution checklist.
            </p>
          )}
          {current.evidence_intact === false && (
            <p className="text-sm text-red-400 bg-red-500/10 rounded px-3 py-2" role="alert">
              Warning: the signed document no longer matches the fingerprint recorded when it was locked. Treat this
              agreement as tampered until a Director reviews it.
            </p>
          )}

          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-sm">
            <div>
              <dt className="text-xs text-text-secondary">Client signatory</dt>
              <dd className="text-text-primary">
                {current.client_signatory_name_snapshot
                  ? `${current.client_signatory_name_snapshot}${current.client_signatory_designation_snapshot ? `, ${current.client_signatory_designation_snapshot}` : ""}`
                  : "--"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-text-secondary">Client signed on</dt>
              <dd className="text-text-primary">{fmtDate(current.client_signed_at)}</dd>
            </div>
            <div>
              <dt className="text-xs text-text-secondary">Nesta Prime signed</dt>
              <dd className="text-text-primary">{current.nesta_signed_at ? fmtDateTime(current.nesta_signed_at) : "--"}</dd>
            </div>
            <div>
              <dt className="text-xs text-text-secondary">Evidence locked</dt>
              <dd className="text-text-primary">{current.evidence_locked_at ? fmtDateTime(current.evidence_locked_at) : "--"}</dd>
            </div>
            {current.signed_document_sha256 && (
              <div className="sm:col-span-2">
                <dt className="text-xs text-text-secondary">Signed document SHA-256</dt>
                <dd className="font-mono text-xs break-all text-text-primary">{current.signed_document_sha256}</dd>
              </div>
            )}
          </dl>

          {canManage && ["drafted", "client_signed"].includes(status) && (
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-text-primary">Signed copy</h4>
              <p className="text-xs text-text-secondary">
                Upload the client-signed document here and set its tag to <span className="font-mono">signed_document</span>.
              </p>
              <AttachmentsPanel token={token} docType="agreement" docId={current.id} role={role} onUploaded={loadAttachments} readOnly={!!current.evidence_locked_at} />
            </div>
          )}

          {canSign && (
            <form onSubmit={submitSign} className="space-y-2 border border-border-dark rounded p-3">
              <h4 className="text-sm font-semibold text-text-primary">Record client signature</h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <label className={FIELD_LABEL}>
                  Client signatory
                  <select value={signForm.signatoryId} onChange={(e) => setSignForm((f) => ({ ...f, signatoryId: e.target.value }))} className={INPUT}>
                    <option value="">Select…</option>
                    {signatories.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.designation})</option>)}
                  </select>
                </label>
                <label className={FIELD_LABEL}>
                  Signing date
                  <input type="date" value={signForm.signedOn} onChange={(e) => setSignForm((f) => ({ ...f, signedOn: e.target.value }))} className={INPUT} />
                </label>
                <label className={FIELD_LABEL}>
                  Signed copy (uploaded)
                  <select value={signForm.attachmentId} onChange={(e) => setSignForm((f) => ({ ...f, attachmentId: e.target.value }))} className={INPUT}>
                    <option value="">Select…</option>
                    {signedCopies.map((a) => <option key={a.id} value={a.id}>{a.original_filename} (v{a.version})</option>)}
                  </select>
                </label>
              </div>
              {signatories.length === 0 && (
                <p className="text-xs text-amber-400">No active client signatory on file -- add one under the client&apos;s signatories first.</p>
              )}
              {signedCopies.length === 0 && (
                <p className="text-xs text-text-secondary">Upload a file tagged signed_document above to enable selection.</p>
              )}
              <button type="submit" disabled={busy} className={BTN}>Record client signature</button>
            </form>
          )}

          <div className="flex flex-wrap items-center gap-4">
            {canExecute && (
              <button type="button" disabled={busy} className={BTN} onClick={() => run(() => executeAgreement(token, current.id))}>
                Execute for Nesta Prime
              </button>
            )}
            {canSupersede && mode !== "supersede" && (
              <button type="button" className={LINK_BTN} onClick={() => setMode("supersede")}>Correct (supersede)</button>
            )}
            {canVoid && mode !== "void" && (
              <button type="button" className={DANGER_BTN} onClick={() => setMode("void")}>Void</button>
            )}
          </div>
          {status === "client_signed" && !isDirector && (
            <p className="text-xs text-text-secondary">Waiting for the Director to execute for Nesta Prime.</p>
          )}
          {mode === "void" && (
            <ReasonForm
              label="Reason for voiding (required)"
              confirmLabel="Confirm void"
              busy={busy}
              onCancel={() => setMode(null)}
              onSubmit={(reason) => run(() => voidAgreement(token, current.id, reason))}
            />
          )}
          {mode === "supersede" && (
            <ReasonForm
              label="Reason for the correction (required) -- a new drafted revision will be created"
              confirmLabel="Confirm correction"
              busy={busy}
              onCancel={() => setMode(null)}
              onSubmit={(reason) => run(() => supersedeAgreement(token, current.id, reason))}
            />
          )}
        </div>
      )}

      {revisions.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-text-secondary">Revision history ({revisions.length})</summary>
          <div className="overflow-x-auto mt-2">
            <table className="min-w-full text-left">
              <thead className="text-text-secondary">
                <tr>
                  <th className="pr-3 py-1">#</th><th className="pr-3 py-1">Status</th>
                  <th className="pr-3 py-1">Client signatory</th><th className="pr-3 py-1">Client signed</th>
                  <th className="pr-3 py-1">Nesta signed</th><th className="pr-3 py-1">Notes</th>
                </tr>
              </thead>
              <tbody>
                {revisions.map((r) => (
                  <tr key={r.id} className="border-t border-border-dark align-top">
                    <td className="pr-3 py-1">{r.id}{r.supersedes_id ? ` (corrects #${r.supersedes_id})` : ""}</td>
                    <td className="pr-3 py-1"><Pill map={AGREEMENT_STATUS} status={r.status} /></td>
                    <td className="pr-3 py-1">{r.client_signatory_name_snapshot ?? "--"}</td>
                    <td className="pr-3 py-1 whitespace-nowrap">{fmtDate(r.client_signed_at)}</td>
                    <td className="pr-3 py-1 whitespace-nowrap">{fmtDate(r.nesta_signed_at)}</td>
                    <td className="pr-3 py-1">
                      {r.void_reason ? `Voided ${fmtDate(r.voided_at)}: ${r.void_reason}` : ""}
                      {r.status === "legacy_adopted" ? "Pre-P5 placeholder, not a signed agreement" : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ Team */

function TeamCard({ token, project, canManage, version, onChanged }) {
  const [members, setMembers] = useState(null);
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [userId, setUserId] = useState("");

  useEffect(() => {
    let cancelled = false;
    setError("");
    listProjectTeam(token, project.id, true)
      .then((rows) => !cancelled && setMembers(rows))
      .catch((err) => !cancelled && setError(err.message));
    return () => { cancelled = true; };
  }, [token, project.id, version]);

  useEffect(() => {
    if (!canManage) return;
    listUsers(token).then(setUsers).catch(() => setUsers([]));
  }, [token, canManage]);

  async function run(fn) {
    setActionError("");
    setBusy(true);
    try {
      await fn();
      onChanged();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const active = (members ?? []).filter((m) => !m.removed_at);
  const removed = (members ?? []).filter((m) => m.removed_at);
  const activeIds = new Set(active.map((m) => m.user_id));
  const candidates = users.filter((u) => u.is_active && TEAM_ROLES.includes(u.role) && !activeIds.has(u.id));
  const hasEngineer = active.some((m) => m.project_role === "site_engineer");

  function add(e) {
    e.preventDefault();
    const u = users.find((x) => String(x.id) === userId);
    if (!u) {
      setActionError("Choose a person to add.");
      return;
    }
    run(async () => {
      await addProjectTeamMember(token, project.id, { userId: u.id, projectRole: u.role });
      setUserId("");
    });
  }

  return (
    <Card title="Project team" subtitle="At least one active Site Engineer is required before execution can start.">
      <SectionError message={error} />
      {!members && !error && <p className="text-sm text-text-secondary">Loading team…</p>}
      {members && !hasEngineer && (
        <p className="text-xs text-amber-400">No active Site Engineer on this project yet.</p>
      )}
      {members && (
        <ul className="space-y-1">
          {active.length === 0 && <li className="text-sm text-text-secondary">No team members yet.</li>}
          {active.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 border border-border-dark rounded px-3 py-1.5 text-sm">
              <span>
                <span className="text-text-primary">{m.user_name}</span>
                <span className="text-text-secondary"> &middot; {ROLE_LABELS[m.project_role] ?? m.project_role} &middot; since {fmtDate(m.assigned_at)}</span>
              </span>
              {canManage && (
                <button type="button" disabled={busy} className={DANGER_BTN} onClick={() => run(() => removeProjectTeamMember(token, project.id, m.id))}>
                  Remove<span className="sr-only"> {m.user_name}</span>
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {actionError && <p className="text-sm text-red-400">{actionError}</p>}
      {canManage && members && (
        <form onSubmit={add} className="flex flex-col sm:flex-row sm:items-end gap-2">
          <label className={`${FIELD_LABEL} flex-1`}>
            Add team member
            <select value={userId} onChange={(e) => setUserId(e.target.value)} className={INPUT}>
              <option value="">Select a person…</option>
              {candidates.map((u) => <option key={u.id} value={u.id}>{u.name} -- {ROLE_LABELS[u.role] ?? u.role}</option>)}
            </select>
          </label>
          <button type="submit" disabled={busy} className={BTN}>Add to team</button>
        </form>
      )}
      {removed.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-text-secondary">History ({removed.length} removed)</summary>
          <ul className="mt-2 space-y-1">
            {removed.map((m) => (
              <li key={m.id} className="text-text-secondary">
                {m.user_name} &middot; {ROLE_LABELS[m.project_role] ?? m.project_role} &middot; {fmtDate(m.assigned_at)} to {fmtDate(m.removed_at)}
              </li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ Work items */

const NEXT_WORK_STATUS = { not_started: { to: "in_progress", label: "Start" }, in_progress: { to: "done", label: "Mark done" }, done: { to: "in_progress", label: "Reopen" } };

function WorkItemsCard({ token, user, project, quotation, canManage, version, onChanged }) {
  const [milestones, setMilestones] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [team, setTeam] = useState([]);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [msForm, setMsForm] = useState({ name: "", target_date: "" });
  const [taskForm, setTaskForm] = useState({ title: "", description: "", assigned_to_id: "", due_date: "", milestone_id: "" });
  const [local, setLocal] = useState(0);
  const planningOff = !quotation;

  useEffect(() => {
    let cancelled = false;
    setError("");
    Promise.all([listMilestones(token, project.id), listTasks(token, project.id), listProjectTeam(token, project.id)])
      .then(([m, t, tm]) => {
        if (cancelled) return;
        setMilestones(m);
        setTasks(t);
        setTeam(tm);
      })
      .catch((err) => !cancelled && setError(err.message));
    return () => { cancelled = true; };
  }, [token, project.id, version, local]);

  async function run(fn) {
    setActionError("");
    setBusy(true);
    try {
      await fn();
      setLocal((n) => n + 1);
      onChanged();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const me = team.find((m) => m.user_id === user.id && !m.removed_at);
  const activeTeam = team.filter((m) => !m.removed_at);
  const memberName = (id) => team.find((m) => m.id === id)?.user_name;

  function addMilestone(e) {
    e.preventDefault();
    if (!msForm.name.trim()) { setActionError("Milestone name is required."); return; }
    run(async () => {
      await createMilestone(token, project.id, { name: msForm.name.trim(), target_date: msForm.target_date || null });
      setMsForm({ name: "", target_date: "" });
    });
  }

  function addTask(e) {
    e.preventDefault();
    if (!taskForm.title.trim()) { setActionError("Task title is required."); return; }
    run(async () => {
      await createTask(token, project.id, {
        title: taskForm.title.trim(),
        description: taskForm.description.trim() || null,
        assigned_to_id: taskForm.assigned_to_id || null,
        due_date: taskForm.due_date || null,
        milestone_id: taskForm.milestone_id || null,
      });
      setTaskForm({ title: "", description: "", assigned_to_id: "", due_date: "", milestone_id: "" });
    });
  }

  return (
    <Card title="Milestones & tasks" subtitle="Plan and track delivery once the quotation is Won.">
      <SectionError message={error} />
      {planningOff && <p className="text-xs text-amber-400">{NO_WON_MESSAGE} Creating milestones and tasks is disabled until then.</p>}
      {actionError && <p className="text-sm text-red-400">{actionError}</p>}
      {!milestones && !error && <p className="text-sm text-text-secondary">Loading…</p>}

      {milestones && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-text-primary">Milestones</h4>
          {milestones.length === 0 && <p className="text-xs text-text-secondary">No milestones yet.</p>}
          {milestones.map((m) => {
            const next = NEXT_WORK_STATUS[m.status];
            return (
              <div key={m.id} className="flex flex-wrap items-center justify-between gap-2 border border-border-dark rounded px-3 py-1.5 text-sm">
                <span>
                  <span className="text-text-primary">{m.name}</span>
                  {m.target_date && <span className="text-text-secondary"> &middot; target {fmtDate(m.target_date)}</span>}
                </span>
                <span className="flex items-center gap-3">
                  <Pill map={WORK_STATUS} status={m.status} />
                  {canManage && next && (
                    <button type="button" disabled={busy} className={LINK_BTN} onClick={() => run(() => updateMilestone(token, m.id, { status: next.to }))}>
                      {next.label}<span className="sr-only"> {m.name}</span>
                    </button>
                  )}
                </span>
              </div>
            );
          })}
          {canManage && (
            <form onSubmit={addMilestone} className="grid grid-cols-1 sm:grid-cols-[1fr_10rem_auto] gap-2 sm:items-end">
              <label className={FIELD_LABEL}>
                New milestone
                <input value={msForm.name} onChange={(e) => setMsForm((f) => ({ ...f, name: e.target.value }))} disabled={planningOff} className={INPUT} />
              </label>
              <label className={FIELD_LABEL}>
                Target date
                <input type="date" value={msForm.target_date} onChange={(e) => setMsForm((f) => ({ ...f, target_date: e.target.value }))} disabled={planningOff} className={INPUT} />
              </label>
              <button type="submit" disabled={busy || planningOff} className={BTN}>Add milestone</button>
            </form>
          )}
        </div>
      )}

      {milestones && (
        <div className="space-y-2 border-t border-border-dark pt-3">
          <h4 className="text-sm font-semibold text-text-primary">Tasks</h4>
          {tasks.length === 0 && <p className="text-xs text-text-secondary">No tasks yet.</p>}
          {tasks.map((t) => {
            const mine = me && t.assigned_to_id === me.id;
            const next = NEXT_WORK_STATUS[t.status];
            const showStatusBtn = next && (canManage || mine);
            return (
              <div key={t.id} className="border border-border-dark rounded px-3 py-2 text-sm space-y-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-text-primary font-medium">{t.title}</span>
                  <span className="flex items-center gap-2">
                    {t.needs_reassignment && <span className="text-xs rounded px-2 py-0.5 bg-red-500/10 text-red-400">Needs reassignment</span>}
                    <Pill map={WORK_STATUS} status={t.status} />
                  </span>
                </div>
                {t.description && <p className="text-xs text-text-secondary">{t.description}</p>}
                <p className="text-xs text-text-secondary">
                  Assignee: {t.assigned_to_id ? (memberName(t.assigned_to_id) ?? t.assigned_to_name ?? `member #${t.assigned_to_id}`) : "unassigned"}
                  {" "}&middot; Due {fmtDate(t.due_date)}
                  {t.milestone_id && <> &middot; {milestones.find((m) => m.id === t.milestone_id)?.name ?? "milestone"}</>}
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  {showStatusBtn && (
                    <button type="button" disabled={busy} className={LINK_BTN} onClick={() => run(() => updateTask(token, t.id, { status: next.to }))}>
                      {mine && !canManage ? (t.status === "not_started" ? "Start" : t.status === "in_progress" ? "Done" : "Reopen") : next.label}
                      <span className="sr-only"> {t.title}</span>
                    </button>
                  )}
                  {canManage && (
                    <label className="text-xs text-text-secondary flex items-center gap-1">
                      Reassign
                      <select
                        value={t.assigned_to_id ?? ""}
                        disabled={busy}
                        onChange={(e) => run(() => updateTask(token, t.id, { assigned_to_id: e.target.value || null }))}
                        className="rounded border border-border-dark bg-surface-raised text-text-primary px-1 py-0.5 text-xs"
                      >
                        <option value="">Unassigned</option>
                        {activeTeam.map((m) => <option key={m.id} value={m.id}>{m.user_name}</option>)}
                      </select>
                    </label>
                  )}
                </div>
              </div>
            );
          })}
          {canManage && (
            <form onSubmit={addTask} className="grid grid-cols-1 sm:grid-cols-2 gap-2 border border-border-dark rounded p-3">
              <label className={`${FIELD_LABEL} sm:col-span-2`}>
                New task title
                <input value={taskForm.title} onChange={(e) => setTaskForm((f) => ({ ...f, title: e.target.value }))} disabled={planningOff} className={INPUT} />
              </label>
              <label className={`${FIELD_LABEL} sm:col-span-2`}>
                Description (optional)
                <textarea rows={2} value={taskForm.description} onChange={(e) => setTaskForm((f) => ({ ...f, description: e.target.value }))} disabled={planningOff} className={INPUT} />
              </label>
              <label className={FIELD_LABEL}>
                Assignee
                <select value={taskForm.assigned_to_id} onChange={(e) => setTaskForm((f) => ({ ...f, assigned_to_id: e.target.value }))} disabled={planningOff} className={INPUT}>
                  <option value="">Unassigned</option>
                  {activeTeam.map((m) => <option key={m.id} value={m.id}>{m.user_name} ({ROLE_LABELS[m.project_role] ?? m.project_role})</option>)}
                </select>
              </label>
              <label className={FIELD_LABEL}>
                Due date
                <input type="date" value={taskForm.due_date} onChange={(e) => setTaskForm((f) => ({ ...f, due_date: e.target.value }))} disabled={planningOff} className={INPUT} />
              </label>
              <label className={FIELD_LABEL}>
                Milestone (optional)
                <select value={taskForm.milestone_id} onChange={(e) => setTaskForm((f) => ({ ...f, milestone_id: e.target.value }))} disabled={planningOff} className={INPUT}>
                  <option value="">None</option>
                  {milestones.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
              </label>
              <div className="sm:self-end">
                <button type="submit" disabled={busy || planningOff} className={BTN}>Add task</button>
              </div>
            </form>
          )}
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ Site issues */

function IssueRow({ token, issue, role, canManage, busy, run }) {
  const [resolving, setResolving] = useState(false);
  const [reason, setReason] = useState("");
  const [localError, setLocalError] = useState("");

  function resolve(e) {
    e.preventDefault();
    if (!reason.trim()) { setLocalError("A resolution reason is required."); return; }
    setLocalError("");
    run(async () => {
      await updateSiteIssue(token, issue.id, { status: "resolved", resolution_reason: reason.trim() });
      setResolving(false);
      setReason("");
    });
  }

  return (
    <div className="border border-border-dark rounded px-3 py-2 text-sm space-y-1">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-text-primary font-medium">{issue.title}</span>
        <span className="flex items-center gap-2">
          <span className={`text-xs rounded px-2 py-0.5 ${SEVERITY_COLORS[issue.severity] ?? SEVERITY_COLORS.low}`}>{issue.severity}</span>
          <Pill map={ISSUE_STATUS} status={issue.status} />
        </span>
      </div>
      {issue.description && <p className="text-xs text-text-secondary">{issue.description}</p>}
      {issue.resolution_reason && <p className="text-xs text-green-400">Resolution: {issue.resolution_reason}</p>}
      {canManage && issue.status !== "resolved" && !resolving && (
        <div className="flex flex-wrap gap-3">
          {issue.status !== "in_review" && (
            <button type="button" disabled={busy} className={LINK_BTN} onClick={() => run(() => updateSiteIssue(token, issue.id, { status: "in_review" }))}>
              Move to in review<span className="sr-only"> {issue.title}</span>
            </button>
          )}
          <button type="button" className={LINK_BTN} onClick={() => setResolving(true)}>
            Resolve<span className="sr-only"> {issue.title}</span>
          </button>
        </div>
      )}
      {resolving && (
        <form onSubmit={resolve} className="space-y-2">
          <label className={FIELD_LABEL}>
            Resolution reason (required)
            <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} className={INPUT} />
          </label>
          {localError && <p className="text-xs text-red-400">{localError}</p>}
          <div className="flex gap-3">
            <button type="submit" disabled={busy} className={BTN}>Confirm resolve</button>
            <button type="button" className="text-xs text-text-secondary hover:underline" onClick={() => { setResolving(false); setLocalError(""); }}>Cancel</button>
          </div>
        </form>
      )}
      <details className="text-xs">
        <summary className="cursor-pointer text-text-secondary">Photos &amp; attachments</summary>
        <div className="mt-2">
          <AttachmentsPanel token={token} docType="site_issue" docId={issue.id} role={role} />
        </div>
      </details>
    </div>
  );
}

function SiteIssuesCard({ token, project, quotation, role, canManage, version, onChanged }) {
  const [issues, setIssues] = useState(null);
  const [team, setTeam] = useState([]);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", severity: "medium" });
  const [local, setLocal] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError("");
    Promise.all([listSiteIssues(token, project.id), listProjectTeam(token, project.id)])
      .then(([i, t]) => { if (!cancelled) { setIssues(i); setTeam(t); } })
      .catch((err) => !cancelled && setError(err.message));
    return () => { cancelled = true; };
  }, [token, project.id, version, local]);

  async function run(fn) {
    setActionError("");
    setBusy(true);
    try {
      await fn();
      setLocal((n) => n + 1);
      onChanged();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const engineerOnTeam = role === "site_engineer" && team.length > 0;
  const canRaise = canManage || engineerOnTeam;
  const planningOff = !quotation;

  function raise(e) {
    e.preventDefault();
    if (!form.title.trim()) { setActionError("Issue title is required."); return; }
    run(async () => {
      await createSiteIssue(token, project.id, {
        title: form.title.trim(),
        description: form.description.trim() || null,
        severity: form.severity,
      });
      setForm({ title: "", description: "", severity: "medium" });
    });
  }

  return (
    <Card title="Site issues" subtitle="Problems found on site, with their review and resolution.">
      <SectionError message={error} />
      {planningOff && <p className="text-xs text-amber-400">{NO_WON_MESSAGE} Raising issues is disabled until then.</p>}
      {actionError && <p className="text-sm text-red-400">{actionError}</p>}
      {!issues && !error && <p className="text-sm text-text-secondary">Loading…</p>}
      {issues && issues.length === 0 && <p className="text-xs text-text-secondary">No site issues raised.</p>}
      {issues && issues.map((i) => (
        <IssueRow key={i.id} token={token} issue={i} role={role} canManage={canManage} busy={busy} run={run} />
      ))}
      {issues && canRaise && (
        <form onSubmit={raise} className="grid grid-cols-1 sm:grid-cols-2 gap-2 border border-border-dark rounded p-3">
          <label className={`${FIELD_LABEL} sm:col-span-2`}>
            Raise an issue -- title
            <input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} disabled={planningOff} className={INPUT} />
          </label>
          <label className={`${FIELD_LABEL} sm:col-span-2`}>
            Description (optional)
            <textarea rows={2} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} disabled={planningOff} className={INPUT} />
          </label>
          <label className={FIELD_LABEL}>
            Severity
            <select value={form.severity} onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value }))} disabled={planningOff} className={INPUT}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </label>
          <div className="sm:self-end">
            <button type="submit" disabled={busy || planningOff} className={BTN}>Raise issue</button>
          </div>
        </form>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ Screen */

/** P5 Agreement & Execution Starter: one scrollable page per project -- start readiness,
 * agreement, project team, milestones/tasks and site issues. Gated in navAccess.js
 * (sales/pm/director/procurement/site_engineer); procurement and site engineers only reach a
 * project's data when they are on its team (the backend answers 403 otherwise, shown here as a
 * friendly empty state). Every authorization decision is re-enforced by the backend. */
export default function Execution({ token, user, project, role, onBack }) {
  const [quotation, setQuotation] = useState(null);
  const [workOrderExists, setWorkOrderExists] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const canManage = MANAGE_ROLES.includes(role);
  const bump = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    // The execution-context endpoint (not the quotations list) so Procurement / Site Engineer team members,
    // who cannot list a project's quotations, still find the Won quotation this screen is built around.
    getExecutionContext(token, project.id)
      .then((ctx) => {
        if (cancelled) return;
        setQuotation(ctx.quotation_id ? { id: ctx.quotation_id, document_no: ctx.quotation_no } : null);
        setWorkOrderExists(ctx.work_order_exists);
      })
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [token, project.id]);

  return (
    <div className="max-w-3xl mx-auto mt-6 mb-10 px-4 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">Execution</h2>
          <p className="text-sm text-text-secondary">
            Project <span className="font-mono">{project.project_no}</span> -- agreement, team and site delivery.
            {role === "sales" && " (Read-only view.)"}
          </p>
        </div>
        {onBack && (
          <button type="button" onClick={onBack} className="text-xs text-text-secondary hover:underline">&larr; Back</button>
        )}
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {loading && <p className="text-sm text-text-secondary">Loading…</p>}
      {!loading && !error && !quotation && (
        <p className="text-sm text-amber-400 bg-amber-500/5 border border-amber-500/30 rounded px-3 py-2">{NO_WON_MESSAGE}</p>
      )}
      {!loading && !error && (
        <>
          <ReadinessCard token={token} quotation={quotation} projectNo={project.project_no} workOrderExists={workOrderExists} canManage={canManage} role={role} version={version} onChanged={bump} />
          <AgreementCard token={token} project={project} quotation={quotation} role={role} canManage={canManage} version={version} onChanged={bump} />
          <TeamCard token={token} project={project} canManage={canManage} version={version} onChanged={bump} />
          <WorkItemsCard token={token} user={user} project={project} quotation={quotation} canManage={canManage} version={version} onChanged={bump} />
          <SiteIssuesCard token={token} project={project} quotation={quotation} role={role} canManage={canManage} version={version} onChanged={bump} />
        </>
      )}
    </div>
  );
}
