import { useEffect, useState } from "react";
import { listClients, updateClientConsent, updateClientFlags } from "./api";

export default function ClientsAdmin({ token, role, onBack }) {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [chatIdDrafts, setChatIdDrafts] = useState({});
  const canEditFlags = role === "director";

  function load() {
    return listClients(token).then(setClients);
  }

  useEffect(() => {
    load()
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

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

      <div className="bg-surface shadow rounded-lg p-6 space-y-2">
        {clients.map((c) => (
          <div key={c.id} className="flex items-center justify-between border border-border-dark rounded px-3 py-2 text-sm">
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
        ))}
        {clients.length === 0 && <p className="text-sm text-text-secondary">No clients yet.</p>}
      </div>
    </div>
  );
}
