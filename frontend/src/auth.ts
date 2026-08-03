/**
 * Identity handling for the Ops frontend.
 *
 * Two modes, mirroring the backend AUTH_MODE setting:
 *
 *   "dev"      - the user picks an identity from /api/auth/dev-users and it is
 *                sent as the X-User-Id header. Local and test use only.
 *   "azure_ad" - an MSAL access token is sent as a bearer token.
 *
 * The Azure AD branch is wired up but intentionally not activated: enabling it
 * needs the MSAL dependency and an app registration. See docs/azure-ad-setup.md
 * for the exact steps, they are deliberately kept in one place.
 */

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
};

const DEV_USER_STORAGE_KEY = "remscheid-ops.dev-user-id";

export function getDevUserId(): string | null {
  try {
    return window.localStorage.getItem(DEV_USER_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setDevUserId(userId: string): void {
  try {
    window.localStorage.setItem(DEV_USER_STORAGE_KEY, userId);
  } catch {
    /* storage unavailable (private mode): the picker still works for this session */
  }
}

/**
 * Returns an Entra ID access token for the backend API.
 *
 * To go live:
 *   1. npm install @azure/msal-browser
 *   2. Replace the body below with:
 *
 *        import { PublicClientApplication } from "@azure/msal-browser";
 *        const msal = new PublicClientApplication({
 *          auth: { clientId: AZURE_CONFIG.clientId, authority: AZURE_CONFIG.authority,
 *                  redirectUri: window.location.origin },
 *          cache: { cacheLocation: "sessionStorage" },
 *        });
 *        await msal.initialize();
 *        const account = msal.getAllAccounts()[0]
 *          ?? (await msal.loginPopup({ scopes: [AZURE_CONFIG.apiScope] })).account;
 *        const result = await msal.acquireTokenSilent({ scopes: [AZURE_CONFIG.apiScope], account });
 *        return result.accessToken;
 *
 *   3. Set VITE_AUTH_MODE=azure_ad and the VITE_AZURE_* variables at build time.
 *   4. Switch the backend to AUTH_MODE=azure_ad.
 */
export async function acquireAccessToken(): Promise<string> {
  throw new Error(
    "Azure AD sign-in is prepared but not enabled. Follow docs/azure-ad-setup.md, then set VITE_AUTH_MODE=azure_ad."
  );
}

/** Headers identifying the caller, for every request against the API. */
export async function getAuthHeaders(): Promise<Record<string, string>> {
  if (AUTH_MODE === "azure_ad") {
    return { Authorization: `Bearer ${await acquireAccessToken()}` };
  }
  const userId = getDevUserId();
  return userId ? { "X-User-Id": userId } : {};
}
