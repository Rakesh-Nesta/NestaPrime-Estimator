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

export async function updateClientFlags(token, clientId, payload) {
  const res = await fetch(`${API_BASE}/clients/${clientId}`, {
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

export async function rejectQuotation(token, quotationId, payload) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/reject`, {
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

export async function createMessage(token, { docType, docId, channel, recipient, templateKey, subject, bodyNote, attachmentId }) {
  const res = await fetch(`${API_BASE}/messages`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({
      doc_type: docType,
      doc_id: docId,
      channel,
      recipient,
      template_key: templateKey || null,
      subject: subject || null,
      body_note: bodyNote || null,
      attachment_id: attachmentId || null,
    }),
  });
  return handle(res);
}

export async function uploadAttachment(token, { docType, docId, tag, approvalStrength, signatoryName, signatoryDesignation, file }) {
  const formData = new FormData();
  formData.append("doc_type", docType);
  formData.append("doc_id", docId);
  formData.append("tag", tag);
  if (approvalStrength) formData.append("approval_strength", approvalStrength);
  if (signatoryName) formData.append("signatory_name", signatoryName);
  if (signatoryDesignation) formData.append("signatory_designation", signatoryDesignation);
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

// --- Part M.6: client-facing Estimate / Quotation PDFs ---

export async function downloadEstimatePdfBlob(token, estimateId) {
  const res = await fetch(`${API_BASE}/estimates/${estimateId}/pdf`, { headers: authHeaders(token) });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `PDF generation failed (${res.status})`);
  }
  return res.blob();
}

export async function downloadQuotationPdfBlob(token, quotationId) {
  const res = await fetch(`${API_BASE}/quotations/${quotationId}/pdf`, { headers: authHeaders(token) });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `PDF generation failed (${res.status})`);
  }
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
