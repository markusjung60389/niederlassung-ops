import { expect, test } from "@playwright/test";
import { HSE, MANAGER, api, createRecord, isoDay, unique } from "./support/api";
import {
  closeDialog,
  createButton,
  dialog,
  expectToast,
  firstTable,
  gotoAs,
  main,
  row,
  segment,
} from "./support/app";

/** A record row, scoped to the records table. */
async function recordRow(page: import("@playwright/test").Page, title: string) {
  const target = row(firstTable(page), title);
  await expect(target).toHaveCount(1);
  return target;
}

test.describe("Compliance", () => {
  test("ein Thema entsteht aus einer Vorlage statt aus dem Kopf", async ({ page, request }) => {
    await gotoAs(page, "compliance");
    await createButton(page, "Thema").click();

    await expect(dialog(page)).toContainText("Aus dem Katalog der Standardpflichten waehlen");
    await dialog(page)
      .getByRole("button", { name: /Gefaehrdungsbeurteilung erstellen und fortschreiben/ })
      .click();

    // Die Vorlage fuellt Rechtsgrundlage, Kategorie, Turnus und Risiko vor.
    await expect(dialog(page).getByLabel("Titel")).toHaveValue(
      "Gefaehrdungsbeurteilung erstellen und fortschreiben"
    );
    await expect(dialog(page).getByLabel("Rechtsgrundlage")).toHaveValue(
      "ArbSchG Paragraf 5, Paragraf 6"
    );
    await expect(dialog(page).getByLabel("Wiederholung")).toHaveValue("yearly");
    await expect(dialog(page).getByLabel("Prioritaet")).toHaveValue("critical");

    const title = unique("E2E Gefaehrdungsbeurteilung");
    await dialog(page).getByLabel("Titel").fill(title);
    await dialog(page).getByLabel("Faellig").fill(isoDay(20));
    await dialog(page).getByRole("button", { name: "Anlegen" }).click();

    await expect(dialog(page)).toHaveCount(0);
    await expectToast(page, "Thema angelegt");

    const created = await recordRow(page, title);
    // Deutsche Beschriftungen statt roher Enum-Werte.
    await expect(created).toContainText("Gefaehrdungsbeurteilung");
    await expect(created).toContainText("offen");

    const records = await api.get<{ title: string; legal_basis: string; recurrence: string }[]>(
      request,
      "/api/compliance-records"
    );
    const stored = records.find((item) => item.title === title);
    expect(stored?.legal_basis).toBe("ArbSchG Paragraf 5, Paragraf 6");
    expect(stored?.recurrence).toBe("yearly");
  });

  test("frei erfassen bleibt moeglich", async ({ page }) => {
    const title = unique("E2E Frei");
    await gotoAs(page, "compliance");
    await createButton(page, "Thema").click();
    await dialog(page).getByRole("button", { name: "Frei erfassen" }).click();

    await expect(dialog(page).getByLabel("Titel")).toHaveValue("");
    await dialog(page).getByLabel("Titel").fill(title);
    await dialog(page).getByLabel("Rechtsgrundlage").fill("Betriebsvereinbarung 4");
    await dialog(page).getByLabel("Kategorie").selectOption("documentation");
    await dialog(page).getByLabel("Faellig").fill(isoDay(45));
    await dialog(page).getByRole("button", { name: "Anlegen" }).click();

    await expect(dialog(page)).toHaveCount(0);
    await expect(await recordRow(page, title)).toContainText("Dokumentation");
  });

  test("ohne Nachweis warnt das Detail, mit Nachweis nicht mehr", async ({ page, request }) => {
    const record = await createRecord(request, { title: unique("E2E Nachweis") });

    await gotoAs(page, "compliance");
    const listed = await recordRow(page, record.title);
    // Null Nachweise werden als Handlungsbedarf markiert (vierte Spalte).
    const evidenceCell = listed.getByRole("gridcell").nth(3);
    await expect(evidenceCell).toHaveText("0");
    await expect(evidenceCell.locator(".ops-date")).toHaveClass(/is-yellow/);

    await listed.click();
    await expect(dialog(page)).toContainText("Kein Nachweis hinterlegt");

    await dialog(page)
      .getByLabel("Datei")
      .setInputFiles({
        name: "pruefprotokoll.pdf",
        mimeType: "application/pdf",
        buffer: Buffer.from("%PDF-1.4 e2e protokoll"),
      });
    await dialog(page).getByLabel("Art").selectOption("protocol");
    await dialog(page).getByLabel("Beschreibung").fill("Protokoll 2026");
    await dialog(page).getByRole("button", { name: "Nachweis hochladen" }).click();

    await expectToast(page, "Nachweis hochgeladen");
    await expect(dialog(page)).toContainText("pruefprotokoll.pdf");
    await expect(dialog(page)).not.toContainText("Kein Nachweis hinterlegt");
    await closeDialog(page);

    await expect((await recordRow(page, record.title)).getByRole("gridcell").nth(3)).toHaveText("1");
  });

  test("eine Massnahme steht beim Thema und laesst sich dort erledigen", async ({
    page,
    request,
  }) => {
    const record = await createRecord(request, { title: unique("E2E Massnahme") });
    const actionTitle = unique("E2E Abstellmassnahme");
    await api.post(request, `/api/compliance-records/${record.id}/actions`, {
      title: actionTitle,
      owner_user_id: MANAGER,
      due_date: isoDay(-2),
      priority: "critical",
      status: "open",
    });

    await gotoAs(page, "compliance");
    await (await recordRow(page, record.title)).click();

    const action = dialog(page).locator(".pds-table__row").filter({ hasText: actionTitle });
    await expect(action).toContainText("offen");
    await action.getByRole("button", { name: "Erledigt" }).click();
    await expectToast(page, "Massnahme aktualisiert");
    await expect(
      dialog(page).locator(".pds-table__row").filter({ hasText: actionTitle })
    ).toContainText("erledigt");
    await closeDialog(page);

    // Erledigte Massnahmen verschwinden aus der Sammelliste.
    await expect(main(page).locator(".ops-section").filter({ hasText: "Offene Massnahmen" })).not.toContainText(
      actionTitle
    );
  });

  test("Kategorie-Chips und Ausschnitt filtern zusammen", async ({ page, request }) => {
    const overdue = await createRecord(request, {
      title: unique("E2E Ueberfaellig"),
      category: "electrical_safety",
      due_date: isoDay(-9),
      review_date: isoDay(-9),
    });
    const future = await createRecord(request, {
      title: unique("E2E Spaeter"),
      category: "first_aid",
      due_date: isoDay(200),
      review_date: isoDay(200),
    });

    await gotoAs(page, "compliance");
    await segment(page, "Ueberfaellig").click();
    await expect(row(firstTable(page), overdue.title)).toHaveCount(1);
    await expect(row(firstTable(page), future.title)).toHaveCount(0);

    await segment(page, "Alle").click();
    await main(page).getByRole("button", { name: /^Erste Hilfe/ }).click();
    await expect(row(firstTable(page), future.title)).toHaveCount(1);
    await expect(row(firstTable(page), overdue.title)).toHaveCount(0);

    await main(page).getByRole("button", { name: "Alle Kategorien" }).click();
    await main(page).getByPlaceholder("Titel oder Rechtsgrundlage").fill(overdue.title);
    await expect(firstTable(page).locator(".pds-table__row")).toHaveCount(1);
  });

  test("HSE darf Compliance schreiben, aber keine Stammdaten pflegen", async ({ page, request }) => {
    const record = await createRecord(request, { title: unique("E2E HSE") });

    await gotoAs(page, "compliance", HSE);
    await expect(createButton(page, "Thema")).toBeVisible();
    await expect(await recordRow(page, record.title)).toHaveCount(1);

    await gotoAs(page, "mitarbeiter", HSE);
    // Personal darf HSE nur lesen.
    await expect(createButton(page, "Mitarbeiter")).toHaveCount(0);
  });
});
