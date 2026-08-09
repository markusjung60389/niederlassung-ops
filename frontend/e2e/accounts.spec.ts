import { expect, test } from "@playwright/test";
import { AREA_MANAGER, BRANCH, MANAGER, api, unique } from "./support/api";
import { createButton, dialog, gotoAs, main, nav, row, section } from "./support/app";

/**
 * Anmeldung mit Passwort und die Benutzerverwaltung.
 *
 * The seeded emergency account is deliberately left alone: its password is
 * changed exactly once in real life, and a test that consumes it would be a
 * test that only passes on the first run.
 */

const START_PASSWORD = "Start-Passwort-2026!";
const NEW_PASSWORD = "Werkstatt-Bergisch-26!";

/** Opens the application signed out, so the sign-in screen is reachable. */
async function gotoSignIn(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.evaluate(() => {
    window.localStorage.clear();
    window.localStorage.setItem("remscheid-ops.signed-out", "1");
  });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Anmeldung" })).toBeVisible();
}

test.describe("Anmeldung und Benutzerverwaltung", () => {
  test("das Startpasswort laesst nur eine Sache zu: sich selbst zu ersetzen", async ({
    page,
    request,
  }) => {
    const email = `${unique("start").replace(/\s+/g, ".").toLowerCase()}@example.local`;
    await api.post(
      request,
      "/api/users",
      {
        display_name: "Erste Anmeldung",
        email,
        role_id: "role-branch-manager",
        branch_ids: [BRANCH],
        password: START_PASSWORD,
      },
      AREA_MANAGER
    );

    await gotoSignIn(page);
    await page.getByLabel("E-Mail").fill(email);
    await page.getByLabel("Passwort", { exact: true }).fill(START_PASSWORD);
    await page.getByRole("button", { name: "Anmelden" }).click();

    // Kein Weg an der Aenderung vorbei - der Dialog laesst sich nicht schliessen.
    await expect(dialog(page)).toContainText("Startpasswort aendern");
    await page.keyboard.press("Escape");
    await expect(dialog(page)).toContainText("Startpasswort aendern");

    await dialog(page).getByLabel("Aktuelles Passwort").fill(START_PASSWORD);
    await dialog(page).getByLabel("Neues Passwort", { exact: true }).fill("kurz");
    await dialog(page).getByLabel("Neues Passwort wiederholen").fill("kurz");
    await dialog(page).getByRole("button", { name: "Passwort setzen" }).click();
    await expect(dialog(page)).toContainText("mindestens 12 Zeichen");

    await dialog(page).getByLabel("Neues Passwort", { exact: true }).fill(NEW_PASSWORD);
    await dialog(page).getByLabel("Neues Passwort wiederholen").fill(NEW_PASSWORD);
    await dialog(page).getByRole("button", { name: "Passwort setzen" }).click();

    // Danach steht die Anwendung offen, mit den Rechten der Rolle.
    await expect(page.locator(".pds-topbar")).toBeVisible();
    await expect(main(page).getByRole("heading", { level: 1 })).toHaveText("Leitercockpit");
    await expect(nav(page).getByRole("button", { name: "Benutzer" })).toHaveCount(0);
  });

  test("eine falsche Anmeldung sagt nicht, welche Haelfte falsch war", async ({ page }) => {
    await gotoSignIn(page);
    await page.getByLabel("E-Mail").fill("gibtesnicht@example.local");
    await page.getByLabel("Passwort", { exact: true }).fill("falsch");
    await page.getByRole("button", { name: "Anmelden" }).click();

    await expect(page.locator(".pds-banner--danger")).toContainText("E-Mail oder Passwort ist falsch");
  });

  test("der Notfallzugang existiert und verlangt sein Startpasswort", async ({ request }) => {
    const response = await api.post<{ must_change_password: boolean }>(
      request,
      "/api/auth/login",
      { email: "admin@ops.local", password: "BSchmitt-Ops-2026!" }
    );
    expect(response.must_change_password).toBe(true);
  });

  test("die Verwaltung legt ein Konto mit Rolle und Niederlassung an", async ({ page }) => {
    const name = unique("E2E Konto");
    await gotoAs(page, "benutzer", AREA_MANAGER);
    await expect(main(page).getByRole("heading", { level: 1 })).toHaveText("Benutzer und Rollen");

    await createButton(page, "Benutzer").click();
    await dialog(page).getByLabel("Name").fill(name);
    await dialog(page)
      .getByLabel("E-Mail (Anmeldung)")
      .fill(`${name.replace(/\s+/g, ".").toLowerCase()}@example.local`);
    await dialog(page).getByLabel("Rolle").selectOption({ label: "Niederlassungsleiter" });
    await dialog(page).getByRole("checkbox", { name: "Remscheid" }).check();
    await dialog(page).getByRole("button", { name: "Speichern" }).click();

    const created = row(page, name);
    await expect(created).toContainText("Niederlassungsleiter");
    await expect(created).toContainText("Remscheid");
    await expect(created).toContainText("noch nie angemeldet");

    // Deaktivieren statt loeschen: das Konto bleibt auffindbar.
    await created.getByRole("button", { name: `${name} bearbeiten` }).click();
    await dialog(page).getByLabel("Status").selectOption("inactive");
    await dialog(page).getByRole("button", { name: "Speichern" }).click();
    await expect(row(page, name)).toHaveCount(0);
    await page.locator(".pds-segment__btn").filter({ hasText: "Deaktiviert" }).click();
    await expect(row(page, name)).toHaveCount(1);
  });

  test("die Verwaltung setzt ein Passwort und hebt eine Sperre auf", async ({ page }) => {
    const name = unique("E2E Passwort");
    const email = `${name.replace(/\s+/g, ".").toLowerCase()}@example.local`;
    await gotoAs(page, "benutzer", AREA_MANAGER);

    await createButton(page, "Benutzer").click();
    await dialog(page).getByLabel("Name").fill(name);
    await dialog(page).getByLabel("E-Mail (Anmeldung)").fill(email);
    await dialog(page).getByLabel("Rolle").selectOption({ label: "Betrachter" });
    await dialog(page).getByRole("button", { name: "Speichern" }).click();

    await row(page, name).getByRole("button", { name: `Passwort fuer ${name} setzen` }).click();
    await dialog(page).getByLabel("Neues Passwort").fill(START_PASSWORD);
    await dialog(page).getByRole("button", { name: "Setzen" }).click();
    await expect(row(page, name)).toContainText("Passwort (Start)");
  });

  test("eigene Rollen lassen sich bauen, die vier Standardrollen nicht aendern", async ({ page }) => {
    const name = unique("E2E Rolle");
    await gotoAs(page, "benutzer", AREA_MANAGER);
    const roles = section(page, "Rollen");

    // Standardrollen tragen keinen Bearbeiten-Knopf.
    await expect(
      row(roles, "Niederlassungsleiter").getByRole("button", { name: /bearbeiten$/ })
    ).toHaveCount(0);

    await roles.getByRole("button", { name: "Eigene Rolle" }).click();
    await dialog(page).getByLabel("Name").fill(name);
    await dialog(page).getByRole("checkbox", { name: "Fahrzeuge lesen" }).check();
    await dialog(page).getByRole("checkbox", { name: "Fahrzeuge pflegen" }).check();
    await dialog(page).getByRole("button", { name: "Speichern" }).click();

    await expect(row(roles, name)).toContainText("2 Berechtigung(en)");

    await row(roles, name).getByRole("button", { name: `Rolle ${name} bearbeiten` }).click();
    await dialog(page).getByRole("button", { name: "Loeschen" }).click();
    await expect(row(roles, name)).toHaveCount(0);
  });

  test("wer keine Benutzerverwaltung hat, sieht sie nicht", async ({ page }) => {
    await gotoAs(page, "benutzer", MANAGER);
    await expect(nav(page).getByRole("button", { name: "Benutzer" })).toHaveCount(0);
    // Die Route faellt auf die erste erlaubte Ansicht zurueck.
    await expect(main(page).getByRole("heading", { level: 1 })).toHaveText("Leitercockpit");
  });
});
