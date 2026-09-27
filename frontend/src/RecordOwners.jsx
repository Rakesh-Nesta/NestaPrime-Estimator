import { useCallback, useEffect, useState } from "react";
import {
  acceptOwnerSuggestions,
  assignOwner,
  getOwnershipOverview,
  listUnassigned,
  reassignAllOwnership,
  setOwnRecordsSwitch,
} from "./api";
import { ownerLabel } from "./OwnerControl";

// Amendment 60 (Section 63): "Record owners" -- who owns which client, project and enquiry, the records that have
// no owner yet, and the Director's switch that makes a Sales user see only their own. PM and Director see this;
// only the Director turns the switch on, and should do so only once nothing important is left unassigned.
const KINDS = [
  { key: "client", label: "Clients", one: "client" },
  { key: "project", label: "Projects", one: "project" },
  { key: "opportunity", label: "Enquiries", one: "enquiry" },
];

export default function RecordOwners({ token, currentUser }) {
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [kind, setKind] = useState("client");
  const [rows, setRows] = useState(null);
  const [busy, setBusy] = useState(false);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const isDirector = currentUser?.role === "director";

  const loadOverview = useCallback(
    () =>
      getOwnershipOverview(token)
        .then(setOverview)
        .catch((err) => setError(err.message)),
    [token]
  );
  const loadRows = useCallback(
    (k) =>
      listUnassigned(token, k)
        .then(setRows)
        .catch((err) => setError(err.message)),
    [token]
  );

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);
  useEffect(() => {
    setRows(null);
    loadRows(kind);
  }, [kind, loadRows]);

  async function run(action, success) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      if (success) setNotice(success);
      await Promise.all([loadOverview(), loadRows(kind)]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function toggleSwitch() {
    const turningOn = !overview.switch_on;
    const unassigned = Object.values(overview.totals).reduce((n, t) => n + t.unassigned, 0);
    const question = turningOn
      ? `Salespeople will see only the clients, projects and enquiries they own.${
          unassigned > 0 ? ` ${unassigned} record(s) still have no owner and will be hidden from every salesperson.` : ""
        } Turn it on?`
      : "Salespeople will see every client, project and enquiry again. Turn it off?";
    if (!window.confirm(question)) return;
    run(() => setOwnRecordsSwitch(token, turningOn), turningOn ? "Own-records is now on." : "Own-records is now off.");
  }

  function moveAll() {
    if (!from || !to) return;
    const fromName = overview.by_owner.find((o) => o.user_id === from)?.name || "that person";
    const toName = overview.owners.find((o) => o.user_id === to)?.name || "the new owner";
    if (!window.confirm(`Move everything ${fromName} owns to ${toName}?`)) return;
    run(async () => {
      const moved = await reassignAllOwnership(token, from, to);
      setNotice(`Moved ${moved.clients} client(s), ${moved.projects} project(s) and ${moved.opportunities} enquiry(ies) to ${toName}.`);
      setFrom("");
      setTo("");
    });
  }

  if (!overview) {
    return (
      <div className="bg-surface shadow rounded-lg p-6">
        {error ? <p className="text-sm text-red-400">{error}</p> : <p className="text-sm text-text-secondary">Loading…</p>}
      </div>
    );
  }

  const suggestible = rows ? rows.filter((r) => r.suggested_owner_id).length : 0;
  const kindLabel = KINDS.find((k) => k.key === kind);

  return (
    <div className="space-y-6">
      {error && <p className="text-sm text-red-400">{error}</p>}
      {notice && <p className="text-sm text-green-400">{notice}</p>}

      <section className="bg-surface shadow rounded-lg p-6 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-text-primary">Each salesperson sees only their own</h3>
            <p className="text-xs text-text-secondary mt-1 max-w-prose">
              When this is on, a Sales user sees only the clients, projects and enquiries they own -- and their
              quotations, estimates and cost sheets. PM and Director always see everything. A record with no owner is
              hidden from every salesperson, so assign the ones below first.
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <span
              className={`text-[10px] uppercase tracking-wider px-2 py-1 rounded-full ${
                overview.switch_on ? "bg-green-500/10 text-green-400" : "bg-surface-raised text-text-secondary"
              }`}
            >
              {overview.switch_on ? "On" : "Off"}
            </span>
            {isDirector ? (
              <button
                onClick={toggleSwitch}
                disabled={busy}
                className="text-sm bg-gold hover:bg-gold-hover text-base rounded px-4 py-2 disabled:opacity-50"
              >
                {overview.switch_on ? "Turn off" : "Turn on"}
              </button>
            ) : (
              <span className="text-xs text-text-secondary">Only the Director can change this.</span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3 pt-2">
          {KINDS.map((k) => {
            const t = overview.totals[k.key];
            return (
              <div key={k.key} className="border border-border-dark rounded-lg p-3">
                <p className="text-xs uppercase tracking-wide text-text-secondary">{k.label}</p>
                <p className="text-xl font-heading font-bold text-text-primary mt-1 tabular-nums">{t.total}</p>
                <p className={`text-xs mt-0.5 tabular-nums ${t.unassigned > 0 ? "text-amber-400" : "text-text-secondary"}`}>
                  {t.unassigned} without an owner
                </p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="bg-surface shadow rounded-lg p-6 space-y-3">
        <h3 className="text-base font-semibold text-text-primary">Who owns what</h3>
        {overview.by_owner.length === 0 ? (
          <p className="text-sm text-text-secondary">No record has an owner yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[22rem]">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-text-secondary border-b border-border-dark">
                  <th className="py-2 pr-3 font-medium">Person</th>
                  <th className="py-2 px-3 font-medium text-right">Clients</th>
                  <th className="py-2 px-3 font-medium text-right">Projects</th>
                  <th className="py-2 pl-3 font-medium text-right">Enquiries</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-dark tabular-nums">
                {overview.by_owner.map((o) => (
                  <tr key={o.user_id}>
                    <td className="py-2 pr-3 text-text-primary">
                      {o.name}
                      <span className="ml-2 text-[10px] uppercase tracking-wider text-text-secondary">{o.role}</span>
                      {!o.is_active && <span className="ml-2 text-[10px] uppercase tracking-wider text-amber-400">inactive</span>}
                    </td>
                    <td className="py-2 px-3 text-right">{o.clients}</td>
                    <td className="py-2 px-3 text-right">{o.projects}</td>
                    <td className="py-2 pl-3 text-right">{o.opportunities}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="border-t border-border-dark pt-3">
          <p className="text-sm font-medium text-text-primary">Move everything from one person to another</p>
          <p className="text-xs text-text-secondary mt-0.5">
            For someone who is leaving or changing role -- every client, project and enquiry they own.
          </p>
          <div className="flex flex-wrap items-center gap-2 mt-2">
            <select
              id="owners-from"
              aria-label="From"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
            >
              <option value="">From…</option>
              {overview.by_owner.map((o) => (
                <option key={o.user_id} value={o.user_id}>
                  {ownerLabel(o)}
                  {o.is_active ? "" : " (inactive)"}
                </option>
              ))}
            </select>
            <span className="text-text-secondary text-sm">to</span>
            <select
              id="owners-to"
              aria-label="To"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
            >
              <option value="">To…</option>
              {overview.owners
                .filter((o) => o.user_id !== from)
                .map((o) => (
                  <option key={o.user_id} value={o.user_id}>
                    {ownerLabel(o)}
                  </option>
                ))}
            </select>
            <button
              onClick={moveAll}
              disabled={busy || !from || !to}
              className="text-sm border border-gold/50 text-gold hover:bg-gold/10 rounded px-4 py-2 disabled:opacity-40"
            >
              Move everything
            </button>
          </div>
        </div>
      </section>

      <section className="bg-surface shadow rounded-lg p-6 space-y-3">
        <h3 className="text-base font-semibold text-text-primary">Without an owner</h3>
        <div className="flex gap-1 border-b border-border-dark overflow-x-auto">
          {KINDS.map((k) => (
            <button
              key={k.key}
              onClick={() => setKind(k.key)}
              className={`text-sm px-3 py-2 border-b-2 -mb-px whitespace-nowrap ${
                kind === k.key ? "border-gold text-gold font-medium" : "border-transparent text-text-secondary hover:text-text-primary"
              }`}
            >
              {k.label} ({overview.totals[k.key].unassigned})
            </button>
          ))}
        </div>

        {suggestible > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="text-text-secondary">{suggestible} of these have a suggested owner, taken from the records themselves.</span>
            <button
              onClick={() =>
                window.confirm(`Assign the ${suggestible} suggested owner(s) shown below?`) &&
                run(() => acceptOwnerSuggestions(token, kind), `Assigned ${suggestible} suggested owner(s).`)
              }
              disabled={busy}
              className="text-sm border border-gold/50 text-gold hover:bg-gold/10 rounded px-3 py-1.5 disabled:opacity-40"
            >
              Accept all suggestions
            </button>
          </div>
        )}

        {rows === null ? (
          <p className="text-sm text-text-secondary">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-text-secondary">Every {kindLabel.one} has an owner.</p>
        ) : (
          <ul className="divide-y divide-border-dark">
            {rows.map((r) => (
              <li key={r.id} className="py-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
                <div className="min-w-0">
                  <p className="text-sm text-text-primary break-words">{r.label}</p>
                  {r.detail && <p className="text-xs text-text-secondary break-words">{r.detail}</p>}
                  {r.suggested_owner_name && (
                    <p className="text-xs text-amber-400 mt-0.5">
                      Suggested: {r.suggested_owner_name} -- {r.evidence}
                    </p>
                  )}
                </div>
                <select
                  aria-label={`Assign ${r.label}`}
                  value=""
                  disabled={busy}
                  onChange={(e) => e.target.value && run(() => assignOwner(token, kind, r.id, e.target.value))}
                  className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5 text-sm max-w-[12rem]"
                >
                  <option value="">Assign to…</option>
                  {r.suggested_owner_id && <option value={r.suggested_owner_id}>{r.suggested_owner_name} (suggested)</option>}
                  {overview.owners
                    .filter((o) => o.user_id !== r.suggested_owner_id)
                    .map((o) => (
                      <option key={o.user_id} value={o.user_id}>
                        {ownerLabel(o)}
                      </option>
                    ))}
                </select>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
