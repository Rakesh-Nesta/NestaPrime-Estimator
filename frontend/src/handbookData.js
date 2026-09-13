// Amendment 10 (Annexure 2), Section 5 scope: the Full Handbook, per-role
// guides, and FAQ (items 2-4 of Amendment 10's own Contents list). Content
// here is drawn from the app's own real screen graph and behavior (verified
// against the actual frontend/backend code, not guessed) -- where the
// registered spec named a worked example that doesn't exist in the real
// project data reviewed for Note R1 ("the Ujjain Pickleball job"), the
// real Ujjain job on record (a squash court, RK Bansal School, Dec 2022) is
// used instead, per Director decision (13 Sept 2026).

export const FULL_HANDBOOK = [
  {
    screen: "Project Setup",
    what: "Create a new project against a new or existing client. Quick mode is the default; Detailed mode is required for Government/Tender clients or any client type with no standard package default.",
    fields: [
      "Client — new (name + type) or pick an existing client from the dropdown",
      "Sport — the first sport for this project (more can be added on Sport Selection)",
      "City / district",
      "Base scope / status — the project's starting condition",
    ],
    whenMissing:
      "Quick mode doesn't ask for anything beyond the four items above — there is no Dimensions field here (court size is set on Sport Selection, next step). Everything Detailed mode would otherwise ask (site condition, soil type, building status, site access, power/water, distance from hub) is defaulted to a standard assumption and printed on the Quotation as a blind-quoting T&C line, per Amendment 2.",
    detailedModeFields:
      "Detailed mode additionally asks: project type, client payment terms, site address, nearest hub, distance from hub, site condition, soil type, building status, site access, power available, water available, number of courts, unit system, package, and (for existing buildings) clear height and safe bearing capacity.",
    watch:
      "\"Existing client\" only starts a NEW project against that client — it doesn't reopen one already in progress. To resume an existing project, use the Dashboard's Recent Projects list or the project search, not New Project Setup.",
  },
  {
    screen: "Sport Selection",
    what: "Pick every sport this project covers, set each one's building status and court count, and optionally customize the court's build size away from the sport's federation standard.",
    fields: [
      "Building status per sport (Existing building / New PEB / Open air / Covered shed)",
      "Number of courts (defaults to 1)",
      "Custom court size (optional) — Length/Width in feet",
      "Actual (as-built) dimensions — site_engineer/PM/Director only, recorded once the court is physically built",
    ],
    whenMissing:
      "Leave court size blank to use the sport's own standard build dimensions — nothing needs to be filled in for a standard-size court.",
    watch:
      "A custom size can't go below the sport's real federation playing dimensions — only the surround/clearance is adjustable; the app states the exact floor if you try to go under it. The court-shape preview only draws a real outline when the sport has a fixed playing rectangle — track and per-lane sports show a placeholder instead, which is expected, not a bug.",
  },
  {
    screen: "Scope",
    what: "Tick every Additional Scope item that actually applies to this site (boundary wall, changing rooms, DG set, etc.).",
    fields: ["One checkbox per scope item, grouped Civil / Electrical / Water / External / Services / Maintenance"],
    whenMissing:
      "An unchecked item is simply excluded from the project — it prints under Exclusions on the Quotation, and is never asked about again later. There's no \"not applicable\" state beyond leaving it unchecked.",
    watch:
      "Each checkbox saves immediately on click — there is no separate Save button and no undo confirmation, so double-check before unticking something that was already correct.",
  },
  {
    screen: "Site Survey",
    what: "An optional, separate record of the physical site (area, slope, soil, power, water, access) plus at least 4 photos, used for sites that need their own documented visit.",
    fields: [
      "Client / site address / PIN / contact name / contact phone (starting the survey)",
      "Available area (L×W + unit), slope, soil type, water-logging, access road width, crane access, power phase/load, water source, existing structures, neighbour constraints, orientation",
    ],
    whenMissing:
      "Every field on this screen is optional — none are marked required, so a survey can be started and saved with only some fields filled. There is no built-in reminder about the photo requirement below.",
    watch:
      "Marking a survey Completed is blocked until at least 4 photos are attached — this isn't shown until you try to complete, so a survey can otherwise look finished and then unexpectedly block you. Once Completed, every field locks.",
  },
  {
    screen: "Rate Sheet",
    what: "The company's own material/labour rate reference (Module 11) — every Cost Sheet line ultimately draws from here, or is entered fresh. New entries always start Manual and Unverified; only a PM/Director confirming one promotes it to an AI (master) rate.",
    fields: [
      "Category, item name, spec, unit, HSN/SAC, rate (Rs)",
      "GST % override — leave blank to use the company-wide default; only set this if the item's real GST rate genuinely differs (e.g. sports-goods equipment is 5%, not the usual 18%)",
      "Vendor, city of quote, labour category (blank = 22% blended fallback), commodity watch flag",
    ],
    whenMissing:
      "If the Rate Sheet has no entry for something you need, there is no app-provided market rate yet — enter a correct one yourself and flag it to a PM/Director for confirmation before it's used on anything large. This is exactly Note R1's open item: the app now ships with a 20-item starter rate card from real historical quotations, but it doesn't cover everything, and every seeded item is still Unverified until a PM/Director reviews it.",
    watch:
      "Unverified rates never become defaults for a new Cost Sheet line — someone still has to type it in or confirm it first. A rate flagged \"commodity watched\" (e.g. steel, turf) triggers an alert when its price moves past the configured threshold since it was last confirmed.",
  },
  {
    screen: "Cost Sheet Builder",
    what: "Build the real, internal cost of the project — one tab per work package (Structures, Base, Flooring, Lighting, HVAC, Pool, and 13 more), each with its own take-off calculator. PM/Director only see real rates here; Sales works in a separate Rate-blind mode (see the Estimator Guide).",
    fields: [
      "Each tab needs the relevant Project Sport plus that package's own inputs — e.g. Structures needs Type, section, wall thickness, build L/W/height, foundation depth and either a netting grade or a manual rate; Flooring (acrylic) needs surface type, coats and rate/sqft/coat; Lighting needs target lux, fixture wattage/count and cable/panel rates.",
      "\"Manual line\" — for anything with no dedicated calculator: work package, category, item, unit, quantity, rate, optional labour category.",
    ],
    whenMissing:
      "A green recommendation banner (drawn from Sport Selection's own Base/Structure/Flooring/Lighting suggestions) offers a one-click \"Use recommendation\" fill on several tabs — use it as a starting point when you don't have a specific spec yet, then adjust.",
    example:
      "Worked example — Ujjain squash court (RK Bansal School, Dec 2022, a real project on record): flooring was 672 sqft of maple wood at Rs 380/sqft = Rs 2,55,360; the surrounding wall system was 1,200 sqft of hard plaster + paint at Rs 175/sqft = Rs 2,10,000; one soundboard accessory at Rs 17,000. GST at 18% (itemized separately, not folded into the rate) added Rs 86,825 — a stated grand total of Rs 5,69,185. This is exactly the shape a Cost Sheet's Flooring, Structure, and Accessories tabs would produce for a similar single-court squash project today.",
    watch:
      "\"Verify Cost Sheet\" is one-way from this screen — once verified, every take-off tab disappears and no more lines can be added, removed, or recomputed here. Rework happens back on the Documents screen (Reject → returns to Draft), not by re-opening this one. A Resurfacing/Repair project won't show Structures/Base/Drainage tabs at all — that's by design (B.1), not a missing feature.",
  },
  {
    screen: "Documents — Estimate, Quotation & Work Order",
    what: "Once the Cost Sheet is Verified (or an approved skip made it Unverified-but-usable), this screen carries the project through Estimate → Quotation → Won → Work Order.",
    fields: [
      "Estimate: Sport + Package (Budget/Standard/Premium) + a cost figure per option — one option per submit, several options can exist side by side for the client to compare.",
      "Quotation: pick the Estimate, an optional discount, and (Tender Mode only) whether GST is quoted exclusive or inclusive of the base price.",
    ],
    whenMissing:
      "If the Cost Sheet situation is genuinely too small to justify a full Estimate (a Resurfacing/Repair job under the Director's fast-track threshold), \"Fast-track\" skips straight from a Verified Cost Sheet to an auto-approved Estimate and Quotation in one step.",
    watch:
      "Release and Send are two separate, sequential steps — a Quotation can't jump straight from Draft to Sent. Won/Lost can only be marked from \"Sent,\" never from \"Released.\" If the underlying Cost Sheet changes after an Estimate or Quotation already exists, nothing updates automatically — the Estimate flags \"rebase required\" and you have to click Rebase yourself before releasing again. Revising a Sent Quotation can change its discount, GST basis, or pricing — it can't add or drop sports; that needs a new Quotation.",
  },
  {
    screen: "Pricing Calculator",
    what: "A standalone what-if margin/GST calculator, reachable by PM/Director from Daily Work (K.3 -- Sales never sees this screen, enforced both in the nav and server-side) — type a cost figure and a client type, see the target margin, selling price, and GST breakdown. Nothing here is saved, and it isn't linked to any real project, Cost Sheet, or Estimate.",
    fields: ["Cost incl. contingency (Rs)", "Client type", "Discount type (None/Percent/Amount) + value"],
    whenMissing: "There's nothing to fill beyond the cost figure and client type — everything else is optional.",
    watch: null,
  },
  {
    screen: "Reports",
    what: "Generate a computed, hash-verified snapshot report (Pipeline / Margin / Override Summary) over a period, then Release it once it's ready to stand as the official record for that range.",
    fields: [
      "Report type (Pipeline — all roles except site_engineer/procurement; Margin — PM/Director; Override Summary — Director only)",
      "Period — Today / This Week / This Month / This Year, or Custom with manual start/end dates",
    ],
    whenMissing: "There's nothing optional to skip here — type and period are both required to generate.",
    watch:
      "Re-running the same period creates a brand-new report rather than editing the old one — every generated report is a frozen, hash-verified snapshot of that moment, by design (T.2).",
  },
  {
    screen: "Clients",
    what: "Toggle two operational flags (Overdue, Blacklisted) and two consent flags (WhatsApp opt-in, Email opt-in) on an existing client. New clients are created inline from Project Setup, not here.",
    fields: ["Overdue (blocks new Quotation release)", "Blacklisted (blocks new Estimates)", "WhatsApp / Email consent"],
    whenMissing: "Nothing here is required — all four are simple on/off toggles.",
    watch:
      "Every toggle here saves instantly on click, with no confirmation step. Overdue and Blacklisted are Director-only (greyed out for other roles); WhatsApp/Email consent can be toggled by Sales, PM, or Director.",
  },
  {
    screen: "Master Settings",
    what: "Director-only. Company-wide constants (GST rate, validity periods, contingency %, fee schedules), company logo/profile, User Management, and the Role & Permissions viewer (Section 5).",
    fields: ["Varies by setting — each is a versioned value, editable only by the Director; PM can view but not edit."],
    whenMissing: "Every setting ships with a sensible default (see Q.1/Q.2) — nothing here blocks daily work if left untouched.",
    watch: "Editing a setting creates a new version effective from today — it never rewrites a document that already froze the old value.",
  },
  {
    screen: "Audit Log",
    what: "Director-only, genuinely enforced (unlike a couple of screens above). A read-only global change log — every waiver, approval, discount, release, and Master Setting edit, with old value → new value and the reason given.",
    fields: ["Document type filter (Estimate / Estimate option / Quotation / Skip request / Vendor price request / Site survey / Master Setting)"],
    whenMissing: "Filtering is by document type only — there's no date range or user filter; export the CSV and search it yourself for anything more specific.",
    watch: null,
  },
];

export const ESTIMATOR_GUIDE = {
  role: "Estimator Guide (Sales + PM)",
  intro:
    "The daily path, start to finish. This goes deeper than the Quick Start card's 5 steps — read that first if you haven't, then use this when you need the detail behind one of them.",
  sections: [
    {
      title: "1. Setup → Sport → Scope",
      body:
        "Quick mode is the default and covers most projects in 4 fields. Add every sport the project needs on Sport Selection, and only customize court size if this project's court is genuinely non-standard. Scope is a straight checklist — leave anything not applicable unchecked.",
    },
    {
      title: "2. Cost Sheet — what Sales actually sees",
      body:
        "Sales never sees real cost or margin figures (K.3) — this is enforced by the server, not just hidden in the browser. Instead of the full Cost Sheet Builder, Sales works in Rate-blind mode: propose a line (work package, category, item, unit, quantity) with no rate field at all — it isn't hidden, it's simply not there. A PM or Director later fills in the rate for each pending line you've proposed. If you need to attach a vendor's quote as reference, use the Attachments panel on the same screen.",
    },
    {
      title: "3. Estimate",
      body:
        "Once a PM/Director has verified the Cost Sheet and priced your proposed lines, you can create an Estimate option per sport/package combination, send it, and record the client's response (Approved, Rejected with a reason, or Demand Received). You'll see the client-facing price range, never the underlying cost.",
    },
    {
      title: "4. Quotation",
      body:
        "Once at least one option is client-approved, create the Quotation, then Release and Send it as two separate steps. Track it to Won or Lost from \"Sent\" — not from \"Released.\" A Won quotation hands off to a PM/Director for the Work Order stage.",
    },
    {
      title: "5. Rate Sheet — what to do when a rate is missing",
      body:
        "If the Rate Sheet has nothing for a material or item you need, there's no app-provided market rate yet. Flag it to a PM/Director rather than guessing on anything large — they can enter and confirm a real rate, or point you to the historical rate reference if one exists for that category.",
    },
  ],
};

export const DIRECTOR_ADMIN_GUIDE = {
  role: "Director / Admin Guide",
  intro: "The screens Sales/PM don't see at all, plus the PM/Director-only steps in the shared document flow.",
  sections: [
    {
      title: "Rate Sheet confirmation workflow",
      body:
        "Every new rate — whether typed in directly or bulk-imported from Excel — starts Manual and Unverified. Confirming it (one click, or bulk-mark) promotes it to an AI (master) rate; this is the only gate between \"someone typed a number\" and \"this is a rate the company trusts by default.\" A rate flagged commodity-watched will alert when it moves past the configured threshold since its last confirmation — review those promptly, since steel/turf price swings affect every open Cost Sheet using that item.",
    },
    {
      title: "Cost Sheet oversight",
      body:
        "PM/Director build and Verify Cost Sheets; Reject sends one back to Draft with a reason category and note. A below-floor margin on any pricing calculation needs Director approval (visible as an amber warning) before it can proceed.",
    },
    {
      title: "User Management",
      body:
        "Create users, assign roles, reset passwords, deactivate/reactivate accounts. Two guardrails are server-enforced and can't be worked around from the UI: you can't deactivate your own account, and you can't deactivate or demote the last active Director — both exist because User Management is itself Director-only, so hitting zero active Directors would need a raw database script to recover from.",
    },
    {
      title: "Role & Permissions viewer",
      body:
        "Master Settings → Role & Permissions shows exactly what each role can currently see/do, mirrored from the backend's real access checks. It's read-only by design — some rules (cost/margin visibility, Director-only release gates, the Director-count guardrail above) are deliberately not adjustable from any screen.",
    },
    {
      title: "Reports",
      body:
        "Pipeline is visible to Sales too (no cost data); Margin is PM/Director only; Override Summary (below-floor pricing overrides) is Director only, as is releasing any Draft report to make it the official record for that period.",
    },
    {
      title: "Master Settings",
      body:
        "Every company-wide constant (GST %, validity periods, contingency %, fee schedules) lives here, Director-editable only; PM has read access. Editing creates a new version effective today — it never rewrites a figure a document already froze.",
    },
    {
      title: "Audit Log",
      body:
        "The one screen genuinely enforced as Director-only end to end. Filter by document type and export CSV for anything needing a date range, user, or free-text search the built-in filter doesn't cover.",
    },
  ],
};

export const FAQ = [
  {
    q: "I forgot my password — what do I do?",
    a: "Ask a Director to reset it from Master Settings → User Management. You'll be forced to set your own password on next login.",
  },
  {
    q: "The Rate Sheet doesn't have the rate I need — what now?",
    a: "There's no app-provided market rate yet for that item. Enter one yourself if you have a defensible figure, and flag it to a PM/Director for confirmation before it's used on anything large — an unconfirmed rate never becomes a default.",
  },
  {
    q: "A Quotation option got rejected by the client — now what?",
    a: "Mark it Rejected with a reason (price/scope/timing/competitor/other). You can revise the Estimate with new pricing and send it again, or start a fresh Quotation once a different option is approved.",
  },
  {
    q: "How do I revise a Sent Estimate or Quotation?",
    a: "Use Revise (PM/Director) on the Documents screen. For an Estimate, edit each option's cost and choose whether to refresh pricing; unchanged options stay frozen. For a Quotation, you can change discount/GST/pricing — not which sports it covers, which needs a new Quotation entirely.",
  },
  {
    q: "Why can't I deactivate this Director account?",
    a: "The app blocks deactivating or demoting the last active Director, and blocks deactivating your own account — both by design, since User Management is Director-only and losing every active Director would be unrecoverable without a database script.",
  },
  {
    q: "What does \"below floor\" mean on a pricing calculation?",
    a: "The selling price implies a margin below the client type's minimum acceptable floor. It still goes through, but needs Director approval — shown as an amber warning wherever it appears.",
  },
  {
    q: "Why did my project's dimensions once show as \"NonexNone\"?",
    a: "A historical display bug in the Recent Activity feed when a dimension field was blank — fixed as part of Amendment 4; it now reads \"Not set.\"",
  },
  {
    q: "How do I create a new user?",
    a: "Master Settings → User Management (Director only). New accounts are forced to change their assigned password on first login.",
  },
  {
    q: "Can I reset someone else's password?",
    a: "Yes, from User Management (Director only) — it forces that user to set their own new password on next login, same as any newly created account.",
  },
  {
    q: "How do I print a Quotation for a client?",
    a: "Open the Quotation from Documents and use its PDF download — it never includes cost or margin figures, regardless of who downloads it.",
  },
  {
    q: "Why does the Cost Sheet Builder show fewer tabs for my project?",
    a: "Resurfacing/Repair projects hide Structures, Base, and Drainage tabs entirely — that's intentional, since those work packages don't apply to a resurfacing job.",
  },
  {
    q: "I verified a Cost Sheet by mistake — can I undo it?",
    a: "Not directly on that screen — Verify is one-way there. Use Reject (PM/Director) from the Documents screen to send it back to Draft with a reason, or Revise once verified to create a new revision.",
  },
  {
    q: "What's the difference between Release and Send on a Quotation?",
    a: "They're two separate, sequential steps — Release moves it out of Draft internally; Send is the actual client-facing dispatch. You can't skip from Draft straight to Sent.",
  },
  {
    q: "Why can't I mark a Quotation Won from \"Released\"?",
    a: "Won/Lost is only reachable from \"Sent\" — Release alone isn't considered dispatched to the client yet.",
  },
  {
    q: "The underlying Cost Sheet changed after I made an Estimate — did the Estimate update?",
    a: "No — nothing propagates automatically. The Estimate is flagged \"rebase required,\" and you need to click Rebase yourself before releasing or sending again.",
  },
  {
    q: "Can Sales see the real cost of a project?",
    a: "No — enforced server-side (K.3), not just hidden in the browser. Sales works in Rate-blind mode: proposing lines with quantities but no rate field at all.",
  },
  {
    q: "What does a commodity-watch alert mean on a rate item?",
    a: "That item's price (e.g. steel, turf) is flagged for tracking, and moved past the Director-configured alert threshold since it was last confirmed — worth reviewing before it's used on a new Cost Sheet line.",
  },
  {
    q: "Why is there no per-client project list on the Clients screen?",
    a: "There isn't one today, despite the register describing it as part of Amendment 4 — this remains a gap. Use the Dashboard's Recent Projects list or project search to find an existing project instead.",
  },
  {
    q: "Is the Pricing Calculator the same as a real Estimate?",
    a: "No — it's a standalone what-if sandbox. Nothing you type there is saved, linked to a real project, or fed into any Cost Sheet or Estimate.",
  },
  {
    q: "Who can see the Audit Log?",
    a: "Director only, and this one is genuinely enforced both in the nav and on the screen itself — unlike a couple of other screens whose own text claims a restriction the app doesn't yet enforce.",
  },
];
