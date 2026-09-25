export default function MiniField({ label, value, onChange, required = false }) {
  return (
    <div>
      <label className="block text-xs text-text-secondary">{label}</label>
      <input
        type="text"
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-sm"
      />
    </div>
  );
}
