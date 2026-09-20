const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

async function request(path, options = {}, token = null) {
  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    ...options,
  });
  const body = await response.json();
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : "Request failed";
    throw new Error(detail);
  }
  return body;
}

export const api = {
  get: (path, token) => request(path, {}, token),
  post: (path, body, token) =>
    request(path, { method: "POST", body: JSON.stringify(body) }, token),
  patch: (path, body, token) =>
    request(path, { method: "PATCH", body: JSON.stringify(body) }, token),
};
