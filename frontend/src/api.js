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
