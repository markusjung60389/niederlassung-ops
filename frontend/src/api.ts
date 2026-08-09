import { elevate, getAuthHeaders } from "./auth";
import { API_BASE } from "./runtimeConfig";

export { API_BASE };

export class ApiError extends Error {
  readonly status: number;
  /**
   * Set when the backend wants a stronger token before it answers.
   *
   * The claims request Entra ID has to satisfy - MSAL passes it straight
   * through, which is why it travels as an opaque string.
   */
  readonly claimsChallenge: string | null;

  constructor(status: number, message: string, claimsChallenge: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.claimsChallenge = claimsChallenge;
  }

  get isAuthError(): boolean {
    return this.status === 401 || this.status === 403;
  }

  get needsStepUp(): boolean {
    return this.claimsChallenge !== null;
  }
}

type ValidationIssue = { loc?: (string | number)[]; msg?: string };

/** The step-up challenge, when the answer carried one. */
function stepUpChallenge(body: unknown): string | null {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === "object" && "claims_challenge" in detail) {
    return String((detail as { claims_challenge?: unknown }).claims_challenge ?? "") || null;
  }
  return null;
}

/** FastAPI returns `detail` as a string, or as a list of issues for 422. */
function describe(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "detail" in detail) {
    return String((detail as { detail?: unknown }).detail);
  }
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

async function request<T>(path: string, init: RequestInit = {}, elevated = false): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { ...(await getAuthHeaders(elevated)), ...(init.headers ?? {}) },
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

  if (!response.ok) {
    throw new ApiError(response.status, describe(response.status, body ?? text), stepUpChallenge(body));
  }
  return body as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

/**
 * A request that may need the extra confirmation, retried once after it.
 *
 * The backend answers 401 with a claims challenge; MSAL turns that into a
 * fresh sign-in prompt and a token that says the authentication context was
 * satisfied. The retry then goes through with it.
 */
export async function apiStepUp<T>(
  path: string,
  init: RequestInit = {},
  onPrompt?: () => void
): Promise<T> {
  try {
    return await request<T>(path, init, true);
  } catch (caught) {
    if (!(caught instanceof ApiError) || !caught.needsStepUp) throw caught;
    onPrompt?.();
    await elevate(caught.claimsChallenge as string);
    return request<T>(path, init, true);
  }
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

export function apiDelete(path: string): Promise<void> {
  return request<void>(path, { method: "DELETE" });
}

/** Multipart upload. The Content-Type header is left to the browser so the
 *  multipart boundary is set correctly. */
export function apiUpload<T>(path: string, form: FormData): Promise<T> {
  return request<T>(path, { method: "POST", body: form });
}

/** Download a protected file: fetched with auth headers, then handed to the browser. */
export async function downloadFile(path: string, fileName: string): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, { headers: await getAuthHeaders() });
  if (!response.ok) throw new ApiError(response.status, describe(response.status, null));
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Unbekannter Fehler";
}
