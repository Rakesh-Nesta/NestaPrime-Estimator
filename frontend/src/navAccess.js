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
  // GET /settings (PM reads; only the Director writes)
  settings: ["pm", "director"],
  // GET /users, GET /role-permissions
  team_access: ["director"],
};

export function canOpen(screen, role) {
  const roles = SCREEN_ROLES[screen];
  return !roles || roles.includes(role);
}
