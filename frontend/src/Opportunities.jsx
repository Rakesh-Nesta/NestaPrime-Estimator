import { useEffect, useState } from "react";
import {
  linkOpportunityClient,
  listClients,
  listOpportunities,
  updateOpportunityDetails,
  updateOpportunityFollowUp,
  updateOpportunityNotes,
  updateOpportunityStage,
} from "./api";
import { DocumentIcon, FunnelIcon, SearchIcon, UsersIcon } from "./Icons";

const STAGES = ["new", "contacted", "qualified", "won", "lost"];
const TERMINAL_STAGES = ["won", "lost"];
const STATUS_FILTERS = ["", ...STAGES];

// Amendment 44 (Section E step 5): same small-local-duplicate style as
// ClientsAdmin.jsx's own STATUS_PILL_STYLE.
const STAGE_PILL_STYLE = {
  new: "bg-surface-raised text-text-secondary",
  contacted: "bg-gold/10 text-gold",
  qualified: "bg-gold-muted text-gold",
  won: "bg-green-500/10 text-green-400",
  lost: "bg-red-500/10 text-red-400",
};
const STAGE_DOT_STYLE = {
  new: "bg-text-secondary",
  contacted: "bg-gold",
  qualified: "bg-gold",
  won: "bg-green-400",
  lost: "bg-red-400",
};
const TILE_STYLE = {
  won: "border-green-500/30 bg-green-500/5",
  lost: "border-red-500/30 bg-red-500/5",
};

const RELATIONSHIP_TABS = [
  { key: "", label: "All" },
  { key: "lead", label: "Leads" },
  { key: "client", label: "Clients" },
];

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function matchesSearch(needle, ...fields) {
  if (!needle) return true;
  return fields.some((f) => (f || "").toLowerCase().includes(needle));
}

// Same write set as the backend's WRITE_ROLES -- Procurement can read the
// pipeline but not change it.
const canEditDetails = (role) => ["sales", "pm", "director"].includes(role);

// Redesign (2026-09-27, Director's request): same screen, same data and the same server calls -- presented
// as a list with a slide-in details panel instead of stacked cards with every field editable inline. The
// sidebar and header are untouched; only this screen's own content changed.
export default function Opportunities({ token, role, onBack, onStartProject }) {
  const [opportunities, setOpportunities] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [clients, setClients] = useState([]);
  const [relationship, setRelationship] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [linkPicks, setLinkPicks] = useState({});
  const [loadFailed, setLoadFailed] = useState(false);
  const [autoSelectDone, setAutoSelectDone] = useState(false);

  function load() {
    return listOpportunities(token, { relationship: relationship || undefined }).then(setOpportunities);
  }

  // The details panel reads as part of the page, not an optional extra -- so the first row is selected by
  // default as soon as there is one, the same as every mockup shows it. Once, not on every load: closing
  // the panel (or an empty list briefly reloading) must not silently reselect something for the user.
  useEffect(() => {
    if (!autoSelectDone && selectedId === null && opportunities.length > 0) {
      setSelectedId(opportunities[0].id);
      setAutoSelectDone(true);
    }
  }, [opportunities, autoSelectDone, selectedId]);

  useEffect(() => {
    setLoading(true);
    Promise.all([load(), listClients(token).then(setClients)])
      .catch((err) => {
        setError(err.message);
        setLoadFailed(true);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, relationship]);

  const clientNameById = Object.fromEntries(clients.map((c) => [c.id, c.name]));

  async function saveRow(o, values) {
    if (values.stage !== o.stage) {
      await updateOpportunityStage(token, o.id, {
        stage: values.stage,
        next_follow_up_date: TERMINAL_STAGES.includes(values.stage) ? null : values.date || null,
        lost_reason: values.stage === "lost" ? values.lostReason || null : null,
      });
    } else if (!TERMINAL_STAGES.includes(o.stage)) {
      await updateOpportunityFollowUp(token, o.id, {
        next_follow_up_date: values.date,
        follow_up_note: values.note || null,
      });
    }
    await updateOpportunityNotes(token, o.id, { notes: values.notes || null });
    setSelectedId(null);
    await load();
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

  // Amendment 47 (Section 52): fixing a typo in name/phone/email, allowed at
  // any stage. Sending blank contact fields clears them.
  async function saveDetails(o, values) {
    await updateOpportunityDetails(token, o.id, {
      lead_name: values.name,
      lead_phone: values.phone || null,
      lead_email: values.email || null,
    });
    await load();
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading Opportunities…</p>;
  }

  const needle = search.trim().toLowerCase();
  const visible = opportunities.filter(
    (o) =>
      (!statusFilter || o.stage === statusFilter) &&
      matchesSearch(needle, o.lead_name, o.lead_phone, o.lead_email, o.client_id && clientNameById[o.client_id])
  );
  const tabCounts = { "": opportunities.length };
  const selected = opportunities.find((o) => o.id === selectedId) || null;
  const tiles = [
    {
      label: "Total opportunities",
      value: opportunities.length,
      icon: DocumentIcon,
      active: !statusFilter && !relationship,
      onClick: () => { setStatusFilter(""); setRelationship(""); },
    },
    {
      label: "Lead only",
      value: opportunities.filter((o) => !o.client_id).length,
      icon: UsersIcon,
      active: relationship === "lead",
      onClick: () => { setStatusFilter(""); setRelationship("lead"); },
    },
    {
      label: "Won",
      value: opportunities.filter((o) => o.stage === "won").length,
      icon: FunnelIcon,
      tone: "won",
      active: statusFilter === "won",
      onClick: () => setStatusFilter(statusFilter === "won" ? "" : "won"),
    },
    {
      label: "Lost",
      value: opportunities.filter((o) => o.stage === "lost").length,
      icon: FunnelIcon,
      tone: "lost",
      active: statusFilter === "lost",
      onClick: () => setStatusFilter(statusFilter === "lost" ? "" : "lost"),
    },
  ];

  return (
    <div className="max-w-[1400px] mx-auto mt-6 mb-10 px-4 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-text-secondary">Workspace / Customer relationships</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1 flex items-center gap-2">
            <FunnelIcon className="w-6 h-6 text-gold" /> Opportunities
          </h2>
          <p className="text-sm text-text-secondary mt-1">Track every enquiry from first contact to outcome.</p>
        </div>
        <div className="text-right shrink-0">
          <button onClick={onBack} className="bg-gold text-base text-sm rounded px-4 py-2 font-semibold hover:bg-gold-hover">
            View Leads &amp; Clients →
          </button>
          <p className="text-[11px] text-text-secondary mt-1">New enquiries are added in Leads &amp; Clients.</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        {tiles.map((tile) => (
          <button
            key={tile.label}
            onClick={tile.onClick}
            className={`text-left rounded-lg border p-4 hover:-translate-y-0.5 transition-all duration-250 ease-out ${
              tile.tone ? TILE_STYLE[tile.tone] : "bg-surface border-border-dark"
            } ${tile.active ? "ring-1 ring-gold" : ""}`}
          >
            <p className="text-xs uppercase tracking-wide text-text-secondary flex items-center gap-1.5">
              <tile.icon className="w-3.5 h-3.5" />
              {tile.label}
            </p>
            <p
              className={`text-2xl font-heading font-bold mt-1 ${
                tile.tone === "won" ? "text-green-400" : tile.tone === "lost" ? "text-red-400" : "text-text-primary"
              }`}
            >
              {tile.value}
            </p>
          </button>
        ))}
      </div>

      <div className="flex flex-col lg:flex-row gap-5">
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-dark">
            <div className="flex items-center gap-5 overflow-x-auto">
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
                  {t.label} {t.key === relationship && <span className="text-xs text-text-secondary">({tabCounts[""] ?? opportunities.length})</span>}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 pb-2 shrink-0">
              <div className="relative">
                <SearchIcon className="w-3.5 h-3.5 text-text-secondary absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search opportunities…"
                  aria-label="Search opportunities"
                  className="rounded border border-border-dark bg-surface-raised text-text-primary pl-7 pr-2 py-1.5 text-xs w-40"
                />
              </div>
              <label className="flex items-center gap-1.5 text-xs text-text-secondary">
                Status
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5 text-xs"
                >
                  {STATUS_FILTERS.map((s) => (
                    <option key={s} value={s}>
                      {s ? s[0].toUpperCase() + s.slice(1) : "All statuses"}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          {visible.length === 0 && loadFailed ? null : visible.length === 0 ? (
            <p className="text-sm text-text-secondary bg-surface border border-border-dark rounded-lg p-5">
              {needle || statusFilter ? "Nothing matches these filters." : "No opportunities in this view yet."}
            </p>
          ) : (
            <ul className="space-y-2">
              {visible.map((o) => {
                const isSelected = selectedId === o.id;
                const Icon = o.client_id ? UsersIcon : DocumentIcon;
                return (
                  <li
                    key={o.id}
                    className={`bg-surface rounded-lg p-4 border ${isSelected ? "border-gold" : "border-border-dark"}`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="w-9 h-9 rounded bg-surface-raised border border-border-dark flex items-center justify-center shrink-0">
                        <Icon className="w-4 h-4 text-gold" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <p className="font-medium text-text-primary truncate">{o.lead_name}</p>
                          <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full shrink-0 ${STAGE_PILL_STYLE[o.stage]}`}>
                            {o.stage}
                          </span>
                        </div>
                        <p className="text-xs text-text-secondary truncate">
                          {o.client_id ? `Client · ${clientNameById[o.client_id] || "linked"}` : "Lead only · Not linked to a client"}
                          {(o.lead_phone || o.lead_email) && ` · ${[o.lead_phone, o.lead_email].filter(Boolean).join(" · ")}`}
                        </p>
                        <div className="flex items-center justify-between gap-2 mt-1.5">
                          <p className="text-xs text-text-secondary truncate">
                            {o.notes ? <>Notes: {o.notes}</> : " "}
                          </p>
                          {canEditDetails(role) && (
                            <button
                              onClick={() => setSelectedId(o.id)}
                              className="text-xs text-gold hover:underline shrink-0"
                            >
                              Edit details →
                            </button>
                          )}
                        </div>
                        {/* WP6 (correction plan, 2026-09-28): "Start Project" moved from Won to
                            Qualified -- see ProjectPhase's own docstring (app/models/project.py).
                            A Project already started stays "started" regardless of what its
                            Opportunity does afterwards (Won via mark_quotation_won, or Lost). */}
                        {o.project_id ? (
                          <p className="mt-1 text-xs text-green-400">🏁 Project started.</p>
                        ) : (
                          o.stage === "qualified" && (
                            <p className="mt-1 text-xs text-text-secondary">Qualified -- open it to start a Project.</p>
                          )
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {selected && (
          <OpportunityPanel
            opportunity={selected}
            clients={clients}
            clientNameById={clientNameById}
            linkPick={linkPicks[selected.id] || ""}
            onLinkPickChange={(v) => setLinkPicks((p) => ({ ...p, [selected.id]: v }))}
            onLinkClient={() => linkClient(selected)}
            onSave={(values) => saveRow(selected, values)}
            onSaveDetails={(values) => saveDetails(selected, values)}
            onStartProject={onStartProject}
            onClose={() => setSelectedId(null)}
          />
        )}
      </div>
    </div>
  );
}

function OpportunityPanel({
  opportunity: o, clients, clientNameById, linkPick, onLinkPickChange, onLinkClient, onSave, onSaveDetails, onStartProject, onClose,
}) {
  const [values, setValues] = useState({
    name: o.lead_name,
    phone: o.lead_phone || "",
    email: o.lead_email || "",
    stage: o.stage,
    date: o.next_follow_up_date || "",
    note: o.follow_up_note || "",
    lostReason: o.lost_reason || "",
    notes: o.notes || "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const overdue = o.next_follow_up_date && o.next_follow_up_date < todayStr();

  function setField(field, value) {
    setValues((v) => ({ ...v, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!values.name.trim()) {
      setError("A name is required.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      if (values.name !== o.lead_name || values.phone !== (o.lead_phone || "") || values.email !== (o.lead_email || "")) {
        await onSaveDetails(values);
      }
      await onSave(values);
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  const inputClass = "mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2.5 py-2 text-sm";
  const labelClass = "block text-xs font-medium text-text-secondary";

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full lg:w-[22rem] shrink-0 bg-surface border border-border-dark rounded-lg p-5 space-y-4 h-fit lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] overflow-y-auto"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-3 min-w-0">
          <span className="w-9 h-9 rounded bg-surface-raised border border-border-dark flex items-center justify-center shrink-0">
            {o.client_id ? <UsersIcon className="w-4 h-4 text-gold" /> : <DocumentIcon className="w-4 h-4 text-gold" />}
          </span>
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-text-primary truncate">Opportunity details</h3>
            <p className="text-xs text-text-secondary truncate">
              {o.client_id ? `Client · ${clientNameById[o.client_id] || "linked"}` : "Lead only · Not linked to a client"}
            </p>
          </div>
        </div>
        <button type="button" onClick={onClose} aria-label="Close" className="text-text-secondary hover:text-text-primary text-lg leading-none shrink-0">
          ✕
        </button>
      </div>

      <div>
        <label className={labelClass}>Name</label>
        <input required value={values.name} onChange={(e) => setField("name", e.target.value)} className={inputClass} />
      </div>
      <div>
        <label className={labelClass}>Phone</label>
        <input inputMode="tel" value={values.phone} onChange={(e) => setField("phone", e.target.value)} className={inputClass} />
      </div>
      <div>
        <label className={labelClass}>Email</label>
        <input type="email" value={values.email} onChange={(e) => setField("email", e.target.value)} className={inputClass} />
      </div>

      <div>
        <label className={labelClass}>Stage *</label>
        <div className="relative mt-1">
          <span className={`absolute left-2.5 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full ${STAGE_DOT_STYLE[values.stage]}`} />
          <select
            value={values.stage}
            onChange={(e) => setField("stage", e.target.value)}
            className="w-full rounded border border-border-dark bg-surface-raised text-text-primary pl-6 pr-2.5 py-2 text-sm capitalize"
          >
            {STAGES.map((s) => (
              <option key={s} value={s} className="capitalize">
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {!TERMINAL_STAGES.includes(values.stage) && (
        <>
          <div>
            <label className={labelClass}>Follow-up date</label>
            <input
              type="date"
              value={values.date}
              onChange={(e) => setField("date", e.target.value)}
              className={`${inputClass} ${overdue ? "text-red-400" : ""}`}
            />
          </div>
          <div>
            <label className={labelClass}>Follow-up note (optional)</label>
            <input value={values.note} onChange={(e) => setField("note", e.target.value)} className={inputClass} />
          </div>
        </>
      )}
      {values.stage === "lost" && (
        <div>
          <label className={labelClass}>Lost reason (optional)</label>
          <input value={values.lostReason} onChange={(e) => setField("lostReason", e.target.value)} className={inputClass} />
        </div>
      )}

      <div>
        <label className={labelClass}>Notes *</label>
        <textarea
          value={values.notes}
          onChange={(e) => setField("notes", e.target.value)}
          rows={3}
          placeholder="Anything else worth noting -- not tied to any field above."
          className={inputClass}
        />
      </div>

      {!o.client_id && (
        <div className="border-t border-border-dark pt-3">
          <label className={labelClass}>Link to existing client</label>
          <div className="flex items-center gap-2 mt-1">
            <select
              value={linkPick}
              onChange={(e) => onLinkPickChange(e.target.value)}
              className="min-w-0 flex-1 rounded border border-border-dark bg-surface-raised text-text-primary px-2.5 py-2 text-sm"
            >
              <option value="">Select a client…</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={onLinkClient}
              disabled={!linkPick}
              className="text-xs border border-gold/50 text-gold rounded px-3 py-2 hover:bg-gold/10 disabled:opacity-40 shrink-0"
            >
              🔗 Link client
            </button>
          </div>
        </div>
      )}

      {o.stage === "qualified" && o.client_id && !o.project_id && (
        <button
          type="button"
          onClick={() =>
            onStartProject({
              opportunityId: o.id,
              clientId: o.client_id,
              clientName: clientNameById[o.client_id] || "the linked client",
              leadName: o.lead_name,
            })
          }
          className="w-full bg-gold text-base rounded px-4 py-2.5 font-semibold hover:bg-gold-hover"
        >
          Start Project →
        </button>
      )}
      {o.project_id && <p className="text-xs text-green-400">🏁 Project started.</p>}

      {error && <p className="text-xs text-red-400">{error}</p>}
      <button
        type="submit"
        disabled={saving}
        className="w-full bg-gold text-base rounded px-4 py-2.5 font-semibold hover:bg-gold-hover disabled:opacity-50"
      >
        💾 {saving ? "Saving…" : "Save changes"}
      </button>
    </form>
  );
}
