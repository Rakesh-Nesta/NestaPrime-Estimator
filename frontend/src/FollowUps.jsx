import { useEffect, useState } from "react";
import {
  listClients,
  listOpportunities,
  updateClientFollowUp,
  updateOpportunityFollowUp,
} from "./api";
import { ClockIcon } from "./Icons";

// Amendment 43 (Section E step 4) built this as an org-wide Client queue.
// Amendment 44 Phase D folds Opportunities into the same queue (a telecaller
// working both needs one list, not two) and adds "My follow-ups": now that
// Opportunity.created_by_id exists there is finally an owner to filter on.
// Client still has no owner field, so the toggle only ever narrows the
// Opportunity half -- Clients stay org-wide, with a note saying so, rather
// than being silently dropped from the filtered view.
//
// Not exported -- Dashboard.jsx keeps its own small local copy of this
// merge (same pattern ClientsAdmin.jsx's STATUS_PILL_STYLE comment already
// documents: a small local duplicate rather than a shared import).
function mergeFollowUps(clients, opportunities, onlyMine, userId) {
  const today = new Date().toISOString().slice(0, 10);
  const mine = onlyMine ? opportunities.filter((o) => o.created_by_id === userId) : opportunities;
  return [
    ...clients.map((c) => ({
      key: `client-${c.id}`,
      kind: "client",
      id: c.id,
      name: c.name,
      date: c.next_follow_up_date,
      note: c.follow_up_note,
    })),
    ...mine.map((o) => ({
      key: `opportunity-${o.id}`,
      kind: "opportunity",
      id: o.id,
      name: o.lead_name,
      date: o.next_follow_up_date,
      note: o.follow_up_note,
    })),
  ]
    .filter((i) => i.date)
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((i) => ({
      ...i,
      // Matches ClientsAdmin.jsx's existing overdue-red convention: only
      // strictly-past dates are "overdue" (red); today is "due", not overdue.
      status: i.date < today ? "overdue" : i.date === today ? "due" : "upcoming",
    }));
}

export default function FollowUps({ token, userId, onBack }) {
  const [clients, setClients] = useState([]);
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [drafts, setDrafts] = useState({});
  const [onlyMine, setOnlyMine] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    Promise.all([listClients(token).then(setClients), listOpportunities(token).then(setOpportunities)])
      .catch((err) => {
        setError(err.message);
        setLoadFailed(true);
      })
      .finally(() => setLoading(false));
  }, [token]);

  async function save(item) {
    setError("");
    const draft = drafts[item.key] || {};
    try {
      if (item.kind === "client") {
        const updated = await updateClientFollowUp(token, item.id, {
          next_follow_up_date: draft.date !== undefined ? draft.date || null : undefined,
          follow_up_note: draft.note !== undefined ? draft.note || null : undefined,
        });
        setClients((cs) => cs.map((c) => (c.id === item.id ? updated : c)));
      } else {
        const date = draft.date !== undefined ? draft.date : item.date;
        if (!date) {
          setError("An Opportunity always needs a follow-up date -- pick one, or close it as Won/Lost.");
          return;
        }
        const updated = await updateOpportunityFollowUp(token, item.id, {
          next_follow_up_date: date,
          follow_up_note: (draft.note !== undefined ? draft.note : item.note) || null,
        });
        setOpportunities((os) => os.map((o) => (o.id === item.id ? updated : o)));
      }
      setDrafts((d) => ({ ...d, [item.key]: undefined }));
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading Follow-ups…</p>;
  }

  const items = mergeFollowUps(clients, opportunities, onlyMine, userId);

  return (
    <div className="max-w-[1000px] mx-auto mt-6 mb-10 space-y-4 px-4 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-text-secondary">NestaPrime / Customer Relationships</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1 flex items-center gap-2">
            <ClockIcon className="w-6 h-6 text-gold" /> Follow-ups
          </h2>
          <p className="text-sm text-text-secondary mt-1">
            Every client and lead with a follow-up date set, soonest and most overdue first.
          </p>
        </div>
        <button onClick={onBack} className="text-xs uppercase tracking-wider text-gold hover:text-gold-hover shrink-0">
          ← Back
        </button>
      </div>

      <div className="flex items-center gap-2">
        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
          <input type="checkbox" checked={onlyMine} onChange={(e) => setOnlyMine(e.target.checked)} />
          My follow-ups
        </label>
        {onlyMine && (
          <span className="text-xs text-text-secondary">
            Narrows leads to the ones you created. Clients have no owner yet, so all are still shown.
          </span>
        )}
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {items.length === 0 && loadFailed ? null : items.length === 0 ? (
        <p className="text-sm text-text-secondary bg-surface border border-border-dark rounded-lg p-5">
          {onlyMine
            ? "None of your leads has a follow-up date set right now."
            : "No client or lead has a follow-up date set right now."}
        </p>
      ) : (
        <ul className="divide-y divide-border-dark bg-surface border border-border-dark rounded-lg">
          {items.map((c) => (
            <li key={c.key} className="p-4 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
              <div className="flex-1 min-w-0">
                <p className="font-medium text-text-primary break-words">
                  {c.name}
                  <span className="ml-2 text-[10px] uppercase tracking-wider text-text-secondary">
                    {c.kind === "client" ? "client" : "lead"}
                  </span>
                </p>
                {c.note && <p className="text-xs text-text-secondary truncate">{c.note}</p>}
              </div>
              <span className={`text-xs font-medium shrink-0 ${c.status === "overdue" ? "text-red-400" : "text-text-secondary"}`}>
                {c.status === "overdue" ? "Overdue" : c.status === "due" ? "Due today" : "Upcoming"} · {c.date}
              </span>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="date"
                  value={drafts[c.key]?.date ?? c.date ?? ""}
                  onChange={(e) => setDrafts((d) => ({ ...d, [c.key]: { ...d[c.key], date: e.target.value } }))}
                  className="rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-0.5 text-xs"
                />
                <input
                  value={drafts[c.key]?.note ?? c.note ?? ""}
                  onChange={(e) => setDrafts((d) => ({ ...d, [c.key]: { ...d[c.key], note: e.target.value } }))}
                  placeholder="Note (optional)"
                  className="w-full sm:w-32 rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-0.5 text-xs"
                />
                <button onClick={() => save(c)} className="text-gold hover:underline text-xs shrink-0">
                  Save
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
