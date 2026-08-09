/**
 * Writes `dist/config.js` the way the container entrypoint does.
 *
 * Keeping the shapes identical means the E2E run exercises the real
 * runtime-config path instead of the build-time VITE_* fallback.
 */

import { writeFileSync } from "node:fs";
import { resolve } from "node:path";

const apiBaseUrl = process.argv[2];
if (!apiBaseUrl) {
  console.error("usage: node e2e/support/write-config.mjs <api-base-url>");
  process.exit(1);
}

const target = resolve("dist/config.js");
writeFileSync(
  target,
  `window.__OPS_CONFIG__ = ${JSON.stringify(
    { apiBaseUrl, authMode: "dev", azureTenantId: "", azureClientId: "", azureApiScope: "" },
    null,
    2
  )};\n`
);

console.log(`wrote ${target} -> ${apiBaseUrl}`);
