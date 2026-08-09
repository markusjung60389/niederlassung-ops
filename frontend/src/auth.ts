/**
 * Identity handling for the Ops frontend.
 *
 * Three ways in, mirroring the backend:
 *
 *   "azure_ad" - Microsoft Entra ID through MSAL. The normal way in.
 *   "password" - e-mail and password against /api/auth/login, valid in both
 *                modes. The emergency door: if Entra ID is unreachable or an
 *                app registration is broken, somebody still has to get in.
 *   "dev"      - the identity is picked from /api/auth/dev-users and sent as
 *                X-User-Id. Local and test use only; the backend refuses it
 *                when APP_ENV is production.
 *
 * A session token, once obtained, wins over the dev identity: whoever signed in
 * with a password is that person until they sign out.
 */

import type { AccountInfo, IPublicClientApplication } from "@azure/msal-browser";
import { AUTH_MODE as RESOLVED_AUTH_MODE, AZURE_API_SCOPE, AZURE_CLIENT_ID, AZURE_TENANT_ID } from "./runtimeConfig";

export type AuthMode = "dev" | "azure_ad";

export const AUTH_MODE: AuthMode = RESOLVED_AUTH_MODE;

export const AZURE_CONFIG = {
  tenantId: AZURE_TENANT_ID,
  clientId: AZURE_CLIENT_ID,
  // Scope exposed by the backend app registration, e.g. "api://<api-client-id>/access_as_user".
  apiScope: AZURE_API_SCOPE,
  get authority() {
    return `https://login.microsoftonline.com/${this.tenantId}`;
  },
  get configured() {
    return Boolean(this.tenantId && this.clientId && this.apiScope);
  },
};

const DEV_USER_STORAGE_KEY = "remscheid-ops.dev-user-id";
const SESSION_STORAGE_KEY = "remscheid-ops.session";
// Set by signing out. Without it, the development mode would immediately pick
// an identity again and the sign-in screen would be unreachable there.
const SIGNED_OUT_KEY = "remscheid-ops.signed-out";

type StoredSession = { token: string; expiresAt: string };

function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode): the session lasts for this page */
  }
}

export function getDevUserId(): string | null {
  return readStorage(DEV_USER_STORAGE_KEY);
}

export function setDevUserId(userId: string): void {
  writeStorage(DEV_USER_STORAGE_KEY, userId);
  writeStorage(SIGNED_OUT_KEY, null);
}

export function isSignedOut(): boolean {
  return readStorage(SIGNED_OUT_KEY) === "1";
}

export function clearSignedOut(): void {
  writeStorage(SIGNED_OUT_KEY, null);
}

/** The stored password session, or null once it has expired. */
export function getSession(): StoredSession | null {
  const raw = readStorage(SESSION_STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredSession;
    // An expired token would only produce 401s; dropping it here sends the
    // user to the login form instead of to an error.
    if (!parsed.token || new Date(parsed.expiresAt).getTime() <= Date.now()) {
      writeStorage(SESSION_STORAGE_KEY, null);
      return null;
    }
    return parsed;
  } catch {
    writeStorage(SESSION_STORAGE_KEY, null);
    return null;
  }
}

export function setSession(session: StoredSession | null): void {
  writeStorage(SESSION_STORAGE_KEY, session ? JSON.stringify(session) : null);
  if (session) writeStorage(SIGNED_OUT_KEY, null);
}

/* --------------------------------------------------------------------------
 * Microsoft Entra ID
 * ----------------------------------------------------------------------- */

let msalPromise: Promise<IPublicClientApplication> | null = null;

/**
 * Creates the MSAL client once, lazily.
 *
 * Lazily because the password login must keep working when Entra ID is
 * misconfigured - constructing the client eagerly would throw during startup
 * and take the login screen down with it.
 */
async function getMsal(): Promise<IPublicClientApplication> {
  if (!AZURE_CONFIG.configured) {
    throw new Error(
      "Microsoft-Anmeldung ist nicht konfiguriert (Mandant, Client-ID oder Scope fehlen)."
    );
  }
  if (!msalPromise) {
    msalPromise = (async () => {
      const { PublicClientApplication } = await import("@azure/msal-browser");
      const instance = new PublicClientApplication({
        auth: {
          clientId: AZURE_CONFIG.clientId,
          authority: AZURE_CONFIG.authority,
          redirectUri: window.location.origin,
        },
        // sessionStorage, not localStorage: the token dies with the tab, which
        // is what a shared workstation needs.
        cache: { cacheLocation: "sessionStorage" },
      });
      await instance.initialize();
      return instance;
    })();
  }
  return msalPromise;
}

function activeAccount(instance: IPublicClientApplication): AccountInfo | null {
  return instance.getActiveAccount() ?? instance.getAllAccounts()[0] ?? null;
}

export function hasAzureSession(): boolean {
  try {
    return Boolean(window.sessionStorage.getItem(`msal.${AZURE_CONFIG.clientId}.active-account`));
  } catch {
    return false;
  }
}

/** Opens the Microsoft sign-in popup. Resolves once an account is present. */
export async function signInWithAzure(): Promise<void> {
  const instance = await getMsal();
  const result = await instance.loginPopup({ scopes: [AZURE_CONFIG.apiScope] });
  if (result.account) instance.setActiveAccount(result.account);
}

/**
 * Returns an Entra ID access token for the backend API.
 *
 * Silent first; only an expired refresh token opens a popup, so the normal
 * request path never interrupts anybody.
 */
export async function acquireAccessToken(): Promise<string> {
  const instance = await getMsal();
  const account = activeAccount(instance);
  if (!account) throw new Error("Nicht bei Microsoft angemeldet.");
  try {
    const result = await instance.acquireTokenSilent({ scopes: [AZURE_CONFIG.apiScope], account });
    return result.accessToken;
  } catch {
    const result = await instance.acquireTokenPopup({ scopes: [AZURE_CONFIG.apiScope], account });
    return result.accessToken;
  }
}

/* --------------------------------------------------------------------------
 * Step-up for pay data
 * ----------------------------------------------------------------------- */

let elevatedToken: { token: string; expiresAt: number } | null = null;

/**
 * Answers a claims challenge with a stronger token.
 *
 * Entra ID runs whatever the Conditional Access policy behind the requested
 * authentication context demands - in practice a fresh confirmation in the
 * Authenticator app. The result is kept in memory only: it must not outlive
 * the tab, and it is never the token the rest of the application uses.
 */
export async function elevate(claimsChallenge: string): Promise<void> {
  const instance = await getMsal();
  const account = activeAccount(instance);
  const result = await instance.acquireTokenPopup({
    scopes: [AZURE_CONFIG.apiScope],
    account: account ?? undefined,
    claims: window.atob(claimsChallenge),
  });
  elevatedToken = {
    token: result.accessToken,
    expiresAt: result.expiresOn ? result.expiresOn.getTime() : Date.now() + 5 * 60_000,
  };
}

export function isElevated(): boolean {
  return elevatedToken !== null && elevatedToken.expiresAt > Date.now();
}

/** Drops the elevated token, e.g. when the pay section is closed again. */
export function dropElevation(): void {
  elevatedToken = null;
}

export async function signOutAzure(): Promise<void> {
  if (!AZURE_CONFIG.configured || !msalPromise) return;
  const instance = await getMsal();
  const account = activeAccount(instance);
  if (account) await instance.logoutPopup({ account });
}

/* --------------------------------------------------------------------------
 * Request headers
 * ----------------------------------------------------------------------- */

/**
 * Headers identifying the caller, for every request against the API.
 *
 * `elevated` asks for the stronger token obtained through `elevate()`. There is
 * no fallback to the ordinary one: a request that needs the second
 * confirmation should be answered with 401 and a challenge, not quietly with
 * the weaker identity.
 */
export async function getAuthHeaders(elevated = false): Promise<Record<string, string>> {
  if (elevated && isElevated()) {
    return { Authorization: `Bearer ${(elevatedToken as { token: string }).token}` };
  }
  const session = getSession();
  if (session) return { Authorization: `Bearer ${session.token}` };

  if (AUTH_MODE === "azure_ad") {
    return { Authorization: `Bearer ${await acquireAccessToken()}` };
  }
  const userId = getDevUserId();
  return userId ? { "X-User-Id": userId } : {};
}

/** Drops every local trace of the signed-in identity. */
export function forgetIdentity(): void {
  elevatedToken = null;
  writeStorage(SESSION_STORAGE_KEY, null);
  writeStorage(DEV_USER_STORAGE_KEY, null);
  writeStorage(SIGNED_OUT_KEY, "1");
}
