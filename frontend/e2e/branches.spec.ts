import { expect, test } from "@playwright/test";
import {
  AREA_MANAGER,
  BRANCH,
  MANAGER,
  api,
  createEmployee,
  createVehicle,
  ensureSecondBranch,
  isoDay,
  unique,
} from "./support/api";
import { closeDialog, createButton, dialog, gotoAs, main, nav, row, section } from "./support/app";

/**
 * Several branches: the switcher, the portfolio, rules and the exceptions.
 *
 * This spec runs first and creates the second branch, so every later spec runs
 * in the multi-branch configuration - which is the one the tool is actually
 * used in and the more demanding of the two.
 */

test.describe("Mehrere Niederlassungen", () => {
  test("die gewaehlte Niederlassung steht in der URL und filtert die Listen", async ({
    page,
    request,
  }) => {
    const second = await ensureSecondBranch(request);
    const here = await createEmployee(request, { full_name: unique("Remscheid Person") });
    const there = await api.post<{ full_name: string }>(
      request,
      "/api/employees",
      {
        branch_id: second.id,
        full_name: unique("Solingen Person"),
        role: "Monteur",
        job_role_id: "jr-monteur",
      },
      AREA_MANAGER
    );

    await gotoAs(page, "mitarbeiter", AREA_MANAGER);
    // Ohne Auswahl: alle Niederlassungen, die der Bereichsleiter sehen darf.
    await expect(row(page, here.full_name)).toHaveCount(1);
    await expect(row(page, there.full_name)).toHaveCount(1);

    await page.getByLabel("Niederlassung").selectOption("rs");
    await expect(page).toHaveURL(/#\/mitarbeiter\/rs$/);
    await expect(row(page, here.full_name)).toHaveCount(1);
    await expect(row(page, there.full_name)).toHaveCount(0);

    // Der Deep Link oeffnet dieselbe Auswahl wieder.
    await page.reload();
    await expect(row(page, there.full_name)).toHaveCount(0);
  });

  test("der Niederlassungsleiter sieht die fremde Niederlassung ueberhaupt nicht", async ({
    page,
    request,
  }) => {
    const second = await ensureSecondBranch(request);
    const foreign = await api.post<{ full_name: string }>(
      request,
      "/api/employees",
      {
        branch_id: second.id,
        full_name: unique("Fremde Person"),
        role: "Monteur",
      },
      AREA_MANAGER
    );

    await gotoAs(page, "mitarbeiter", MANAGER);
    await expect(row(page, foreign.full_name)).toHaveCount(0);
    // Kein Umschalter, weil es fuer ihn nichts umzuschalten gibt.
    await expect(page.getByLabel("Niederlassung")).toHaveCount(0);
    await expect(nav(page).getByRole("button", { name: "Niederlassungen" })).toHaveCount(0);
  });

  test("das Portfolio stellt die Niederlassungen nebeneinander", async ({ page, request }) => {
    const second = await ensureSecondBranch(request);
    await createEmployee(request, { full_name: unique("Ohne Nachweise") });

    await gotoAs(page, "niederlassungen", AREA_MANAGER);
    await expect(main(page).getByRole("heading", { level: 1 })).toHaveText("Niederlassungen");

    const comparison = section(page, "Niederlassungen im Vergleich");
    await expect(comparison.locator(".pds-table__row")).toHaveCount(2);
    await expect(row(comparison, "Remscheid")).toContainText("kritisch");
    await expect(row(comparison, second.name)).toHaveCount(1);

    // Ein Klick fuehrt in die Niederlassung.
    await row(comparison, "Remscheid").click();
    await expect(page).toHaveURL(/#\/cockpit\/rs$/);
  });

  test("eine Ausnahme der Niederlassung erscheint beim Vorgesetzten und wird widerrufen", async ({
    page,
    request,
  }) => {
    await ensureSecondBranch(request);
    const employee = await createEmployee(request, { full_name: unique("Mit Ausnahme") });

    // Der Niederlassungsleiter setzt sie selbst, ohne Freigabe.
    await gotoAs(page, "stammdaten/rs", MANAGER);
    await row(page, "Monteur").click();
    await dialog(page)
      .locator(".pds-table__row")
      .filter({ hasText: "IPAF" })
      .getByRole("button", { name: "Ausnahme" })
      .click();
    await dialog(page).getByLabel("Begruendung").fill("Keine Hubarbeitsbuehnen im Einsatz");
    await dialog(page).getByRole("button", { name: "Ausnahme setzen" }).click();
    await expect(page.locator("dialog[open]")).toHaveCount(1);
    await closeDialog(page);

    // Die Anforderung ist fuer diese Niederlassung weg.
    await gotoAs(page, "mitarbeiter/rs", MANAGER);
    await row(page, employee.full_name).click();
    await expect(dialog(page)).not.toContainText("IPAF-Bedienerschulung");
    await closeDialog(page);

    // Der Bereichsleiter sieht sie als neu und widerruft sie.
    await gotoAs(page, "niederlassungen", AREA_MANAGER);
    const register = section(page, "Ausnahmen der Niederlassungen");
    await expect(row(register, "Keine Hubarbeitsbuehnen")).toHaveCount(1);
    await row(register, "Keine Hubarbeitsbuehnen")
      .getByRole("button", { name: "Ausnahme widerrufen" })
      .click();
    await dialog(page).getByLabel("Begruendung des Widerrufs").fill("Buehnen sind wieder im Einsatz");
    await dialog(page).getByLabel("Gilt ab (optional)").fill(isoDay(-1));
    await dialog(page).getByRole("button", { name: "Widerrufen" }).click();
    await expect(page.locator("dialog[open]")).toHaveCount(0);

    // Ab dem Stichtag gilt die Anforderung wieder.
    await gotoAs(page, "mitarbeiter/rs", MANAGER);
    await row(page, employee.full_name).click();
    await expect(dialog(page)).toContainText("IPAF-Bedienerschulung");
    await closeDialog(page);
  });

  test("ein Fahrzeug wandert in die andere Niederlassung und wieder zurueck", async ({
    page,
    request,
  }) => {
    const second = await ensureSecondBranch(request);
    const vehicle = await createVehicle(request);

    await gotoAs(page, "fahrzeuge/rs", AREA_MANAGER);
    await row(page, vehicle.license_plate)
      .getByRole("button", { name: `${vehicle.license_plate} verlegen` })
      .click();
    await dialog(page).getByLabel("Steht kuenftig in").selectOption({ label: second.name });
    await dialog(page).getByRole("button", { name: "Verlegen" }).click();
    await expect(page.locator("dialog[open]")).toHaveCount(0);

    // Faellig ist es dort, wo es steht - also nicht mehr in Remscheid.
    await expect(row(page, vehicle.license_plate)).toHaveCount(0);

    await page.getByLabel("Niederlassung").selectOption("sg");
    const moved = await expect(row(page, vehicle.license_plate)).toHaveCount(1);
    void moved;
    await expect(row(page, vehicle.license_plate)).toContainText(`steht in ${second.name}`);

    await row(page, vehicle.license_plate)
      .getByRole("button", { name: `${vehicle.license_plate} verlegen` })
      .click();
    await dialog(page).getByLabel("Steht kuenftig in").selectOption({ label: "Remscheid (Heimat)" });
    await dialog(page).getByRole("button", { name: "Verlegen" }).click();
    await expect(page.locator("dialog[open]")).toHaveCount(0);
    await expect(row(page, vehicle.license_plate)).toHaveCount(0);
  });

  test("ein Mitarbeiter wird in einer zweiten Niederlassung eingesetzt", async ({
    page,
    request,
  }) => {
    const second = await ensureSecondBranch(request);
    const employee = await createEmployee(request, { full_name: unique("Wander Arbeiter") });

    await gotoAs(page, "mitarbeiter/rs", AREA_MANAGER);
    await row(page, employee.full_name).click();
    await dialog(page).getByLabel("Weitere Niederlassung").selectOption({ label: second.name });
    await dialog(page).getByRole("button", { name: "Einsatzort" }).click();
    await expect(dialog(page)).toContainText(second.name);
    await closeDialog(page);

    // In der zweiten Niederlassung taucht die Person jetzt ebenfalls auf.
    await page.getByLabel("Niederlassung").selectOption("sg");
    await expect(row(page, employee.full_name)).toHaveCount(1);
  });

  test("eine Vorgabe der Niederlassung wird zur Gruppenvorgabe", async ({ page, request }) => {
    const second = await ensureSecondBranch(request);
    const title = unique("E2E Vorgabe");
    await api.post(
      request,
      "/api/compliance-rules",
      {
        title,
        category: "training_instruction",
        control_type: "training",
        legal_basis: "DGUV Vorschrift 1",
        branch_id: BRANCH,
        first_due_date: isoDay(60),
      },
      MANAGER
    );

    await gotoAs(page, "vorgaben", AREA_MANAGER);
    await expect(row(page, title)).toContainText("Niederlassung");

    await row(page, title).getByRole("button", { name: `Geltung von ${title} aendern` }).click();
    await dialog(page).getByLabel("Neue Geltung").selectOption("");
    // Die Vorschau sagt vorher, was passiert.
    await expect(dialog(page)).toContainText(second.name);
    await dialog(page).getByLabel("Erster Termin fuer neue Eintraege").fill(isoDay(90));
    await dialog(page).getByRole("button", { name: "Uebernehmen" }).click();
    await expect(page.locator("dialog[open]")).toHaveCount(0);

    await expect(row(page, title)).toContainText("Gruppe");
    await expect(row(page, title)).toContainText("2 Niederlassungen");

    // In der zweiten Niederlassung ist daraus ein Compliance-Eintrag geworden.
    await gotoAs(page, "compliance/sg", AREA_MANAGER);
    await expect(row(page, title)).toContainText("Gruppenvorgabe");
  });

  test("der Niederlassungsleiter darf keine Gruppenvorgabe anlegen", async ({ page }) => {
    await gotoAs(page, "vorgaben/rs", MANAGER);
    await createButton(page, "Vorgabe").click();
    // Die Option "alle Niederlassungen" wird gar nicht erst angeboten.
    await expect(dialog(page).getByLabel("Gilt fuer")).not.toContainText("alle Niederlassungen");
    await closeDialog(page);
  });
});
