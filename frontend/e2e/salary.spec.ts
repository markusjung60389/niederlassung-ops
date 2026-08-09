import { expect, test } from "@playwright/test";
import { AREA_MANAGER, MANAGER, api, createEmployee, unique } from "./support/api";
import { closeDialog, dialog, gotoAs, row } from "./support/app";

/**
 * Entgeltdaten in der Oberflaeche.
 *
 * Im Entwicklungsmodus gibt es keinen zweiten Faktor zu verlangen - der
 * Step-up ist dort erfuellt (siehe `auth.step_up_satisfied`). Geprueft wird
 * deshalb hier, was auch dann gelten muss: ohne Berechtigung kein Abschnitt,
 * kein Betrag ohne bewusstes Aufklappen, und jeder Zugriff im Protokoll.
 */

test.describe("Entgelt", () => {
  test("ohne Berechtigung gibt es den Abschnitt nicht", async ({ page, request }) => {
    const employee = await createEmployee(request, { full_name: unique("Ohne Zugriff") });
    await gotoAs(page, "mitarbeiter/rs", MANAGER);

    await row(page, employee.full_name).click();
    await expect(dialog(page).getByRole("button", { name: "Entgelt anzeigen" })).toHaveCount(0);
    await expect(dialog(page)).not.toContainText("Monatsbrutto");
    await closeDialog(page);
  });

  test("das Entgelt wird erst auf Anforderung geladen und dann gepflegt", async ({
    page,
    request,
  }) => {
    const employee = await createEmployee(request, { full_name: unique("Mit Entgelt") });
    await gotoAs(page, "mitarbeiter/rs", AREA_MANAGER);

    await row(page, employee.full_name).click();
    // Der Betrag steht nicht schon da, nur der Weg dorthin.
    await expect(dialog(page)).toContainText("Jeder Zugriff wird protokolliert");
    await dialog(page).getByRole("button", { name: "Entgelt anzeigen" }).click();
    await expect(dialog(page)).toContainText("kein Entgelt hinterlegt");

    await dialog(page).getByRole("button", { name: "Entgelt erfassen" }).click();
    await dialog(page).getByLabel("Betrag in EUR").fill("4200");
    await dialog(page).getByLabel("Wochenstunden").fill("40");
    await dialog(page).getByLabel("Gueltig ab").fill("2026-01-01");
    await dialog(page).getByRole("button", { name: "Speichern" }).click();

    await expect(dialog(page)).toContainText("4.200");
    await expect(dialog(page)).toContainText("Monatsbrutto");
    await closeDialog(page);

    // Auch beim Wiederoeffnen bleibt der Betrag zugeklappt.
    await row(page, employee.full_name).click();
    await expect(dialog(page)).not.toContainText("4.200");
    await dialog(page).getByRole("button", { name: "Entgelt anzeigen" }).click();
    await expect(dialog(page)).toContainText("4.200");
    await closeDialog(page);
  });

  test("jeder Blick auf das Entgelt steht im Protokoll, der Betrag nicht", async ({
    page,
    request,
  }) => {
    const employee = await createEmployee(request, { full_name: unique("Protokolliert") });
    await api.put(
      request,
      `/api/employees/${employee.id}/salary`,
      { amount: 3900, period: "monthly", hours_per_week: 38, valid_from: "2026-02-01" },
      AREA_MANAGER
    );

    await gotoAs(page, "mitarbeiter/rs", AREA_MANAGER);
    await row(page, employee.full_name).click();
    await dialog(page).getByRole("button", { name: "Entgelt anzeigen" }).click();
    await expect(dialog(page)).toContainText("3.900");
    await closeDialog(page);

    const entries = await api.get<{ action: string; entity_id: string }[]>(
      request,
      "/api/audit-log?entity_type=employee_salary",
      AREA_MANAGER
    );
    const mine = entries.filter((entry) => entry.entity_id === employee.id);
    expect(mine.map((entry) => entry.action)).toContain("viewed");
    expect(JSON.stringify(mine)).not.toContain("3900");
  });
});
