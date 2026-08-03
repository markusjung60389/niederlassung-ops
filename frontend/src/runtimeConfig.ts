/**
 * Configuration resolved at runtime.
 *
 * `config.js` is written by the container entrypoint on every start, so one
 * published image works against any backend URL. During `npm run dev` no such
 * file exists and the build-time VITE_* variables are used instead.
 */

type OpsConfig = {
  apiBaseUrl?: string;
  authMode?: "dev" | "azure_ad";
  azureTenantId?: string;
  azureClientId?: string;
  azureApiScope?: string;
};

declare global {
  interface Window {
    __OPS_CONFIG__?: OpsConfig;
  }
}

const runtime: OpsConfig = (typeof window !== "undefined" && window.__OPS_CONFIG__) || {};

function pick(runtimeValue: string | undefined, buildValue: string | undefined, fallback = ""): string {
  return (runtimeValue || "").trim() || (buildValue || "").trim() || fallback;
}

export const API_BASE = pick(
  runtime.apiBaseUrl,
  import.meta.env.VITE_API_BASE_URL,
  `${window.location.protocol}//${window.location.hostname}:8000`
);

export const AUTH_MODE = pick(runtime.authMode, import.meta.env.VITE_AUTH_MODE, "dev") as
  | "dev"
  | "azure_ad";

export const AZURE_TENANT_ID = pick(runtime.azureTenantId, import.meta.env.VITE_AZURE_TENANT_ID);
export const AZURE_CLIENT_ID = pick(runtime.azureClientId, import.meta.env.VITE_AZURE_CLIENT_ID);
export const AZURE_API_SCOPE = pick(runtime.azureApiScope, import.meta.env.VITE_AZURE_API_SCOPE);
