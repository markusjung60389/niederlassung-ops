import { expect, test } from "@playwright/test";
import {
  QUALIFICATION,
  addQualification,
  createEmployee,
  createRecord,
  createVehicle,
  isoDay,
  unique,
} from "./support/api";
import { gotoAs, main, row, segment } from "./support/app";

/** Reads a metric tile by its label. */
function metric(page: import("@playwright/test").Page, label: string) {
  return page.locator(".ops-metric").filter({ hasText: label });
}

test.describe("Cockpit", () => {
  test("die Kennzahlen bilden den tatsaechlichen Stand ab", async ({ page, request }) => {
    await gotoAs(page, "cockpit");
    const blockedBefore = Number(await metric(page, "Nicht einsatzfaehig").locator("strong").innerText());

    await createEmployee(request, { full_name: unique("E2E Kennzahl") });
    await page.reload();

    await expect(metric(page, "Nicht einsatzfaehig").locator("strong")).toHaveText(
      String(blockedBefore + 1)
    );
    await expect(metric(page, "Nicht einsatzfaehig")).toHaveClass(/is-red/);
  });

  test("die Arbeitsliste trennt ueberfaellig, 30 Tage und spaeter", async ({ page, request }) => {
    const employee = await createEmployee(request, { full_name: unique("E2E Frist") });
    // Abgelaufen, bald faellig und weit in der Zukunft.
    await addQualification(request, employee.id, QUALIFICATION.unterweisung, { validUntil: isoDay(-4) });
    await addQualification(request, employee.id, QUALIFICATION.ipaf, { validUntil: isoDay(20) });
    await addQualification(request, employee.id, QUALIFICATION.arbeitsmedizin, { validUntil: isoDay(50) });

    await gotoAs(page, "cockpit");

    await expect(
      row(page, `${employee.full_name}: Jaehrliche Unterweisung`)
    ).toHaveCount(1);
    await expect(row(page, `${employee.full_name}: Jaehrliche Unterweisung`)).toContainText(
      "ueberfaellig"
    );

    await segment(page, "30 Tage").click();
    await expect(row(page, `${employee.full_name}: IPAF`)).toHaveCount(1);
    await expect(row(page, `${employee.full_name}: Jaehrliche Unterweisung`)).toHaveCount(0);

    await segment(page, "Spaeter").click();
    await expect(row(page, `${employee.full_name}: Arbeitsmedizinische Vorsorge`)).toHaveCount(1);
  });

  test("eine Zeile der Arbeitsliste springt in den zustaendigen Bereich", async ({
    page,
    request,
  }) => {
    const vehicle = await createVehicle(request, { hu_due_date: isoDay(-6) });

    await gotoAs(page, "cockpit");
    await row(page, `${vehicle.license_plate}: HU faellig`).click();

    await expect(page).toHaveURL(/#\/fahrzeuge$/);
    await expect(main(page).getByRole("heading", { level: 1 })).toHaveText("Fahrzeuge");
  });

  test("die Banner nennen den Handlungsbedarf und verlinken ihn", async ({ page, request }) => {
    const driver = await createEmployee(request, { full_name: unique("E2E Banner") });
    await createVehicle(request, { assigned_employee_id: driver.id });

    await gotoAs(page, "cockpit");
    const banners = main(page).locator(".pds-banner--warn");
    await expect(banners.filter({ hasText: "nicht einsatzfaehig" })).toHaveCount(1);
    await expect(banners.filter({ hasText: "Halterhaftung" })).toHaveCount(1);

    await main(page).getByRole("button", { name: "Zur Qualifikationsmatrix" }).click();
    await expect(page).toHaveURL(/#\/qualifikationen$/);
    await expect(main(page).getByRole("heading", { level: 1 })).toHaveText("Qualifikationsmatrix");
  });

  test("die Ersthelferquote wird gegen die Mindestzahl gestellt", async ({ page, request }) => {
    // Ab drei Beschaeftigten verlangt DGUV Vorschrift 1 mindestens einen.
    for (let index = 0; index < 3; index += 1) {
      await createEmployee(request, { full_name: unique("E2E Quote"), first_aider: true });
    }

    await gotoAs(page, "cockpit");
    const readiness = main(page).locator(".ops-section").filter({ hasText: "Einsatzfaehigkeit" });
    await expect(readiness).toContainText("Ersthelfer");
    await expect(readiness).toContainText("erforderlich");
  });

  test("ueberfaellige Compliance schlaegt in der Kachel und der Navigation durch", async ({
    page,
    request,
  }) => {
    await createRecord(request, {
      title: unique("E2E Cockpit Pflicht"),
      due_date: isoDay(-15),
      review_date: isoDay(-15),
    });

    await gotoAs(page, "cockpit");
    const overdue = metric(page, "Compliance ueberfaellig");
    await expect(overdue).toHaveClass(/is-red/);
    expect(Number(await overdue.locator("strong").innerText())).toBeGreaterThanOrEqual(1);

    // Der Zaehler an der Navigation zaehlt die ueberfaelligen Erinnerungen.
    await expect(page.locator(".pds-nav__count")).toBeVisible();
  });
});
