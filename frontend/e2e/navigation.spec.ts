import { expect, test } from "@playwright/test";
import { HSE, VIEWER, createEmployee } from "./support/api";
import { closeDialog, createButton, dialog, gotoAs, main, nav, row } from "./support/app";

test.describe("Shell, Routing und Berechtigungen", () => {
  test("die Ansicht steht in der URL und ueberlebt Neuladen und Zurueck", async ({ page }) => {
    await gotoAs(page, "cockpit");
    await expect(main(page).getByRole("heading", { level: 1 })).toHaveText("Leitercockpit");

    await nav(page).getByRole("button", { name: "Fahrzeuge" }).click();
    await expect(page).toHaveURL(/#\/fahrzeuge$/);
    await expect(main(page).getByRole("heading", { level: 1 })).toHaveText("Fahrzeuge");

    // F5 landete frueher wieder im Cockpit, weil die Ansicht nur React-State war.
    await page.reload();
    await expect(main(page).getByRole("heading", { level: 1 })).toHaveText("Fahrzeuge");

    await page.goBack();
    await expect(main(page).getByRole("heading", { level: 1 })).toHaveText("Leitercockpit");

    await page.goForward();
    await expect(main(page).getByRole("heading", { level: 1 })).toHaveText("Fahrzeuge");
  });

  test("ein Deep Link oeffnet die Ansicht direkt", async ({ page }) => {
    await gotoAs(page, "qualifikationen");
    await expect(main(page).getByRole("heading", { level: 1 })).toHaveText("Qualifikationsmatrix");
  });

  test("eine unbekannte Route faellt auf die erste erlaubte Ansicht zurueck", async ({ page }) => {
    await gotoAs(page, "gibtesnicht");
    await expect(main(page).getByRole("heading", { level: 1 })).toHaveText("Leitercockpit");
  });

  test("der Betrachter sieht keine schreibenden Aktionen", async ({ page, request }) => {
    const employee = await createEmployee(request);

    await gotoAs(page, "mitarbeiter", VIEWER);
    await expect(row(page, employee.full_name)).toHaveCount(1);

    await expect(createButton(page, "Mitarbeiter")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /bearbeiten$/ })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /loeschen$/ })).toHaveCount(0);

    // Lesen bleibt vollstaendig moeglich, inklusive Detail.
    await row(page, employee.full_name).click();
    await expect(dialog(page)).toContainText(employee.full_name);
    await expect(dialog(page).getByRole("button", { name: "Erfassen" })).toHaveCount(0);
  });

  test("HSE liest ueberall, schreibt aber nur in seinem Bereich", async ({ page }) => {
    await gotoAs(page, "compliance", HSE);
    // Alle drei Presets halten saemtliche :read-Rechte, die Navigation ist
    // deshalb vollstaendig; unterschieden wird beim Schreiben.
    for (const area of ["Cockpit", "Mitarbeiter", "Fahrzeuge", "Compliance", "Vorgaben"]) {
      await expect(nav(page).getByRole("button", { name: area })).toBeVisible();
    }
    await expect(createButton(page, "Thema")).toBeVisible();

    await gotoAs(page, "fahrzeuge", HSE);
    await expect(createButton(page, "Fahrzeug")).toHaveCount(0);
  });

  test("Dialoge schliessen ueber Escape und ueber den Backdrop", async ({ page, request }) => {
    const employee = await createEmployee(request);
    await gotoAs(page, "mitarbeiter");

    await row(page, employee.full_name).click();
    await expect(dialog(page)).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog(page)).toHaveCount(0);

    await row(page, employee.full_name).click();
    await expect(dialog(page)).toBeVisible();
    // Klick auf die Flaeche neben dem Dialograhmen.
    await dialog(page).click({ position: { x: 2, y: 2 } });
    await expect(dialog(page)).toHaveCount(0);
  });

  test("ein veraendertes Formular fragt vor dem Verwerfen nach", async ({ page }) => {
    await gotoAs(page, "mitarbeiter");
    await createButton(page, "Mitarbeiter").click();
    await dialog(page).getByLabel("Name").fill("Wird verworfen");

    let asked = false;
    page.once("dialog", (confirmation) => {
      asked = true;
      void confirmation.dismiss();
    });
    await dialog(page).getByRole("button", { name: "Schliessen" }).click();

    expect(asked).toBe(true);
    // Abgelehnt: der Dialog bleibt mit den Eingaben stehen.
    await expect(dialog(page)).toBeVisible();
    await expect(dialog(page).getByLabel("Name")).toHaveValue("Wird verworfen");

    page.once("dialog", (confirmation) => void confirmation.accept());
    await closeDialog(page);
  });

  test("Vertrieb ist aus der Anwendung verschwunden", async ({ page }) => {
    await gotoAs(page, "cockpit");
    await expect(nav(page).getByRole("button", { name: "Vertrieb" })).toHaveCount(0);
    // Die Kennzahl dahinter ebenfalls: sie kam aus dem Vertrieb.
    await expect(main(page)).not.toContainText("Pipeline");
  });

  test("die Seite scrollt nie horizontal", async ({ page }) => {
    for (const route of ["cockpit", "mitarbeiter", "qualifikationen", "fahrzeuge", "compliance", "vorgaben", "stammdaten"]) {
      await gotoAs(page, route);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth
      );
      expect(overflow, `${route} scrollt horizontal`).toBeLessThanOrEqual(0);
    }
  });
});
