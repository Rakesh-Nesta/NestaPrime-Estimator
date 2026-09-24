import { useState } from "react";

// Amendment 47 (Section 52): inline "fix a typo" form shared by lead rows
// (Opportunities) and client cards (Leads & Clients). The caller decides
// what a save means -- this only collects name / [contact name] / phone /
// email and reports the values back.
export default function EditDetailsForm({ initial, withContactName = false, withCity = false, idPrefix, onSave, onCancel }) {
  const [values, setValues] = useState({
    name: initial.name || "",
    contact_name: initial.contact_name || "",
    phone: initial.phone || "",
    email: initial.email || "",
    city: initial.city || "",
  });
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
    setError("");
    setSaving(true);
    try {
      await onSave(values);
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  const inputClass =
    "mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1.5 text-sm";
  const labelClass = "block text-xs font-medium text-text-secondary";

  return (
    <form onSubmit={handleSubmit} className="space-y-3 border-t border-border-dark pt-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label htmlFor={`${idPrefix}-name`} className={labelClass}>Name</label>
          <input
            id={`${idPrefix}-name`}
            type="text"
            value={values.name}
            onChange={(e) => setField("name", e.target.value)}
            className={inputClass}
          />
        </div>
        {withContactName && (
          <div>
            <label htmlFor={`${idPrefix}-contact`} className={labelClass}>Contact name</label>
            <input
              id={`${idPrefix}-contact`}
              type="text"
              value={values.contact_name}
              onChange={(e) => setField("contact_name", e.target.value)}
              className={inputClass}
            />
          </div>
        )}
        <div>
          <label htmlFor={`${idPrefix}-phone`} className={labelClass}>Phone</label>
          <input
            id={`${idPrefix}-phone`}
            type="text"
            inputMode="tel"
            value={values.phone}
            onChange={(e) => setField("phone", e.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor={`${idPrefix}-email`} className={labelClass}>Email</label>
          <input
            id={`${idPrefix}-email`}
            type="email"
            value={values.email}
            onChange={(e) => setField("email", e.target.value)}
            className={inputClass}
          />
        </div>
        {withCity && (
          <div>
            <label htmlFor={`${idPrefix}-city`} className={labelClass}>City (optional)</label>
            <input
              id={`${idPrefix}-city`}
              type="text"
              maxLength={100}
              value={values.city}
              onChange={(e) => setField("city", e.target.value)}
              className={inputClass}
            />
          </div>
        )}
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      <div className="flex items-center gap-4 text-xs">
        <button
          type="submit"
          disabled={saving}
          className="bg-gold text-base rounded px-3 py-1.5 font-semibold hover:bg-gold-hover disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save details"}
        </button>
        <button type="button" onClick={onCancel} disabled={saving} className="text-text-secondary hover:text-text-primary">
          Cancel
        </button>
      </div>
    </form>
  );
}
