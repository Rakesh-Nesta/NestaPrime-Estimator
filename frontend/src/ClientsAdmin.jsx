import { useEffect, useState } from "react";
import { createClient, listClients, listProjects, updateClientConsent, updateClientFlags } from "./api";

const CLIENT_TYPES = ["school", "college", "housing_society", "corporate", "club", "government", "individual"];
const emptyClientForm = { name: "", type: "school", contact_name: "", phone: "", email: "" };
const canCreateClient = (role) => ["sales", "pm", "director"].includes(role);

// Section 19 (Amendment 4 continuation): reuses AllProjects.jsx's own status
// pill colors, kept as a small local duplicate rather than a shared import,
// same pattern already used for other small per-file constant maps.
const STATUS_PILL_STYLE = {
  open: "bg-gold/10 text-gold",
  won: "bg-green-500/10 text-green-400",
  lost: "bg-red-500/10 text-red-400",
};

export default function ClientsAdmin({ token, role, onOpenProject, onBack }) {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [chatIdDrafts, setChatIdDrafts] = useState({});
  const [form, setForm] = useState(emptyClientForm);
  const [submitting, setSubmitting] = useState(false);
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
    return listClients(token).then(setClients);
  }

  useEffect(() => {
    load()
      .catch((err) => setError(err.message))
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
      });
      setForm(emptyClientForm);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
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

  if (loading) {
    return <p className="text-center text-text-secondary mt-10">Loading clients…</p>;
  }

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Clients</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-xs text-text-secondary mt-1">
          Part O: "overdue_flag (blocks new Quotation release until Director clears), blacklist_flag (blocks new
          Estimates)." Overdue/Blacklisted are Director-only (enforced below, not just server-side); consent
          toggles are open to Sales/PM/Director.
        </p>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
      </div>

      {canCreateClient(role) && (
        <form onSubmit={handleCreateClient} className="bg-surface shadow rounded-lg p-6 space-y-3">
          <h3 className="text-sm font-semibold text-text-secondary">Add a client</h3>
          <div className="grid grid-cols-2 gap-3">
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
            <div className="col-span-2">
              <label className="block text-sm font-medium text-text-secondary">Email</label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setField("email", e.target.value)}
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

      <div className="bg-surface shadow rounded-lg p-6 space-y-2">
        {clients.map((c) => (
          <div key={c.id} className="border border-border-dark rounded px-3 py-2 text-sm space-y-2">
          <div className="flex items-center justify-between">
            <span>
              <span className="font-medium">{c.name}</span>{" "}
              <span className="text-xs text-text-secondary">({c.type})</span>
            </span>
            <div className="flex items-center gap-4 text-xs">
              <label
                className={`flex items-center gap-1 ${!canEditFlags ? "opacity-50" : ""}`}
                title={canEditFlags ? undefined : "Director only"}
              >
                <input
                  type="checkbox"
                  checked={c.overdue_flag}
                  disabled={!canEditFlags}
                  onChange={(e) => toggleFlag(c.id, "overdue_flag", e.target.checked)}
                />
                Overdue
              </label>
              <label
                className={`flex items-center gap-1 ${!canEditFlags ? "opacity-50" : ""}`}
                title={canEditFlags ? undefined : "Director only"}
              >
                <input
                  type="checkbox"
                  checked={c.blacklist_flag}
                  disabled={!canEditFlags}
                  onChange={(e) => toggleFlag(c.id, "blacklist_flag", e.target.checked)}
                />
                Blacklisted
              </label>
              <span className="border-l border-border-dark pl-4 flex items-center gap-4">
                <label className="flex items-center gap-1" title="M.7.2 rule 5 (DPDP Act)">
                  <input
                    type="checkbox"
                    checked={c.whatsapp_opt_in}
                    onChange={(e) => toggleConsent(c.id, "whatsapp_opt_in", e.target.checked)}
                  />
                  WhatsApp opt-in
                </label>
                <label className="flex items-center gap-1" title="M.7.2 rule 5 (DPDP Act)">
                  <input
                    type="checkbox"
                    checked={c.email_opt_in}
                    onChange={(e) => toggleConsent(c.id, "email_opt_in", e.target.checked)}
                  />
                  Email opt-in
                </label>
                <label
                  className="flex items-center gap-1"
                  title="Amendment 8: a bot can only message a chat that has messaged it first"
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
        ))}
        {clients.length === 0 && <p className="text-sm text-text-secondary">No clients yet.</p>}
      </div>
    </div>
  );
}
