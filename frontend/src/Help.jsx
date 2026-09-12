// Amendment 10 (Annexure 2), Section 4 scope: the one-page Quick Start
// card only -- "5-step daily path, printable, kept at each desk." The
// full handbook, per-role guides and FAQ (items 2-4 of Amendment 10's own
// Contents list) are Section 5, not built here. Steps match the app's
// real screen graph (Amendment 4's own breadcrumb), and each "watch out
// for" line is drawn from an actual gap this session found live, not
// invented -- so a new estimator hears it once here instead of hitting it
// cold on a real project.
const STEPS = [
  {
    n: 1,
    title: "Setup",
    body: "Dashboard -> + New project. Quick mode asks 5 things (Client, Sport, City, " +
      "Dimensions, Base scope) and creates the project + sport in one step. Switch to " +
      "Detailed if the client is Government/Tender, or you need site details up front.",
    watch: "\"Existing client\" only starts a NEW project against that client -- it doesn't " +
      "reopen one already in progress. To get back into an existing project, use the " +
      "Dashboard's Recent projects list, not New Project Setup.",
  },
  {
    n: 2,
    title: "Sport",
    body: "Pick the sport(s) for the project. Each tile shows the standard playing/build " +
      "size -- click \"Customize size\" if this project's court is a non-standard size; " +
      "it applies to every cost-sheet line for that sport automatically.",
    watch: "A custom size can't go below the sport's real federation playing dimensions " +
      "(only the surround/clearance is adjustable) -- the app will tell you the exact " +
      "floor if you try.",
  },
  {
    n: 3,
    title: "Scope",
    body: "Tick the Additional Scope items that actually apply to this site (changing " +
      "rooms, boundary wall, DG, etc.) -- unchecked items are simply excluded, not asked " +
      "about again later. Site Survey is a separate optional step from here if the site " +
      "needs its own record.",
    watch: null,
  },
  {
    n: 4,
    title: "Documents",
    body: "Build the Cost Sheet from take-off (Structures, Base, Flooring, Lighting, " +
      "etc.), or add lines manually. Verify it once it's ready, then create the Estimate.",
    watch: "The Rate Sheet may be empty for a rate you need -- if so, there's no app-" +
      "provided market rate yet, and entering a correct one is on you until a real rate " +
      "card is loaded (Note R1). Check with a PM/Director before guessing on anything " +
      "large.",
  },
  {
    n: 5,
    title: "Quotation",
    body: "Once an Estimate option is Client-approved (or demand-received), create the " +
      "Quotation, release it, send it, and track it through to Won or Lost.",
    watch: null,
  },
];

export default function Help({ onBack }) {
  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 px-4">
      <div className="flex items-center justify-between mb-4 print:hidden">
        <div>
          <h2 className="font-heading font-bold text-text-primary text-lg">Quick Start</h2>
          <p className="text-sm text-text-secondary">The 5-step daily path -- print it, keep it at your desk.</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => window.print()}
            className="text-xs uppercase tracking-wider bg-gold hover:bg-gold-hover text-base rounded px-4 py-2 font-semibold transition-colors duration-200"
          >
            Print / Save as PDF
          </button>
          <button onClick={onBack} className="text-xs uppercase tracking-wider text-text-secondary hover:text-text-primary">
            Back
          </button>
        </div>
      </div>

      <div className="bg-surface border border-border-dark rounded-lg p-6 sm:p-8 print:border-black print:bg-white">
        <div className="flex items-center gap-2.5 mb-1 print:hidden">
          <span className="w-8 h-8 rounded bg-base border border-gold/40 flex items-center justify-center text-gold font-heading font-bold text-sm">
            N
          </span>
          <span className="font-heading font-bold text-text-primary tracking-tight">
            NestaPrime <span className="text-text-secondary font-normal">Estimator</span>
          </span>
        </div>
        <h1 className="font-heading font-bold text-text-primary text-2xl mt-3 print:text-black">
          Quick Start — the 5-step daily path
        </h1>
        <p className="text-sm text-text-secondary mt-1 print:text-gray-700">
          Amendment 10 (User Handbook) · Section 4 · v1
        </p>

        <ol className="mt-6 space-y-5">
          {STEPS.map((step) => (
            <li key={step.n} className="flex gap-4">
              <span className="shrink-0 w-8 h-8 rounded-full bg-gold text-base font-heading font-bold flex items-center justify-center text-sm print:border print:border-black print:bg-white print:text-black">
                {step.n}
              </span>
              <div>
                <h3 className="font-heading font-semibold text-text-primary print:text-black">{step.title}</h3>
                <p className="text-sm text-text-secondary mt-0.5 print:text-gray-800">{step.body}</p>
                {step.watch && (
                  <p className="text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1 mt-1.5 print:bg-white print:text-gray-700 print:border print:border-gray-400">
                    Watch out for: {step.watch}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
