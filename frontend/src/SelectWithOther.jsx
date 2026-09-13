import { useState } from "react";

// Amendment 5's dropdown "Others" rule: "append 'Others' to every dropdown
// component in the app; selecting it dynamically renders a text input
// below; the typed text becomes the display label." Scoped (per the
// Director-approved Section 6 spec) to dropdowns whose value becomes a
// client-facing label -- not business-logic enums that drive computed
// pricing/scope. `options` is an array of plain strings; `value` may be
// anything, including free text that doesn't match any option (e.g. a
// legacy value, or a vendor typed before the master list existed) -- that
// case starts in Others mode automatically so the real value is never
// silently dropped.
export default function SelectWithOther({ label, value, onChange, options, required = false, small = false }) {
  const [othersMode, setOthersMode] = useState(value !== "" && !options.includes(value));

  function handleSelectChange(e) {
    const selected = e.target.value;
    if (selected === "__others__") {
      setOthersMode(true);
      onChange("");
    } else {
      setOthersMode(false);
      onChange(selected);
    }
  }

  return (
    <div>
      {label && (
        <label className={`block font-medium text-text-secondary ${small ? "text-xs" : "text-sm"}`}>{label}</label>
      )}
      <select
        value={othersMode ? "__others__" : value}
        onChange={handleSelectChange}
        required={required && !othersMode}
        className={`mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 ${
          small ? "py-1 text-xs" : "py-2 text-sm"
        }`}
      >
        <option value="" disabled={required}>
          {required ? "Select…" : "None"}
        </option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
        <option value="__others__">Others…</option>
      </select>
      {othersMode && (
        <input
          type="text"
          value={value}
          required={required}
          placeholder="Type the value"
          onChange={(e) => onChange(e.target.value)}
          className={`mt-1 w-full rounded border border-gold/40 bg-surface-raised text-text-primary px-2 ${
            small ? "py-1 text-xs" : "py-2 text-sm"
          }`}
        />
      )}
    </div>
  );
}
