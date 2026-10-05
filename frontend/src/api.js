const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

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

export async function updateClientFlags(token, clientId, payload) {
  const res = await fetch(`${API_BASE}/clients/${clientId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateClientConsent(token, clientId, payload) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/consent`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateClientFollowUp(token, clientId, payload) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/follow-up`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateClientNotes(token, clientId, payload) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/notes`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateClientDetails(token, clientId, payload) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/details`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function listClientSignatories(token, clientId, includeInactive = false) {
  const params = includeInactive ? "?include_inactive=true" : "";
  const res = await fetch(`${API_BASE}/clients/${clientId}/signatories${params}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function getClientTypeDefaults(token, clientType) {
  const res = await fetch(`${API_BASE}/clients/type-defaults/${clientType}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createClientSignatory(token, clientId, payload) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/signatories`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateClientSignatory(token, clientId, signatoryId, payload) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/signatories/${signatoryId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function getClient(token, clientId) {
  const res = await fetch(`${API_BASE}/clients/${clientId}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function updateClientSource(token, clientId, payload) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/source`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateOpportunitySource(token, opportunityId, payload) {
  const res = await fetch(`${API_BASE}/opportunities/${opportunityId}/source`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

// P2 (Client 360 contract): Contacts.
export async function listClientContacts(token, clientId) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/contacts`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createClientContact(token, clientId, payload) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/contacts`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateClientContact(token, clientId, contactId, payload) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/contacts/${contactId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

// P2: Sites.
export async function listClientSites(token, clientId) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/sites`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createClientSite(token, clientId, payload) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/sites`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateClientSite(token, clientId, siteId, payload) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/sites/${siteId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateProjectSite(token, projectId, payload) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/site`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

// P2: Communication tab.
export async function listClientMessages(token, clientId) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/messages`, { headers: authHeaders(token) });
  return handle(res);
}

// P2: duplicate suggestions.
export async function listClientDuplicates(token, clientId) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/duplicates`, { headers: authHeaders(token) });
  return handle(res);
}

export async function dismissClientDuplicate(token, clientId, otherClientId) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/duplicates/dismiss`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ other_client_id: otherClientId }),
  });
  return handle(res);
}

export async function restoreClientDuplicate(token, clientId, otherClientId) {
  const res = await fetch(`${API_BASE}/clients/${clientId}/duplicates/restore`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ other_client_id: otherClientId }),
  });
  if (!res.ok && res.status !== 204) return handle(res);
  return null;
}

export async function createProject(token, payload) {
  const res = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function getProject(token, projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}`, { headers: authHeaders(token) });
  return handle(res);
}

// Project Overview (correction plan Part 4, 2026-09-28): one aggregated read of phase/owner,
// pending work with a waiting-on-us/client/vendor split, readiness gaps, payment blockers
// and latest activity -- each section already role-gated server-side.
export async function getProjectOverview(token, projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/overview`, { headers: authHeaders(token) });
  return handle(res);
}

export async function updateProjectNotes(token, projectId, payload) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/notes`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

// Amendment 59 (Section 62): the Admin's people-and-activity Overview (Admin and Director).
export async function getAdminOverview(token) {
  const res = await fetch(`${API_BASE}/admin/overview`, { headers: authHeaders(token) });
  return handle(res);
}

export async function getDashboard(token) {
  const res = await fetch(`${API_BASE}/dashboard`, { headers: authHeaders(token) });
  return handle(res);
}

// Amendment 44 (Section E step 5): Opportunity -- pipeline-stage leads/
// enquiries, distinct from Client.
export async function createOpportunity(token, payload) {
  const res = await fetch(`${API_BASE}/opportunities`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function listOpportunities(token, { stage, relationship, source, unassigned } = {}) {
  const params = new URLSearchParams();
  if (stage) params.set("stage", stage);
  if (relationship) params.set("relationship", relationship);
  if (source) params.set("source", source);
  if (unassigned) params.set("unassigned", "true");
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/opportunities${qs ? `?${qs}` : ""}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function updateOpportunityStage(token, opportunityId, payload) {
  const res = await fetch(`${API_BASE}/opportunities/${opportunityId}/stage`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateOpportunityFollowUp(token, opportunityId, payload) {
  const res = await fetch(`${API_BASE}/opportunities/${opportunityId}/follow-up`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function linkOpportunityClient(token, opportunityId, payload) {
  const res = await fetch(`${API_BASE}/opportunities/${opportunityId}/link-client`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateOpportunityNotes(token, opportunityId, payload) {
  const res = await fetch(`${API_BASE}/opportunities/${opportunityId}/notes`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateOpportunityDetails(token, opportunityId, payload) {
  const res = await fetch(`${API_BASE}/opportunities/${opportunityId}/details`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

// Amendment 12 (Section 11): drill-downs behind the Dashboard's own tiles.
// Section 19 adds client_id, for ClientsAdmin.jsx's per-client project list.
export async function listProjects(token, { search, status, client_id } = {}) {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  if (client_id) params.set("client_id", client_id);
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/projects${qs ? `?${qs}` : ""}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function listAllEstimates(token, { search, status } = {}) {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/estimates${qs ? `?${qs}` : ""}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function listRegionalMultipliers(token) {
  const res = await fetch(`${API_BASE}/regional-multipliers`, { headers: authHeaders(token) });
  return handle(res);
}

export async function listSports(token, includeInactive = false) {
  const params = includeInactive ? "?include_inactive=true" : "";
  const res = await fetch(`${API_BASE}/sports${params}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createSport(token, payload) {
  const res = await fetch(`${API_BASE}/sports`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateSport(token, sportId, payload) {
  const res = await fetch(`${API_BASE}/sports/${sportId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
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

export async function updateActualDimensions(token, projectId, selectionId, payload) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/sports/${selectionId}/actual-dimensions`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateBuildSize(token, projectId, selectionId, payload) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/sports/${selectionId}/build-size`, {
    method: "PATCH",
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

export async function listScopeItems(token, includeInactive = false) {
  const params = includeInactive ? "?include_inactive=true" : "";
  const res = await fetch(`${API_BASE}/scope-items${params}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createScopeItem(token, payload) {
  const res = await fetch(`${API_BASE}/scope-items`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateScopeItem(token, scopeItemId, payload) {
  const res = await fetch(`${API_BASE}/scope-items/${scopeItemId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function listHubs(token, includeInactive = false) {
  const params = includeInactive ? "?include_inactive=true" : "";
  const res = await fetch(`${API_BASE}/hubs${params}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createHub(token, payload) {
  const res = await fetch(`${API_BASE}/hubs`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateHub(token, hubId, payload) {
  const res = await fetch(`${API_BASE}/hubs/${hubId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
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

export async function updateRateItem(token, rateItemId, payload) {
  const res = await fetch(`${API_BASE}/rate-items/${rateItemId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateRateValue(token, rateItemId, payload) {
  const res = await fetch(`${API_BASE}/rate-items/${rateItemId}/rate`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function getRateHistory(token, rateItemId) {
  const res = await fetch(`${API_BASE}/rate-items/${rateItemId}/history`, { headers: authHeaders(token) });
  return handle(res);
}

export async function syncDraftLinesToMasterRate(token, rateItemId) {
  const res = await fetch(`${API_BASE}/rate-items/${rateItemId}/sync-draft-lines`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function bulkMarkRateItems(token, payload) {
  const res = await fetch(`${API_BASE}/rate-items/bulk-mark`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function bulkUpdateRateItems(token, payload) {
  const res = await fetch(`${API_BASE}/rate-items/bulk-rate-update`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function exportRateItemsBlob(token) {
  const res = await fetch(`${API_BASE}/rate-items/export`, { headers: authHeaders(token) });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Export failed (${res.status})`);
  }
  return res.blob();
}

export async function importRateItemsExcel(token, file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/rate-items/import`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });
  return handle(res);
}

export async function listMarginPolicies(token) {
  const res = await fetch(`${API_BASE}/margin-policies`, { headers: authHeaders(token) });
  return handle(res);
}

export async function listSportMarginPolicies(token) {
  const res = await fetch(`${API_BASE}/sport-margin-policies`, { headers: authHeaders(token) });
  return handle(res);
}

export async function upsertSportMarginPolicy(token, sportId, payload) {
  const res = await fetch(`${API_BASE}/sport-margin-policies/${sportId}`, {
    method: "PUT",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function deleteSportMarginPolicy(token, sportId) {
  const res = await fetch(`${API_BASE}/sport-margin-policies/${sportId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok && res.status !== 204) return handle(res);
}

export async function listPackageContents(token, sportId) {
  const params = sportId ? `?sport_id=${sportId}` : "";
  const res = await fetch(`${API_BASE}/package-contents${params}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function upsertPackageContent(token, sportId, tier, payload) {
  const res = await fetch(`${API_BASE}/package-contents/${sportId}/${tier}`, {
    method: "PUT",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function listFlooringGuides(token, sportId) {
  const params = sportId ? `?sport_id=${sportId}` : "";
  const res = await fetch(`${API_BASE}/flooring-guides${params}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function upsertFlooringGuide(token, sportId, payload) {
  const res = await fetch(`${API_BASE}/flooring-guides/${sportId}`, {
    method: "PUT",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function listConstructionSequence(token, sportId) {
  const params = sportId ? `?sport_id=${sportId}` : "";
  const res = await fetch(`${API_BASE}/construction-sequence${params}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function saveConstructionSequence(token, sportId, steps) {
  const res = await fetch(`${API_BASE}/construction-sequence/${sportId}`, {
    method: "PUT",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ steps }),
  });
  return handle(res);
}

export async function draftConstructionSequence(token, sportId) {
  const res = await fetch(`${API_BASE}/construction-sequence/draft/${sportId}`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function listLightingLuxStandards(token) {
  const res = await fetch(`${API_BASE}/lighting-standards/lux`, { headers: authHeaders(token) });
  return handle(res);
}

export async function upsertLightingLuxStandard(token, category, payload) {
  const res = await fetch(`${API_BASE}/lighting-standards/lux/${category}`, {
    method: "PUT",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function listSportPoleCounts(token, sportId) {
  const params = sportId ? `?sport_id=${sportId}` : "";
  const res = await fetch(`${API_BASE}/lighting-standards/pole-counts${params}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function upsertSportPoleCount(token, sportId, payload) {
  const res = await fetch(`${API_BASE}/lighting-standards/pole-counts/${sportId}`, {
    method: "PUT",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function deleteSportPoleCount(token, sportId) {
  const res = await fetch(`${API_BASE}/lighting-standards/pole-counts/${sportId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok && res.status !== 204) return handle(res);
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

export async function listCompetitorBids(token, projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/tender-details/competitor-bids`, {
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function addCompetitorBid(token, projectId, payload) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/tender-details/competitor-bids`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function deleteCompetitorBid(token, projectId, bidId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/tender-details/competitor-bids/${bidId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok && res.status !== 204) return handle(res);
}

export async function getL1View(token, quotationId) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/l1-view`, { headers: authHeaders(token) });
  return handle(res);
}

export async function getTechnicalBidChecklist(token, projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/technical-bid-checklist`, {
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function updateTechnicalBidChecklistItem(token, projectId, key, confirmed) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/technical-bid-checklist/${key}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ confirmed }),
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

export async function listSkipRequests(token, projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/skip-requests`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createSkipRequest(token, projectId, payload) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/skip-requests`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function approveSkipRequest(token, skipRequestId, payload) {
  const res = await fetch(`${API_BASE}/skip-requests/${skipRequestId}/approve`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

// WP7 (correction plan, 2026-09-28): readiness checks before document issuance.
export async function getProjectReadiness(token, projectId, { documentType, documentId } = {}) {
  const params = new URLSearchParams();
  if (documentType) params.set("document_type", documentType);
  if (documentId) params.set("document_id", documentId);
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/projects/${projectId}/readiness${qs ? `?${qs}` : ""}`, {
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function confirmEmptyScope(token, projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/scope-items/confirm-empty`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function createReadinessException(token, payload) {
  const res = await fetch(`${API_BASE}/readiness-exceptions`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function listReadinessExceptions(token, documentType, documentId) {
  const params = new URLSearchParams({ document_type: documentType, document_id: documentId });
  const res = await fetch(`${API_BASE}/readiness-exceptions?${params.toString()}`, {
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function approveReadinessException(token, exceptionId) {
  const res = await fetch(`${API_BASE}/readiness-exceptions/${exceptionId}/approve`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function rejectReadinessException(token, exceptionId, payload) {
  const res = await fetch(`${API_BASE}/readiness-exceptions/${exceptionId}/reject`, {
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

export async function rejectCostSheet(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/reject`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
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

// Amendment 57: add / remove a sport option on a Draft Estimate (PM/Director).
export async function addEstimateOption(token, estimateId, option) {
  const res = await fetch(`${API_BASE}/estimates/${estimateId}/options`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(option),
  });
  return handle(res);
}

export async function removeEstimateOption(token, estimateId, optionId) {
  const res = await fetch(`${API_BASE}/estimates/${estimateId}/options/${optionId}`, {
    method: "DELETE",
    headers: authHeaders(token),
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

export async function rebaseEstimate(token, estimateId) {
  const res = await fetch(`${API_BASE}/estimates/${estimateId}/rebase`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function reviseEstimate(token, estimateId, payload) {
  const res = await fetch(`${API_BASE}/estimates/${estimateId}/revise`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
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

export async function createFastTrackQuotation(token, projectId, payload) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/quotations/fast-track`, {
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

// Amendment 13 (Section 12): AI-drafted, always human-reviewed before saving.
export async function draftQuotationCoverNote(token, quotationId) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/draft-cover-note`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function updateQuotationCoverNote(token, quotationId, coverNote) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/cover-note`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ cover_note: coverNote }),
  });
  return handle(res);
}

export async function rejectQuotation(token, quotationId, payload) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/reject`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function reviseQuotation(token, quotationId, payload) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/revise`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
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

export async function markQuotationWon(token, quotationId, { reason, waiveEvidenceReason } = {}) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/mark-won`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({
      reason: reason || null,
      ...(waiveEvidenceReason ? { waive_evidence_reason: waiveEvidenceReason } : {}),
    }),
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

export async function getWorkOrder(token, quotationId) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/work-order`, { headers: authHeaders(token) });
  if (res.status === 404) return null;
  return handle(res);
}

export async function createWorkOrder(token, quotationId) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/work-order`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function updateWorkOrderStatus(token, workOrderId, status) {
  const res = await fetch(`${API_BASE}/work-orders/${workOrderId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  return handle(res);
}

export async function listWorkOrderPaymentEntries(token, workOrderId) {
  const res = await fetch(`${API_BASE}/work-orders/${workOrderId}/payment-entries`, { headers: authHeaders(token) });
  return handle(res);
}

export async function addWorkOrderPaymentEntry(token, workOrderId, payload) {
  const res = await fetch(`${API_BASE}/work-orders/${workOrderId}/payment-entries`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

// Amendment 50 (Section 54): expected payments (milestones), receipt edits and
// the org-wide Payments list. Reconciliation only -- the API derives status,
// overdue and outstanding from what people entered.
export async function listPayments(token, { overdue, search } = {}) {
  const params = new URLSearchParams();
  if (overdue !== undefined) params.set("overdue", String(overdue));
  if (search) params.set("search", search);
  const qs = params.toString() ? `?${params}` : "";
  const res = await fetch(`${API_BASE}/payments${qs}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function getWorkOrderPaymentSummary(token, workOrderId) {
  const res = await fetch(`${API_BASE}/work-orders/${workOrderId}/payment-summary`, { headers: authHeaders(token) });
  return handle(res);
}

export async function listWorkOrderPaymentMilestones(token, workOrderId) {
  const res = await fetch(`${API_BASE}/work-orders/${workOrderId}/payment-milestones`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createWorkOrderPaymentMilestone(token, workOrderId, payload) {
  const res = await fetch(`${API_BASE}/work-orders/${workOrderId}/payment-milestones`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updatePaymentMilestone(token, milestoneId, payload) {
  const res = await fetch(`${API_BASE}/payment-milestones/${milestoneId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function deletePaymentMilestone(token, milestoneId) {
  const res = await fetch(`${API_BASE}/payment-milestones/${milestoneId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  // 204 No Content on success -- there is no body for handle() to parse.
  if (res.status === 204) return null;
  return handle(res);
}

export async function updatePaymentEntry(token, entryId, payload) {
  const res = await fetch(`${API_BASE}/payment-entries/${entryId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
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

export async function exportSettingsBlob(token) {
  const res = await fetch(`${API_BASE}/settings/export`, { headers: authHeaders(token) });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Export failed (${res.status})`);
  }
  return res.blob();
}

export async function importSettingsExcel(token, file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/settings/import`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });
  return handle(res);
}

export async function createOverride(token, payload) {
  const res = await fetch(`${API_BASE}/overrides`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function getK1Constants(token, costSheetId) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/k1-constants`, { headers: authHeaders(token) });
  return handle(res);
}

// --- Part T: Reporting & Extraction ---

export async function listReports(token) {
  const res = await fetch(`${API_BASE}/reports`, { headers: authHeaders(token) });
  return handle(res);
}

export async function generateReport(token, payload) {
  const res = await fetch(`${API_BASE}/reports/generate`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function releaseReport(token, reportId) {
  const res = await fetch(`${API_BASE}/reports/${reportId}/release`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

// Amendment 13 (Section 12): on-demand, never persisted -- a read-only
// convenience layer over the report's own already-computed content.
export async function summarizeReport(token, reportId) {
  const res = await fetch(`${API_BASE}/reports/${reportId}/summary`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function exportReportBlob(token, reportId) {
  const res = await fetch(`${API_BASE}/reports/${reportId}/export`, { headers: authHeaders(token) });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Export failed (${res.status})`);
  }
  return res.blob();
}

export async function exportReportPdfBlob(token, reportId) {
  const res = await fetch(`${API_BASE}/reports/${reportId}/pdf`, { headers: authHeaders(token) });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Export failed (${res.status})`);
  }
  return res.blob();
}

// --- Parts D/E/F/G.5/H/J.2: Cost Sheet take-off engines ---

export async function listCostSheetLines(token, costSheetId) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/lines`, { headers: authHeaders(token) });
  return handle(res);
}

export async function addCostSheetLine(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/lines`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateCostSheetLine(token, costSheetId, lineId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/lines/${lineId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function deleteCostSheetLine(token, costSheetId, lineId) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/lines/${lineId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok && res.status !== 204) return handle(res);
}

export async function recomputeCostSheet(token, costSheetId) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/recompute`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function getLabourWarnings(token, costSheetId) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/labour-warnings`, {
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function getConsumptionSheet(token, costSheetId) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/consumption-sheet`, {
    headers: authHeaders(token),
  });
  return handle(res);
}

// --- Part O: Vendors & Purchase Orders ---

export async function listVendors(token) {
  const res = await fetch(`${API_BASE}/vendors`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createVendor(token, payload) {
  const res = await fetch(`${API_BASE}/vendors`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateVendor(token, vendorId, payload) {
  const res = await fetch(`${API_BASE}/vendors/${vendorId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

// --- Amendment 7: Products (a vendor's own catalog reference) ---

export async function listProducts(token, vendorId) {
  const res = await fetch(`${API_BASE}/vendors/${vendorId}/products`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createProduct(token, vendorId, payload) {
  const res = await fetch(`${API_BASE}/vendors/${vendorId}/products`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateProduct(token, productId, payload) {
  const res = await fetch(`${API_BASE}/products/${productId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function deleteProduct(token, productId) {
  const res = await fetch(`${API_BASE}/products/${productId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok && res.status !== 204) return handle(res);
}

export async function listPurchaseOrders(token, costSheetId) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/purchase-orders`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createPurchaseOrder(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/purchase-orders`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function issuePurchaseOrder(token, poId) {
  const res = await fetch(`${API_BASE}/purchase-orders/${poId}/issue`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function cancelPurchaseOrder(token, poId) {
  const res = await fetch(`${API_BASE}/purchase-orders/${poId}/cancel`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function receivePurchaseOrder(token, poId, payload) {
  const res = await fetch(`${API_BASE}/purchase-orders/${poId}/receive`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

// --- M.7.3: Vendor price-update requests ---

export async function listPriceRequests(token, { status, overdueOnly } = {}) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (overdueOnly) params.set("overdue_only", "true");
  const res = await fetch(`${API_BASE}/price-requests?${params}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function getPriceRequest(token, priceRequestId) {
  const res = await fetch(`${API_BASE}/price-requests/${priceRequestId}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createPriceRequest(token, payload) {
  const res = await fetch(`${API_BASE}/price-requests`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function closePriceRequest(token, priceRequestId) {
  const res = await fetch(`${API_BASE}/price-requests/${priceRequestId}/close`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function listVendorReplies(token, priceRequestId, itemId) {
  const res = await fetch(`${API_BASE}/price-requests/${priceRequestId}/items/${itemId}/replies`, {
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function createVendorReply(token, priceRequestId, itemId, payload) {
  const res = await fetch(`${API_BASE}/price-requests/${priceRequestId}/items/${itemId}/replies`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function useVendorReply(token, replyId, payload) {
  const res = await fetch(`${API_BASE}/vendor-replies/${replyId}/use`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addStructureTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/structures`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addBaseTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/base`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addSitePrepTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/site-prep`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addFreightCraneTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/freight-crane`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addDesignApprovalsTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/design-approvals`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addTenderOverheadsTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/tender-overheads`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addDrainageTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/drainage`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addTurfTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/flooring/turf`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addWoodenFlooringTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/flooring/wooden`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addAcrylicPuTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/flooring/acrylic-pu`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addLineMarkingTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/flooring/line-marking`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addLightingTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/lighting`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addHvacTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/hvac`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addAccessoriesTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/accessories`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function listAccessoryCatalog(token, sportId, includeInactive = false) {
  const params = new URLSearchParams();
  if (sportId) params.set("sport_id", sportId);
  if (includeInactive) params.set("include_inactive", "true");
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/accessory-catalog${qs ? `?${qs}` : ""}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createAccessoryCatalogItem(token, payload) {
  const res = await fetch(`${API_BASE}/accessory-catalog`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateAccessoryCatalogItem(token, itemId, payload) {
  const res = await fetch(`${API_BASE}/accessory-catalog/${itemId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function listNettingGrades(token, includeInactive = false) {
  const qs = includeInactive ? "?include_inactive=true" : "";
  const res = await fetch(`${API_BASE}/netting-grades${qs}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createNettingGrade(token, payload) {
  const res = await fetch(`${API_BASE}/netting-grades`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateNettingGrade(token, gradeId, payload) {
  const res = await fetch(`${API_BASE}/netting-grades/${gradeId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function listVehicleClasses(token, includeInactive = false) {
  const qs = includeInactive ? "?include_inactive=true" : "";
  const res = await fetch(`${API_BASE}/vehicle-classes${qs}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createVehicleClass(token, payload) {
  const res = await fetch(`${API_BASE}/vehicle-classes`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateVehicleClass(token, vehicleClassId, payload) {
  const res = await fetch(`${API_BASE}/vehicle-classes/${vehicleClassId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addAthleticsTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/athletics`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addPlayEquipmentTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/play-equipment`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addGymTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/gym`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addPoolTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/pool`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addNaturalGrassTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/flooring/natural-grass`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function addHockeyIrrigationTakeoff(token, costSheetId, payload) {
  const res = await fetch(`${API_BASE}/cost-sheets/${costSheetId}/flooring/hockey-irrigation`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

// --- Appendix C: Site Survey Form ---

export async function listSiteSurveys(token, projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/site-surveys`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createSiteSurvey(token, projectId, payload) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/site-surveys`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateSiteSurvey(token, siteSurveyId, payload) {
  const res = await fetch(`${API_BASE}/site-surveys/${siteSurveyId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function completeSiteSurvey(token, siteSurveyId) {
  const res = await fetch(`${API_BASE}/site-surveys/${siteSurveyId}/complete`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

// --- Part M.3: Attachments & approval evidence ---

export async function listAttachments(token, docType, docId, includeSuperseded = false) {
  const params = new URLSearchParams({ doc_type: docType, doc_id: docId });
  if (includeSuperseded) params.set("include_superseded", "true");
  const res = await fetch(`${API_BASE}/attachments?${params.toString()}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function listMessages(token, docType, docId) {
  const params = new URLSearchParams({ doc_type: docType, doc_id: docId });
  const res = await fetch(`${API_BASE}/messages?${params.toString()}`, { headers: authHeaders(token) });
  return handle(res);
}

// Amendment 13 (Section 12): AI-drafted, always human-reviewed before sending.
export async function draftMessage(token, { docType, docId, channel }) {
  const res = await fetch(`${API_BASE}/messages/draft`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ doc_type: docType, doc_id: docId, channel }),
  });
  return handle(res);
}

// A send carries a stable request id: retrying the SAME send (same id) returns the existing outcome and never sends
// again. Structured refusals (excluded PDF images, a busy PDF service) surface as PdfExportError so the screen can show them.
export class NetworkOutcomeUnknownError extends Error {
  constructor() {
    super("The connection was lost before the response arrived. The message may or may not have been sent.");
  }
}

async function messageResponse(res) {
  if (res.ok) return res.json();
  const body = await res.json().catch(() => ({}));
  const detail = body.detail;
  if (detail && typeof detail === "object") {
    if (detail.code === "pdf_images_excluded") throw new PdfExportError("excluded", detail.message, detail.excluded || []);
    if (detail.code === "pdf_busy") throw new PdfExportError("busy", detail.message);
    const err = new Error(detail.message || `Request failed (${res.status})`);
    err.code = detail.code;
    err.detail = detail;
    throw err;
  }
  return handle({ ok: false, status: res.status, json: async () => body });
}

export async function createMessage(token, { docType, docId, channel, recipient, templateKey, templateId, subject, bodyNote, attachmentId, includeDocument, requestId }) {
  let res;
  try {
    res = await fetch(`${API_BASE}/messages`, {
      method: "POST",
      headers: { ...authHeaders(token), "Content-Type": "application/json" },
      body: JSON.stringify({
        doc_type: docType,
        doc_id: docId,
        channel,
        recipient,
        template_key: templateKey || null,
        template_id: templateId || null,
        subject: subject || null,
        body_note: bodyNote || null,
        attachment_id: attachmentId || null,
        include_document: !!includeDocument,
        request_id: requestId || null,
      }),
    });
  } catch {
    throw new NetworkOutcomeUnknownError(); // the request may have reached the server: retry with the SAME request id
  }
  return messageResponse(res);
}

// "Send again anyway": a NEW linked attempt. Unless the earlier attempt is a confirmed failure the caller must pass
// confirmDuplicateRisk=true after showing the user the duplicate warning.
export async function resendMessage(token, messageId, { requestId, confirmDuplicateRisk } = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE}/messages/${messageId}/resend`, {
      method: "POST",
      headers: { ...authHeaders(token), "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: requestId || null, confirm_duplicate_risk: !!confirmDuplicateRisk }),
    });
  } catch {
    throw new NetworkOutcomeUnknownError();
  }
  return messageResponse(res);
}

export async function listMessageTemplates(token, { channel, documentType, includeInactive } = {}) {
  const params = new URLSearchParams();
  if (channel) params.set("channel", channel);
  if (documentType) params.set("document_type", documentType);
  if (includeInactive) params.set("include_inactive", "true");
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/message-templates${qs ? `?${qs}` : ""}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createMessageTemplate(token, payload) {
  const res = await fetch(`${API_BASE}/message-templates`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateMessageTemplate(token, templateId, payload) {
  const res = await fetch(`${API_BASE}/message-templates/${templateId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function uploadAttachment(token, { docType, docId, tag, approvalStrength, signatoryName, signatoryDesignation, capturedAt, capturedAtSource, file }) {
  const formData = new FormData();
  formData.append("doc_type", docType);
  formData.append("doc_id", docId);
  formData.append("tag", tag);
  if (approvalStrength) formData.append("approval_strength", approvalStrength);
  if (signatoryName) formData.append("signatory_name", signatoryName);
  if (signatoryDesignation) formData.append("signatory_designation", signatoryDesignation);
  if (capturedAt) formData.append("captured_at", capturedAt);
  if (capturedAtSource) formData.append("captured_at_source", capturedAtSource);
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/attachments`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });
  return handle(res);
}

export async function downloadAttachmentBlob(token, attachmentId) {
  const res = await fetch(`${API_BASE}/attachments/${attachmentId}/download`, { headers: authHeaders(token) });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Download failed (${res.status})`);
  }
  return res.blob();
}

export async function getCompanyLogoMeta(token) {
  const res = await fetch(`${API_BASE}/company/logo/meta`, { headers: authHeaders(token) });
  if (res.status === 404) return null;
  return handle(res);
}

export async function downloadCompanyLogoBlob(token) {
  const res = await fetch(`${API_BASE}/company/logo`, { headers: authHeaders(token) });
  if (res.status === 404) return null;
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Download failed (${res.status})`);
  }
  return res.blob();
}

export async function uploadCompanyLogo(token, file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/company/logo`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });
  return handle(res);
}

// --- Part M.6: client-facing Estimate / Quotation PDFs ---

// --- PDF export problems: never a silent omission, never a lost place ---

export class PdfExportError extends Error {
  constructor(kind, message, excluded = []) {
    super(message);
    this.kind = kind; // "excluded" | "busy"
    this.excluded = excluded;
  }
}

async function pdfFailure(res, fallback) {
  const body = await res.json().catch(() => ({}));
  const detail = body.detail;
  if (detail && typeof detail === "object" && detail.code === "pdf_images_excluded") {
    return new PdfExportError("excluded", detail.message, detail.excluded || []);
  }
  if (detail && typeof detail === "object" && detail.code === "pdf_busy") {
    return new PdfExportError("busy", detail.message);
  }
  return new Error(typeof detail === "string" ? detail : `${fallback} (${res.status})`);
}

export async function getPdfCheck(token, docType, docId) {
  const res = await fetch(`${API_BASE}/${docType === "estimate" ? "estimates" : "quotations"}/${docId}/pdf-check`, {
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function excludeImageFromDocument(token, { doc_type, doc_id, attachment_id, reason }) {
  const res = await fetch(`${API_BASE}/pdf-image-exclusions`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ doc_type, doc_id, attachment_id, reason: reason ?? null }),
  });
  return handle(res);
}

export async function restoreImageToDocument(token, exclusionId) {
  const res = await fetch(`${API_BASE}/pdf-image-exclusions/${exclusionId}`, { method: "DELETE", headers: authHeaders(token) });
  if (!res.ok) return handle(res);
  return null;
}


export async function downloadEstimatePdfBlob(token, estimateId) {
  const res = await fetch(`${API_BASE}/estimates/${estimateId}/pdf`, { headers: authHeaders(token) });
  if (!res.ok) throw await pdfFailure(res, "PDF generation failed");
  return res.blob();
}

export async function downloadQuotationPdfBlob(token, quotationId) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/pdf`, { headers: authHeaders(token) });
  if (!res.ok) throw await pdfFailure(res, "PDF generation failed");
  return res.blob();
}

export async function getQuotationTemplateDefaults(token) {
  const res = await fetch(`${API_BASE}/quotation-template-defaults`, { headers: authHeaders(token) });
  return handle(res);
}

// Section 14: renders draft (unsaved) T&C/warranty-table text against a
// real Quotation's own data -- never writes anything to the database.
export async function previewQuotationTemplateBlob(token, quotationId, { terms, warrantyTable } = {}) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/preview-pdf`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ terms: terms ?? null, warranty_table: warrantyTable ?? null }),
  });
  if (!res.ok) throw await pdfFailure(res, "Preview failed");
  return res.blob();
}

export async function listAuditLog(token, { documentType, documentId } = {}) {
  const params = new URLSearchParams();
  if (documentType) params.set("document_type", documentType);
  if (documentId) params.set("document_id", documentId);
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/audit-log${qs ? `?${qs}` : ""}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function downloadAuditLogCsvBlob(token, { documentType, documentId } = {}) {
  const params = new URLSearchParams();
  if (documentType) params.set("document_type", documentType);
  if (documentId) params.set("document_id", documentId);
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/audit-log/export${qs ? `?${qs}` : ""}`, { headers: authHeaders(token) });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Export failed (${res.status})`);
  }
  return res.blob();
}

export async function supersedeAttachment(token, attachmentId, { tag, approvalStrength, file }) {
  const formData = new FormData();
  if (tag) formData.append("tag", tag);
  if (approvalStrength) formData.append("approval_strength", approvalStrength);
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/attachments/${attachmentId}/supersede`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });
  return handle(res);
}

// --- P4 (document library and engineer evidence) ---------------------------------------------

export async function getAttachmentLineages(token, docType, docId) {
  const res = await fetch(`${API_BASE}/attachments/${docType}/${docId}/lineages`, { headers: authHeaders(token) });
  return handle(res);
}

export async function searchAttachments(token, q, { docType, limit = 20, offset = 0, signal } = {}) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (q) params.set("q", q);
  if (docType) params.set("doc_type", docType);
  const res = await fetch(`${API_BASE}/attachments/search?${params}`, { headers: authHeaders(token), signal });
  return handle(res);
}

export async function reviewAttachment(token, attachmentId, status) {
  const res = await fetch(`${API_BASE}/attachments/${attachmentId}/review`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  return handle(res);
}

export async function approveMarketingReuse(token, attachmentId) {
  const res = await fetch(`${API_BASE}/attachments/${attachmentId}/marketing-reuse/approve`, {
    method: "POST", headers: authHeaders(token),
  });
  return handle(res);
}

export async function revokeMarketingReuse(token, attachmentId) {
  const res = await fetch(`${API_BASE}/attachments/${attachmentId}/marketing-reuse/revoke`, {
    method: "POST", headers: authHeaders(token),
  });
  return handle(res);
}

export async function listProjectStages(token, projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/stages`, { headers: authHeaders(token) });
  return handle(res);
}

export async function submitStage(token, stageId) {
  const res = await fetch(`${API_BASE}/stages/${stageId}/submit`, { method: "POST", headers: authHeaders(token) });
  return handle(res);
}

export async function reviewStage(token, stageId, { action, rejectionReason }) {
  const res = await fetch(`${API_BASE}/stages/${stageId}/review`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ action, rejection_reason: rejectionReason }),
  });
  return handle(res);
}

// Chunked/resumable upload (P4 contract v7, Section 4). Four calls, matching the backend's own
// four-endpoint session lifecycle -- never assume a single "upload" call for a large file.
export async function startUploadSession(token, { docType, docId, filename, declaredSize, declaredSha256, chunkSize }) {
  const res = await fetch(`${API_BASE}/attachments/upload-sessions`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({
      doc_type: docType, doc_id: docId, filename, declared_size: declaredSize,
      declared_sha256: declaredSha256, chunk_size: chunkSize,
    }),
  });
  return handle(res);
}

export async function getUploadSessionStatus(token, sessionId) {
  const res = await fetch(`${API_BASE}/attachments/upload-sessions/${sessionId}/status`, { headers: authHeaders(token) });
  return handle(res);
}

export async function uploadSessionChunk(token, sessionId, chunkIndex, chunkBlob) {
  const formData = new FormData();
  formData.append("file", chunkBlob, "chunk");
  const res = await fetch(`${API_BASE}/attachments/upload-sessions/${sessionId}/chunks/${chunkIndex}`, {
    method: "POST", headers: authHeaders(token), body: formData,
  });
  return handle(res);
}

export async function completeUploadSession(token, sessionId) {
  const res = await fetch(`${API_BASE}/attachments/upload-sessions/${sessionId}/complete`, {
    method: "POST", headers: authHeaders(token),
  });
  return handle(res);
}

export async function changePassword(token, { currentPassword, newPassword }) {
  const res = await fetch(`${API_BASE}/auth/change-password`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  return handle(res);
}

export async function listUsers(token) {
  const res = await fetch(`${API_BASE}/users`, { headers: authHeaders(token) });
  return handle(res);
}

// Amendment 51 (Section 55): the Director's "who can do what" view, generated by
// the backend from the same role gates it enforces (Director-only).
export async function getRolePermissions(token) {
  const res = await fetch(`${API_BASE}/role-permissions`, { headers: authHeaders(token) });
  return handle(res);
}

// Amendment 53 (Section 57): global quick search -- clients, leads, projects and
// quotations in groups (each only for roles that can already read that kind).
export async function globalSearch(token, q, { signal } = {}) {
  const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(q)}`, { headers: authHeaders(token), signal });
  return handle(res);
}

export async function createUser(token, { name, email, role, password }) {
  const res = await fetch(`${API_BASE}/users`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, role, password }),
  });
  return handle(res);
}

export async function updateUser(token, userId, payload) {
  const res = await fetch(`${API_BASE}/users/${userId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function resetUserPassword(token, userId, newPassword) {
  const res = await fetch(`${API_BASE}/users/${userId}/reset-password`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ new_password: newPassword }),
  });
  return handle(res);
}

// Amendment 3 (Section 7): "Complete Your Facility" cross-sell add-ons.

export async function listCrossSellAddons(token) {
  const res = await fetch(`${API_BASE}/cross-sell-addons`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createCrossSellAddon(token, payload) {
  const res = await fetch(`${API_BASE}/cross-sell-addons`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateCrossSellAddon(token, addonId, payload) {
  const res = await fetch(`${API_BASE}/cross-sell-addons/${addonId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function setCrossSellAddonSports(token, addonId, sportIds) {
  const res = await fetch(`${API_BASE}/cross-sell-addons/${addonId}/sports`, {
    method: "PUT",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ sport_ids: sportIds }),
  });
  return handle(res);
}

export async function listSuggestedAddonsForProject(token, projectId) {
  const res = await fetch(`${API_BASE}/cross-sell-addons/suggestions/for-project/${projectId}`, {
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function listEstimateOptionAddons(token, optionId) {
  const res = await fetch(`${API_BASE}/estimate-options/${optionId}/addons`, { headers: authHeaders(token) });
  return handle(res);
}

export async function addEstimateOptionAddon(token, optionId, addonId) {
  const res = await fetch(`${API_BASE}/estimate-options/${optionId}/addons`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ addon_id: addonId }),
  });
  return handle(res);
}

export async function removeEstimateOptionAddon(token, rowId) {
  const res = await fetch(`${API_BASE}/estimate-option-addons/${rowId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok && res.status !== 204) return handle(res);
}

// Amendment 5 Phase 2 (Section 6): "admin sets each field compulsory/
// optional/hidden from Master Settings" -- New Project Setup's governed
// fields.

export async function listFieldSettings(token) {
  const res = await fetch(`${API_BASE}/field-settings`, { headers: authHeaders(token) });
  return handle(res);
}

export async function updateFieldSetting(token, fieldKey, state) {
  const res = await fetch(`${API_BASE}/field-settings/${fieldKey}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ state }),
  });
  return handle(res);
}

// --- Amendment 6b (Section 9): Director-only, cross-project quotations review ---

function _allQuotationsParams({ status, statusGroup, projectId, clientId, dateFrom, dateTo } = {}) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  else if (statusGroup) params.set("status_group", statusGroup);
  if (projectId) params.set("project_id", projectId);
  if (clientId) params.set("client_id", clientId);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  return params.toString();
}

export async function listAllQuotations(token, filters = {}) {
  const qs = _allQuotationsParams(filters);
  const res = await fetch(`${API_BASE}/quotations${qs ? `?${qs}` : ""}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function downloadAllQuotationsCsvBlob(token, filters = {}) {
  const qs = _allQuotationsParams(filters);
  const res = await fetch(`${API_BASE}/quotations/export${qs ? `?${qs}` : ""}`, { headers: authHeaders(token) });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Export failed (${res.status})`);
  }
  return res.blob();
}

// --- Section 15 (Amendment 15): Education tab AI assistant ---

export async function askEducationAssistant(token, { question, context, history }) {
  const res = await fetch(`${API_BASE}/education/ask`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ question, context, history: history || [] }),
  });
  return handle(res);
}

// Amendment 60 (Section 63): who owns which client, project and enquiry (PM and Director; the switch is
// Director only).
export async function getOwnershipOverview(token) {
  const res = await fetch(`${API_BASE}/ownership/overview`, { headers: authHeaders(token) });
  return handle(res);
}

export async function listUnassigned(token, kind) {
  const res = await fetch(`${API_BASE}/ownership/unassigned?kind=${encodeURIComponent(kind)}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function assignOwner(token, kind, recordId, ownerId, { cascade = true } = {}) {
  const res = await fetch(`${API_BASE}/ownership/${kind}/${recordId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ owner_id: ownerId || null, cascade }),
  });
  return handle(res);
}

export async function reassignAllOwnership(token, fromUserId, toUserId) {
  const res = await fetch(`${API_BASE}/ownership/reassign-all`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ from_user_id: fromUserId, to_user_id: toUserId }),
  });
  return handle(res);
}

export async function acceptOwnerSuggestions(token, kind) {
  const res = await fetch(`${API_BASE}/ownership/accept-suggestions`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ kind }),
  });
  return handle(res);
}

export async function setOwnRecordsSwitch(token, on) {
  const res = await fetch(`${API_BASE}/ownership/switch`, {
    method: "PUT",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ on }),
  });
  return handle(res);
}

// WP5 integration (correction plan, 2026-09-28): the shared follow-up API. FollowUps.jsx
// is the one screen wired to it directly -- ClientsAdmin.jsx/Opportunities.jsx keep
// calling updateClientFollowUp/updateOpportunityFollowUp above, which the backend now
// writes through to this same table on their behalf (app/core/follow_up_sync.py).
export async function listFollowUps(token, { entityType, entityId, ownerId, status } = {}) {
  const params = new URLSearchParams();
  if (entityType) params.set("entity_type", entityType);
  if (entityId) params.set("entity_id", entityId);
  if (ownerId) params.set("owner_id", ownerId);
  if (status) params.set("status", status);
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/follow-ups${qs ? `?${qs}` : ""}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function createFollowUp(token, payload) {
  const res = await fetch(`${API_BASE}/follow-ups`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function updateFollowUp(token, followUpId, payload) {
  const res = await fetch(`${API_BASE}/follow-ups/${followUpId}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handle(res);
}

export async function deleteFollowUp(token, followUpId) {
  const res = await fetch(`${API_BASE}/follow-ups/${followUpId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  return handle(res);
}

// WP8 (correction plan, 2026-09-29): the in-app notification inbox.
export async function listNotifications(token, { unreadOnly } = {}) {
  const params = new URLSearchParams();
  if (unreadOnly) params.set("unread_only", "true");
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/notifications${qs ? `?${qs}` : ""}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function getUnreadNotificationCount(token) {
  const res = await fetch(`${API_BASE}/notifications/unread-count`, { headers: authHeaders(token) });
  return handle(res);
}

export async function markNotificationRead(token, notificationId) {
  const res = await fetch(`${API_BASE}/notifications/${notificationId}/read`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function markAllNotificationsRead(token) {
  const res = await fetch(`${API_BASE}/notifications/mark-all-read`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle(res);
}

export async function listNotificationDeliveryFailures(token) {
  const res = await fetch(`${API_BASE}/notifications/delivery-failures`, { headers: authHeaders(token) });
  return handle(res);
}

// P3 (IndiaMART Intake & Marketing Starter contract): Section 5/7 Opportunity extensions.
export async function getOpportunityImportDetail(token, opportunityId) {
  const res = await fetch(`${API_BASE}/opportunities/${opportunityId}/import-detail`, { headers: authHeaders(token) });
  return handle(res);
}

export async function listPossibleClientMatches(token, opportunityId) {
  const res = await fetch(`${API_BASE}/opportunities/${opportunityId}/possible-client-matches`, { headers: authHeaders(token) });
  return handle(res);
}

// P3: Section 8 operational screen (PM/Director only).
export async function getMarketplaceConnectionHealth(token) {
  const res = await fetch(`${API_BASE}/marketplace-imports/connection-health`, { headers: authHeaders(token) });
  return handle(res);
}

export async function getMarketplaceImportsSummary(token) {
  const res = await fetch(`${API_BASE}/marketplace-imports/summary`, { headers: authHeaders(token) });
  return handle(res);
}

export async function listMarketplaceImports(token, status) {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  const res = await fetch(`${API_BASE}/marketplace-imports${qs}`, { headers: authHeaders(token) });
  return handle(res);
}

export async function verifyMarketplaceKey(token) {
  const res = await fetch(`${API_BASE}/marketplace-imports/verify-key`, { method: "POST", headers: authHeaders(token) });
  return handle(res);
}

export async function retryMarketplaceImport(token, ledgerRowId) {
  const res = await fetch(`${API_BASE}/marketplace-imports/${ledgerRowId}/retry`, { method: "POST", headers: authHeaders(token) });
  return handle(res);
}

export async function runMarketplaceBackfill(token, { rangeStart, rangeEnd }) {
  const res = await fetch(`${API_BASE}/marketplace-imports/backfill`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ range_start: rangeStart, range_end: rangeEnd }),
  });
  return handle(res);
}

// P3: Section 9 Marketing Phase A aggregate dashboard.
// M4: the cohort basis (enquiry_time | received_at) and the date-bucket size (day | week | month) are explicit choices.
export async function getMarketingDashboard(token, { periodStart, periodEnd, basis = "enquiry_time", bucket = "day" }) {
  const params = new URLSearchParams({ period_start: periodStart, period_end: periodEnd, basis, bucket });
  const res = await fetch(`${API_BASE}/marketplace-imports/marketing/dashboard?${params}`, { headers: authHeaders(token) });
  return handle(res);
}

// P5: Agreement & Execution Starter -- agreements, execution readiness/authorization, project
// team, milestones, tasks and site issues.
async function p5Json(token, method, path, payload) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: payload === undefined ? authHeaders(token) : { ...authHeaders(token), "Content-Type": "application/json" },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  return handle(res);
}

export async function getExecutionContext(token, projectId) {
  return p5Json(token, "GET", `/projects/${projectId}/execution-context`);
}

export async function createAgreementDraft(token, quotationId) {
  return p5Json(token, "POST", `/quotations/${quotationId}/agreement`);
}

export async function getCurrentAgreement(token, quotationId) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/agreement`, { headers: authHeaders(token) });
  if (res.status === 404) return null;
  return handle(res);
}

export async function listAgreementRevisions(token, quotationId) {
  return p5Json(token, "GET", `/quotations/${quotationId}/agreements`);
}

export async function getAgreement(token, agreementId) {
  return p5Json(token, "GET", `/agreements/${agreementId}`);
}

export async function clientSignAgreement(token, agreementId, { clientSignatoryId, signedOn, attachmentId }) {
  return p5Json(token, "POST", `/agreements/${agreementId}/client-sign`, {
    client_signatory_id: clientSignatoryId,
    signed_on: signedOn,
    attachment_id: attachmentId,
  });
}

export async function executeAgreement(token, agreementId) {
  return p5Json(token, "POST", `/agreements/${agreementId}/execute`);
}

export async function voidAgreement(token, agreementId, reason) {
  return p5Json(token, "POST", `/agreements/${agreementId}/void`, { reason });
}

export async function supersedeAgreement(token, agreementId, reason) {
  return p5Json(token, "POST", `/agreements/${agreementId}/supersede`, { reason });
}

export async function getExecutionReadiness(token, quotationId) {
  return p5Json(token, "GET", `/quotations/${quotationId}/execution-readiness`);
}

export async function authorizeExecution(token, quotationId) {
  return p5Json(token, "POST", `/quotations/${quotationId}/execution-authorization`);
}

export async function listExecutionAuthorizations(token, quotationId) {
  return p5Json(token, "GET", `/quotations/${quotationId}/execution-authorizations`);
}

export async function listProjectTeam(token, projectId, includeRemoved = false) {
  const qs = includeRemoved ? "?include_removed=true" : "";
  return p5Json(token, "GET", `/projects/${projectId}/team${qs}`);
}

export async function addProjectTeamMember(token, projectId, { userId, projectRole }) {
  return p5Json(token, "POST", `/projects/${projectId}/team`, { user_id: userId, project_role: projectRole });
}

export async function removeProjectTeamMember(token, projectId, teamMemberId) {
  return p5Json(token, "DELETE", `/projects/${projectId}/team/${teamMemberId}`);
}

export async function listMilestones(token, projectId) {
  return p5Json(token, "GET", `/projects/${projectId}/milestones`);
}

export async function createMilestone(token, projectId, payload) {
  return p5Json(token, "POST", `/projects/${projectId}/milestones`, payload);
}

export async function updateMilestone(token, milestoneId, payload) {
  return p5Json(token, "PATCH", `/milestones/${milestoneId}`, payload);
}

export async function listTasks(token, projectId) {
  return p5Json(token, "GET", `/projects/${projectId}/tasks`);
}

export async function createTask(token, projectId, payload) {
  return p5Json(token, "POST", `/projects/${projectId}/tasks`, payload);
}

export async function updateTask(token, taskId, payload) {
  return p5Json(token, "PATCH", `/tasks/${taskId}`, payload);
}

export async function listSiteIssues(token, projectId) {
  return p5Json(token, "GET", `/projects/${projectId}/site-issues`);
}

export async function createSiteIssue(token, projectId, payload) {
  return p5Json(token, "POST", `/projects/${projectId}/site-issues`, payload);
}

export async function updateSiteIssue(token, issueId, payload) {
  return p5Json(token, "PATCH", `/site-issues/${issueId}`, payload);
}
