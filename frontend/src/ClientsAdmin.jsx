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
import EditDetailsForm from "./EditDetailsForm";
import { UsersIcon } from "./Icons";

const CLIENT_TYPES = ["school", "college", "housing_society", "corporate", "club", "government", "individual"];
const emptyClientForm = { name: "", type: "school", contact_name: "", phone: "", email: "", city: "", notes: "" };
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
const emptyEnquiryForm = {
  lead_name: "",
  lead_phone: "",
  lead_email: "",
  next_follow_up_date: defaultEnquiryFollowUpDate(),
  notes: "",
};

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

// Amendment 53: `initialSearch` pre-fills the search box when a client or lead is opened
// from the global quick search (there is no per-record view; the record is the first row).
export default function ClientsAdmin({ token, role, onOpenProject, onOpenOpportunities, onBack, initialSearch = "" }) {
  const [clients, setClients] = useState([]);
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("all");
  const [search, setSearch] = useState(initialSearch);
  const [showClientForm, setShowClientForm] = useState(false);
  const [showEnquiryForm, setShowEnquiryForm] = useState(false);
  const [editingLeadId, setEditingLeadId] = useState(null);
  const [chatIdDrafts, setChatIdDrafts] = useState({});
  const [followUpDrafts, setFollowUpDrafts] = useState({});
  const [notesDrafts, setNotesDrafts] = useState({});
  const [editingClientId, setEditingClientId] = useState(null);
  const [form, setForm] = useState(emptyClientForm);
  const [submitting, setSubmitting] = useState(false);
  const [enquiryForm, setEnquiryForm] = useState(emptyEnquiryForm);
  const [submittingEnquiry, setSubmittingEnquiry] = useState(false);
  const [enquirySaved, setEnquirySaved] = useState(false);
  const canEditFlags = role === "director";

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

  function setField(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleCreateClient(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await createClient(token, {
        name: form.name,
        type: form.type,
        contact_name: form.contact_name || null,
        phone: form.phone || null,
        email: form.email || null,
        city: form.city || null,
        notes: form.notes || null,
      });
      setForm(emptyClientForm);
      setShowClientForm(false);
      if (tab === "leads") setTab("clients");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  function setEnquiryField(field, value) {
    setEnquiryForm((f) => ({ ...f, [field]: value }));
  }

  async function handleCreateEnquiry(e) {
    e.preventDefault();
    setError("");
    setEnquirySaved(false);
    setSubmittingEnquiry(true);
    try {
      await createOpportunity(token, {
        lead_name: enquiryForm.lead_name,
        lead_phone: enquiryForm.lead_phone || null,
        lead_email: enquiryForm.lead_email || null,
        next_follow_up_date: enquiryForm.next_follow_up_date,
        notes: enquiryForm.notes || null,
      });
      setEnquiryForm({
        lead_name: "",
        lead_phone: "",
        lead_email: "",
        next_follow_up_date: defaultEnquiryFollowUpDate(),
        notes: "",
      });
      setEnquirySaved(true);
      setShowEnquiryForm(false);
      if (tab === "clients") setTab("leads");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmittingEnquiry(false);
    }
  }

  async function toggleFlag(clientId, field, value) {
    setError("");
    try {
      await updateClientFlags(token, clientId, { [field]: value });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleConsent(clientId, field, value) {
    setError("");
    try {
      await updateClientConsent(token, clientId, {
        [field]: value,
        ...(value && field !== "telegram_opt_in" ? { consent_date: new Date().toISOString().slice(0, 10) } : {}),
      });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function saveTelegramChatId(clientId) {
    setError("");
    try {
      await updateClientConsent(token, clientId, { telegram_chat_id: chatIdDrafts[clientId] || null });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  // Amendment 42 (Section 48): a simple, optional reminder -- not
  // mandatory, not audit-logged, same style as the Telegram chat-id draft
  // pattern above (local draft state, explicit Save).
  async function saveFollowUp(clientId) {
    setError("");
    const draft = followUpDrafts[clientId] || {};
    try {
      await updateClientFollowUp(token, clientId, {
        next_follow_up_date: draft.date !== undefined ? draft.date || null : undefined,
        follow_up_note: draft.note !== undefined ? draft.note || null : undefined,
      });
      setFollowUpDrafts((d) => ({ ...d, [clientId]: undefined }));
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  // Amendment 45 (Section 51): a general free-text catch-all, distinct
  // from the follow-up note above -- same draft/Save pattern.
  async function saveNotes(clientId) {
    setError("");
    try {
      await updateClientNotes(token, clientId, { notes: notesDrafts[clientId] || null });
      setNotesDrafts((d) => ({ ...d, [clientId]: undefined }));
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  // Amendment 47 (Section 52): fixing a typo in a client's name / contact
  // details. Type is deliberately not editable here (it drives the default
  // package and payment terms).
  async function saveDetails(clientId, values) {
    await updateClientDetails(token, clientId, {
      name: values.name,
      contact_name: values.contact_name || null,
      phone: values.phone || null,
      email: values.email || null,
      city: values.city || null,
    });
    setEditingClientId(null);
    await load();
  }

  async function saveLeadDetails(leadId, values) {
    await updateOpportunityDetails(token, leadId, {
      lead_name: values.name,
      lead_phone: values.phone || null,
      lead_email: values.email || null,
    });
    setEditingLeadId(null);
    await load();
  }

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading leads and clients…</p>;
  }

  const needle = search.trim().toLowerCase();
  const visibleLeads = leads
    .filter((o) => matchesSearch(needle, o.lead_name, o.lead_phone, o.lead_email))
    .sort(byFollowUp);
  const visibleClients = clients
    .filter((c) => matchesSearch(needle, c.name, c.phone, c.email))
    .sort((a, b) => a.name.localeCompare(b.name));
  const rows = [
    ...(tab !== "clients" ? visibleLeads.map((o) => ({ kind: "lead", key: `lead-${o.id}`, o })) : []),
    ...(tab !== "leads" ? visibleClients.map((c) => ({ kind: "client", key: `client-${c.id}`, c })) : []),
  ];
  const tabCount = { all: visibleLeads.length + visibleClients.length, leads: visibleLeads.length, clients: visibleClients.length };

  return (
    <div className="max-w-[1000px] mx-auto mt-6 mb-10 space-y-4 px-4 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-text-secondary">NestaPrime / Customer Relationships</p>
          <h2 className="font-heading font-bold text-text-primary text-2xl sm:text-3xl mt-1 flex items-center gap-2">
            <UsersIcon className="w-6 h-6 text-gold" /> Leads &amp; Clients
          </h2>
          <p className="text-sm text-text-secondary mt-1">
            Everyone you sell to -- new enquiries and existing clients -- with consent preferences and follow-up
            reminders. Stage changes for a lead happen on the Opportunities screen.
            {canEditFlags &&
              " Overdue blocks releasing new Quotations and Blacklisted blocks new Estimates -- only a Director can set either."}
          </p>
        </div>
        {onBack && (
          <button onClick={onBack} className="text-xs uppercase tracking-wider text-gold hover:text-gold-hover shrink-0">
            ← Back
          </button>
        )}
      </div>

      <div className="flex items-center gap-5 border-b border-border-dark overflow-x-auto">
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

      <div className="flex flex-wrap items-center gap-3">
        <input
          id="leads-clients-search"
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name, phone or email"
          aria-label="Search leads and clients"
          className="flex-1 min-w-[12rem] rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
        />
        {canCreateClient(role) && (
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => setShowEnquiryForm((v) => !v)}
              className="bg-gold text-base text-sm rounded px-4 py-2 font-semibold hover:bg-gold-hover"
            >
              {showEnquiryForm ? "Close enquiry form" : "+ Add Enquiry"}
            </button>
            <button
              onClick={() => setShowClientForm((v) => !v)}
              className="border border-gold text-gold text-sm rounded px-4 py-2 font-semibold hover:bg-gold/10"
            >
              {showClientForm ? "Close client form" : "+ Add a client"}
            </button>
          </div>
        )}
      </div>

      {enquirySaved && !showEnquiryForm && (
        <p className="text-xs text-gold">Enquiry saved -- it is in the Leads list below.</p>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}

      {canCreateClient(role) && showClientForm && (
        <form onSubmit={handleCreateClient} className="bg-surface border border-border-dark rounded-lg p-5 space-y-3">
          <h3 className="text-sm font-semibold text-text-secondary">Add a client</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-text-secondary">Name</label>
              <input
                type="text"
                required
                value={form.name}
                onChange={(e) => setField("name", e.target.value)}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary">Type</label>
              <select
                value={form.type}
                onChange={(e) => setField("type", e.target.value)}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
              >
                {CLIENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.replace("_", " ")}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary">Contact name</label>
              <input
                type="text"
                value={form.contact_name}
                onChange={(e) => setField("contact_name", e.target.value)}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary">Phone</label>
              <input
                type="text"
                value={form.phone}
                onChange={(e) => setField("phone", e.target.value)}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary">Email</label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setField("email", e.target.value)}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
              />
            </div>
            <div>
              <label htmlFor="new-client-city" className="block text-sm font-medium text-text-secondary">
                City (optional)
              </label>
              <input
                id="new-client-city"
                type="text"
                maxLength={100}
                value={form.city}
                onChange={(e) => setField("city", e.target.value)}
                placeholder="Pre-fills the city of this client's new projects"
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="block text-sm font-medium text-text-secondary">Notes / remarks</label>
              <textarea
                value={form.notes}
                onChange={(e) => setField("notes", e.target.value)}
                rows={3}
                placeholder="Anything else worth noting -- not tied to any field above."
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="bg-gold text-base text-sm rounded px-4 py-2 hover:bg-gold-hover hover:-translate-y-0.5 transition-all duration-250 ease-out disabled:opacity-50"
          >
            {submitting ? "Saving…" : "Save client"}
          </button>
        </form>
      )}

      {canCreateClient(role) && showEnquiryForm && (
        <form onSubmit={handleCreateEnquiry} className="bg-surface border border-border-dark rounded-lg p-5 space-y-3">
          <h3 className="text-sm font-semibold text-text-secondary">Add Enquiry</h3>
          <p className="text-xs text-text-secondary">
            A raw lead -- just a name and contact, not a full client record yet. Every enquiry needs a follow-up
            date; there is no way to leave one blank.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-text-secondary">Name</label>
              <input
                type="text"
                required
                value={enquiryForm.lead_name}
                onChange={(e) => setEnquiryField("lead_name", e.target.value)}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary">Follow-up date</label>
              <input
                type="date"
                required
                value={enquiryForm.next_follow_up_date}
                onChange={(e) => setEnquiryField("next_follow_up_date", e.target.value)}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary">Phone</label>
              <input
                type="text"
                value={enquiryForm.lead_phone}
                onChange={(e) => setEnquiryField("lead_phone", e.target.value)}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary">Email</label>
              <input
                type="email"
                value={enquiryForm.lead_email}
                onChange={(e) => setEnquiryField("lead_email", e.target.value)}
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="block text-sm font-medium text-text-secondary">Notes / remarks</label>
              <textarea
                value={enquiryForm.notes}
                onChange={(e) => setEnquiryField("notes", e.target.value)}
                rows={3}
                placeholder="Anything else worth noting -- not tied to any field above."
                className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-2 text-sm"
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={submittingEnquiry}
              className="bg-gold text-base text-sm rounded px-4 py-2 hover:bg-gold-hover hover:-translate-y-0.5 transition-all duration-250 ease-out disabled:opacity-50"
            >
              {submittingEnquiry ? "Saving…" : "Save enquiry"}
            </button>
          </div>
        </form>
      )}

      <div className="space-y-3">
        {rows.map((row) => {
          if (row.kind === "lead") {
            const o = row.o;
            const overdue = o.next_follow_up_date && o.next_follow_up_date < todayStr();
            return (
              <div key={row.key} className="bg-surface border border-border-dark rounded-lg px-4 py-3 text-sm space-y-2">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <span className="min-w-0 break-words">
                    <span className="font-medium">{o.lead_name}</span>{" "}
                    <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${RELATIONSHIP_BADGE_STYLE.lead}`}>
                      Lead
                    </span>
                  </span>
                  <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full shrink-0 ${STAGE_PILL_STYLE[o.stage]}`}>
                    {o.stage}
                  </span>
                </div>

                {editingLeadId !== o.id && (
                  <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-xs text-text-secondary">
                    <span className="min-w-0 break-words">
                      {[o.lead_phone, o.lead_email].filter(Boolean).join(" · ") || "No contact details yet"}
                    </span>
                    <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
                      {canCreateClient(role) && (
                        <button onClick={() => setEditingLeadId(o.id)} className="text-gold hover:underline">
                          Edit details
                        </button>
                      )}
                      {onOpenOpportunities && (
                        <button onClick={onOpenOpportunities} className="text-gold hover:underline">
                          Open in Opportunities →
                        </button>
                      )}
                    </span>
                  </div>
                )}

                {editingLeadId === o.id && (
                  <EditDetailsForm
                    idPrefix={`lead-${o.id}`}
                    initial={{ name: o.lead_name, phone: o.lead_phone, email: o.lead_email }}
                    onSave={(values) => saveLeadDetails(o.id, values)}
                    onCancel={() => setEditingLeadId(null)}
                  />
                )}

                {o.next_follow_up_date && (
                  <p className={`text-xs ${overdue ? "text-red-400" : "text-text-secondary"}`}>
                    <span className="font-medium">Follow-up</span> {o.next_follow_up_date}
                    {overdue && " (overdue)"}
                    {o.follow_up_note && ` · ${o.follow_up_note}`}
                  </p>
                )}
                {o.notes && (
                  <p className="text-xs text-text-secondary whitespace-pre-wrap break-words">
                    <span className="font-medium">Notes</span> {o.notes}
                  </p>
                )}
                {o.stage === "won" && (
                  <p className="text-xs text-text-secondary">
                    Won -- open it in Opportunities and link a client to start a Project.
                  </p>
                )}
              </div>
            );
          }
          const c = row.c;
          return (
          <div key={row.key} className="bg-surface border border-border-dark rounded-lg px-4 py-3 text-sm space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="min-w-0 break-words">
              <span className="font-medium">{c.name}</span>{" "}
              <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${RELATIONSHIP_BADGE_STYLE.client}`}>
                Client
              </span>{" "}
              <span className="text-xs text-text-secondary">({c.type})</span>
            </span>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
              {canEditFlags && (
                <>
                  <label className="flex items-center gap-1">
                    <input
                      type="checkbox"
                      checked={c.overdue_flag}
                      onChange={(e) => toggleFlag(c.id, "overdue_flag", e.target.checked)}
                    />
                    Overdue
                  </label>
                  <label className="flex items-center gap-1">
                    <input
                      type="checkbox"
                      checked={c.blacklist_flag}
                      onChange={(e) => toggleFlag(c.id, "blacklist_flag", e.target.checked)}
                    />
                    Blacklisted
                  </label>
                </>
              )}
              <span className={`flex flex-wrap items-center gap-x-4 gap-y-2 ${canEditFlags ? "sm:border-l border-border-dark sm:pl-4" : ""}`}>
                <label className="flex items-center gap-1" title="Only message this client on WhatsApp if they have agreed to it.">
                  <input
                    type="checkbox"
                    checked={c.whatsapp_opt_in}
                    onChange={(e) => toggleConsent(c.id, "whatsapp_opt_in", e.target.checked)}
                  />
                  WhatsApp opt-in
                </label>
                <label className="flex items-center gap-1" title="Leave ticked unless the client has asked not to receive email.">
                  <input
                    type="checkbox"
                    checked={c.email_opt_in}
                    onChange={(e) => toggleConsent(c.id, "email_opt_in", e.target.checked)}
                  />
                  Email opt-in
                </label>
                <label
                  className="flex items-center gap-1"
                  title="A Telegram bot can only message a chat that has messaged it first."
                >
                  <input
                    type="checkbox"
                    checked={c.telegram_opt_in}
                    onChange={(e) => toggleConsent(c.id, "telegram_opt_in", e.target.checked)}
                  />
                  Telegram opt-in
                </label>
                <span className="flex items-center gap-1">
                  <input
                    value={chatIdDrafts[c.id] ?? c.telegram_chat_id ?? ""}
                    onChange={(e) => setChatIdDrafts((d) => ({ ...d, [c.id]: e.target.value }))}
                    placeholder="Telegram chat id"
                    className="w-28 rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-0.5 text-xs"
                  />
                  <button onClick={() => saveTelegramChatId(c.id)} className="text-gold hover:underline">
                    Save
                  </button>
                </span>
              </span>
            </div>
          </div>

          {(c.contact_name || c.phone || c.email || canCreateClient(role)) && editingClientId !== c.id && (
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-xs text-text-secondary">
              <span className="min-w-0 break-words">
                {[c.contact_name, c.phone, c.email].filter(Boolean).join(" · ") || "No contact details yet"}
              </span>
              {canCreateClient(role) && (
                <button onClick={() => setEditingClientId(c.id)} className="text-gold hover:underline shrink-0">
                  Edit details
                </button>
              )}
            </div>
          )}

          {editingClientId === c.id && (
            <EditDetailsForm
              idPrefix={`client-${c.id}`}
              withContactName
              withCity
              initial={{ name: c.name, contact_name: c.contact_name, phone: c.phone, email: c.email, city: c.city }}
              onSave={(values) => saveDetails(c.id, values)}
              onCancel={() => setEditingClientId(null)}
            />
          )}

          {canCreateClient(role) && (
            <div
              className={`flex flex-wrap items-center gap-2 text-xs ${
                c.next_follow_up_date && c.next_follow_up_date < new Date().toISOString().slice(0, 10)
                  ? "text-red-400"
                  : "text-text-secondary"
              }`}
            >
              <span className="font-medium">Follow-up</span>
              <input
                type="date"
                value={followUpDrafts[c.id]?.date ?? c.next_follow_up_date ?? ""}
                onChange={(e) =>
                  setFollowUpDrafts((d) => ({ ...d, [c.id]: { ...d[c.id], date: e.target.value } }))
                }
                className="rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-0.5 text-xs"
              />
              <input
                value={followUpDrafts[c.id]?.note ?? c.follow_up_note ?? ""}
                onChange={(e) =>
                  setFollowUpDrafts((d) => ({ ...d, [c.id]: { ...d[c.id], note: e.target.value } }))
                }
                placeholder="Note (optional)"
                className="flex-1 min-w-[8rem] rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-0.5 text-xs"
              />
              <button onClick={() => saveFollowUp(c.id)} className="text-gold hover:underline shrink-0">
                Save
              </button>
            </div>
          )}

          {canCreateClient(role) && (
            <div className="flex flex-wrap items-start gap-2 text-xs text-text-secondary">
              <span className="font-medium pt-1 shrink-0">Notes</span>
              <textarea
                value={notesDrafts[c.id] ?? c.notes ?? ""}
                onChange={(e) => setNotesDrafts((d) => ({ ...d, [c.id]: e.target.value }))}
                rows={1}
                placeholder="Notes / remarks (optional)"
                className="flex-1 min-w-[8rem] rounded border border-border-dark bg-surface-raised text-text-primary px-1.5 py-0.5 text-xs"
              />
              <button onClick={() => saveNotes(c.id)} className="text-gold hover:underline shrink-0">
                Save
              </button>
            </div>
          )}

          <div>
            <button onClick={() => toggleProjects(c.id)} className="text-xs text-gold hover:underline">
              {expandedClientId === c.id ? "▾ Hide projects" : "▸ Projects"}
            </button>
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
                        <span
                          className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full ${STATUS_PILL_STYLE[p.status] || ""}`}
                        >
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
        </div>
          );
        })}
        {rows.length === 0 && !loadFailed && (
          <p className="text-sm text-text-secondary bg-surface border border-border-dark rounded-lg p-5">
            {needle
              ? "Nothing matches that search."
              : tab === "leads"
                ? "No open leads yet -- use \"Add Enquiry\" to capture one."
                : tab === "clients"
                  ? "No clients yet."
                  : "No leads or clients yet."}
          </p>
        )}
      </div>
    </div>
  );
}
