import { useEffect, useState } from "react";
import { listClients, updateClientFollowUp } from "./api";
import { ClockIcon } from "./Icons";

// Amendment 43 (Section E step 4): reuses GET /clients (Amendment 42 already
// returns next_follow_up_date/follow_up_note on every ClientOut) rather than
// a new list endpoint. Org-wide only -- Client has no owner/assigned-rep
// field yet, so a per-rep "my follow-ups" filter isn't honestly buildable
// until Opportunities (step 5) adds one; every sales/pm/director/procurement
// user sees the same queue, same role gate GET /clients already has.
// Not exported -- Dashboard.jsx keeps its own small local copy of this
// filter (same pattern ClientsAdmin.jsx's STATUS_PILL_STYLE comment already
// documents: a small local duplicate rather than a shared import).
function dueFollowUps(clients) {
  const today = new Date().toISOString().slice(0, 10);
  return clients
    .filter((c) => c.next_follow_up_date)
    .sort((a, b) => a.next_follow_up_date.localeCompare(b.next_follow_up_date))
    .map((c) => ({
      ...c,
      // Matches ClientsAdmin.jsx's existing overdue-red convention: only
      // strictly-past dates are "overdue" (red); today is "due", not overdue.
      status: c.next_follow_up_date < today ? "overdue" : c.next_follow_up_date === today ? "due" : "upcoming",
    }));
}

export default function FollowUps({ token, onBack }) {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [drafts, setDrafts] = useState({});

  useEffect(() => {
    listClients(token)
      .then(setClients)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  async function save(clientId) {
    setError("");
    const draft = drafts[clientId] || {};
    try {
      const updated = await updateClientFollowUp(token, clientId, {
        next_follow_up_date: draft.date !== undefined ? draft.date || null : undefined,
        follow_up_note: draft.note !== undefined ? draft.note || null : undefined,
      });
      setClients((cs) => cs.map((c) => (c.id === clientId ? updated : c)));
      setDrafts((d) => ({ ...d, [clientId]: undefined }));
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading Follow-ups…</p>;
  }

  const due = dueFollowUps(clients);

  return (
    <div className="max-w-[1000px] mx-auto mt-6 mb-10 space-y-4 px-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-text-secondary">NestaPrime / Customer Relationships</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1 flex items-center gap-2">
            <ClockIcon className="w-6 h-6 text-gold" /> Follow-ups
          </h2>
          <p className="text-sm text-text-secondary mt-1">
            Every client with a follow-up date set, soonest and most overdue first.
          </p>
        </div>
        <button onClick={onBack} className="text-xs uppercase tracking-wider text-gold hover:text-gold-hover shrink-0">
          ← Back
        </button>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {due.length === 0 ? (
        <p className="text-sm text-text-secondary bg-surface border border-border-dark rounded-lg p-5">
          No client has a follow-up date set right now.
        </p>
      ) : (
        <ul className="divide-y divide-border-dark bg-surface border border-border-dark rounded-lg">
          {due.map((c) => (
            <li key={c.id} className="p-4 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
              <div className="flex-1 min-w-0">
                <p className="font-medium text-text-primary truncate">{c.name}</p>
                {c.follow_up_note && <p className="text-xs text-text-secondary truncate">{c.follow_up_note}</p>}
              </div>
              <span className={`text-xs font-medium shrink-0 ${c.status === "overdue" ? "text-red-400" : "text-text-secondary"}`}>
                {c.status === "overdue" ? "Overdue" : c.status === "due" ? "Due today" : "Upcoming"} · {c.next_follow_up_date}
              </span>
              <div className="flex items-center gap-2 shrink-0">
                <input
                  type="date"
                  value={drafts[c.id]?.date ?? c.next_follow_up_date ?? ""}
                  onChange={(e) => setDrafts((d) => ({ ...d, [c.id]: { ...d[c.id], date: e.target.value } }))}
                  className="rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-0.5 text-xs"
                />
                <input
                  value={drafts[c.id]?.note ?? c.follow_up_note ?? ""}
                  onChange={(e) => setDrafts((d) => ({ ...d, [c.id]: { ...d[c.id], note: e.target.value } }))}
                  placeholder="Note (optional)"
                  className="w-32 rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-0.5 text-xs"
                />
                <button onClick={() => save(c.id)} className="text-gold hover:underline text-xs shrink-0">
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
