import { expect, test } from "@playwright/test";
import {
  JOB_ROLE,
  QUALIFICATION,
  api,
  addQualification,
  createEmployee,
  createReadyMonteur,
  isoDay,
  unique,
} from "./support/api";
import { closeDialog, createButton, dialog, gotoAs, main, row, section, segment } from "./support/app";

/** A cell in the matrix, addressed by employee row and column header. */
async function cell(page: import("@playwright/test").Page, employee: string, qualification: string) {
  const headers = await page.locator(".ops-matrix thead th").allInnerTexts();
  const index = headers.findIndex((text) => text.trim().toLowerCase() === qualification.toLowerCase());
  expect(index, `Spalte "${qualification}" fehlt in [${headers.join(" | ")}]`).toBeGreaterThan(-1);
  return page
    .locator(".ops-matrix tbody tr")
    .filter({ hasText: employee })
    .locator("td")
    .nth(index);
}

test.describe("Qualifikationsmatrix", () => {
  test("die Matrix zeigt je Anforderung einen Zustand, nicht nur eine Farbe", async ({
    page,
    request,
  }) => {
    const employee = await createEmployee(request, { full_name: unique("E2E Matrix") });
    // Gueltig mit Nachweis, gueltig ohne Nachweis, abgelaufen, fehlt.
    await addQualification(request, employee.id, QUALIFICATION.unterweisung);
    await addQualification(request, employee.id, QUALIFICATION.psaAbsturz, { withDocument: false });
    await addQualification(request, employee.id, QUALIFICATION.ipaf, {
      validUntil: isoDay(-5),
    });
    // Die Spalten sind die Vereinigung ueber alle vorkommenden Funktionen. Der
    // Service-Techniker bringt "Befaehigte Person" mit, die der Monteur nicht
    // braucht - genau der Fall, den die neutrale Markierung abdecken muss.
    await createEmployee(request, {
      full_name: unique("E2E Matrix Techniker"),
      job_role_id: JOB_ROLE.serviceTechniker,
    });

    await gotoAs(page, "qualifikationen");

    await expect(await cell(page, employee.full_name, "Jaehrliche Unterweisung")).toHaveText("OK");
    await expect(await cell(page, employee.full_name, "PSA gegen Absturz")).toHaveText("?");
    await expect(await cell(page, employee.full_name, "IPAF-Bedienerschulung")).toHaveText("X");
    await expect(await cell(page, employee.full_name, "Arbeitsmedizinische Vorsorge")).toHaveText("-");

    // Nicht geforderte Anforderungen sind neutral, nicht rot.
    const notRequired = await cell(page, employee.full_name, "Befaehigte Person zur Pruefung");
    await expect(notRequired).toHaveText("·");
    await expect(notRequired.locator(".ops-mark")).toHaveClass(/ops-mark--muted/);

    await expect(
      page.locator(".ops-matrix tbody tr").filter({ hasText: employee.full_name })
    ).toContainText("nicht einsatzfaehig");
  });

  test("der Ausschnitt zeigt nur Personen mit Luecken", async ({ page, request }) => {
    const complete = await createReadyMonteur(request, { full_name: unique("E2E Matrix Voll") });
    const incomplete = await createEmployee(request, { full_name: unique("E2E Matrix Luecke") });

    await gotoAs(page, "qualifikationen");
    await segment(page, "Nicht einsatzfaehig").click();

    await expect(page.locator(".ops-matrix tbody tr").filter({ hasText: incomplete.full_name })).toHaveCount(1);
    await expect(page.locator(".ops-matrix tbody tr").filter({ hasText: complete.full_name })).toHaveCount(0);

    await main(page).getByPlaceholder("Name oder Funktion").fill(complete.full_name);
    await expect(page.locator(".ops-matrix tbody tr")).toHaveCount(0);
  });
});

test.describe("Stammdaten", () => {
  test("eine neue Qualifikationsart landet im Katalog", async ({ page, request }) => {
    const name = unique("E2E Schein");
    const code = `e2e_${Date.now().toString(36)}`;

    await gotoAs(page, "stammdaten");
    await createButton(page, "Qualifikationsart").click();
    await dialog(page).getByLabel("Bezeichnung").fill(name);
    await dialog(page).getByLabel("Kuerzel").fill(code);
    await dialog(page).getByLabel("Kategorie").selectOption("training");
    await dialog(page).getByLabel("Gueltigkeit in Monaten").fill("18");
    await dialog(page).getByLabel("Vorwarnung in Tagen").fill("45");
    await dialog(page).getByLabel("Rechtsgrundlage").fill("DGUV Vorschrift 68");
    await dialog(page).getByRole("button", { name: "Speichern" }).click();

    await expect(dialog(page)).toHaveCount(0);
    const created = row(section(page, "Qualifikationsarten"), name);
    await expect(created).toContainText("18 Monate");
    await expect(created).toContainText("45 Tage");
    await expect(created).toContainText("DGUV Vorschrift 68");

    const types = await api.get<{ code: string; validity_months: number }[]>(
      request,
      "/api/qualification-types"
    );
    expect(types.find((item) => item.code === code)?.validity_months).toBe(18);
  });

  test("eine Anforderung umzustellen aendert die Einsatzfaehigkeit sofort", async ({
    page,
    request,
  }) => {
    const employee = await createReadyMonteur(request, { full_name: unique("E2E Anforderung") });
    expect((await api.get<{ readiness: string }>(request, `/api/employees/${employee.id}`)).readiness).toBe(
      "ready"
    );

    await gotoAs(page, "stammdaten");
    await row(section(page, "Funktionen und ihre Anforderungen"), "Monteur").click();
    await expect(dialog(page)).toContainText("Anforderungen: Monteur");

    // Erste-Hilfe ist beim Monteur optional; als Pflicht fehlt sie sofort.
    const requirement = dialog(page)
      .locator(".pds-table__row")
      .filter({ hasText: "Erste-Hilfe-Ausbildung" });
    await expect(requirement.locator("select")).toHaveValue("optional");
    await requirement.locator("select").selectOption("mandatory");
    await expect(requirement.locator("select")).toHaveValue("mandatory");

    await expect
      .poll(async () =>
        (await api.get<{ readiness: string }>(request, `/api/employees/${employee.id}`)).readiness
      )
      .toBe("blocked");

    // Zuruecksetzen, damit der Katalog fuer die uebrigen Tests unveraendert bleibt.
    await requirement.locator("select").selectOption("optional");
    await expect
      .poll(async () =>
        (await api.get<{ readiness: string }>(request, `/api/employees/${employee.id}`)).readiness
      )
      .toBe("ready");
    await closeDialog(page);
  });

  test("die Funktionsliste zeigt Pflicht und optional getrennt", async ({ page }) => {
    await gotoAs(page, "stammdaten");
    const monteur = row(section(page, "Funktionen und ihre Anforderungen"), "Monteur");

    await expect(monteur).toContainText("IPAF-Bedienerschulung");
    await expect(monteur).toContainText("Fuehrerscheinkontrolle (optional)");
    await expect(monteur.locator(".pds-pill--info").filter({ hasText: "IPAF" })).toHaveCount(1);
  });

  test("eine benutzte Qualifikationsart laesst sich nicht entfernen", async ({ page }) => {
    await gotoAs(page, "stammdaten");
    const catalogue = section(page, "Qualifikationsarten");
    await row(catalogue, "IPAF-Bedienerschulung").getByRole("button", { name: /entfernen$/ }).click();
    await dialog(page).getByRole("button", { name: "Entfernen", exact: true }).click();

    await expect(main(page).locator(".pds-banner--danger")).toContainText("requirement");
    await expect(row(catalogue, "IPAF-Bedienerschulung")).toHaveCount(1);
  });
});
