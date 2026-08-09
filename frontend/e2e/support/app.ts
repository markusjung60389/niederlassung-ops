import { expect, type Locator, type Page } from "@playwright/test";
import { MANAGER } from "./api";

/** Interaction helpers shared by the specs. */

const DEV_USER_STORAGE_KEY = "remscheid-ops.dev-user-id";

/**
 * Opens a view as a given identity.
 *
 * The identity is written to localStorage before the page script runs, so the
 * application starts authenticated instead of falling back to whichever
 * dev-user the picker defaults to. Called again with another user, the later
 * script wins.
 */
export async function gotoAs(page: Page, route: string, userId: string = MANAGER): Promise<void> {
  await page.addInitScript(
    ([key, value]) => window.localStorage.setItem(key, value),
    [DEV_USER_STORAGE_KEY, userId] as const
  );
  // A page is already open: going to another route would only change the hash,
  // the document would never be re-created and the init script above would
  // never run - the identity would silently stay the previous one. Worse, the
  // running application would first see a route it may not open and redirect
  // away from it. The blank page in between makes it a real navigation.
  if (page.url().startsWith("http")) await page.goto("about:blank");
  await page.goto(`/#/${route}`);
  await expect(page.locator(".pds-topbar")).toBeVisible();
  await expect(page.getByText("Daten werden geladen...")).toHaveCount(0);
}

/** The main content area, so a selector never catches the topbar navigation. */
export function main(page: Page): Locator {
  return page.locator("main");
}

export function nav(page: Page): Locator {
  return page.locator("header .pds-nav");
}

/**
 * The dialog on top.
 *
 * Two can be open at once - recording a qualification opens on top of the
 * employee detail - so the topmost one is the one under test.
 */
export function dialog(page: Page): Locator {
  return page.locator("dialog[open]").last();
}

export function openDialogs(page: Page): Locator {
  return page.locator("dialog[open]");
}

/**
 * Closes the topmost dialog via the icon in its header.
 *
 * The footer of some dialogs carries a "Schliessen" button as well, so the
 * selector has to name the header control specifically.
 */
export async function closeDialog(page: Page): Promise<void> {
  const before = await openDialogs(page).count();
  await dialog(page).locator('button.pds-icon-btn[aria-label="Schliessen"]').click();
  await expect(openDialogs(page)).toHaveCount(before - 1);
}

/** A table row containing the given text, excluding the header row. */
export function row(scope: Page | Locator, text: string): Locator {
  return scope.locator(".pds-table__row").filter({ hasText: text });
}

/**
 * The first table in the content area.
 *
 * Some views carry a second one - Compliance lists the open actions below the
 * records, and an action row repeats the title of its record, so an unscoped
 * lookup by title matches twice.
 */
export function firstTable(page: Page): Locator {
  return main(page).locator(".pds-table").first();
}

/** A page section by its heading, so a row lookup stays inside it. */
export function section(page: Page, title: string): Locator {
  return main(page).locator(".ops-section").filter({
    has: page.locator(".ops-section__title", { hasText: title }),
  });
}

/** Primary action in the content area, e.g. "+ Mitarbeiter". */
export function createButton(page: Page, label: string): Locator {
  return main(page).getByRole("button", { name: label, exact: true });
}

export function segment(page: Page, label: string): Locator {
  return page.locator(".pds-segment__btn").filter({ hasText: label });
}

/** Reads the counter a segment carries, e.g. "Aktiv · 6" -> 6. */
export async function segmentCount(page: Page, label: string): Promise<number> {
  const text = (await segment(page, label).innerText()).trim();
  const match = text.match(/(\d+)\s*$/);
  if (!match) throw new Error(`segment "${label}" carries no count: ${text}`);
  return Number(match[1]);
}

export async function expectToast(page: Page, text: string): Promise<void> {
  await expect(page.locator(".pds-toast")).toHaveText(text);
}

/** Waits for the table to reflect a reload triggered by a save. */
export async function expectRow(page: Page, text: string): Promise<Locator> {
  const target = row(page, text);
  await expect(target).toHaveCount(1);
  return target;
}
