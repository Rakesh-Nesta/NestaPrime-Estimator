// Amendment 51 (Section 55): who is shown which screen -- one table, used by both
// the sidebar/More menu (what to list) and App.jsx (what to render), so the two
// cannot disagree. The rule is Amendment 46's: show a link only to a role the API
// lets use it. The API stays the authority; this only follows it, and each row
// names the endpoints it was derived from so it can be re-checked against the
// Director's Roles & permissions screen (GET /role-permissions).
//
// A screen that is not listed here is open to every role (or gated where it is
// rendered, for the older screens Amendment 51 did not touch).
export const SCREEN_ROLES = {
  // GET /vendors
  vendors_admin: ["pm", "director", "procurement"],
  // POST /pricing/quote
  pricing: ["pm", "director"],
  // GET /rate-items, /labour-categories (site_engineer reads the rate sheet; the
  // vendor picker is procurement-only, so RateSheet skips /vendors for them)
  rates: ["pm", "director", "procurement", "site_engineer"],
  // GET /price-requests
  price_requests: ["pm", "director", "procurement"],
  // GET /reports (Reports has no CA/Tax, Procurement or Site Engineer variant)
  reports: ["sales", "pm", "director"],
  // /sports, /scope-items, /margin-policies, /hubs ... admin tabs
  sports_scope_admin: ["pm", "director"],
  // GET /settings (PM reads; only the Director writes). Amendment 59: an Admin reads and changes the company-
  // identity settings, templates and field settings only -- the screen shows just those for that role.
  settings: ["pm", "director", "admin"],
  // GET /users (Admin, Director, PM), GET /role-permissions (Admin, Director). A PM gets the People tab only.
  team_access: ["admin", "director", "pm"],
  // GET /audit-log (Admin sees who and when with cost/margin values hidden; the Director sees everything)
  audit_log: ["director", "admin"],
  // Amendment 59: a pure calculator, but not an Admin's business -- listed so the open-by-default rule below
  // does not hand it to the seventh role.
  calculator: ["sales", "pm", "director", "procurement", "site_engineer", "ca_tax"],
  // WP8 (correction plan): GET /notifications is scoped to the caller's own inbox, so every
  // role that exists gets it -- listed anyway so this open-to-all decision is explicit, not
  // just the default falling through.
  notifications: ["sales", "pm", "director", "procurement", "site_engineer", "ca_tax", "admin", "marketing"],
  // P3 contract, Section 8: GET /marketplace-imports/* -- matches the ledger's own read-access
  // gate exactly (PM/Director only).
  marketplace_imports_ops: ["pm", "director"],
  // P3 contract, Section 9: GET /marketplace-imports/marketing/dashboard -- Marketing is added
  // to this one screen's gate and nowhere else; PM/Director can also see their own aggregates.
  marketing_dashboard: ["pm", "director", "marketing"],
  // P3 correction (2026-09-30): the Sidebar's "Delivery" group used to show Projects to every
  // non-Admin role unconditionally, which silently included Marketing too once that role
  // existed -- the same "open by default" hazard the calculator comment above already names,
  // just not caught for this screen until Marketing could actually click through and get a
  // real 403 (LIST_ROLES, GET /projects, app/api/projects.py) -- confirmed directly against the
  // live backend, not inferred, before this fix. Matches LIST_ROLES exactly.
  projects_admin: ["sales", "pm", "director", "procurement", "site_engineer", "ca_tax"],
  // P4 contract v7, Section 3/7: stage evidence follows the same gate as its own backend
  // STAGE_ROLES (attachments.py) -- upload/view/submit is site_engineer/pm/director; review
  // itself is further narrowed to pm/director inside the screen and re-enforced by the backend.
  stage_evidence: ["site_engineer", "pm", "director"],
  // P5: the Execution tab -- agreement, readiness, team, milestones/tasks, site issues. Sales is
  // read-only; procurement/site_engineer only get data for projects they are on the team of
  // (the screen shows a friendly empty state on the backend's 403). Admin/marketing/ca_tax: no tab.
  execution: ["sales", "pm", "director", "procurement", "site_engineer"],
};

export function canOpen(screen, role) {
  const roles = SCREEN_ROLES[screen];
  return !roles || roles.includes(role);
}
