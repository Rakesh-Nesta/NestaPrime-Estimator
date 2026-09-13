import { useState } from "react";
import { DIRECTOR_ADMIN_GUIDE, ESTIMATOR_GUIDE, FAQ, FULL_HANDBOOK } from "./handbookData";

// Amendment 10 (Annexure 2): Section 4 shipped the Quick Start card alone
// (v1). This file now also carries Section 5's items 2-4 -- Full Handbook,
// per-role guides, FAQ -- as v2 of the same handbook (see the Maintenance
// note in the register: "every shipped amendment wave updates the relevant
// chapter"). Steps match the app's real screen graph (Amendment 4's own
// breadcrumb), and each "watch out for" line is drawn from an actual gap
// this session found live, not invented -- so a new estimator hears it once
// here instead of hitting it cold on a real project.
const STEPS = [
  {
    n: 1,
    title: "Setup",
    body: "Dashboard -> + New project. Quick mode asks 4 things (Client, Sport, City, " +
      "Base scope/status) and creates the project + sport in one step -- court size is " +
      "set on the next screen, Sport Selection, not here. Switch to Detailed if the " +
      "client is Government/Tender, or you need site details up front.",
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

const TABS = [
  { key: "quick_start", label: "Quick Start" },
  { key: "handbook", label: "Full Handbook" },
  { key: "estimator", label: "Estimator Guide" },
  { key: "admin", label: "Director/Admin Guide", adminOnly: true },
  { key: "faq", label: "FAQ" },
];

function Card({ children }) {
  return (
    <div className="bg-surface border border-border-dark rounded-lg p-6 sm:p-8 print:border-black print:bg-white">
      {children}
    </div>
  );
}

function BrandHeader() {
  return (
    <div className="flex items-center gap-2.5 mb-1 print:hidden">
      <span className="w-8 h-8 rounded bg-base border border-gold/40 flex items-center justify-center text-gold font-heading font-bold text-sm">
        N
      </span>
      <span className="font-heading font-bold text-text-primary tracking-tight">
        NestaPrime <span className="text-text-secondary font-normal">Estimator</span>
      </span>
    </div>
  );
}

export default function Help({ role, onBack }) {
  const isAdmin = role === "director";
  const [tab, setTab] = useState("quick_start");
  const visibleTabs = TABS.filter((t) => !t.adminOnly || isAdmin);

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 px-4">
      <div className="flex items-center justify-between mb-4 print:hidden">
        <div>
          <h2 className="font-heading font-bold text-text-primary text-lg">Help</h2>
          <p className="text-sm text-text-secondary">Quick Start, the full handbook, your role's guide, and the FAQ.</p>
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

      <div className="flex gap-1 mb-4 border-b border-border-dark print:hidden">
        {visibleTabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`text-sm px-3 py-2 border-b-2 -mb-px ${
              tab === t.key ? "border-gold text-gold font-medium" : "border-transparent text-text-secondary hover:text-text-primary"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "quick_start" && (
        <Card>
          <BrandHeader />
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
        </Card>
      )}

      {tab === "handbook" && (
        <Card>
          <BrandHeader />
          <h1 className="font-heading font-bold text-text-primary text-2xl mt-3 print:text-black">Full Handbook</h1>
          <p className="text-sm text-text-secondary mt-1 print:text-gray-700">
            Amendment 10 (User Handbook) · Section 5 · v2 — every screen, what it does, and what to do
            when the client hasn't given you the data.
          </p>
          <div className="mt-6 space-y-6">
            {FULL_HANDBOOK.map((s) => (
              <div key={s.screen} className="border-t border-border-dark pt-4 first:border-t-0 first:pt-0 print:border-gray-300">
                <h3 className="font-heading font-semibold text-text-primary print:text-black">{s.screen}</h3>
                <p className="text-sm text-text-secondary mt-1 print:text-gray-800">{s.what}</p>
                {s.fields?.length > 0 && (
                  <ul className="list-disc list-inside text-sm text-text-secondary mt-2 space-y-0.5 print:text-gray-800">
                    {s.fields.map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                  </ul>
                )}
                {s.detailedModeFields && (
                  <p className="text-sm text-text-secondary mt-2 print:text-gray-800">{s.detailedModeFields}</p>
                )}
                {s.whenMissing && (
                  <p className="text-xs text-text-secondary mt-2 italic print:text-gray-700">
                    When the client hasn't provided this: {s.whenMissing}
                  </p>
                )}
                {s.example && (
                  <p className="text-xs text-text-secondary bg-surface-raised rounded px-2 py-1.5 mt-2 print:bg-gray-100 print:text-gray-800">
                    {s.example}
                  </p>
                )}
                {s.watch && (
                  <p className="text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1 mt-2 print:bg-white print:text-gray-700 print:border print:border-gray-400">
                    Watch out for: {s.watch}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {tab === "estimator" && (
        <Card>
          <BrandHeader />
          <h1 className="font-heading font-bold text-text-primary text-2xl mt-3 print:text-black">
            {ESTIMATOR_GUIDE.role}
          </h1>
          <p className="text-sm text-text-secondary mt-1 print:text-gray-700">{ESTIMATOR_GUIDE.intro}</p>
          <div className="mt-6 space-y-4">
            {ESTIMATOR_GUIDE.sections.map((s) => (
              <div key={s.title}>
                <h3 className="font-heading font-semibold text-text-primary print:text-black">{s.title}</h3>
                <p className="text-sm text-text-secondary mt-1 print:text-gray-800">{s.body}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {tab === "admin" && isAdmin && (
        <Card>
          <BrandHeader />
          <h1 className="font-heading font-bold text-text-primary text-2xl mt-3 print:text-black">
            {DIRECTOR_ADMIN_GUIDE.role}
          </h1>
          <p className="text-sm text-text-secondary mt-1 print:text-gray-700">{DIRECTOR_ADMIN_GUIDE.intro}</p>
          <div className="mt-6 space-y-4">
            {DIRECTOR_ADMIN_GUIDE.sections.map((s) => (
              <div key={s.title}>
                <h3 className="font-heading font-semibold text-text-primary print:text-black">{s.title}</h3>
                <p className="text-sm text-text-secondary mt-1 print:text-gray-800">{s.body}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {tab === "faq" && (
        <Card>
          <BrandHeader />
          <h1 className="font-heading font-bold text-text-primary text-2xl mt-3 print:text-black">FAQ</h1>
          <p className="text-sm text-text-secondary mt-1 print:text-gray-700">
            The questions the team actually asks.
          </p>
          <div className="mt-6 space-y-4">
            {FAQ.map((item) => (
              <div key={item.q}>
                <h3 className="text-sm font-semibold text-text-primary print:text-black">{item.q}</h3>
                <p className="text-sm text-text-secondary mt-0.5 print:text-gray-800">{item.a}</p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
