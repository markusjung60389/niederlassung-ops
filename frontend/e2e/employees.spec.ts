import { expect, test } from "@playwright/test";
import {
  JOB_ROLE,
  QUALIFICATION,
  addMonths,
  api,
  addQualification,
  createEmployee,
  createReadyMonteur,
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
  segmentCount,
} from "./support/app";

test.describe("Mitarbeiter", () => {
  test("die Tabelle zeigt Einsatzfaehigkeit, Funktion und die naechste Frist", async ({
    page,
    request,
  }) => {
    const blocked = await createEmployee(request, { full_name: unique("E2E Ohne Nachweise") });
    const ready = await createReadyMonteur(request, { full_name: unique("E2E Vollstaendig") });

    await gotoAs(page, "mitarbeiter");

    const blockedRow = await expectRow(page, blocked.full_name);
    await expect(blockedRow).toContainText("nicht einsatzfaehig");
    await expect(blockedRow).toContainText("Monteur");
    // Vier Pflichtanforderungen fehlen, drei optionale zaehlen als offen mit.
    await expect(blockedRow).toContainText("0 / 7");

    const readyRow = await expectRow(page, ready.full_name);
    await expect(readyRow).toContainText("einsatzfaehig");
    await expect(readyRow).toContainText("nichts offen");
  });

  test("ein Mitarbeiter wird im Dialog angelegt und erscheint in der Tabelle", async ({ page }) => {
    const name = unique("E2E Neuanlage");
    await gotoAs(page, "mitarbeiter");
    const before = await segmentCount(page, "Aktiv");

    await createButton(page, "Mitarbeiter").click();
    await dialog(page).getByLabel("Name").fill(name);
    await dialog(page).getByLabel("Funktion").selectOption({ label: "Service-Techniker" });
    await dialog(page).getByLabel("Team").fill("Service Ost");
    await dialog(page).getByLabel("Eintritt").fill(isoDay(-30));
    await dialog(page).getByLabel("Benannter Ersthelfer").check();
    await dialog(page).getByRole("button", { name: "Speichern" }).click();

    await expect(dialog(page)).toHaveCount(0);
    await expectToast(page, "Mitarbeiter angelegt");

    const created = await expectRow(page, name);
    await expect(created).toContainText("Service-Techniker");
    await expect(created).toContainText("Service Ost");
    // Ohne jede Qualifikation kann niemand eingesetzt werden.
    await expect(created).toContainText("nicht einsatzfaehig");
    expect(await segmentCount(page, "Aktiv")).toBe(before + 1);
  });

  test("Bearbeiten aendert den Datensatz und behaelt die uebrigen Profilfelder", async ({
    page,
    request,
  }) => {
    const employee = await createEmployee(request);
    // Ein Profilfeld, das das Formular nicht anzeigt: es darf beim Speichern
    // nicht verloren gehen, weil der Endpunkt das Profil komplett ersetzt.
    await api.post(request, "/api/employee-profiles", {
      employee_id: employee.id,
      contract_type: "befristet",
      contract_end: isoDay(120),
      driver_license_classes: ["B", "BE"],
    });

    await gotoAs(page, "mitarbeiter");
    await (await expectRow(page, employee.full_name)).getByRole("button", { name: /bearbeiten$/ }).click();

    await expect(dialog(page).getByLabel("Vertragsart")).toHaveValue("befristet");
    await dialog(page).getByLabel("Team").fill("Umgezogen");
    await dialog(page).getByRole("button", { name: "Speichern" }).click();

    await expect(dialog(page)).toHaveCount(0);
    await expectToast(page, "Aenderungen gespeichert");
    await expect(await expectRow(page, employee.full_name)).toContainText("Umgezogen");

    const reloaded = await api.get<{ profile: { driver_license_classes: string[]; contract_end: string } }>(
      request,
      `/api/employees/${employee.id}`
    );
    expect(reloaded.profile.driver_license_classes).toEqual(["B", "BE"]);
    expect(reloaded.profile.contract_end).toBe(isoDay(120));
  });

  test("eine erfasste Qualifikation macht aus nicht einsatzfaehig eingeschraenkt", async ({
    page,
    request,
  }) => {
    const employee = await createEmployee(request);
    // Alles ausser der Unterweisung liegt vor, die fehlt noch.
    for (const typeId of [QUALIFICATION.ipaf, QUALIFICATION.psaAbsturz, QUALIFICATION.arbeitsmedizin]) {
      await addQualification(request, employee.id, typeId);
    }

    await gotoAs(page, "mitarbeiter");
    await (await expectRow(page, employee.full_name)).click();
    await expect(dialog(page)).toContainText("kein Einsatz in dieser Funktion");

    const requirement = dialog(page).locator(".pds-table__row").filter({ hasText: "Jaehrliche Unterweisung" });
    await expect(requirement).toContainText("fehlt");
    await requirement.getByRole("button", { name: "Erfassen" }).click();

    // Der Katalog rechnet das Ablaufdatum aus dem Kursdatum.
    await expect(dialog(page)).toContainText("Gueltigkeit 12 Monate");
    await dialog(page).getByLabel("Kurs-/Pruefdatum").fill(isoDay(-10));
    await dialog(page).getByRole("button", { name: "Speichern" }).click();
    await expectToast(page, "Qualifikation erfasst");

    await expect(await expectRow(page, employee.full_name)).toContainText("eingeschraenkt");

    const refreshed = await api.get<{
      readiness: string;
      requirements: { qualification_type_id: string; state: string; valid_until: string }[];
    }>(request, `/api/employees/${employee.id}`);
    const unterweisung = refreshed.requirements.find(
      (item) => item.qualification_type_id === QUALIFICATION.unterweisung
    );
    expect(unterweisung?.valid_until).toBe(addMonths(isoDay(-10), 12));
    // Gueltig, aber ohne hinterlegtes Dokument.
    expect(unterweisung?.state).toBe("evidence_missing");
    expect(refreshed.readiness).toBe("limited");
  });

  test("Suche und Ausschnitt filtern die Liste", async ({ page, request }) => {
    const needle = unique("E2E Suchfall");
    await createEmployee(request, { full_name: needle });
    await createReadyMonteur(request);

    await gotoAs(page, "mitarbeiter");
    await main(page).getByPlaceholder("Name, Funktion, Team").fill(needle);
    await expect(page.locator(".pds-table__row")).toHaveCount(1);
    await expect(page.locator(".pds-table__row")).toContainText(needle);

    await main(page).getByPlaceholder("Name, Funktion, Team").fill("");
    await segment(page, "Nicht einsatzfaehig").click();
    await expect(row(page, needle)).toHaveCount(1);
    for (const text of await page.locator(".pds-table__row").allInnerTexts()) {
      expect(text).toContain("nicht einsatzfaehig");
    }
  });

  test("ausgeschieden statt geloescht: der Datensatz bleibt auffindbar", async ({ page, request }) => {
    const employee = await createEmployee(request, { full_name: unique("E2E Austritt") });

    await gotoAs(page, "mitarbeiter");
    await (await expectRow(page, employee.full_name)).getByRole("button", { name: /bearbeiten$/ }).click();
    await dialog(page).getByLabel("Status").selectOption("inactive");
    await dialog(page).getByLabel("Austritt").fill(isoDay(-1));
    await dialog(page).getByRole("button", { name: "Speichern" }).click();
    await expect(dialog(page)).toHaveCount(0);

    await expect(row(page, employee.full_name)).toHaveCount(0);
    await segment(page, "Ausgeschieden").click();
    const inactive = await expectRow(page, employee.full_name);
    await expect(inactive).toContainText("ausgeschieden");
    // Ausgeschiedene loesen keine Erinnerungen mehr aus.
    await expect(inactive).toContainText("einsatzfaehig");
  });

  test("das Loeschen warnt vor Aufbewahrungsfristen und laesst sich abbrechen", async ({
    page,
    request,
  }) => {
    const employee = await createEmployee(request, { full_name: unique("E2E Loeschfall") });

    await gotoAs(page, "mitarbeiter");
    await (await expectRow(page, employee.full_name)).getByRole("button", { name: /loeschen$/ }).click();

    await expect(dialog(page)).toContainText("Aufbewahrungsfristen");
    await dialog(page).getByRole("button", { name: "Abbrechen" }).click();
    await expect(row(page, employee.full_name)).toHaveCount(1);

    await (await expectRow(page, employee.full_name)).getByRole("button", { name: /loeschen$/ }).click();
    await dialog(page).getByRole("button", { name: "Loeschen", exact: true }).click();
    await expectToast(page, "Mitarbeiter geloescht");
    await expect(row(page, employee.full_name)).toHaveCount(0);
  });

  test("ein Loeschen mit abhaengigem Fahrzeug scheitert sichtbar", async ({ page, request }) => {
    const employee = await createEmployee(request, { full_name: unique("E2E Mit Fahrzeug") });
    await createVehicle(request, { assigned_employee_id: employee.id });

    await gotoAs(page, "mitarbeiter");
    await (await expectRow(page, employee.full_name)).getByRole("button", { name: /loeschen$/ }).click();
    await dialog(page).getByRole("button", { name: "Loeschen", exact: true }).click();

    await expect(main(page).locator(".pds-banner--danger")).toContainText("assigned vehicle");
    await expect(row(page, employee.full_name)).toHaveCount(1);
  });

  test("ohne Funktion sagt das Detail, warum nichts gefordert ist", async ({ page, request }) => {
    const employee = await createEmployee(request, {
      full_name: unique("E2E Ohne Funktion"),
      job_role_id: null,
    });

    await gotoAs(page, "mitarbeiter");
    const listed = await expectRow(page, employee.full_name);
    await expect(listed).toContainText("keine Funktion zugeordnet");

    await listed.click();
    await expect(dialog(page)).toContainText("Keine Funktion zugeordnet");
    await closeDialog(page);
  });

  test("die Funktion laesst sich im Dialog wechseln und aendert die Anforderungen", async ({
    page,
    request,
  }) => {
    const employee = await createReadyMonteur(request, { full_name: unique("E2E Wechsel") });

    await gotoAs(page, "mitarbeiter");
    await expect(await expectRow(page, employee.full_name)).toContainText("einsatzfaehig");

    await (await expectRow(page, employee.full_name)).getByRole("button", { name: /bearbeiten$/ }).click();
    await dialog(page).getByLabel("Funktion").selectOption({ label: "Service-Techniker" });
    await dialog(page).getByRole("button", { name: "Speichern" }).click();
    await expect(dialog(page)).toHaveCount(0);

    // Der Service-Techniker fordert zusaetzlich Fahrerlaubnis, Kontrolle und
    // befaehigte Person - die fehlen jetzt.
    const updated = await expectRow(page, employee.full_name);
    await expect(updated).toContainText("Service-Techniker");
    await expect(updated).toContainText("nicht einsatzfaehig");

    const refreshed = await api.get<{ job_role_id: string; readiness: string }>(
      request,
      `/api/employees/${employee.id}`
    );
    expect(refreshed.job_role_id).toBe(JOB_ROLE.serviceTechniker);
    expect(refreshed.readiness).toBe("blocked");
  });
});
