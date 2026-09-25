// Amendment 10 (Annexure 2), Section 5 scope: the Full Handbook, per-role
// guides, and FAQ (items 2-4 of Amendment 10's own Contents list). Content
// here is drawn from the app's own real screen graph and behavior (verified
// against the actual frontend/backend code, not guessed) -- where the
// registered spec named a worked example that doesn't exist in the real
// project data reviewed for Note R1 ("the Ujjain Pickleball job"), the
// real Ujjain job on record (a squash court, RK Bansal School, Dec 2022) is
// used instead, per Director decision (13 Sept 2026).
//
// v3 (Section 13, 16 Sept 2026, Director-approved): closes the gap Annexure-2
// v1.11's register reconciliation found -- this file hadn't been touched
// since v2 (13 Sept) despite Amendments 11-13 shipping seven new/updated
// screens since. Added: All Projects, All Estimates, All Quotations, Vendors
// Admin, Price Requests, Cross-Sell Admin, Sports & Scope Admin; updated the
// now-stale Documents (AI cover note, Messages) and Reports (AI summary,
// Excel/PDF export) entries; wove in the register's own named Hindi terms
// (labour/mazdoori, material/saaman, dhanda) into the Quick Start and
// Estimator Guide. Messages Panel and Purchase Orders are documented as
// sub-bullets on their parent screen rather than standalone entries, since
// neither is independently nav-reachable (Director decision, Section 13).
//
// 18 Sept 2026: Master Settings entry updated for Section 14 (Company
// details panel, Quotation terms & warranty editor) -- caught during a
// session review of what was left open, same discipline v3 itself exists
// to enforce; not treated as a new full version bump since it's a single
// entry's content, not a new wave of screens.
//
// v4 (Section 20, 18 Sept 2026, Director-approved): closes the gap
// Annexure-2's Amendment 10 continuation found -- Education (Amendment
// 15's Chat assistant, Amendment 16's Sport Build Guide and Section 18's
// Construction Sequence) had never been documented, and three passages
// were describing pre-fix behavior: Documents claimed email "delivers
// nothing" (superseded by Section 17's real SMTP sending), and both the
// Clients chapter and FAQ Q18 still described the per-client project
// list as missing (superseded by Section 19). Added the Education
// chapter, fixed all three stale passages, and folded in two small
// related items (Sports & Scope Admin's field list now names the
// Construction Sequence tab; this file's own version label in Help.jsx
// updated 3->4). Simple Calculator, Tender Mode, and Amendment 11/14's
// smaller content gaps were explicitly scoped out of this pass (Director
// decision, Section 20) -- not forgotten, on record as still open.

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
    screen: "Vendors Admin",
    what: "Vendor master list (PM/Director/procurement) with each vendor's nested product catalog underneath it — approximate pricing for planning, not a locked quote.",
    fields: [
      "Vendor — name (required), vendor code, city, category, contact name/phone/email, GSTIN, payment terms",
      "Product (per vendor) — name (required), spec, unit, approx price (Rs), category",
    ],
    whenMissing:
      "Only a vendor's name and a product's name are required — everything else, including vendor code, can be filled in later (vendor code is editable inline right on the list after creation).",
    watch:
      "These product prices are explicitly approximate planning figures, not a vendor-confirmed quote — for a real, current rate, use Price Requests instead. There's no delete for a vendor itself, only for individual products under it.",
  },
  {
    screen: "Price Requests",
    what: "Ask vendors for a current price on specific Rate Sheet items (over WhatsApp/Email), log what they actually replied, then apply that reply to the master Rate Sheet or a specific Cost Sheet line.",
    fields: [
      "Request — one or more Rate Sheet items, one or more vendors, channel(s) (WhatsApp/Email), required-by date, requested validity (days)",
      "Reply (per vendor, per item) — the vendor's raw reply text (required); rate, unit, GST basis, and validity are all auto-proposed from that text and overridable",
    ],
    whenMissing:
      "Everything except the raw reply text is optional and auto-parsed from what the vendor actually wrote — typing \"Rs 68/kg ex-GST, valid 15 days\" as the raw reply is often enough on its own.",
    watch:
      "No real WhatsApp/email provider sends these requests — both the send and the reply are manually recorded, not automated. \"Use for master rate\" creates the item exactly like typing a new Rate Sheet entry by hand — Manual and Unverified — a PM/Director still has to confirm it separately before it becomes a trusted default. \"Use for this line\" needs the target Cost Sheet line's ID typed into a plain text box, not picked from a list — easy to mistype.",
  },
  {
    screen: "Cost Sheet Builder",
    what: "Build the real, internal cost of the project — one tab per work package (Structures, Base, Flooring, Lighting, HVAC, Pool, and 13 more), each with its own take-off calculator. PM/Director only see real rates here; Sales works in a separate Rate-blind mode (see the Estimator Guide).",
    fields: [
      "Each tab needs the relevant Project Sport plus that package's own inputs — e.g. Structures needs Type, section, wall thickness, build L/W/height, foundation depth and either a netting grade or a manual rate; Flooring (acrylic) needs surface type, coats and rate/sqft/coat; Lighting needs target lux, fixture wattage/count and cable/panel rates.",
      "\"Manual line\" — for anything with no dedicated calculator: work package, category, item, unit, quantity, rate, optional labour category.",
      "Purchase Orders (PM/Director/procurement) — a panel on this same screen to raise a PO against consumption lines: vendor, one or more lines with quantity/rate (pre-filled from the line, overridable), optional delivery date and e-way bill number; goods receipt is recorded per line afterwards.",
    ],
    whenMissing:
      "A green recommendation banner (drawn from Sport Selection's own Base/Structure/Flooring/Lighting suggestions) offers a one-click \"Use recommendation\" fill on several tabs — use it as a starting point when you don't have a specific spec yet, then adjust.",
    example:
      "Worked example — Ujjain squash court (RK Bansal School, Dec 2022, a real project on record): flooring was 672 sqft of maple wood at Rs 380/sqft = Rs 2,55,360; the surrounding wall system was 1,200 sqft of hard plaster + paint at Rs 175/sqft = Rs 2,10,000; one soundboard accessory at Rs 17,000. GST at 18% (itemized separately, not folded into the rate) added Rs 86,825 — a stated grand total of Rs 5,69,185. This is exactly the shape a Cost Sheet's Flooring, Structure, and Accessories tabs would produce for a similar single-court squash project today.",
    watch:
      "\"Verify Cost Sheet\" is one-way from this screen — once verified, every take-off tab disappears and no more lines can be added, removed, or recomputed here. Rework happens back on the Documents screen (Reject → returns to Draft), not by re-opening this one. A Resurfacing/Repair project won't show Structures/Base/Drainage tabs at all — that's by design (B.1), not a missing feature. On Purchase Orders: a Cost Sheet line can only be on one open PO at a time; \"Issue\" only works from Draft and can't be undone; a PO can still be cancelled even after it's partially received, which drops the remaining un-received balance — it's blocked only once fully Received.",
  },
  {
    screen: "Documents — Estimate, Quotation & Work Order",
    what: "Once the Cost Sheet is Verified (or an approved skip made it Unverified-but-usable), this screen carries the project through Estimate → Quotation → Won → Work Order.",
    fields: [
      "Estimate: Sport + Package (Budget/Standard/Premium) + a cost figure per option — one option per submit, several options can exist side by side for the client to compare.",
      "Quotation: pick the Estimate, an optional discount, and (Tender Mode only) whether GST is quoted exclusive or inclusive of the base price.",
      "Cover Note (Quotation) — \"Draft with AI\" proposes two short paragraphs written only from what is set for the quotation (client, site, sports, package content, timeline); a human always reviews and explicitly saves it. Once saved, and until the quotation is sent, the Quotation PDF opens as a letter: Kind attention (the client's active signatory, else the contact name), a subject line, your note, and a sign-off with the authorised signatory from Master Settings. The Scope of work (package content and what is included, with no prices) also prints on a quotation not yet sent. A quiet \"The PDF will leave out:\" list under the note says what is missing.",
      "Messages (on Cost Sheet/Estimate/Quotation rows) — a panel to send or log outbound communication about that document: channel (Email/WhatsApp/Telegram), template, recipient (required), subject, message text, and a \"Draft with AI\" button that proposes the message text for you to review before sending.",
    ],
    whenMissing:
      "If the Cost Sheet situation is genuinely too small to justify a full Estimate (a Resurfacing/Repair job under the Director's fast-track threshold), \"Fast-track\" skips straight from a Verified Cost Sheet to an auto-approved Estimate and Quotation in one step.",
    watch:
      "Release and Send are two separate, sequential steps — a Quotation can't jump straight from Draft to Sent. Won/Lost can only be marked from \"Sent,\" never from \"Released.\" If the underlying Cost Sheet changes after an Estimate or Quotation already exists, nothing updates automatically — the Estimate flags \"rebase required\" and you have to click Rebase yourself before releasing again. Revising a Sent Quotation can change its discount, GST basis, or pricing — it can't add or drop sports; that needs a new Quotation. On Messages: WhatsApp, Telegram, and Email (Section 17) are all real sends now — a failure shows as a clear Failed status immediately, never a false success. None of the three can confirm actual delivery, only that the provider accepted the send, so \"Delivered\" stays unused by design. A send can still fail even after you fill and submit the form, if the client hasn't opted in to that channel (see Clients) or a WhatsApp template isn't yet Meta-approved.",
  },
  {
    screen: "All Projects",
    what: "Cross-project browse list — every project in the system, filterable by Open/Won/Lost, with a search box for project number or client name.",
    fields: ["Status filter (All/Open/Won/Lost)", "Search (project number or client name)"],
    whenMissing:
      "Nothing to fill in — this is a read-only browse/filter screen. It's also reachable pre-filtered: clicking a Dashboard tile like \"Open Projects\" opens this screen already set to that status.",
    watch:
      "A project's Won/Lost status here is computed live from its Quotations, not stored on the project itself — it changes automatically the moment a Quotation's own status changes, with nothing to update by hand.",
  },
  {
    screen: "All Estimates",
    what: "Cross-project Estimate list, filterable by status (Draft/Sent/Won/Lost/Expired/Superseded) — the Estimates tab of the Quotations screen, the same shape as All Projects.",
    fields: ["Status filter", "Search (project number or client name)"],
    whenMissing: "Nothing required — read-only browse/filter, same as All Projects.",
    watch:
      "Open to every role that can see Estimates at all (Sales through site_engineer), not Director-only — an Estimate only ever shows the client-facing price range, never the underlying cost, so it doesn't need the stricter cost/margin rules the Quotations list applies (cost and margin shown to PM and Director only).",
  },
  {
    screen: "Quotations",
    what: "The cross-project Quotation list, opened from the Quotations header by Sales, PM and Director — every Quotation across every project, with a per-row PDF download and, for the Director only, a CSV export. The Estimates list is its second tab. This is Amendment 6b's \"review all quotations\" screen, opened to Sales and PM by Amendment 49.",
    fields: [
      "Status filter, or the quicker All / Pending / Old group pills (Pending = draft+released+sent; Old = every finished status) — picking an exact status overrides the group pill",
      "Date from / Date to — filters on when the Quotation was created, not when it was released or sent",
      "Search (project number or client name)",
      "Export CSV — same filters, downloads the full filtered list as a spreadsheet",
    ],
    whenMissing: "All filters are optional and combine together — leave everything blank to see every Quotation.",
    watch:
      "Cost and margin, including the red \"(below floor)\" flag, are shown to PM and Director only — Sales sees the client-facing totals with those figures left out, the same rule as the single-project Documents screen. Export CSV is Director-only. The date filter is on creation date, not the date it was actually released or sent.",
  },
  {
    screen: "Cross-Sell Admin",
    what: "Catalog management for the \"Complete Your Facility\" add-ons suggested at the Estimate step (lighting, fencing, seating, AMC, other) — separate from the suggestion picker itself, which lives on the Documents screen.",
    fields: [
      "Name (required), category, description, unit, cost (Rs), margin %",
      "\"Suggest for all sports\" checkbox, or specific sport tags if left unchecked",
      "Active/Inactive toggle, per add-on",
    ],
    whenMissing:
      "Only name and category are required to save a draft add-on — but cost and margin must both be filled in before it can be switched Active; the Activate control stays disabled with a tooltip until both are set.",
    watch:
      "Creating or editing is Director-only (PM can view the catalog read-only). Deactivating an add-on never deletes it — it just stops appearing as a live suggestion at the Estimate step.",
  },
  {
    screen: "Pricing Calculator",
    what: "A standalone what-if margin/GST calculator, reachable by PM/Director from More > Tools & reports (K.3 -- Sales never sees this screen, enforced both in the nav and server-side) — type a cost figure and a client type, see the target margin, selling price, and GST breakdown. Nothing here is saved, and it isn't linked to any real project, Cost Sheet, or Estimate. (For quick arithmetic that doesn't need margin/GST logic at all, a plain +/-/×/÷/% calculator lives under More > Tools & reports instead, open to every role.)",
    fields: ["Cost incl. contingency (Rs)", "Client type", "Discount type (None/Percent/Amount) + value"],
    whenMissing: "There's nothing to fill beyond the cost figure and client type — everything else is optional.",
    watch: null,
  },
  {
    screen: "Reports",
    what: "Generate a computed, hash-verified snapshot report (Pipeline / Margin / Override Summary) over a period, then Release it once it's ready to stand as the official record for that range. Open it from More > Tools & reports (Sales, PM and Director) or the Overview shortcut.",
    fields: [
      "Report type (Pipeline — Sales, PM and Director; Margin — PM/Director; Override Summary — Director only). The screen tells you which types your role can generate.",
      "Period — Today / This Week / This Month / This Year, or Custom with manual start/end dates",
      "Generate/Regenerate summary — a \"Draft with AI\" style button that writes a narrative paragraph over the report's own already-computed content; never persisted, regenerate any time",
      "Download Excel / Download PDF — the report's real, shareable form; there's no on-screen raw data view any more",
    ],
    whenMissing: "There's nothing optional to skip here — type and period are both required to generate.",
    watch:
      "Re-running the same period creates a brand-new report rather than editing the old one — every generated report is a frozen, hash-verified snapshot of that moment, by design (T.2). The AI summary is generated fresh each time you click it and isn't saved anywhere — if you need it again later, regenerate it.",
  },
  {
    screen: "Clients",
    what: "Toggle two operational flags (Overdue, Blacklisted) and two consent flags (WhatsApp opt-in, Email opt-in) on an existing client, and (Section 19) see that client's own projects without leaving the screen. New clients are created inline from Project Setup, not here.",
    fields: [
      "Overdue (blocks new Quotation release)", "Blacklisted (blocks new Estimates)", "WhatsApp / Email consent",
      "\"▸ Projects\" (Section 19) — collapsed by default per client; expanding it lists exactly that client's own projects with status and an \"Open →\" link, the same row shape as All Projects",
    ],
    whenMissing: "Nothing here is required — all four flags are simple on/off toggles, and \"Projects\" stays collapsed until you click it.",
    watch:
      "Every toggle here saves instantly on click, with no confirmation step. Overdue and Blacklisted are Director-only (greyed out for other roles); WhatsApp/Email consent can be toggled by Sales, PM, or Director. A client with no projects yet shows \"No projects yet\" when expanded, not an empty list with no explanation.",
  },
  {
    screen: "Quick search",
    what: "One search box for finding a record fast, from anywhere in the app: press / or Ctrl+K (Cmd+K on a Mac), tap Search at the top of the sidebar, or tap the magnifier at the top of the phone screen. It finds clients, leads, projects and quotations, and shows only the kinds your role can already open.",
    fields: [
      "What it searches — clients by name, contact name, phone, email or city; leads by name, phone or email; projects by project number, client name or city; quotations by document number, project number or client name",
      "Phone numbers — type the digits with any spacing (98765 43210 finds +91-98765-43210)",
      "Results — grouped by kind, up to six per group with the true total shown; use the arrow keys and Enter, or tap a row",
    ],
    whenMissing: "Type at least two characters. If nothing matches it says so; if the search itself fails it shows an error and a Try again button, never an empty list.",
    watch:
      "A project or quotation opens that project. A client or lead opens Leads & Clients with the name already in its search box, so the record is the first row. Results never show prices, costs or margins. Procurement sees clients, leads and projects (no quotations); Site Engineer and CA/Tax see projects only.",
  },
  {
    screen: "Master Settings",
    what: "Company-wide constants (GST rate, validity periods, contingency %, fee schedules), company logo/profile, quotation terms and message templates. The Director edits them; the PM can view them but not change them. (User management and the role view now live under Team & Access.)",
    fields: [
      "Varies by setting — each is a versioned value, editable only by the Director; PM can view but not edit.",
      "Company details (Section 14) — a labeled panel for the company identity/bank fields (legal name, PAN, GSTIN, registered office city, bank details) that print on the Quotation PDF — the same underlying Settings the raw key/value form below always could edit, just with real labels now. It also holds the authorised signatory's name and designation, which sign off the cover letter.",
      "Quotation terms & warranty (Section 14) — the Quotation PDF's own T&C clauses and warranty table, editable as plain text; \"Preview\" renders the draft against a real Quotation before you save, so a wording mistake is caught before it's live on every future Quotation.",
    ],
    whenMissing: "Every setting ships with a sensible default (see Q.1/Q.2) — nothing here blocks daily work if left untouched. The T&C/warranty editor is seeded with today's actual PDF wording, so leaving it alone changes nothing.",
    watch: "Editing a setting creates a new version effective from today — it never rewrites a document that already froze the old value. Always use Preview before saving a T&C/warranty change — there's no undo beyond editing it again.",
  },
  {
    screen: "Sports & Scope Admin",
    what: "Director-only master-data configuration for the catalogs everything else in the app draws from — Sports, Scope items, margin-floor overrides, package contents, hubs, accessory catalog, netting grades, vehicle classes, flooring guides, and lighting standards, each its own tab.",
    fields: [
      "Sports — key (required, permanent once set), name, category, playing/build dimensions, min clear height, governing body, active/inactive",
      "Scope items — key (required, permanent once set), group, name",
      "Margin floor overrides — per-sport floor % that replaces the client-type default when set (e.g. Pool 15%, PEB 14%)",
      "Package contents — per sport × tier (Budget/Standard/Premium): flooring/structure/lighting text, scope bullets, warranty years",
      "Construction sequence (Section 18) — six fixed phases per sport (site prep, sub-base, flooring, structure/fixtures, lighting, accessories/finishing); \"Draft with AI\" proposes text from that sport's own real data, a human always reviews and explicitly saves it, same as a Cover Note draft never auto-publishing",
    ],
    whenMissing:
      "Most descriptive fields are optional — only a Sport or Scope item's key is required, and it's worth getting right the first time: it can't be changed once created.",
    watch:
      "\"Deactivate\" everywhere on this screen is a soft toggle, not a delete — it retires an item without breaking any existing project that already references it. A brand-new sport gets no Base/Structure/Flooring/Lighting recommendation on the Cost Sheet until someone separately extends the recommendation tables for its key — adding the sport here alone isn't enough to make the one-click \"Use recommendation\" fill work for it elsewhere in the app.",
  },
  {
    screen: "Audit Log",
    what: "Director-only, genuinely enforced (unlike a couple of screens above). A read-only global change log — every waiver, approval, discount, release, and Master Setting edit, with old value → new value and the reason given.",
    fields: ["Document type filter (Estimate / Estimate option / Quotation / Skip request / Vendor price request / Site survey / Master Setting)"],
    whenMissing: "Filtering is by document type only — there's no date range or user filter; export the CSV and search it yourself for anything more specific.",
    watch: null,
  },
  {
    screen: "Education",
    what: "Two tabs, open to every role including ca_tax (unlike Sports & Scope Admin, whose own catalog data feeds the second tab here): Chat, a Q&A assistant grounded only in this handbook (Amendment 15); and Build Guide, a structured per-sport reference assembled from the same real data Sports & Scope Admin manages (Amendment 16).",
    fields: [
      "Chat — ask anything about how to use the app; answers come only from this handbook's own content, never live project/client/pricing data",
      "Build Guide — pick a sport (Indoor/Outdoor shown as separate entries where a sport has both) to see its dimensions, accessory list, flooring recommendation, and package-tier structure/lighting/scope, exactly as Sports & Scope Admin has them set",
      "Build Guide's Construction Sequence section (Section 18) — six fixed phases (site prep, sub-base, flooring, structure/fixtures, lighting, accessories/finishing) with a standing disclaimer, shown only for a sport a Director has actually authored one for",
    ],
    whenMissing:
      "A sport with no flooring guide, no package content, or no construction sequence saved simply shows nothing for that section — never an invented answer or a placeholder implying content exists when it doesn't.",
    watch:
      "Chat will say \"I don't know\" rather than guess when the handbook doesn't cover something — that's by design, not a bug. Selecting a sport in Build Guide also feeds Chat's own grounding, so a freeform question about that sport and the structured screen never disagree. The Construction Sequence disclaimer (\"confirm against site conditions with a qualified site engineer before execution\") is real — it's general guidance, not a site-specific method statement, even when it reads as specific to your sport.",
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
        "Sales never sees real cost or margin figures (K.3) — this is enforced by the server, not just hidden in the browser. Instead of the full Cost Sheet Builder, Sales works in Rate-blind mode: propose a line (work package, category, item, unit, quantity) with no rate field at all — it isn't hidden, it's simply not there. A PM or Director later fills in the rate for each pending line you've proposed (that rate, and the labour/mazdoori split behind it, is exactly what Rate-blind mode keeps out of Sales' view). If you need to attach a vendor's quote as reference, use the Attachments panel on the same screen.",
    },
    {
      title: "3. Estimate",
      body:
        "Once a PM/Director has verified the Cost Sheet and priced your proposed lines, you can create an Estimate option per sport/package combination, send it, and record the client's response (Approved, Rejected with a reason, or Demand Received). You'll see the client-facing price range, never the underlying cost.",
    },
    {
      title: "4. Quotation",
      body:
        "Once at least one option is client-approved, create the Quotation, then Release and Send it as two separate steps. Track it to Won or Lost from \"Sent\" — not from \"Released.\" A Won quotation hands off to a PM/Director for the Work Order stage. A Quotation can also carry an AI-drafted Cover Note — you always review and save it yourself before it appears on the client's PDF, it's never sent on its own.",
    },
    {
      title: "5. Rate Sheet — what to do when a rate is missing",
      body:
        "If the Rate Sheet has nothing for a material (saaman) or item you need, there's no app-provided market rate yet. Flag it to a PM/Director rather than guessing on anything large — they can enter and confirm a real rate, or point you to the historical rate reference if one exists for that category.",
    },
    {
      title: "6. Messages — talking to the client from inside the app",
      body:
        "From any Cost Sheet, Estimate, or Quotation row, open Messages to send or log a note to the client over Email, WhatsApp, or Telegram. \"Draft with AI\" proposes the message text for you to read and edit before it goes — nothing is ever sent without you clicking Send yourself. A send can fail even after you submit the form if the client hasn't opted in to that channel (check Clients) — that's not a bug, it's the consent flag doing its job.",
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
      title: "Team & Access — People",
      body:
        "Create users, assign roles, reset passwords, deactivate/reactivate accounts. Two guardrails are server-enforced and can't be worked around from the UI: you can't deactivate your own account, and you can't deactivate or demote the last active Director — both exist because Team & Access is itself Director-only, so hitting zero active Directors would need a raw database script to recover from.",
    },
    {
      title: "Team & Access — Roles & permissions",
      body:
        "Team & Access → Roles & permissions shows exactly what each role can do, read live from the access checks the server enforces, so it cannot fall out of date. It's read-only by design — some rules (cost/margin visibility, Director-only release gates, the Director-count guardrail above) are deliberately not adjustable from any screen.",
    },
    {
      title: "All Quotations — reviewing every quotation, not just one project's",
      body:
        "The cross-project register (Amendment 6b): filter by status or the quicker All/Pending/Old pills, plus a date range on when each Quotation was created. This is the one cross-project list that shows real cost and margin figures, including a below-floor flag — Export CSV for anything you want to review or hand off outside the app.",
    },
    {
      title: "Vendors Admin & Price Requests — the procurement bridge",
      body:
        "Vendors Admin holds the vendor master and each vendor's approximate product pricing (planning-only, not a locked quote). Price Requests is where you actually go for a current, vendor-confirmed rate — request over WhatsApp/Email, log the vendor's raw reply, and apply it either to the master Rate Sheet (as a new Manual/Unverified item you still have to confirm) or straight onto a specific Cost Sheet line.",
    },
    {
      title: "Sports & Scope Admin",
      body:
        "The master-data catalogs everything else in the app draws from — Sports, Scope items, margin-floor overrides, package contents, hubs, accessory catalog, netting grades, vehicle classes, and more, each its own tab. A Sport or Scope item's key is permanent once set, so double-check it before saving. \"Deactivate\" is always a soft toggle, never a delete.",
    },
    {
      title: "Reports",
      body:
        "Pipeline is visible to Sales too (no cost data); Margin is PM/Director only; Override Summary (below-floor pricing overrides) is Director only, as is releasing any Draft report to make it the official record for that period. Every report can generate an AI summary and export to Excel or PDF for sharing outside the app — nothing is shown as raw on-screen data any more.",
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
    a: "Ask a Director to reset it from Team & Access → People. You'll be forced to set your own password on next login.",
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
    a: "The app blocks deactivating or demoting the last active Director, and blocks deactivating your own account — both by design, since Team & Access is Director-only and losing every active Director would be unrecoverable without a database script.",
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
    a: "Team & Access → People (Director only). New accounts are forced to change their assigned password on first login.",
  },
  {
    q: "Can I reset someone else's password?",
    a: "Yes, from Team & Access → People (Director only) — it forces that user to set their own new password on next login, same as any newly created account.",
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
    q: "How do I see a client's own projects?",
    a: "On the Clients screen, expand \"▸ Projects\" under that client (Section 19) — no need to go to Dashboard or search by name. The Dashboard's Recent Projects list and Projects → All Projects search still work too, for browsing across every client at once.",
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
