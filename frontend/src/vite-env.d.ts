/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_AUTH_MODE?: "dev" | "azure_ad";
  readonly VITE_AZURE_TENANT_ID?: string;
  readonly VITE_AZURE_CLIENT_ID?: string;
  readonly VITE_AZURE_API_SCOPE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
