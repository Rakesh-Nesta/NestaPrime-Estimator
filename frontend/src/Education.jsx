// Amendment 12 (Section 11): "add one more header Education we describe
// after all process done which points cover in education part" -- a nav
// slot reserved now, content to follow once Amendment 12 ships.
export default function Education({ onBack }) {
  return (
    <div className="max-w-2xl mx-auto mt-8 mb-10 px-4">
      <div className="bg-surface border border-border-dark rounded-lg p-8 text-center space-y-3">
        <div className="flex items-center justify-between text-left">
          <h2 className="font-heading font-bold text-text-primary text-lg">Education</h2>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>
        <p className="text-text-secondary text-sm pt-6">Coming soon.</p>
      </div>
    </div>
  );
}
