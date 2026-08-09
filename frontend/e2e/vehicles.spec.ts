import { expect, test } from "@playwright/test";
import {
  QUALIFICATION,
  api,
  addQualification,
  createEmployee,
  createVehicle,
  isoDay,
  unique,
} from "./support/api";
import {
  closeDialog,
  createButton,
  dialog,
  expectRow,
  expectToast,
  gotoAs,
  main,
  row,
  segment,
} from "./support/app";

test.describe("Fahrzeuge", () => {
  test("die Tabelle zeigt Fahrer und Prueffristen mit Ampel", async ({ page, request }) => {
    const driver = await createEmployee(request, { full_name: unique("E2E Fahrer") });
    const vehicle = await createVehicle(request, {
      assigned_employee_id: driver.id,
      hu_due_date: isoDay(-3),
      service_due_date: isoDay(10),
    });

    await gotoAs(page, "fahrzeuge");
    const listed = await expectRow(page, vehicle.license_plate);

    // Die Zuordnung war frueher setzbar und nirgends sichtbar.
    await expect(listed).toContainText(driver.full_name);
    await expect(listed).toContainText("faellig");
    await expect(listed.locator(".ops-date.is-red")).toHaveCount(1);
  });

  test("ein Fahrzeug wird im Dialog angelegt und im Detail vollstaendig gezeigt", async ({ page }) => {
    const plate = unique("RS-NEU").replace(/\s+/g, "-");

    await gotoAs(page, "fahrzeuge");
    await createButton(page, "Fahrzeug").click();
    await dialog(page).getByLabel("Kennzeichen").fill(plate);
    await dialog(page).getByLabel("Marke").fill("VW");
    await dialog(page).getByLabel("Modell / Typ").fill("Crafter");
    await dialog(page).getByLabel("FIN / VIN").fill("WVWZZZ1KZAW000123");
    await dialog(page).getByLabel("Kilometerstand").fill("84500");
    await dialog(page).getByLabel("Tankkarte").fill("DKV-12345678");
    await dialog(page).getByLabel("HU faellig").fill(isoDay(200));
    await dialog(page).getByLabel("Ausstattung (kommagetrennt)").fill("Leiter, Feuerloescher");
    await dialog(page).getByRole("button", { name: "Speichern" }).click();

    await expect(dialog(page)).toHaveCount(0);
    await expectToast(page, "Fahrzeug angelegt");

    await (await expectRow(page, plate)).click();
    const detail = dialog(page);
    // Alles hier war bisher erfasst und nie dargestellt.
    await expect(detail).toContainText("WVWZZZ1KZAW000123");
    await expect(detail).toContainText("84.500 km");
    await expect(detail).toContainText("DKV-12345678");
    await expect(detail).toContainText("Feuerloescher");
    await closeDialog(page);
  });

  test("der Kilometerstand laesst sich nachtragen", async ({ page, request }) => {
    const vehicle = await createVehicle(request, { mileage: 10_000 });

    await gotoAs(page, "fahrzeuge");
    await (await expectRow(page, vehicle.license_plate)).getByRole("button", { name: /bearbeiten$/ }).click();
    await dialog(page).getByLabel("Kilometerstand").fill("123456");
    await dialog(page).getByRole("button", { name: "Speichern" }).click();
    await expect(dialog(page)).toHaveCount(0);
    await expectToast(page, "Aenderungen gespeichert");

    const reloaded = await api.get<{ mileage: number }>(request, `/api/vehicles/${vehicle.id}`);
    expect(reloaded.mileage).toBe(123456);
  });

  test("eine ueberfaellige Fuehrerscheinkontrolle des Fahrers wird gemeldet", async ({
    page,
    request,
  }) => {
    const driver = await createEmployee(request, { full_name: unique("E2E Halterhaftung") });
    const vehicle = await createVehicle(request, { assigned_employee_id: driver.id });

    await gotoAs(page, "fahrzeuge");
    await expect(main(page).locator(".pds-banner--warn")).toContainText(
      "Fuehrerscheinkontrolle"
    );
    await expect(await expectRow(page, vehicle.license_plate)).toContainText(
      "Fuehrerscheinkontrolle pruefen"
    );

    await (await expectRow(page, vehicle.license_plate)).click();
    await expect(dialog(page)).toContainText("keine Fuehrerscheinkontrolle erfasst");
    await expect(dialog(page)).toContainText("Halterrisiko");
    await closeDialog(page);

    // Abgelaufene Kontrolle: der Hinweis nennt die Tage.
    await addQualification(request, driver.id, QUALIFICATION.fuehrerscheinKontrolle, {
      validUntil: isoDay(-40),
    });
    await page.reload();
    await expect(await expectRow(page, vehicle.license_plate)).toContainText(
      "Fuehrerscheinkontrolle pruefen"
    );
    await (await expectRow(page, vehicle.license_plate)).click();
    await expect(dialog(page)).toContainText("40 Tagen ueberfaellig");
    await closeDialog(page);

    // Gueltige Kontrolle: der Hinweis verschwindet.
    await addQualification(request, driver.id, QUALIFICATION.fuehrerscheinKontrolle, {
      validUntil: isoDay(120),
    });
    await page.reload();
    await expect(await expectRow(page, vehicle.license_plate)).not.toContainText(
      "Fuehrerscheinkontrolle pruefen"
    );
  });

  test("der Ausschnitt trennt Handlungsbedarf und Fahrzeuge ohne Fahrer", async ({
    page,
    request,
  }) => {
    const free = await createVehicle(request, { assigned_employee_id: null });
    const overdue = await createVehicle(request, {
      assigned_employee_id: null,
      uvv_next_check: isoDay(-2),
    });

    await gotoAs(page, "fahrzeuge");
    await segment(page, "Handlungsbedarf").click();
    await expect(row(page, overdue.license_plate)).toHaveCount(1);
    await expect(row(page, free.license_plate)).toHaveCount(0);

    await segment(page, "Ohne Fahrer").click();
    await expect(row(page, free.license_plate)).toHaveCount(1);

    await main(page).getByPlaceholder("Kennzeichen, Marke, Fahrer").fill(free.license_plate);
    await expect(page.locator(".pds-table__row")).toHaveCount(1);
  });

  test("ein Fahrzeug laesst sich nach Rueckfrage loeschen", async ({ page, request }) => {
    const vehicle = await createVehicle(request);

    await gotoAs(page, "fahrzeuge");
    await (await expectRow(page, vehicle.license_plate)).getByRole("button", { name: /loeschen$/ }).click();
    await expect(dialog(page)).toContainText(vehicle.license_plate);
    await dialog(page).getByRole("button", { name: "Loeschen", exact: true }).click();

    await expectToast(page, "Fahrzeug geloescht");
    await expect(row(page, vehicle.license_plate)).toHaveCount(0);
  });
});
