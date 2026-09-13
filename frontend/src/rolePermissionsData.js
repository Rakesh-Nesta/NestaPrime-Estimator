// Amendment 6a (Option A, Director-approved 13 Sept 2026): a READ-ONLY mirror
// of the backend's actual role checks -- not an editable permissions engine.
// Every role set below is a hardcoded `require_roles(...)` call in
// backend/app/api/*.py (192 call sites across 41 files); nothing here is a
// database row, and nothing in this screen can change what the backend
// enforces. Keep this in sync by hand when a role check changes -- there is
// no live introspection wiring it to the backend.

export const ROLE_LABELS = {
  sales: "Sales",
  pm: "PM",
  director: "Director",
  procurement: "Procurement",
  site_engineer: "Site Engineer",
  ca_tax: "CA / Tax",
};

export const ALL_ROLES = Object.keys(ROLE_LABELS);

// Each feature area groups endpoints by the exact role-set that can reach
// them, so the same information reads as "who can do what" rather than one
// row per API call.
export const FEATURE_AREAS = [
  {
    area: "Projects & Clients",
    groups: [
      { roles: ["sales", "pm", "director"], items: ["Create project", "Create client", "Update client flags/consent", "Create/update client signatory"] },
      { roles: ["sales", "pm", "director", "procurement"], items: ["View client type defaults", "List/view clients", "List client signatories", "List regional multipliers"] },
      { roles: ["sales", "pm", "director", "procurement", "site_engineer"], items: ["View a project"] },
      { roles: ["director"], items: ["Deactivate/reactivate a client"] },
    ],
  },
  {
    area: "Sport & Scope Selection",
    groups: [
      { roles: ["sales", "pm", "director", "procurement", "site_engineer"], items: ["List sports catalog", "List a project's selected sports", "List/view scope items"] },
      { roles: ["sales", "pm", "director"], items: ["Add/remove a sport on a project", "Update a sport's build size", "Select/deselect scope items"] },
      { roles: ["site_engineer", "pm", "director"], items: ["Update a project sport's as-built dimensions"] },
      { roles: ["director"], items: ["Master Sport/Scope Item catalog (Sports & Scope Admin)", "Flooring guides, lighting standards, pole counts"] },
    ],
  },
  {
    area: "Site Surveys",
    groups: [{ roles: ["site_engineer", "pm", "director"], items: ["Create/view/update a site survey", "Mark a site survey complete"] }],
  },
  {
    area: "Cost Sheets, Estimates & Quotations",
    groups: [
      { roles: ["pm", "director"], items: ["Create/verify/reject/revise Cost Sheet", "Add/update/delete Cost Sheet lines", "Create Estimate", "Fast-track Estimate/Quotation", "Release Quotation"] },
      { roles: ["sales", "pm", "director"], items: ["View a Cost Sheet (Sales: cost fields stripped, K.3)", "Propose a pending line (Sales: no rate, K.3)"] },
      { roles: ["sales", "pm", "director"], items: ["Send Estimate", "Mark client status on an Estimate option", "Create/revise/send/reject Quotation", "Mark Quotation Won/Lost"] },
    ],
  },
  {
    area: "PDF & Attachments",
    groups: [
      { roles: ["sales", "pm", "director"], items: ["Download Estimate/Quotation PDF (never includes cost or margin, K.3)"] },
      { roles: ["sales", "pm", "director", "procurement", "site_engineer"], items: ["Upload/list/download attachments (vendor quotes, site-survey images)"] },
    ],
  },
  {
    area: "Messages & Templates",
    groups: [
      { roles: ["sales", "pm", "director"], items: ["Log an outbound message", "List messages/templates"] },
      { roles: ["director"], items: ["Create/update message templates"] },
    ],
  },
  {
    area: "Work Orders & Payments",
    groups: [{ roles: ["pm", "director"], items: ["Create work order from a Won quotation", "Update work order status", "Add/list payment entries"] }],
  },
  {
    area: "Skip-Stage Requests",
    groups: [
      { roles: ["sales", "pm", "director"], items: ["Create/list a skip-stage request"] },
      { roles: ["pm", "director"], items: ["Approve a skip-stage request (\"Sales cannot skip alone\", M.2 rule 3)"] },
    ],
  },
  {
    area: "Costing / Takeoff screens",
    groups: [
      {
        roles: ["pm", "director"],
        items: [
          "Every takeoff type (Athletics, Flooring, Gym, HVAC, Lighting, Play Equipment, Pool, Site Works, Structures, Accessories, Overheads) -- all K.3-gated identically",
        ],
      },
      { roles: ["sales", "pm", "director", "procurement", "site_engineer"], items: ["List accessory catalog items"] },
      { roles: ["pm", "director", "procurement", "site_engineer"], items: ["List vehicle classes, netting grades catalog"] },
      { roles: ["director"], items: ["Create/update accessory catalog, vehicle classes, netting grades"] },
    ],
  },
  {
    area: "Rate Sheet",
    groups: [
      { roles: ["pm", "director", "procurement", "site_engineer"], items: ["List rate items, rate history", "Export rate items to Excel"] },
      { roles: ["pm", "director", "procurement"], items: ["Create/update rate item", "Update a rate's value", "Bulk-update rates", "Import rate items from Excel"] },
      { roles: ["pm", "director"], items: ["Confirm a rate item (Manual → AI)", "Bulk-mark rate items"] },
    ],
  },
  {
    area: "Vendors, Price Requests & Purchase Orders",
    groups: [{ roles: ["pm", "director", "procurement"], items: ["Create/list/update vendor", "Create/manage price requests (RFQ)", "Create/issue/receive Purchase Orders"] }],
  },
  {
    area: "Exports",
    groups: [
      { roles: ["pm", "director"], items: ["Export Cost Sheet (full cost/labour/overhead figures — internal only)"] },
      { roles: ["pm", "director", "procurement"], items: ["Export Consumption Sheet, RFQ, BOM (item/qty/rate only, no cost/margin)"] },
      { roles: ["sales", "pm", "director"], items: ["Export Billing Handoff (no cost/margin content by construction)"] },
    ],
  },
  {
    area: "Pricing & Margin Policies",
    groups: [
      { roles: ["pm", "director"], items: ["List margin policies", "Run a pricing quote calculation"] },
      { roles: ["director"], items: ["Set a sport-type margin floor override"] },
    ],
  },
  {
    area: "Tender Mode",
    groups: [
      { roles: ["pm", "director"], items: ["Tender details, competitor bids, technical bid checklist", "BG-cost / net-receivable calculators"] },
      { roles: ["sales", "pm", "director"], items: ["View \"L1\" lowest-bidder ranking (margin % stripped for Sales, K.3)"] },
    ],
  },
  {
    area: "Reports",
    groups: [
      { roles: ["sales", "pm", "director"], items: ["Generate/view Pipeline report (no cost data)"] },
      { roles: ["pm", "director"], items: ["Generate/view Margin report (K.3-restricted)"] },
      { roles: ["director"], items: ["Generate/view Override Summary report", "Release a Draft report"] },
    ],
  },
  {
    area: "Dashboard",
    groups: [
      { roles: ["sales", "pm", "director", "procurement", "site_engineer", "ca_tax"], items: ["View dashboard summary"] },
      { roles: ["director"], items: ["See the Recent Activity feed (same response, hidden for every other role)"] },
    ],
  },
  {
    area: "User Management, Master Settings & Audit Log (Admin)",
    groups: [
      { roles: ["director"], items: ["Create/update users, reset passwords", "Master Settings (rates policy, GST%, fee schedules, company profile)", "Below-floor overrides", "Hubs, package contents", "Audit log (view + export)"] },
      { roles: ["pm", "director"], items: ["View current settings and their history (read-only for PM)"] },
    ],
  },
];

// Rules that stay hardcoded no matter what -- the whole reason 6a shipped as
// a read-only viewer (Option A) rather than an editable permissions engine.
export const SAFETY_CRITICAL_RULES = [
  {
    name: "K.3 — Cost & margin hidden from Sales",
    detail:
      "\"Cost, contingency, markup and margin are never visible to Sales or Procurement — enforced at the API, not just hidden in the browser.\" Sales sees a Rate-blind Cost Sheet with cost fields stripped, never the real figure. Procurement sees item/qty/rate on exports, never an aggregate cost or margin.",
  },
  {
    name: "M.2 — Director-only quotation lifecycle gates",
    detail:
      "An Estimate can't be created until its Cost Sheet is Verified. Sales can request a stage skip but can't approve one alone (rule 3). Editing a Verified/Sent document creates a new revision and blocks re-release until rebased (rule 4). Rejecting a client status requires a reason (rule 9).",
  },
  {
    name: "Director-count guardrail",
    detail:
      "A Director can't deactivate their own account, and can't deactivate or demote the last active Director — User Management is itself Director-only, so hitting zero active Directors would make the app unrecoverable without a raw database script.",
  },
];

// Worth surfacing rather than hiding: ca_tax currently has no feature-level
// access anywhere except the shared Dashboard summary endpoint (plus the
// universal /auth/me and /auth/change-password). Confirm this is
// intentional (a minimal, still-being-built-out role) rather than an
// oversight -- it doesn't appear in any other module's role list at all.
export const CA_TAX_NOTE =
  "The CA / Tax role currently has access to the Dashboard summary only — it appears nowhere else in the backend's role checks. Confirm this is intentional (a role still being built out) rather than an oversight.";
