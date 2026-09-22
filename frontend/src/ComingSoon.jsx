// Amendment 36 (Section 42): placeholder for a header whose real backend
// doesn't exist yet (Opportunities/Follow-ups/Payments -- Phases 4/5/7).
// Deliberately not a "0" or empty list anywhere -- an unbuilt capability
// must never look like a real, empty one.
export default function ComingSoon({ title, description, onBack }) {
  return (
    <div className="max-w-2xl mx-auto mt-16 px-4 text-center">
      <p className="text-xs uppercase tracking-wider text-gold font-semibold mb-3">Coming soon</p>
      <h2 className="font-heading font-bold text-text-primary text-2xl mb-3">{title}</h2>
      <p className="text-text-secondary text-sm mb-8">{description}</p>
      {onBack && (
        <button
          onClick={onBack}
          className="text-xs uppercase tracking-wider bg-surface border border-border-dark text-text-secondary hover:text-text-primary hover:border-gold/40 rounded px-4 py-2 font-semibold transition-all duration-250 ease-out"
        >
          ← Back to Overview
        </button>
      )}
    </div>
  );
}
