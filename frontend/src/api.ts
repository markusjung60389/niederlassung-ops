import { getAuthHeaders } from "./auth";

export const API_BASE =
  import.meta.env.VITE_API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8000`;

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }

  get isAuthError(): boolean {
    return this.status === 401 || this.status === 403;
  }
}

type ValidationIssue = { loc?: (string | number)[]; msg?: string };

/** FastAPI returns `detail` as a string, or as a list of issues for 422. */
function describe(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const issues = (detail as ValidationIssue[])
      .map((issue) => {
        const field = (issue.loc ?? []).filter((part) => part !== "body").join(".");
        return field ? `${field}: ${issue.msg ?? "ungueltig"}` : issue.msg ?? "ungueltig";
      })
      .filter(Boolean);
    if (issues.length) return issues.join("; ");
  }
  if (status === 401) return "Nicht angemeldet.";
  if (status === 403) return "Keine Berechtigung fuer diese Aktion.";
  return `HTTP ${status}`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { ...(await getAuthHeaders()), ...(init.headers ?? {}) },
    });
  } catch (cause) {
    throw new ApiError(0, `Backend nicht erreichbar: ${cause instanceof Error ? cause.message : cause}`);
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }

  if (!response.ok) throw new ApiError(response.status, describe(response.status, body ?? text));
  return body as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function apiPost<T>(path: string, payload: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function apiPatch<T>(path: string, payload: unknown): Promise<T> {
  return request<T>(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Unbekannter Fehler";
}
