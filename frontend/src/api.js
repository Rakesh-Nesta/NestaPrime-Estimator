const API_BASE = "http://127.0.0.1:8000";

function authHeaders(token) {
  return { Authorization: `Bearer ${token}` };
}

async function handle(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    let message = `Request failed (${res.status})`;
    if (typeof body.detail === "string") {
      message = body.detail;
    } else if (Array.isArray(body.detail)) {
      message = body.detail.map((e) => `${e.loc?.at(-1)}: ${e.msg}`).join("; ");
    }
    throw new Error(message);
  }
  return res.json();
}

export async function login(email, password) {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);

  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) throw new Error("Incorrect email or password");
  return res.json(); // { access_token, token_type }
}

export async function getCurrentUser(token) {
  const res = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error("Session expired");
  return res.json(); // { id, name, email, role }
}

export async function listClients(token) {
  const res = await fetch(`${API_BASE}/clients`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createClient(token, payload) {
  const res = await fetch(`${API_BASE}/clients`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function createProject(token, payload) {
  const res = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function listRegionalMultipliers(token) {
  const res = await fetch(`${API_BASE}/regional-multipliers`, { headers: authHeaders(token) });
  return handle(res);
}

export async function listSports(token) {
  const res = await fetch(`${API_BASE}/sports`, { headers: authHeaders(token) });
  return handle(res);
}

export async function listProjectSports(token, projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/sports`, { headers: authHeaders(token) });
  return handle(res);
}

export async function addProjectSport(token, projectId, payload) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/sports`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function removeProjectSport(token, projectId, selectionId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/sports/${selectionId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok && res.status !== 204) return handle(res);
}

export async function listScopeItems(token) {
  const res = await fetch(`${API_BASE}/scope-items`, { headers: authHeaders(token) });
  return handle(res);
}

export async function listProjectScopeItems(token, projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/scope-items`, { headers: authHeaders(token) });
  return handle(res);
}

export async function addProjectScopeItem(token, projectId, payload) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/scope-items`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function removeProjectScopeItem(token, projectId, selectionId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/scope-items/${selectionId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok && res.status !== 204) return handle(res);
}

export async function listLabourCategories(token) {
  const res = await fetch(`${API_BASE}/labour-categories`, { headers: authHeaders(token) });
  return handle(res);
}

export async function listRateItems(token) {
  const res = await fetch(`${API_BASE}/rate-items`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createRateItem(token, payload) {
  const res = await fetch(`${API_BASE}/rate-items`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function confirmRateItem(token, rateItemId) {
  const res = await fetch(`${API_BASE}/rate-items/${rateItemId}/confirm`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function listMarginPolicies(token) {
  const res = await fetch(`${API_BASE}/margin-policies`, { headers: authHeaders(token) });
  return handle(res);
}

export async function priceQuote(token, payload) {
  const res = await fetch(`${API_BASE}/pricing/quote`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function getTenderDetails(token, projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/tender-details`, {
    headers: authHeaders(token),
  });
  if (res.status === 404) return null;
  return handle(res);
}

export async function createTenderDetails(token, projectId, payload) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/tender-details`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function performanceBgCost(token, payload) {
  const res = await fetch(`${API_BASE}/tender/performance-bg-cost`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function netReceivable(token, payload) {
  const res = await fetch(`${API_BASE}/tender/net-receivable`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

// --- Part M: document state machine (Cost Sheet -> Estimate -> Quotation) ---

export async function listCostSheets(token, projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/cost-sheets`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createCostSheet(token, projectId, payload) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/cost-sheets`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function verifyCostSheet(token, costSheetId) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/verify`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function reviseCostSheet(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/revise`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function listEstimates(token, projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/estimates`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createEstimate(token, projectId, payload) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/estimates`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function sendEstimate(token, estimateId) {
  const res = await fetch(`${API_BASE}/estimates/${estimateId}/send`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function updateEstimateOptionClientStatus(token, estimateId, optionId, payload) {
  const res = await fetch(`${API_BASE}/estimates/${estimateId}/options/${optionId}/client-status`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function listQuotations(token, projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/quotations`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createQuotation(token, projectId, payload) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/quotations`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function releaseQuotation(token, quotationId) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/release`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function sendQuotation(token, quotationId) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/send`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function markQuotationWon(token, quotationId, reason) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/mark-won`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason || null }),
  });
  return handle(res);
}

export async function markQuotationLost(token, quotationId, reason) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/mark-lost`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason || null }),
  });
  return handle(res);
}

export async function getSchedule(token, projectSportId, startDate) {
  const params = startDate ? `?start_date=${startDate}` : "";
  const res = await fetch(`${API_BASE}/schedule/project-sports/${projectSportId}${params}`, {
    headers: authHeaders(token),
  });
  return handle(res);
}

// --- Part Q: Master Settings & Overrides ---

export async function listSettings(token) {
  const res = await fetch(`${API_BASE}/settings`, { headers: authHeaders(token) });
  return handle(res);
}

export async function getSettingHistory(token, key) {
  const res = await fetch(`${API_BASE}/settings/${key}/history`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createSettingVersion(token, payload) {
  const res = await fetch(`${API_BASE}/settings`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function bulkUpdateSettings(token, payload) {
  const res = await fetch(`${API_BASE}/settings/bulk-update`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}
