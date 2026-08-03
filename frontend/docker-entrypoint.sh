#!/bin/sh
# Run by the nginx image from /docker-entrypoint.d/ before the server starts.
# It must not exec the CMD; the nginx entrypoint does that itself afterwards.
set -eu

# Vite inlines VITE_* variables at build time, which would tie a published image
# to one API URL. config.js is rewritten on every container start instead, so
# the same image works in any environment.
cat > /usr/share/nginx/html/config.js <<CONFIG
window.__OPS_CONFIG__ = {
  apiBaseUrl: "${API_BASE_URL:-}",
  authMode: "${AUTH_MODE:-dev}",
  azureTenantId: "${AZURE_TENANT_ID:-}",
  azureClientId: "${AZURE_CLIENT_ID:-}",
  azureApiScope: "${AZURE_API_SCOPE:-}"
};
CONFIG

echo "ops-frontend: runtime config written (api=${API_BASE_URL:-<same host:8000>}, auth=${AUTH_MODE:-dev})"
