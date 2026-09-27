import { useEffect, useState } from "react";
import {
  createClient,
  createOpportunity,
  listClients,
  listOpportunities,
  listProjects,
  updateClientConsent,
  updateClientDetails,
  updateClientFlags,
  updateClientFollowUp,
  updateClientNotes,
  updateOpportunityDetails,
} from "./api";
import { BellIcon, FunnelIcon, GridIcon, SearchIcon, UsersIcon } from "./Icons";
import OwnerControl, { CAN_ASSIGN_OWNERS, ownerLabel, useOwners } from "./OwnerControl";

const CLIENT_TYPES = ["school", "college", "housing_society", "corporate", "club", "government", "individual"];
const canCreateClient = (role) => ["sales", "pm", "director"].includes(role);

// Amendment 44 (Section E step 5, Design input 2026-09-23): a quick-capture
// intake distinct from "Add a client" -- just name/phone/email, no
// ClientType or any other full-Client field, since forcing that form at
// first contact is itself the friction point the Design input calls out.
// Pre-filled two days out rather than left blank, matching the mandatory-
// follow-up-date discipline (never created without one) while still being
// a one-click-adjustable default, not a locked value.
function defaultEnquiryFollowUpDate() {
  const d = new Date();
  d.setDate(d.getDate() + 2);
  return d.toISOString().slice(0, 10);
}

// Section 19 (Amendment 4 continuation): reuses AllProjects.jsx's own status
// pill colors, kept as a small local duplicate rather than a shared import,
// same pattern already used for other small per-file constant maps.
const STATUS_PILL_STYLE = {
  open: "bg-gold/10 text-gold",
  won: "bg-green-500/10 text-green-400",
  lost: "bg-red-500/10 text-red-400",
};

// Amendment 47 Part B (Section 52): the directory has three views. "Leads"
// are lead-only Opportunities that are not Lost (Lost ones stay visible on
// the Opportunities screen); "Clients" are the client cards.
const TABS = [
  { key: "all", label: "All" },
  { key: "leads", label: "Leads" },
  { key: "clients", label: "Clients" },
];

// Same small-local-duplicate style as Opportunities.jsx.
const STAGE_PILL_STYLE = {
  new: "bg-surface-raised text-text-secondary",
  contacted: "bg-gold/10 text-gold",
  qualified: "bg-gold-muted text-gold",
  won: "bg-green-500/10 text-green-400",
  lost: "bg-red-500/10 text-red-400",
};

const RELATIONSHIP_BADGE_STYLE = {
  lead: "bg-gold/10 text-gold",
  client: "bg-surface-raised text-text-secondary",
};

const UNASSIGNED = "__unassigned__";

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function matchesSearch(needle, ...fields) {
  if (!needle) return true;
  return fields.some((f) => (f || "").toLowerCase().includes(needle));
}

// Soonest follow-up first; a lead with no date (a Won one) goes last.
function byFollowUp(a, b) {
  if (a.next_follow_up_date === b.next_follow_up_date) return 0;
  if (!a.next_follow_up_date) return 1;
  if (!b.next_follow_up_date) return -1;
  return a.next_follow_up_date < b.next_follow_up_date ? -1 : 1;
}

function ConsentPill({ ok, label, title }) {
  return (
    <span
      title={title}
      className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full border ${
        ok ? "bg-green-500/10 text-green-400 border-green-500/30" : "bg-surface-raised text-text-secondary border-border-dark"
      }`}
    >
      {label}
    </span>
  );
}

// A compact on/off switch, the one new visual primitive this redesign needed -- everything else reuses
// existing pill/button/input styles already in the app.
function Toggle({ checked, onChange, disabled, label, hint }) {
  return (
    <label className={`flex items-center justify-between gap-3 py-1.5 ${disabled ? "opacity-50" : ""}`} title={hint}>
      <span className="text-sm text-text-primary">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
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
    </label>
  );
}

// Amendment 53: `initialSearch` pre-fills the search box when a client or lead is opened
// from the global quick search (there is no per-record view; the record is the first row).
//
// Redesign (2026-09-27, Director's request): same screen, same data and the same server calls --
// presented as a list with a slide-in details panel instead of stacked cards with inline forms. The
// sidebar and header are untouched; only this screen's own content changed.
export default function ClientsAdmin({ token, role, onOpenProject, onOpenOpportunities, onBack, initialSearch = "" }) {
  const [clients, setClients] = useState([]);
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("all");
  const [search, setSearch] = useState(initialSearch);
  const [ownerFilter, setOwnerFilter] = useState("");
  const [panel, setPanel] = useState(null); // null | {mode:"new-client"|"new-lead"} | {mode:"edit-client"|"edit-lead", id}
  const [autoSelectDone, setAutoSelectDone] = useState(false);
  const canEditFlags = role === "director";
  const owners = useOwners(token, role);
  const canAssign = CAN_ASSIGN_OWNERS.includes(role);

  const [expandedClientId, setExpandedClientId] = useState(null);
  const [projectsByClient, setProjectsByClient] = useState({});
  const [loadingProjects, setLoadingProjects] = useState(false);

  async function toggleProjects(clientId) {
    if (expandedClientId === clientId) {
      setExpandedClientId(null);
      return;
    }
    setExpandedClientId(clientId);
    if (!projectsByClient[clientId]) {
      setLoadingProjects(true);
      try {
        const rows = await listProjects(token, { client_id: clientId });
        setProjectsByClient((m) => ({ ...m, [clientId]: rows }));
      } catch (err) {
        setError(err.message);
      } finally {
        setLoadingProjects(false);
      }
    }
  }

  function load() {
    return Promise.all([
      listClients(token).then(setClients),
      listOpportunities(token, { relationship: "lead" }).then((rows) => setLeads(rows.filter((o) => o.stage !== "lost"))),
    ]);
  }

  useEffect(() => {
    load()
      .catch((err) => {
        setError(err.message);
        setLoadFailed(true);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // The details panel reads as part of the page, not an optional extra -- so the first client (or the
  // first lead, if there is no client yet) is selected by default as soon as there is one, the same as
  // every mockup shows it. Once, not on every load: closing the panel must not silently reselect something.
  useEffect(() => {
    if (autoSelectDone || panel !== null) return;
    if (clients.length > 0) {
      const first = clients.slice().sort((a, b) => a.name.localeCompare(b.name))[0];
      setPanel({ mode: "edit-client", id: first.id });
      setAutoSelectDone(true);
    } else if (leads.length > 0) {
      const first = leads.slice().sort(byFollowUp)[0];
      setPanel({ mode: "edit-lead", id: first.id });
      setAutoSelectDone(true);
    }
  }, [clients, leads, autoSelectDone, panel]);

  function closePanel() {
    setPanel(null);
  }

  async function handleCreateClient(values) {
    await createClient(token, {
      name: values.name,
      type: values.type,
      contact_name: values.contact_name || null,
      phone: values.phone || null,
      email: values.email || null,
      city: values.city || null,
      notes: values.notes || null,
    });
    if (tab === "leads") setTab("clients");
    closePanel();
    await load();
  }

  async function handleCreateEnquiry(values) {
    await createOpportunity(token, {
      lead_name: values.lead_name,
      lead_phone: values.lead_phone || null,
      lead_email: values.lead_email || null,
      next_follow_up_date: values.next_follow_up_date,
      notes: values.notes || null,
    });
    if (tab === "clients") setTab("leads");
    closePanel();
    await load();
  }

  // Amendment 47 (Section 52): fixing a typo in a client's name / contact details, plus (this redesign)
  // everything else the panel can change, gathered into the one "Save changes" action. Type is
  // deliberately not editable here (it drives the default package and payment terms) -- unchanged from
  // before, just shown disabled instead of omitted.
  async function saveClient(client, values) {
    await updateClientDetails(token, client.id, {
      name: values.name,
      contact_name: values.contact_name || null,
      phone: values.phone || null,
      email: values.email || null,
      city: values.city || null,
    });
    await updateClientFollowUp(token, client.id, {
      next_follow_up_date: values.followUpDate || null,
      follow_up_note: values.followUpNote || null,
    });
    await updateClientNotes(token, client.id, { notes: values.notes || null });
    await updateClientConsent(token, client.id, {
      whatsapp_opt_in: values.whatsapp_opt_in,
      email_opt_in: values.email_opt_in,
      telegram_opt_in: values.telegram_opt_in,
      telegram_chat_id: values.telegram_chat_id || null,
    });
    if (canEditFlags) {
      await updateClientFlags(token, client.id, {
        overdue_flag: values.overdue_flag,
        blacklist_flag: values.blacklist_flag,
      });
    }
    closePanel();
    await load();
  }

  async function saveLead(lead, values) {
    await updateOpportunityDetails(token, lead.id, {
      lead_name: values.name,
      lead_phone: values.phone || null,
      lead_email: values.email || null,
    });
    closePanel();
    await load();
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading leads and clients…</p>;
  }

  const needle = search.trim().toLowerCase();
  const ownerOk = (ownerId) => {
    if (!ownerFilter) return true;
    if (ownerFilter === UNASSIGNED) return !ownerId;
    return ownerId === ownerFilter;
  };
  const visibleLeads = leads
    .filter((o) => matchesSearch(needle, o.lead_name, o.lead_phone, o.lead_email) && ownerOk(o.owner_id))
    .sort(byFollowUp);
  const visibleClients = clients
    .filter((c) => matchesSearch(needle, c.name, c.phone, c.email) && ownerOk(c.owner_id))
    .sort((a, b) => a.name.localeCompare(b.name));
  const rows = [
    ...(tab !== "clients" ? visibleLeads.map((o) => ({ kind: "lead", key: `lead-${o.id}`, o })) : []),
    ...(tab !== "leads" ? visibleClients.map((c) => ({ kind: "client", key: `client-${c.id}`, c })) : []),
  ];
  const tabCount = { all: visibleLeads.length + visibleClients.length, leads: visibleLeads.length, clients: visibleClients.length };
  const unassignedCount = leads.filter((o) => !o.owner_id).length + clients.filter((c) => !c.owner_id).length;
  const selectedId = panel && (panel.mode === "edit-client" || panel.mode === "edit-lead") ? panel.id : null;

  const summaryTiles = [
    { label: "Total contacts", value: leads.length + clients.length, icon: UsersIcon, onClick: () => { setTab("all"); setOwnerFilter(""); } },
    { label: "Leads", value: leads.length, icon: FunnelIcon, onClick: () => { setTab("leads"); setOwnerFilter(""); } },
    { label: "Clients", value: clients.length, icon: GridIcon, onClick: () => { setTab("clients"); setOwnerFilter(""); } },
    ...(canAssign
      ? [
          {
            label: "Unassigned",
            value: unassignedCount,
            icon: BellIcon,
            warn: unassignedCount > 0,
            onClick: () => { setTab("all"); setOwnerFilter(UNASSIGNED); },
          },
        ]
      : []),
  ];

  return (
    <div className="max-w-[1400px] mx-auto mt-6 mb-10 px-4 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-text-secondary">Workspace / Customer relationships</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1 flex items-center gap-2">
            <UsersIcon className="w-6 h-6 text-gold" /> Leads &amp; Clients
          </h2>
          <p className="text-sm text-text-secondary mt-1">
            Manage enquiries, clients and follow-ups.
            {canEditFlags &&
              " Overdue blocks releasing new Quotations and Blacklisted blocks new Estimates -- only a Director can set either."}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {canCreateClient(role) && (
            <>
              <button
                onClick={() => setPanel((p) => (p?.mode === "new-lead" ? null : { mode: "new-lead" }))}
                className="border border-gold text-gold text-sm rounded px-4 py-2 font-semibold hover:bg-gold/10"
              >
                + Add enquiry
              </button>
              <button
                onClick={() => setPanel((p) => (p?.mode === "new-client" ? null : { mode: "new-client" }))}
                className="bg-gold text-base text-sm rounded px-4 py-2 font-semibold hover:bg-gold-hover"
              >
                + Add client
              </button>
            </>
          )}
          {onBack && (
            <button onClick={onBack} className="text-xs uppercase tracking-wider text-gold hover:text-gold-hover shrink-0">
              ← Back
            </button>
          )}
        </div>
      </div>

      <div className={`grid grid-cols-2 ${summaryTiles.length > 3 ? "md:grid-cols-4" : "md:grid-cols-3"} gap-4 mb-5`}>
        {summaryTiles.map((tile) => {
          const active =
            tile.label === "Total contacts"
              ? tab === "all" && !ownerFilter
              : tile.label === "Leads"
                ? tab === "leads" && !ownerFilter
                : tile.label === "Clients"
                  ? tab === "clients" && !ownerFilter
                  : ownerFilter === UNASSIGNED;
          return (
            <button
              key={tile.label}
              onClick={tile.onClick}
              className={`text-left bg-surface border rounded-lg p-4 hover:border-gold hover:-translate-y-0.5 transition-all duration-250 ease-out ${
                active ? "border-gold" : "border-border-dark"
              }`}
            >
              <p className="text-xs uppercase tracking-wide text-text-secondary flex items-center gap-1.5">
                <tile.icon className="w-3.5 h-3.5" />
                {tile.label}
              </p>
              <p className={`text-2xl font-heading font-bold mt-1 ${tile.warn ? "text-amber-400" : "text-text-primary"}`}>
                {tile.value}
              </p>
            </button>
          );
        })}
      </div>

      <div className="flex flex-col lg:flex-row gap-5">
        <div className={`min-w-0 space-y-3 ${panel ? "lg:flex-1" : "flex-1"}`}>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-dark">
            <div className="flex items-center gap-5 overflow-x-auto">
              {TABS.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={`text-sm pb-2.5 border-b-2 whitespace-nowrap transition-colors duration-200 ${
                    tab === t.key
                      ? "text-gold border-gold font-medium"
                      : "text-text-secondary border-transparent hover:text-text-primary"
                  }`}
                >
                  {t.label} <span className="text-xs text-text-secondary">({tabCount[t.key]})</span>
                </button>
              ))}
            </div>
            {canAssign && (
              <label className="flex items-center gap-2 text-xs text-text-secondary pb-2 shrink-0">
                Owner
                <select
                  value={ownerFilter}
                  onChange={(e) => setOwnerFilter(e.target.value)}
                  className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5 text-xs"
                >
                  <option value="">All owners</option>
                  <option value={UNASSIGNED}>Unassigned</option>
                  {owners.options.map((o) => (
                    <option key={o.user_id} value={o.user_id}>
                      {ownerLabel(o)}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>

          <div className="relative">
            <SearchIcon className="w-4 h-4 text-text-secondary absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              id="leads-clients-search"
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name, phone or email"
              aria-label="Search leads and clients"
              className="w-full rounded border border-border-dark bg-surface-raised text-text-primary pl-9 pr-3 py-2 text-sm"
            />
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <div className="space-y-2">
            {rows.map((row) => {
              if (row.kind === "lead") {
                const o = row.o;
                const overdue = o.next_follow_up_date && o.next_follow_up_date < todayStr();
                const isSelected = selectedId === o.id;
                return (
                  <div
                    key={row.key}
                    className={`bg-surface rounded-lg px-4 py-3 text-sm space-y-2 border ${
                      isSelected ? "border-gold" : "border-border-dark"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <span className="min-w-0 break-words">
                        <span className="font-medium">{o.lead_name}</span>{" "}
                        <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${RELATIONSHIP_BADGE_STYLE.lead}`}>
                          Lead
                        </span>
                      </span>
                      <span className="flex items-center gap-2 shrink-0">
                        <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${STAGE_PILL_STYLE[o.stage]}`}>
                          {o.stage}
                        </span>
                        {canCreateClient(role) && (
                          <button
                            onClick={() => setPanel({ mode: "edit-lead", id: o.id })}
                            className="text-xs border border-border-dark rounded px-2.5 py-1 text-gold hover:bg-gold/10"
                          >
                            Edit details
                          </button>
                        )}
                      </span>
                    </div>
                    <p className="text-xs text-text-secondary break-words">
                      {[o.lead_phone, o.lead_email].filter(Boolean).join(" · ") || "No contact details yet"}
                    </p>
                    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
                      {canAssign && (
                        <OwnerControl
                          token={token}
                          kind="opportunity"
                          recordId={o.id}
                          ownerId={o.owner_id}
                          owners={owners}
                          onChanged={(next) => setLeads((ls) => ls.map((l) => (l.id === o.id ? { ...l, owner_id: next } : l)))}
                        />
                      )}
                      {o.next_follow_up_date && (
                        <span className={`text-xs ${overdue ? "text-red-400" : "text-text-secondary"}`}>
                          Follow-up {o.next_follow_up_date}
                          {overdue && " (overdue)"}
                        </span>
                      )}
                      {onOpenOpportunities && (
                        <button onClick={onOpenOpportunities} className="text-xs text-gold hover:underline">
                          Open in Opportunities →
                        </button>
                      )}
                    </div>
                    {o.stage === "won" && (
                      <p className="text-xs text-text-secondary">
                        Won -- open it in Opportunities and link a client to start a Project.
                      </p>
                    )}
                  </div>
                );
              }
              const c = row.c;
              const isSelected = selectedId === c.id;
              return (
                <div
                  key={row.key}
                  className={`bg-surface rounded-lg px-4 py-3 text-sm space-y-2 border ${
                    isSelected ? "border-gold" : "border-border-dark"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="min-w-0 break-words">
                      <span className="font-medium">{c.name}</span>{" "}
                      <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${RELATIONSHIP_BADGE_STYLE.client}`}>
                        Client
                      </span>{" "}
                      <span className="text-xs text-text-secondary capitalize">{c.type.replace("_", " ")}</span>
                    </span>
                    <span className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={() => toggleProjects(c.id)}
                        className="text-xs border border-border-dark rounded px-2.5 py-1 text-text-secondary hover:text-text-primary hover:bg-surface-raised"
                      >
                        {expandedClientId === c.id ? "Hide projects" : "View projects"}
                      </button>
                      {canCreateClient(role) && (
                        <button
                          onClick={() => setPanel({ mode: "edit-client", id: c.id })}
                          className="text-xs border border-border-dark rounded px-2.5 py-1 text-gold hover:bg-gold/10"
                        >
                          Edit details
                        </button>
                      )}
                    </span>
                  </div>

                  <p className="text-xs text-text-secondary break-words">
                    {[c.contact_name, c.phone, c.email].filter(Boolean).join(" · ") || "No contact details yet"}
                  </p>

                  <div className="flex flex-wrap items-center gap-1.5">
                    <ConsentPill ok={c.whatsapp_opt_in} label="WhatsApp" title="Only message this client on WhatsApp if they have agreed to it." />
                    <ConsentPill ok={c.email_opt_in} label="Email" title="Leave ticked unless the client has asked not to receive email." />
                    <ConsentPill ok={c.telegram_opt_in} label="Telegram" title="A Telegram bot can only message a chat that has messaged it first." />
                    {canEditFlags && c.overdue_flag && <ConsentPill ok={false} label="Overdue" />}
                    {canEditFlags && c.blacklist_flag && <ConsentPill ok={false} label="Blacklisted" />}
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
                    {canAssign && (
                      <OwnerControl
                        token={token}
                        kind="client"
                        recordId={c.id}
                        ownerId={c.owner_id}
                        owners={owners}
                        onChanged={(next) => setClients((cs) => cs.map((x) => (x.id === c.id ? { ...x, owner_id: next } : x)))}
                      />
                    )}
                    <span className={`text-xs ${c.next_follow_up_date && c.next_follow_up_date < todayStr() ? "text-red-400" : "text-text-secondary"}`}>
                      Follow-up {c.next_follow_up_date || "—"}
                    </span>
                    <span className="text-xs text-text-secondary truncate max-w-[16rem]">
                      {c.notes ? c.notes : "No notes yet"}
                    </span>
                  </div>

                  {expandedClientId === c.id && (
                    <div className="mt-2 border-t border-border-dark pt-2 space-y-1">
                      {loadingProjects && !projectsByClient[c.id] ? (
                        <p className="text-xs text-text-secondary">Loading projects…</p>
                      ) : (projectsByClient[c.id] || []).length === 0 ? (
                        <p className="text-xs text-text-secondary">No projects yet.</p>
                      ) : (
                        projectsByClient[c.id].map((p) => (
                          <button
                            key={p.id}
                            onClick={() => onOpenProject(p.id)}
                            className="w-full text-left flex items-center justify-between text-xs rounded px-2 py-1 hover:bg-surface-raised transition-all duration-250 ease-out"
                          >
                            <span>
                              <span className="font-mono text-text-primary">{p.project_no}</span>{" "}
                              <span className="text-text-secondary">· {p.city}</span>
                            </span>
                            <span className="flex items-center gap-2">
                              <span className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full ${STATUS_PILL_STYLE[p.status] || ""}`}>
                                {p.status}
                              </span>
                              <span className="text-gold">Open →</span>
                            </span>
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </div>
              );
            })}
            {rows.length === 0 && !loadFailed && (
              <p className="text-sm text-text-secondary bg-surface border border-border-dark rounded-lg p-5">
                {needle || ownerFilter
                  ? "Nothing matches these filters."
                  : tab === "leads"
                    ? "No open leads yet -- use \"+ Add enquiry\" to capture one."
                    : tab === "clients"
                      ? "No clients yet."
                      : "No leads or clients yet."}
              </p>
            )}
          </div>
        </div>

        {panel && (
          <DetailsPanel
            panel={panel}
            client={panel.mode === "edit-client" ? clients.find((c) => c.id === panel.id) : null}
            lead={panel.mode === "edit-lead" ? leads.find((o) => o.id === panel.id) : null}
            canEditFlags={canEditFlags}
            canAssign={canAssign}
            owners={owners}
            token={token}
            onClose={closePanel}
            onCreateClient={handleCreateClient}
            onCreateEnquiry={handleCreateEnquiry}
            onSaveClient={saveClient}
            onSaveLead={saveLead}
            onOwnerChanged={(kind, id, next) => {
              if (kind === "client") setClients((cs) => cs.map((x) => (x.id === id ? { ...x, owner_id: next } : x)));
              else setLeads((ls) => ls.map((l) => (l.id === id ? { ...l, owner_id: next } : l)));
            }}
            onOpenOpportunities={onOpenOpportunities}
          />
        )}
      </div>
    </div>
  );
}

// The one thing every mode of this panel shares: a header (title + record-type badge + close), a body of
// fields, an error line and a "Save changes" button. What's inside the body is the only thing that varies.
function DetailsPanel({
  panel, client, lead, canEditFlags, canAssign, owners, token,
  onClose, onCreateClient, onCreateEnquiry, onSaveClient, onSaveLead, onOwnerChanged, onOpenOpportunities,
}) {
  const isNewClient = panel.mode === "new-client";
  const isNewLead = panel.mode === "new-lead";
  const isClient = isNewClient || panel.mode === "edit-client";
  const record = client || lead;

  const [values, setValues] = useState(() => ({
    name: client?.name ?? lead?.lead_name ?? "",
    type: client?.type ?? "school",
    contact_name: client?.contact_name ?? "",
    phone: client?.phone ?? lead?.lead_phone ?? "",
    email: client?.email ?? lead?.lead_email ?? "",
    city: client?.city ?? "",
    notes: client?.notes ?? "",
    followUpDate: client?.next_follow_up_date ?? (isNewLead ? defaultEnquiryFollowUpDate() : ""),
    followUpNote: client?.follow_up_note ?? "",
    whatsapp_opt_in: client?.whatsapp_opt_in ?? true,
    email_opt_in: client?.email_opt_in ?? true,
    telegram_opt_in: client?.telegram_opt_in ?? false,
    telegram_chat_id: client?.telegram_chat_id ?? "",
    overdue_flag: client?.overdue_flag ?? false,
    blacklist_flag: client?.blacklist_flag ?? false,
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function setField(field, value) {
    setValues((v) => ({ ...v, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!values.name.trim()) {
      setError("A name is required.");
      return;
    }
    if (isNewLead && !values.followUpDate) {
      setError("Every enquiry needs a follow-up date.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      if (isNewClient) await onCreateClient(values);
      else if (isNewLead) await onCreateEnquiry({ lead_name: values.name, lead_phone: values.phone, lead_email: values.email, next_follow_up_date: values.followUpDate, notes: values.notes });
      else if (isClient) await onSaveClient(client, values);
      else await onSaveLead(lead, values);
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
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-text-primary">
          {isNewClient ? "Add client" : isNewLead ? "Add enquiry" : isClient ? "Client details" : "Lead details"}
        </h3>
        <span className="flex items-center gap-2">
          <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${RELATIONSHIP_BADGE_STYLE[isClient ? "client" : "lead"]}`}>
            {isClient ? "Client" : "Lead"}
          </span>
          <button type="button" onClick={onClose} aria-label="Close" className="text-text-secondary hover:text-text-primary text-lg leading-none">
            ✕
          </button>
        </span>
      </div>

      <div>
        <label className={labelClass}>Name</label>
        <input required value={values.name} onChange={(e) => setField("name", e.target.value)} className={inputClass} />
      </div>

      {isClient && (
        <div>
          <label className={labelClass}>Type</label>
          <select
            value={values.type}
            disabled={!isNewClient}
            title={!isNewClient ? "Type can't be changed once a client exists -- it drives the default package and payment terms." : undefined}
            onChange={(e) => setField("type", e.target.value)}
            className={`${inputClass} ${!isNewClient ? "opacity-60 cursor-not-allowed" : ""}`}
          >
            {CLIENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace("_", " ")}
              </option>
            ))}
          </select>
        </div>
      )}

      {canAssign && !isNewClient && !isNewLead && (
        <div>
          <label className={labelClass}>Owner</label>
          <div className="mt-1">
            <OwnerControl
              token={token}
              kind={isClient ? "client" : "opportunity"}
              recordId={record.id}
              ownerId={record.owner_id}
              owners={owners}
              onChanged={(next) => onOwnerChanged(isClient ? "client" : "opportunity", record.id, next)}
            />
          </div>
        </div>
      )}

      {isClient && (
        <div>
          <label className={labelClass}>Contact name</label>
          <input value={values.contact_name} onChange={(e) => setField("contact_name", e.target.value)} className={inputClass} />
        </div>
      )}
      <div>
        <label className={labelClass}>Phone</label>
        <input inputMode="tel" value={values.phone} onChange={(e) => setField("phone", e.target.value)} className={inputClass} />
      </div>
      <div>
        <label className={labelClass}>Email</label>
        <input type="email" value={values.email} onChange={(e) => setField("email", e.target.value)} className={inputClass} />
      </div>
      {isClient && (
        <div>
          <label className={labelClass}>City (optional)</label>
          <input maxLength={100} value={values.city} onChange={(e) => setField("city", e.target.value)} className={inputClass} />
        </div>
      )}

      {(isNewLead || (isClient && !isNewClient)) && (
        <div>
          <label className={labelClass}>Follow-up date{isNewLead && " (required)"}</label>
          <input
            type="date"
            required={isNewLead}
            value={values.followUpDate}
            onChange={(e) => setField("followUpDate", e.target.value)}
            className={inputClass}
          />
        </div>
      )}
      {isClient && !isNewClient && (
        <div>
          <label className={labelClass}>Follow-up note (optional)</label>
          <input value={values.followUpNote} onChange={(e) => setField("followUpNote", e.target.value)} className={inputClass} />
        </div>
      )}

      {!isNewLead && !(panel.mode === "edit-lead") && (
        <div>
          <label className={labelClass}>Notes / remarks</label>
          <textarea
            value={values.notes}
            onChange={(e) => setField("notes", e.target.value)}
            rows={3}
            placeholder="Anything else worth noting -- not tied to any field above."
            className={inputClass}
          />
        </div>
      )}
      {panel.mode === "edit-lead" && (
        <>
          {lead.notes && (
            <p className="text-xs text-text-secondary whitespace-pre-wrap break-words">
              <span className="font-medium">Notes</span> {lead.notes}
            </p>
          )}
          <p className="text-xs text-text-secondary">
            Notes, follow-up date and stage changes for a lead happen on the Opportunities screen.
          </p>
          {onOpenOpportunities && (
            <button type="button" onClick={onOpenOpportunities} className="text-xs text-gold hover:underline">
              Open in Opportunities →
            </button>
          )}
        </>
      )}
      {isNewLead && (
        <p className="text-xs text-text-secondary">
          A raw lead -- just a name and contact, not a full client record yet.
        </p>
      )}

      {isClient && !isNewClient && (
        <div className="border-t border-border-dark pt-3 space-y-1">
          <p className="text-sm font-medium text-text-primary mb-1">Communication preferences</p>
          <p className="text-xs text-text-secondary mb-2">Consent preferences and follow-up reminders.</p>
          <Toggle checked={values.whatsapp_opt_in} onChange={(v) => setField("whatsapp_opt_in", v)} label="WhatsApp opt-in" hint="Only message this client on WhatsApp if they have agreed to it." />
          <Toggle checked={values.email_opt_in} onChange={(v) => setField("email_opt_in", v)} label="Email opt-in" hint="Leave on unless the client has asked not to receive email." />
          <Toggle checked={values.telegram_opt_in} onChange={(v) => setField("telegram_opt_in", v)} label="Telegram opt-in" hint="A Telegram bot can only message a chat that has messaged it first." />
          <input
            value={values.telegram_chat_id}
            onChange={(e) => setField("telegram_chat_id", e.target.value)}
            placeholder="Enter Telegram chat id (optional)"
            className={inputClass}
          />
        </div>
      )}

      {isClient && !isNewClient && canEditFlags && (
        <div className="border-t border-border-dark pt-3 space-y-1">
          <div className="flex items-center justify-between mb-1">
            <p className="text-sm font-medium text-text-primary">Account controls</p>
            <span className="text-[10px] uppercase tracking-wider text-text-secondary">Director only</span>
          </div>
          <Toggle checked={values.overdue_flag} onChange={(v) => setField("overdue_flag", v)} label="Overdue" hint="Blocks releasing new Quotations for this client." />
          <Toggle checked={values.blacklist_flag} onChange={(v) => setField("blacklist_flag", v)} label="Blacklisted" hint="Blocks new Estimates for this client." />
        </div>
      )}

      {error && <p className="text-xs text-red-400">{error}</p>}
      <button
        type="submit"
        disabled={saving}
        className="w-full bg-gold text-base rounded px-4 py-2.5 font-semibold hover:bg-gold-hover disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save changes"}
      </button>
    </form>
  );
}
