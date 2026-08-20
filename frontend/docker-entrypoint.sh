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

# `connect-src` has to name the API host and, under Entra ID, the Microsoft
# login endpoint MSAL calls directly from the browser - both only known once
# API_BASE_URL and AUTH_MODE are set, so this is written here rather than
# baked into nginx.conf. Included from every `location` block (see
# nginx.conf) rather than declared once at server level, because an
# add_header in a location resets inheritance from its parent.
#
# `frame-src` needs the same Microsoft origin: MSAL's silent token renewal
# (acquireTokenSilent) opens it in a hidden iframe, not just a fetch - without
# this the renewal fails closed and every expiry forces an interactive login.
azure_src=""
if [ "${AUTH_MODE:-dev}" = "azure_ad" ]; then
    azure_src=" https://login.microsoftonline.com"
fi
cat > /etc/nginx/conf.d/security-headers.conf <<HEADERS
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "same-origin" always;
add_header X-Frame-Options "DENY" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; connect-src 'self'${API_BASE_URL:+ $API_BASE_URL}${azure_src}; frame-src 'self'${azure_src}" always;
HEADERS
