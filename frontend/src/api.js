// Thin client for the backend REST API. Errors are normalized to { code, message }.

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  constructor(code, message, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function parseResponse(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    // Non-JSON body (for example a proxy error page).
  }
  if (response.ok) return body;

  const error = body?.error;
  throw new ApiError(error?.code ?? "UNKNOWN", error?.message ?? "Unexpected error.", response.status);
}

async function request(path, options) {
  try {
    const response = await fetch(`${API_BASE}${path}`, options);
    return await parseResponse(response);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError("NETWORK", "The server could not be reached.", 0);
  }
}

/** Health check used to detect a sleeping server (free hosting). `signal` lets the caller cancel it. */
export function getHealth(signal) {
  return request("/api/v1/health", { signal });
}

export function listByEmail(email) {
  return request(`/api/v1/onboarding?email=${encodeURIComponent(email)}`);
}

// ---- operator review (protected with the X-Review-Key header) ----

export function listPendingReviews(key) {
  return request("/api/v1/reviews/pending", { headers: { "X-Review-Key": key } });
}

export function reviewRecord(key, id, { decision, reviewer, comment }) {
  return request(`/api/v1/reviews/${id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Review-Key": key },
    body: JSON.stringify({ decision, reviewer, comment: comment || null }),
  });
}

// ---- admin dashboard (same X-Review-Key secret) ----

function adminHeaders(key) {
  return { "X-Review-Key": key };
}

function filterQuery({ status, q, dateFrom, dateTo }) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (q) params.set("q", q);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  return params;
}

export function adminOverview(key) {
  return request("/api/v1/admin/overview", { headers: adminHeaders(key) });
}

export function adminSearch(key, filters, { limit, offset }) {
  const params = filterQuery(filters);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return request(`/api/v1/admin/onboardings?${params}`, { headers: adminHeaders(key) });
}

export function adminDetail(key, id) {
  return request(`/api/v1/admin/onboardings/${id}`, { headers: adminHeaders(key) });
}

export function adminAnonymize(key, id, { reviewer, reason }) {
  return request(`/api/v1/admin/onboardings/${id}/anonymize`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...adminHeaders(key) },
    body: JSON.stringify({ reviewer, reason: reason || null }),
  });
}

/** Downloads the filtered records as a CSV file (the browser needs a Blob because of the secret header). */
export async function adminExportCsv(key, filters) {
  let response;
  try {
    response = await fetch(`${API_BASE}/api/v1/admin/export.csv?${filterQuery(filters)}`, {
      headers: adminHeaders(key),
    });
  } catch {
    throw new ApiError("NETWORK", "The server could not be reached.", 0);
  }
  if (!response.ok) await parseResponse(response); // throws the normalized error
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "onboardings.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function createOnboarding({ email, file }) {
  const form = new FormData();
  form.append("email", email);
  form.append("document", file);
  return request("/api/v1/onboarding", { method: "POST", body: form });
}

export function askChatbot(question) {
  return request("/api/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}
