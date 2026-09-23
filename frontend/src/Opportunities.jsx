import { useEffect, useState } from "react";
import { linkOpportunityClient, listClients, listOpportunities, updateOpportunityFollowUp, updateOpportunityStage } from "./api";
import { FunnelIcon } from "./Icons";

const STAGES = ["new", "contacted", "qualified", "won", "lost"];
const TERMINAL_STAGES = ["won", "lost"];

// Amendment 44 (Section E step 5): same small-local-duplicate style as
// ClientsAdmin.jsx's own STATUS_PILL_STYLE.
const STAGE_PILL_STYLE = {
  new: "bg-surface-raised text-text-secondary",
  contacted: "bg-gold/10 text-gold",
  qualified: "bg-gold-muted text-gold",
  won: "bg-green-500/10 text-green-400",
  lost: "bg-red-500/10 text-red-400",
};

const RELATIONSHIP_TABS = [
  { key: "", label: "All" },
  { key: "lead", label: "Leads" },
  { key: "client", label: "Clients" },
];

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

export default function Opportunities({ token, onBack }) {
  const [opportunities, setOpportunities] = useState([]);
  const [clients, setClients] = useState([]);
  const [relationship, setRelationship] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [drafts, setDrafts] = useState({});
  const [linkPicks, setLinkPicks] = useState({});

  function load() {
    return listOpportunities(token, { relationship: relationship || undefined }).then(setOpportunities);
  }

  useEffect(() => {
    setLoading(true);
    Promise.all([load(), listClients(token).then(setClients)])
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, relationship]);

  const clientNameById = Object.fromEntries(clients.map((c) => [c.id, c.name]));

  function draftFor(o) {
    return drafts[o.id] || { stage: o.stage, date: o.next_follow_up_date || "", note: o.follow_up_note || "" };
  }
  function setDraftField(id, field, value) {
    setDrafts((d) => ({ ...d, [id]: { ...draftFor(opportunities.find((o) => o.id === id)), ...d[id], [field]: value } }));
  }

  async function saveRow(o) {
    setError("");
    const draft = draftFor(o);
    try {
      if (draft.stage !== o.stage) {
        await updateOpportunityStage(token, o.id, {
          stage: draft.stage,
          next_follow_up_date: TERMINAL_STAGES.includes(draft.stage) ? null : draft.date || null,
          lost_reason: draft.stage === "lost" ? draft.lostReason || null : null,
        });
      } else if (!TERMINAL_STAGES.includes(o.stage)) {
        await updateOpportunityFollowUp(token, o.id, {
          next_follow_up_date: draft.date,
          follow_up_note: draft.note || null,
        });
      }
      setDrafts((d) => ({ ...d, [o.id]: undefined }));
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function linkClient(o) {
    setError("");
    const clientId = linkPicks[o.id];
    if (!clientId) return;
    try {
      await linkOpportunityClient(token, o.id, { client_id: clientId });
      setLinkPicks((p) => ({ ...p, [o.id]: undefined }));
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading Opportunities…</p>;
  }

  return (
    <div className="max-w-[1000px] mx-auto mt-6 mb-10 space-y-4 px-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-text-secondary">NestaPrime / Customer Relationships</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1 flex items-center gap-2">
            <FunnelIcon className="w-6 h-6 text-gold" /> Opportunities
          </h2>
          <p className="text-sm text-text-secondary mt-1">
            Leads and enquiries, from first contact through Won or Lost. New enquiries start on
            "Leads & Clients" -- "Add Enquiry".
          </p>
        </div>
        <button onClick={onBack} className="text-xs uppercase tracking-wider text-gold hover:text-gold-hover shrink-0">
          ← Back
        </button>
      </div>

      <div className="flex items-center gap-5 border-b border-border-dark">
        {RELATIONSHIP_TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setRelationship(t.key)}
            className={`text-sm pb-2.5 border-b-2 whitespace-nowrap transition-colors duration-200 ${
              relationship === t.key
                ? "text-gold border-gold font-medium"
                : "text-text-secondary border-transparent hover:text-text-primary"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {opportunities.length === 0 ? (
        <p className="text-sm text-text-secondary bg-surface border border-border-dark rounded-lg p-5">
          No opportunities in this view yet.
        </p>
      ) : (
        <ul className="space-y-3">
          {opportunities.map((o) => {
            const draft = draftFor(o);
            const overdue = o.next_follow_up_date && o.next_follow_up_date < todayStr();
            const closed = TERMINAL_STAGES.includes(o.stage);
            const dirty = draft.stage !== o.stage || draft.date !== (o.next_follow_up_date || "") || draft.note !== (o.follow_up_note || "");
            return (
              <li key={o.id} className="bg-surface border border-border-dark rounded-lg p-4 space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-text-primary truncate">{o.lead_name}</p>
                    <p className="text-xs text-text-secondary truncate">
                      {o.client_id ? `Client · ${clientNameById[o.client_id] || "linked"}` : "Lead only -- not yet a Client"}
                      {(o.lead_phone || o.lead_email) && ` · ${[o.lead_phone, o.lead_email].filter(Boolean).join(" · ")}`}
                    </p>
                  </div>
                  <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full shrink-0 ${STAGE_PILL_STYLE[o.stage]}`}>
                    {o.stage}
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <select
                    value={draft.stage}
                    onChange={(e) => setDraftField(o.id, "stage", e.target.value)}
                    className="rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-1"
                  >
                    {STAGES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>

                  {!TERMINAL_STAGES.includes(draft.stage) && (
                    <>
                      <input
                        type="date"
                        value={draft.date}
                        onChange={(e) => setDraftField(o.id, "date", e.target.value)}
                        className={`rounded border border-border-dark bg-surface-raised px-1.5 py-1 ${overdue ? "text-red-400" : "text-text-primary"}`}
                      />
                      <input
                        value={draft.note}
                        onChange={(e) => setDraftField(o.id, "note", e.target.value)}
                        placeholder="Note (optional)"
                        className="flex-1 min-w-[8rem] rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-1"
                      />
                    </>
                  )}
                  {draft.stage === "lost" && (
                    <input
                      value={draft.lostReason || ""}
                      onChange={(e) => setDraftField(o.id, "lostReason", e.target.value)}
                      placeholder="Lost reason (optional)"
                      className="flex-1 min-w-[8rem] rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-1"
                    />
                  )}

                  <button
                    onClick={() => saveRow(o)}
                    disabled={!dirty && closed}
                    className="text-gold hover:underline shrink-0 disabled:opacity-40 disabled:no-underline"
                  >
                    Save
                  </button>
                </div>

                {!o.client_id && (
                  <div className="flex items-center gap-2 text-xs border-t border-border-dark pt-2">
                    <span className="text-text-secondary">Link to an existing client:</span>
                    <select
                      value={linkPicks[o.id] || ""}
                      onChange={(e) => setLinkPicks((p) => ({ ...p, [o.id]: e.target.value }))}
                      className="rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-1"
                    >
                      <option value="">Select a client…</option>
                      {clients.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                    <button onClick={() => linkClient(o)} disabled={!linkPicks[o.id]} className="text-gold hover:underline disabled:opacity-40">
                      Link
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
