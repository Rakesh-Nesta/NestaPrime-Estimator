import { useEffect, useState } from "react";
import {
  createClientContact,
  createClientSite,
  dismissClientDuplicate,
  getClient,
  listClientContacts,
  listClientDuplicates,
  listClientMessages,
  listClientSites,
  listOpportunities,
  listProjects,
  restoreClientDuplicate,
  updateClientContact,
  updateClientDetails,
  updateClientSite,
  updateClientSource,
} from "./api";
import ClientSignatoriesPanel from "./ClientSignatoriesPanel";
import OwnerControl, { CAN_ASSIGN_OWNERS, useOwners } from "./OwnerControl";

// P2 (Client 360 contract): five tabs, matching Section 2's own table exactly -- Overview,
// Relationships, Contacts & Sites, Communication, Possible duplicates.
const TABS = [
  { key: "overview", label: "Overview" },
  { key: "relationships", label: "Relationships" },
  { key: "contacts_sites", label: "Contacts & Sites" },
  { key: "communication", label: "Communication" },
  { key: "duplicates", label: "Possible duplicates" },
];

const canEditClient = (role) => ["sales", "pm", "director"].includes(role);
const canEditSource = (role) => ["pm", "director"].includes(role);

function Field({ label, value }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-text-secondary">{label}</div>
      <div className="text-sm text-text-primary break-words">{value || "—"}</div>
    </div>
  );
}

function TabButton({ tab, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`text-sm px-3 py-2 rounded-t-md border-b-2 ${
        active ? "border-gold text-gold font-medium" : "border-transparent text-text-secondary hover:text-text-primary"
      }`}
    >
      {tab.label}
    </button>
  );
}

export default function ClientDetail({ token, role, clientId, onBack, onOpenProject }) {
  const [tab, setTab] = useState("overview");
  const [clientRecord, setClientRecord] = useState(null);
  const [error, setError] = useState("");
  const owners = useOwners(token, role);
  const canAssign = CAN_ASSIGN_OWNERS.includes(role);

  useEffect(() => {
    setTab("overview");
  }, [clientId]);

  useEffect(() => {
    getClient(token, clientId)
      .then(setClientRecord)
      .catch((err) => setError(err.message));
  }, [token, clientId]);

  if (error) {
    return (
      <div className="p-4">
        <p className="text-red-400 text-sm">{error}</p>
        <button onClick={onBack} className="text-xs text-gold hover:underline mt-2">← Back to Leads & Clients</button>
      </div>
    );
  }
  if (!clientRecord) {
    return <div className="p-4 text-sm text-text-secondary">Loading…</div>;
  }

  return (
    <div className="p-4 max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <button onClick={onBack} className="text-xs text-gold hover:underline">← Leads & Clients</button>
          <h1 className="text-lg font-semibold text-text-primary mt-1">{clientRecord.name}</h1>
          <p className="text-xs text-text-secondary capitalize">{clientRecord.type.replace("_", " ")}</p>
        </div>
        {canAssign && (
          <OwnerControl
            token={token}
            kind="client"
            recordId={clientRecord.id}
            ownerId={clientRecord.owner_id}
            owners={owners}
            onChanged={(next) => setClientRecord((c) => ({ ...c, owner_id: next }))}
          />
        )}
      </div>

      <div className="flex flex-wrap border-b border-border-dark">
        {TABS.map((t) => (
          <TabButton key={t.key} tab={t} active={tab === t.key} onClick={() => setTab(t.key)} />
        ))}
      </div>

      {tab === "overview" && (
        <OverviewTab token={token} role={role} client={clientRecord} onChanged={setClientRecord} />
      )}
      {tab === "relationships" && (
        <RelationshipsTab token={token} clientId={clientId} onOpenProject={onOpenProject} />
      )}
      {tab === "contacts_sites" && <ContactsSitesTab token={token} role={role} clientId={clientId} />}
      {tab === "communication" && <CommunicationTab token={token} clientId={clientId} />}
      {tab === "duplicates" && <DuplicatesTab token={token} role={role} clientId={clientId} />}
    </div>
  );
}

// --- Overview ------------------------------------------------------------------------------

function OverviewTab({ token, role, client, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(client);
  const [sourceDraft, setSourceDraft] = useState(client.source || "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function saveDetails(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const updated = await updateClientDetails(token, client.id, {
        name: form.name, contact_name: form.contact_name, phone: form.phone, email: form.email, city: form.city,
      });
      onChanged((c) => ({ ...c, ...updated }));
      setEditing(false);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveSource() {
    setBusy(true);
    setErr("");
    try {
      const updated = await updateClientSource(token, client.id, { source: sourceDraft || null });
      onChanged((c) => ({ ...c, ...updated }));
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-surface rounded-lg border border-border-dark p-4 space-y-4">
      {err && <p className="text-red-400 text-xs">{err}</p>}
      {editing ? (
        <form onSubmit={saveDetails} className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="text-xs text-text-secondary">Name
            <input className="mt-1 w-full bg-base border border-border-dark rounded px-2 py-1.5 text-sm" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </label>
          <label className="text-xs text-text-secondary">Contact name
            <input className="mt-1 w-full bg-base border border-border-dark rounded px-2 py-1.5 text-sm" value={form.contact_name || ""} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} />
          </label>
          <label className="text-xs text-text-secondary">Phone
            <input className="mt-1 w-full bg-base border border-border-dark rounded px-2 py-1.5 text-sm" value={form.phone || ""} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </label>
          <label className="text-xs text-text-secondary">Email
            <input className="mt-1 w-full bg-base border border-border-dark rounded px-2 py-1.5 text-sm" value={form.email || ""} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </label>
          <label className="text-xs text-text-secondary">City
            <input className="mt-1 w-full bg-base border border-border-dark rounded px-2 py-1.5 text-sm" value={form.city || ""} onChange={(e) => setForm({ ...form, city: e.target.value })} />
          </label>
          <div className="sm:col-span-2 flex gap-2">
            <button type="submit" disabled={busy} className="text-xs bg-gold text-base rounded px-3 py-1.5 font-medium">Save</button>
            <button type="button" onClick={() => { setEditing(false); setForm(client); }} className="text-xs border border-border-dark rounded px-3 py-1.5">Cancel</button>
          </div>
        </form>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <Field label="Contact name" value={client.contact_name} />
            <Field label="Phone" value={client.phone} />
            <Field label="Email" value={client.email} />
            <Field label="City" value={client.city} />
            <Field label="GSTIN" value={client.gstin} />
            <Field label="Payment terms" value={client.payment_terms} />
          </div>
          {canEditClient(role) && (
            <button onClick={() => setEditing(true)} className="text-xs border border-border-dark rounded px-2.5 py-1 text-gold hover:bg-gold/10">Edit details</button>
          )}
        </>
      )}

      <div className="flex flex-wrap items-center gap-1.5 pt-1">
        {client.overdue_flag && <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400">Overdue</span>}
        {client.blacklist_flag && <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400">Blacklisted</span>}
        <span className={`text-xs ${client.next_follow_up_date ? "text-text-secondary" : "text-text-secondary"}`}>
          Next follow-up: {client.next_follow_up_date || "—"}
        </span>
      </div>

      <div className="border-t border-border-dark pt-3">
        <div className="text-[10px] uppercase tracking-wider text-text-secondary mb-1">Source</div>
        {canEditSource(role) ? (
          <div className="flex items-center gap-2">
            <input
              className="bg-base border border-border-dark rounded px-2 py-1.5 text-sm w-48"
              placeholder="e.g. referral, website, IndiaMART"
              value={sourceDraft}
              onChange={(e) => setSourceDraft(e.target.value)}
            />
            <button onClick={saveSource} disabled={busy} className="text-xs border border-border-dark rounded px-2.5 py-1 text-gold hover:bg-gold/10">Save</button>
          </div>
        ) : (
          <p className="text-sm text-text-primary">{client.source || "—"} <span className="text-xs text-text-secondary">(PM/Director only to correct)</span></p>
        )}
      </div>
    </div>
  );
}

// --- Relationships ---------------------------------------------------------------------------

function RelationshipsTab({ token, clientId, onOpenProject }) {
  const [projects, setProjects] = useState(null);
  const [opportunities, setOpportunities] = useState(null);

  useEffect(() => {
    listProjects(token, { client_id: clientId }).then(setProjects).catch(() => setProjects([]));
    listOpportunities(token).then((all) => setOpportunities(all.filter((o) => o.client_id === clientId))).catch(() => setOpportunities([]));
  }, [token, clientId]);

  if (projects === null || opportunities === null) return <p className="text-sm text-text-secondary">Loading…</p>;
  if (projects.length === 0 && opportunities.length === 0) {
    return <p className="text-sm text-text-secondary">No opportunities or projects yet.</p>;
  }
  return (
    <div className="space-y-3">
      {projects.length > 0 && (
        <div className="bg-surface rounded-lg border border-border-dark p-3">
          <div className="text-xs uppercase tracking-wider text-text-secondary mb-2">Projects</div>
          <div className="space-y-1.5">
            {projects.map((p) => (
              <button
                key={p.id}
                onClick={() => onOpenProject && onOpenProject(p.id)}
                className="block w-full text-left text-sm text-gold hover:underline"
              >
                {p.project_no} — {p.city}
              </button>
            ))}
          </div>
        </div>
      )}
      {opportunities.length > 0 && (
        <div className="bg-surface rounded-lg border border-border-dark p-3">
          <div className="text-xs uppercase tracking-wider text-text-secondary mb-2">Opportunities</div>
          <div className="space-y-1.5">
            {opportunities.map((o) => (
              <div key={o.id} className="text-sm text-text-primary">{o.lead_name} <span className="text-xs text-text-secondary capitalize">({o.stage})</span></div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// --- Contacts & Sites ------------------------------------------------------------------------

function ContactsSitesTab({ token, role, clientId }) {
  const [contacts, setContacts] = useState(null);
  const [sites, setSites] = useState(null);
  const [newContact, setNewContact] = useState({ name: "", designation: "", phone: "" });
  const [newSite, setNewSite] = useState({ label: "", city: "", site_address: "" });
  const [err, setErr] = useState("");
  const editable = canEditClient(role);

  function reload() {
    listClientContacts(token, clientId).then(setContacts).catch((e) => setErr(e.message));
    listClientSites(token, clientId).then(setSites).catch((e) => setErr(e.message));
  }
  useEffect(reload, [token, clientId]);

  async function addContact(e) {
    e.preventDefault();
    if (!newContact.name.trim()) return;
    try {
      await createClientContact(token, clientId, newContact);
      setNewContact({ name: "", designation: "", phone: "" });
      reload();
    } catch (e2) { setErr(e2.message); }
  }
  async function addSite(e) {
    e.preventDefault();
    if (!newSite.label.trim() || !newSite.city.trim()) return;
    try {
      await createClientSite(token, clientId, newSite);
      setNewSite({ label: "", city: "", site_address: "" });
      reload();
    } catch (e2) { setErr(e2.message); }
  }
  async function toggleContact(c) {
    try {
      await updateClientContact(token, clientId, c.id, { is_active: !c.is_active });
      reload();
    } catch (e2) { setErr(e2.message); }
  }
  async function toggleSite(s) {
    try {
      await updateClientSite(token, clientId, s.id, { is_active: !s.is_active });
      reload();
    } catch (e2) { setErr(e2.message); }
  }

  return (
    <div className="space-y-4">
      {err && <p className="text-red-400 text-xs">{err}</p>}

      <div className="bg-surface rounded-lg border border-border-dark p-3">
        <div className="text-xs uppercase tracking-wider text-text-secondary">Contacts</div>
        <p className="text-xs text-text-secondary mb-2">Who to call at this client.</p>
        {contacts === null ? (
          <p className="text-sm text-text-secondary">Loading…</p>
        ) : contacts.length === 0 ? (
          <p className="text-sm text-text-secondary">No contacts yet.</p>
        ) : (
          <div className="space-y-1.5">
            {contacts.map((c) => (
              <div key={c.id} className="flex items-center justify-between text-sm">
                <span className={c.is_active ? "text-text-primary" : "text-text-secondary line-through"}>
                  {c.name}{c.designation ? ` — ${c.designation}` : ""}{c.phone ? ` · ${c.phone}` : ""}
                </span>
                {editable && (
                  <button onClick={() => toggleContact(c)} className="text-xs text-gold hover:underline shrink-0 ml-2">
                    {c.is_active ? "Deactivate" : "Reactivate"}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        {editable && (
          <form onSubmit={addContact} className="flex flex-wrap gap-2 mt-3 pt-2 border-t border-border-dark">
            <input className="bg-base border border-border-dark rounded px-2 py-1 text-xs flex-1 min-w-[8rem]" placeholder="Name" value={newContact.name} onChange={(e) => setNewContact({ ...newContact, name: e.target.value })} />
            <input className="bg-base border border-border-dark rounded px-2 py-1 text-xs flex-1 min-w-[8rem]" placeholder="Designation" value={newContact.designation} onChange={(e) => setNewContact({ ...newContact, designation: e.target.value })} />
            <input className="bg-base border border-border-dark rounded px-2 py-1 text-xs flex-1 min-w-[8rem]" placeholder="Phone" value={newContact.phone} onChange={(e) => setNewContact({ ...newContact, phone: e.target.value })} />
            <button type="submit" className="text-xs bg-gold text-base rounded px-3 py-1 font-medium">Add</button>
          </form>
        )}
      </div>

      <div className="bg-surface rounded-lg border border-border-dark p-3">
        <div className="text-xs uppercase tracking-wider text-text-secondary">Sites</div>
        <p className="text-xs text-text-secondary mb-2">Locations belonging to this client -- selectable on a Project.</p>
        {sites === null ? (
          <p className="text-sm text-text-secondary">Loading…</p>
        ) : sites.length === 0 ? (
          <p className="text-sm text-text-secondary">No sites yet.</p>
        ) : (
          <div className="space-y-1.5">
            {sites.map((s) => (
              <div key={s.id} className="flex items-center justify-between text-sm">
                <span className={s.is_active ? "text-text-primary" : "text-text-secondary line-through"}>
                  {s.label} — {s.city}{s.site_address ? `, ${s.site_address}` : ""}
                </span>
                {editable && (
                  <button onClick={() => toggleSite(s)} className="text-xs text-gold hover:underline shrink-0 ml-2">
                    {s.is_active ? "Deactivate" : "Reactivate"}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        {editable && (
          <form onSubmit={addSite} className="flex flex-wrap gap-2 mt-3 pt-2 border-t border-border-dark">
            <input className="bg-base border border-border-dark rounded px-2 py-1 text-xs flex-1 min-w-[8rem]" placeholder="Label" value={newSite.label} onChange={(e) => setNewSite({ ...newSite, label: e.target.value })} />
            <input className="bg-base border border-border-dark rounded px-2 py-1 text-xs flex-1 min-w-[8rem]" placeholder="City" value={newSite.city} onChange={(e) => setNewSite({ ...newSite, city: e.target.value })} />
            <input className="bg-base border border-border-dark rounded px-2 py-1 text-xs flex-1 min-w-[8rem]" placeholder="Address" value={newSite.site_address} onChange={(e) => setNewSite({ ...newSite, site_address: e.target.value })} />
            <button type="submit" className="text-xs bg-gold text-base rounded px-3 py-1 font-medium">Add</button>
          </form>
        )}
      </div>

      <div className="bg-surface rounded-lg border border-border-dark p-3">
        <div className="text-xs uppercase tracking-wider text-text-secondary">Signatories</div>
        <p className="text-xs text-text-secondary mb-2">Who is authorised to accept documents on this client's behalf. Edit only to correct an error -- changes affect future approval matching.</p>
        <ClientSignatoriesPanel token={token} clientId={clientId} />
      </div>
    </div>
  );
}

// --- Communication -----------------------------------------------------------------------------

function CommunicationTab({ token, clientId }) {
  const [messages, setMessages] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    listClientMessages(token, clientId).then(setMessages).catch((e) => setErr(e.message));
  }, [token, clientId]);

  if (err) return <p className="text-red-400 text-xs">{err}</p>;
  if (messages === null) return <p className="text-sm text-text-secondary">Loading…</p>;
  if (messages.length === 0) return <p className="text-sm text-text-secondary">No messages available to you.</p>;

  return (
    <div className="space-y-2">
      {messages.map((m) => (
        <div key={m.id} className="bg-surface rounded-lg border border-border-dark p-3 text-sm">
          <div className="flex items-center justify-between text-xs text-text-secondary">
            <span className="uppercase tracking-wider">{m.doc_type.replace("_", " ")} · {m.channel}</span>
            <span>{new Date(m.created_at).toLocaleString()}</span>
          </div>
          {m.subject && <div className="font-medium mt-1">{m.subject}</div>}
          <div className="text-text-primary mt-0.5">{m.body_note || "(no note)"}</div>
          <div className="text-xs text-text-secondary mt-1">To: {m.recipient} · {m.status}</div>
        </div>
      ))}
    </div>
  );
}

// --- Possible duplicates -------------------------------------------------------------------------

function DuplicatesTab({ token, role, clientId }) {
  const [candidates, setCandidates] = useState(null);
  const [err, setErr] = useState("");
  const canDismiss = ["sales", "pm", "director"].includes(role);
  const canRestore = ["pm", "director"].includes(role);

  function reload() {
    listClientDuplicates(token, clientId).then(setCandidates).catch((e) => setErr(e.message));
  }
  useEffect(reload, [token, clientId]);

  async function dismiss(otherId) {
    try {
      await dismissClientDuplicate(token, clientId, otherId);
      reload();
    } catch (e2) { setErr(e2.message); }
  }
  async function restore(otherId) {
    try {
      await restoreClientDuplicate(token, clientId, otherId);
      reload();
    } catch (e2) { setErr(e2.message); }
  }

  if (err) return <p className="text-red-400 text-xs">{err}</p>;
  if (candidates === null) return <p className="text-sm text-text-secondary">Loading…</p>;
  if (candidates.length === 0) return <p className="text-sm text-text-secondary">No likely duplicates found.</p>;

  return (
    <div className="space-y-2">
      <p className="text-xs text-text-secondary">Suggestions only -- dismissing affects every viewer's list, not just yours. No merge action exists here.</p>
      {candidates.map((c) => (
        <div key={c.client_id} className="bg-surface rounded-lg border border-border-dark p-3 flex items-center justify-between text-sm">
          <span>{c.name} <span className="text-xs text-text-secondary">(matched on {c.matched_field})</span></span>
          <span className="flex gap-2">
            {canDismiss && (
              <button onClick={() => dismiss(c.client_id)} className="text-xs border border-border-dark rounded px-2.5 py-1 text-text-secondary hover:text-text-primary">Dismiss</button>
            )}
            {canRestore && (
              <button onClick={() => restore(c.client_id)} className="text-xs border border-border-dark rounded px-2.5 py-1 text-text-secondary hover:text-text-primary">Restore if dismissed</button>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}
