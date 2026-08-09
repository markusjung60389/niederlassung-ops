import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests: a real browser against the built frontend and a real
 * backend.
 *
 * Deliberately the production artefact, not the dev server. The frontend is
 * built and served from `dist`, and its backend URL comes from `/config.js` -
 * the same runtime-config path the container entrypoint writes. That path is
 * what silently broke the first live deployment, so it belongs in the test.
 *
 * The backend runs against a throwaway SQLite file that is deleted before
 * every run, so a suite always starts from the same state: migrations applied,
 * catalogue and functions seeded, nothing else.
 */

const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT ?? 8123);
const FRONTEND_PORT = Number(process.env.E2E_FRONTEND_PORT ?? 4173);
const PYTHON = process.env.E2E_PYTHON ?? "python3";

export const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
export const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./.e2e/results",
  // The suite shares one backend and one database. Running it serially keeps
  // the state a test sees the state it created; the whole run takes under two
  // minutes, so parallelism would buy little and cost determinism.
  workers: 1,
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  timeout: 30_000,
  expect: { timeout: 7_000 },

  use: {
    baseURL: FRONTEND_URL,
    locale: "de-DE",
    timezoneId: "Europe/Berlin",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    // CI installs the browser Playwright expects. Set E2E_CHROMIUM to reuse a
    // Chromium that is already on the machine instead of downloading one.
    launchOptions: process.env.E2E_CHROMIUM ? { executablePath: process.env.E2E_CHROMIUM } : {},
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    {
      // The styleguide names iPad landscape as an equal target, not a reduced
      // one. Only the layout-sensitive specs run here.
      name: "tablet",
      testMatch: /(navigation|employees)\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 1024, height: 820 } },
    },
  ],

  webServer: [
    {
      command: [
        "rm -rf .e2e/state",
        "mkdir -p .e2e/state",
        `DATABASE_URL=sqlite:///$(pwd)/.e2e/state/ops.db UPLOADS_DIR=$(pwd)/.e2e/state/uploads`
          + ` AUTH_MODE=dev APP_ENV=test`
          + ` CORS_ALLOW_ORIGINS=${FRONTEND_URL},http://localhost:${FRONTEND_PORT}`
          + ` ${PYTHON} -m uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT}`,
      ].join(" && "),
      cwd: "../backend",
      url: `${BACKEND_URL}/health`,
      reuseExistingServer: false,
      timeout: 90_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command:
        `npm run build && node e2e/support/write-config.mjs ${BACKEND_URL}`
        + ` && npx vite preview --host 127.0.0.1 --port ${FRONTEND_PORT} --strictPort`,
      cwd: ".",
      url: FRONTEND_URL,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
});
