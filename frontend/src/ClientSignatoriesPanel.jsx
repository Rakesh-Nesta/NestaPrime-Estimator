import { useEffect, useState } from "react";
import { createClientSignatory, listClientSignatories, updateClientSignatory } from "./api";

function emptyForm() {
  return { name: "", designation: "", email: "", phone: "", authorization_date: "", expiry_date: "" };
}

export default function ClientSignatoriesPanel({ token, clientId }) {
  const [signatories, setSignatories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [form, setForm] = useState(emptyForm());
  const [saving, setSaving] = useState(false);

  function load() {
    return listClientSignatories(token, clientId, true)
      .then(setSignatories)
      .catch((err) => setError(err.message));
  }

  useEffect(() => {
    setLoading(true);
    load().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, clientId]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      await createClientSignatory(token, clientId, {
        name: form.name,
        designation: form.designation,
        email: form.email || null,
        phone: form.phone || null,
        authorization_date: form.authorization_date,
        expiry_date: form.expiry_date || null,
      });
      setForm(emptyForm());
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(signatory) {
    setError("");
    try {
      await updateClientSignatory(token, clientId, signatory.id, { is_active: !signatory.is_active });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  if (loading) return null;

  return (
    <div className="bg-surface shadow rounded-lg p-6 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-text-secondary">Client signatories (Part O)</h3>
          <p className="text-xs text-text-secondary">
            Named approvers whose name + designation an approval_evidence attachment can be matched against (M.3).
          </p>
        </div>
        <button onClick={() => setExpanded((v) => !v)} className="text-xs text-gold hover:underline">
          {expanded ? "Hide" : signatories.length === 0 ? "+ Add signatory" : `${signatories.length} on file`}
        </button>
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}

      {expanded && (
        <>
          {signatories.map((s) => (
            <div
              key={s.id}
              className="flex flex-wrap items-center justify-between gap-2 text-xs bg-surface-raised rounded px-2 py-1 border border-border-dark"
            >
              <span>
                <span className="font-medium">{s.name}</span> · {s.designation}
                {s.email && <span className="text-text-secondary"> · {s.email}</span>}
                <span className="text-text-secondary">
                  {" "}
                  · authorized {s.authorization_date}
                  {s.expiry_date ? ` – ${s.expiry_date}` : ""}
                </span>
                <span className={s.is_active ? "text-green-400" : "text-text-secondary"}> · {s.is_active ? "active" : "inactive"}</span>
              </span>
              <button onClick={() => toggleActive(s)} className="text-text-secondary hover:underline">
                {s.is_active ? "Deactivate" : "Reactivate"}
              </button>
            </div>
          ))}

          <form onSubmit={handleCreate} className="grid grid-cols-2 gap-2 pt-1">
            <input
              value={form.name}
              onChange={set("name")}
              placeholder="Name"
              required
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs"
            />
            <input
              value={form.designation}
              onChange={set("designation")}
              placeholder="Designation"
              required
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs"
            />
            <input
              value={form.email}
              onChange={set("email")}
              placeholder="Email (optional)"
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs"
            />
            <input
              value={form.phone}
              onChange={set("phone")}
              placeholder="Phone (optional)"
              className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs"
            />
            <label className="text-xs text-text-secondary flex items-center gap-1">
              Authorized from
              <input
                type="date"
                value={form.authorization_date}
                onChange={set("authorization_date")}
                required
                className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs flex-1"
              />
            </label>
            <label className="text-xs text-text-secondary flex items-center gap-1">
              Expires (optional)
              <input
                type="date"
                value={form.expiry_date}
                onChange={set("expiry_date")}
                className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs flex-1"
              />
            </label>
            <button
              type="submit"
              disabled={saving}
              className="col-span-2 bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover disabled:opacity-50"
            >
              {saving ? "Saving…" : "Add signatory"}
            </button>
          </form>
        </>
      )}
    </div>
  );
}
