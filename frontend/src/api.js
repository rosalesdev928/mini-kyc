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
