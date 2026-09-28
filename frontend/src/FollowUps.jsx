import { useEffect, useState } from "react";
import { listClients, listOpportunities, listFollowUps, updateFollowUp } from "./api";
import { CalendarIcon, ClockIcon } from "./Icons";
import { CAN_ASSIGN_OWNERS, ownerLabel, useOwners } from "./OwnerControl";

// Amendment 43 (Section E step 4) built this as an org-wide Client queue.
// Amendment 44 Phase D folds Opportunities into the same queue (a telecaller
// working both needs one list, not two) and adds "My follow-ups".
//
// WP2 fix (2026-09-27): "My follow-ups" filters both Clients and
// Opportunities by their current owner_id (Amendment 60), not by who
// originally created the record.
//
// WP5 integration (correction plan, 2026-09-28): this screen is now wired to
// the shared /follow-ups API instead of reading Client/Opportunity rows
// directly -- ClientsAdmin.jsx and Opportunities.jsx keep calling their own
// existing endpoints unchanged (updateClientFollowUp/updateOpportunityFollowUp),
// which the backend now writes through to this same shared table on their
// behalf (app/core/follow_up_sync.py), so an action taken on either source
// screen shows up here immediately. listClients/listOpportunities are still
// fetched, but only to resolve an entity_id to a display name -- the shared
// API itself has no denormalised name field.
function mergeFollowUps(followUps, clientNames, opportunityNames, onlyMine, userId) {
  const today = new Date().toISOString().slice(0, 10);
  // A completed/cancelled follow-up is done -- it drops off this queue rather
  // than cluttering "upcoming" forever, same as the old system where clearing
  // the date removed it from view.
  const open = followUps.filter((f) => f.status === "open" || f.status === "in_progress" || f.status === "waiting");
  const mine = onlyMine ? open.filter((f) => f.owner_id === userId) : open;
  return mine
    .map((f) => ({
      key: f.id,
      id: f.id,
      kind: f.entity_type,
      entityId: f.entity_id,
      name: (f.entity_type === "client" ? clientNames : opportunityNames)[f.entity_id] || "Unknown record",
      date: f.due_date,
      note: f.next_action,
      ownerId: f.owner_id,
      lifecycle: f.status,
      waitingParty: f.waiting_party,
    }))
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((i) => ({
      ...i,
      // Matches ClientsAdmin.jsx's existing overdue-red convention: only
      // strictly-past dates are "overdue" (red); today is "due", not overdue.
      status: i.date < today ? "overdue" : i.date === today ? "due" : "upcoming",
    }));
}

const STATUS_TABS = [
  { key: "", label: "All follow-ups" },
  { key: "overdue", label: "Overdue" },
  { key: "due", label: "Today" },
  { key: "upcoming", label: "Upcoming" },
];

function Toggle({ checked, onChange, label }) {
  return (
    <label className="flex items-center gap-2.5 cursor-pointer select-none">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors duration-200 ${
          checked ? "bg-gold" : "bg-surface-raised border border-border-dark"
        }`}
      >
        <span
          className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform duration-200 ${
            checked ? "translate-x-4" : "translate-x-1"
          }`}
        />
      </button>
      <span className="text-sm text-text-secondary">{label}</span>
    </label>
  );
}

// Redesign (2026-09-27, Director's request): same screen, same data and the same server calls -- summary
// tiles and status tabs on top of the existing merged queue, and an illustrated empty state pointing at
// Leads & Clients. Sidebar and header are untouched; only this screen's own content changed.
export default function FollowUps({ token, userId, role, onBack, onOpenLeadsClients }) {
  const [clients, setClients] = useState([]);
  const [opportunities, setOpportunities] = useState([]);
  const [followUps, setFollowUps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [drafts, setDrafts] = useState({});
  const [onlyMine, setOnlyMine] = useState(false);
  const [statusTab, setStatusTab] = useState("");
  const [loadFailed, setLoadFailed] = useState(false);
  const owners = useOwners(token, role);
  const canReassign = CAN_ASSIGN_OWNERS.includes(role);

  function reload() {
    return Promise.all([
      listClients(token).then(setClients),
      listOpportunities(token).then(setOpportunities),
      listFollowUps(token).then(setFollowUps),
    ]);
  }

  useEffect(() => {
    setLoading(true);
    reload()
      .catch((err) => {
        setError(err.message);
        setLoadFailed(true);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function reschedule(item) {
    setError("");
    const draft = drafts[item.key] || {};
    const date = draft.date !== undefined ? draft.date : item.date;
    if (!date) {
      setError("A follow-up always needs a date -- pick one, or complete/close the record instead.");
      return;
    }
    try {
      const updated = await updateFollowUp(token, item.id, {
        due_date: date,
        next_action: (draft.note !== undefined ? draft.note : item.note) || "Follow up",
      });
      setFollowUps((rows) => rows.map((r) => (r.id === updated.id ? updated : r)));
      setDrafts((d) => ({ ...d, [item.key]: undefined }));
    } catch (err) {
      setError(err.message);
    }
  }

  async function complete(item) {
    setError("");
    try {
      const updated = await updateFollowUp(token, item.id, { status: "completed" });
      setFollowUps((rows) => rows.map((r) => (r.id === updated.id ? updated : r)));
    } catch (err) {
      // The Opportunity last-open-follow-up guard answers 400 with a message telling the
      // user to reschedule instead -- surfaced as-is rather than a generic failure.
      setError(err.message);
    }
  }

  async function reassign(item, newOwnerId) {
    setError("");
    try {
      const updated = await updateFollowUp(token, item.id, { owner_id: newOwnerId || null });
      setFollowUps((rows) => rows.map((r) => (r.id === updated.id ? updated : r)));
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading Follow-ups…</p>;
  }

  const clientNames = Object.fromEntries(clients.map((c) => [c.id, c.name]));
  const opportunityNames = Object.fromEntries(opportunities.map((o) => [o.id, o.lead_name]));
  const allItems = mergeFollowUps(followUps, clientNames, opportunityNames, onlyMine, userId);
  const items = statusTab ? allItems.filter((i) => i.status === statusTab) : allItems;
  const tabCounts = {
    "": allItems.length,
    overdue: allItems.filter((i) => i.status === "overdue").length,
    due: allItems.filter((i) => i.status === "due").length,
    upcoming: allItems.filter((i) => i.status === "upcoming").length,
  };

  const tiles = [
    { key: "overdue", label: "Overdue", value: tabCounts.overdue, icon: ClockIcon, tone: "text-red-400" },
    { key: "due", label: "Due today", value: tabCounts.due, icon: ClockIcon, tone: "text-gold" },
    { key: "upcoming", label: "Upcoming", value: tabCounts.upcoming, icon: CalendarIcon, tone: "text-text-primary" },
  ];

  return (
    <div className="max-w-[1000px] mx-auto mt-6 mb-10 space-y-4 px-4 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-text-secondary">Workspace / Customer relationships</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1 flex items-center gap-2">
            <ClockIcon className="w-6 h-6 text-gold" /> Follow-ups
          </h2>
          <p className="text-sm text-text-secondary mt-1">Stay on top of every client conversation.</p>
        </div>
        {onBack && (
          <button onClick={onBack} className="text-xs uppercase tracking-wider text-gold hover:text-gold-hover shrink-0">
            ← Back
          </button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-4">
        {tiles.map((tile) => (
          <button
            key={tile.key}
            onClick={() => setStatusTab(statusTab === tile.key ? "" : tile.key)}
            className={`text-left bg-surface border rounded-lg p-4 flex items-center justify-between gap-2 hover:-translate-y-0.5 transition-all duration-250 ease-out ${
              statusTab === tile.key ? "border-gold" : "border-border-dark"
            }`}
          >
            <span className="min-w-0">
              <span className={`text-xs uppercase tracking-wide flex items-center gap-1.5 ${tile.tone}`}>
                <tile.icon className="w-3.5 h-3.5" />
                {tile.label}
              </span>
              <span className="text-xl font-heading font-bold text-text-primary block mt-1">{tile.value}</span>
            </span>
            <span className="text-text-secondary shrink-0">›</span>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-dark">
        <div className="flex items-center gap-5 overflow-x-auto">
          {STATUS_TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setStatusTab(t.key)}
              className={`text-sm pb-2.5 border-b-2 whitespace-nowrap transition-colors duration-200 ${
                statusTab === t.key
                  ? "text-gold border-gold font-medium"
                  : "text-text-secondary border-transparent hover:text-text-primary"
              }`}
            >
              {t.label} <span className="text-xs text-text-secondary">({tabCounts[t.key]})</span>
            </button>
          ))}
        </div>
        <div className="pb-2 shrink-0">
          <Toggle checked={onlyMine} onChange={setOnlyMine} label="My follow-ups" />
        </div>
      </div>
      {onlyMine && (
        <p className="text-xs text-text-secondary -mt-2">
          Narrows to the clients and leads currently assigned to you.
        </p>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}

      {items.length === 0 && loadFailed ? null : items.length === 0 ? (
        <div className="bg-surface border border-border-dark rounded-lg p-10 text-center space-y-4">
          <div className="mx-auto w-16 h-16 rounded-full bg-gold/10 flex items-center justify-center">
            <CalendarIcon className="w-8 h-8 text-gold" />
          </div>
          <div>
            <p className="text-text-primary font-heading font-bold text-lg">No follow-ups scheduled.</p>
            <p className="text-sm text-text-secondary mt-1">
              {statusTab || onlyMine
                ? "Nothing matches these filters right now."
                : "No client or lead has an open follow-up. Set one in Leads & Clients to see it here."}
            </p>
          </div>
          {onOpenLeadsClients && (
            <button
              onClick={onOpenLeadsClients}
              className="bg-gold text-base text-sm rounded px-5 py-2.5 font-semibold hover:bg-gold-hover"
            >
              Go to Leads &amp; Clients →
            </button>
          )}
          <p className="text-xs text-text-secondary">Follow-ups appear here with overdue items first.</p>

          <div className="border-t border-border-dark pt-6 mt-6 grid sm:grid-cols-3 gap-6 text-left">
            <p className="sm:col-span-3 text-sm font-semibold text-text-primary text-center -mt-2 mb-1">
              Schedule your first follow-up
            </p>
            {[
              { n: 1, title: "Open a lead or client", body: "Go to Leads & Clients and open the relevant record." },
              { n: 2, title: "Set a follow-up date and note", body: "Add a follow-up date and a note in the client or lead record." },
              { n: 3, title: "Save your changes", body: "Save the record to schedule your follow-up." },
            ].map((step) => (
              <div key={step.n} className="flex items-start gap-3">
                <span className="w-7 h-7 rounded-full border border-gold/50 text-gold text-xs font-semibold flex items-center justify-center shrink-0">
                  {step.n}
                </span>
                <div>
                  <p className="text-sm font-medium text-text-primary">{step.title}</p>
                  <p className="text-xs text-text-secondary mt-0.5">{step.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
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
                <button onClick={() => reschedule(c)} className="text-gold hover:underline text-xs shrink-0">
                  Save
                </button>
                <button onClick={() => complete(c)} className="text-emerald-400 hover:underline text-xs shrink-0">
                  Complete
                </button>
                {canReassign && (
                  <select
                    aria-label="Reassign"
                    value={c.ownerId || ""}
                    onChange={(e) => reassign(c, e.target.value)}
                    className="rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-0.5 text-xs max-w-[9rem]"
                  >
                    <option value="">Unassigned</option>
                    {owners.options.map((o) => (
                      <option key={o.user_id} value={o.user_id}>
                        {ownerLabel(o)}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
