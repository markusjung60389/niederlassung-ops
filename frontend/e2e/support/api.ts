import type { APIRequestContext } from "@playwright/test";
import { BACKEND_URL } from "../../playwright.config";

/**
 * Preconditions are created through the API, behaviour is exercised through
 * the UI.
 *
 * Clicking a thirty-field form open just to get an employee that a test then
 * edits would make every spec depend on the create dialog, and a failure there
 * would light up the whole suite.
 */

export const AREA_MANAGER = "user-area-manager";
export const MANAGER = "user-branch-manager";
export const HSE = "user-hse";
export const VIEWER = "user-viewer";
export const BRANCH = "branch-remscheid";

/**
 * A second branch, created once and reused.
 *
 * The seed deliberately creates only Remscheid - the names of the other
 * branches belong to the organisation, not to a seed file - so the multi-branch
 * specs create their own and the single-branch specs never see it.
 */
export async function ensureSecondBranch(
  request: APIRequestContext,
  name = "E2E Solingen",
  code = "SG"
): Promise<{ id: string; name: string; code: string }> {
  const existing = await api.get<{ id: string; name: string; code: string }[]>(
    request,
    "/api/branches",
    AREA_MANAGER
  );
  const match = existing.find((item) => item.name === name);
  if (match) return match;
  return api.post(request, "/api/branches", { name, code, location: name }, AREA_MANAGER);
}

export const JOB_ROLE = {
  projektleiter: "jr-projektleiter",
  serviceTechniker: "jr-service-techniker",
  monteur: "jr-monteur",
} as const;

export const QUALIFICATION = {
  unterweisung: "qt-unterweisung",
  ipaf: "qt-ipaf",
  psaAbsturz: "qt-psa-absturz",
  arbeitsmedizin: "qt-arbeitsmedizin",
  fuehrerschein: "qt-fuehrerschein",
  fuehrerscheinKontrolle: "qt-fuehrerschein-kontrolle",
  ersteHilfe: "qt-erste-hilfe",
  befaehigtePerson: "qt-befaehigte-person",
} as const;

/** Everything a Monteur must hold to count as deployable. */
export const MONTEUR_MANDATORY = [
  QUALIFICATION.unterweisung,
  QUALIFICATION.ipaf,
  QUALIFICATION.psaAbsturz,
  QUALIFICATION.arbeitsmedizin,
];

let counter = 0;

/** Unique across a run, so specs never collide in the shared database. */
export function unique(prefix: string): string {
  counter += 1;
  return `${prefix} ${Date.now().toString(36).slice(-4)}${counter}`;
}

export function isoDay(offsetDays: number): string {
  const date = new Date();
  date.setHours(12, 0, 0, 0);
  date.setDate(date.getDate() + offsetDays);
  return date.toISOString().slice(0, 10);
}

/**
 * Mirrors `domain.add_months` on the backend: whole calendar months, clamped
 * to the end of the target month. Written out here so the expectation is
 * independent of the implementation it checks.
 */
export function addMonths(isoDate: string, months: number): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  const total = month - 1 + months;
  const targetYear = year + Math.floor(total / 12);
  const targetMonth = (total % 12) + 1;
  const lastDay = new Date(Date.UTC(targetYear, targetMonth, 0)).getUTCDate();
  const targetDay = Math.min(day, lastDay);
  return [
    targetYear,
    String(targetMonth).padStart(2, "0"),
    String(targetDay).padStart(2, "0"),
  ].join("-");
}

async function call<T>(
  request: APIRequestContext,
  method: "post" | "patch" | "get" | "delete",
  path: string,
  body?: unknown,
  userId: string = MANAGER
): Promise<T> {
  const response = await request[method](`${BACKEND_URL}${path}`, {
    headers: { "X-User-Id": userId, "Content-Type": "application/json" },
    data: body === undefined ? undefined : body,
  });
  if (!response.ok()) {
    throw new Error(`${method.toUpperCase()} ${path} -> ${response.status()} ${await response.text()}`);
  }
  return response.status() === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const api = {
  get: <T>(request: APIRequestContext, path: string, userId?: string) =>
    call<T>(request, "get", path, undefined, userId),
  post: <T>(request: APIRequestContext, path: string, body: unknown, userId?: string) =>
    call<T>(request, "post", path, body, userId),
  patch: <T>(request: APIRequestContext, path: string, body: unknown, userId?: string) =>
    call<T>(request, "patch", path, body, userId),
  delete: (request: APIRequestContext, path: string, userId?: string) =>
    call<void>(request, "delete", path, undefined, userId),
};

export type Employee = {
  id: string;
  full_name: string;
  readiness: "ready" | "limited" | "blocked";
  due_state: "red" | "yellow" | "green";
  open_requirements: number;
  requirements: { qualification_type_id: string; state: string; mandatory: boolean }[];
};

export async function createEmployee(
  request: APIRequestContext,
  overrides: Record<string, unknown> = {}
): Promise<Employee> {
  return api.post<Employee>(request, "/api/employees", {
    branch_id: BRANCH,
    full_name: unique("E2E Person"),
    role: "Mitarbeiter",
    job_role_id: JOB_ROLE.monteur,
    team: "E2E",
    start_date: isoDay(-400),
    ...overrides,
  });
}

export async function uploadDocument(
  request: APIRequestContext,
  title: string
): Promise<{ id: string }> {
  const response = await request.post(`${BACKEND_URL}/api/documents`, {
    headers: { "X-User-Id": MANAGER },
    multipart: {
      file: { name: `${title}.pdf`, mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 e2e") },
      title,
    },
  });
  if (!response.ok()) throw new Error(`document upload -> ${response.status()} ${await response.text()}`);
  return response.json();
}

/**
 * Records a qualification. `withDocument` matters: every catalogue entry
 * requires evidence, so a valid date on its own only reaches
 * "Nachweis fehlt".
 */
export async function addQualification(
  request: APIRequestContext,
  employeeId: string,
  typeId: string,
  options: { validUntil?: string | null; issuedOn?: string; withDocument?: boolean } = {}
): Promise<{ id: string; valid_until: string | null; title: string }> {
  const { validUntil = isoDay(900), issuedOn, withDocument = true } = options;
  const document = withDocument ? await uploadDocument(request, `${employeeId}-${typeId}`) : null;
  return api.post(request, "/api/employee-qualifications", {
    employee_id: employeeId,
    qualification_type_id: typeId,
    issued_on: issuedOn ?? null,
    valid_until: validUntil,
    document_id: document?.id ?? null,
  });
}

/** An employee that satisfies every mandatory requirement of their function. */
export async function createReadyMonteur(
  request: APIRequestContext,
  overrides: Record<string, unknown> = {}
): Promise<Employee> {
  const employee = await createEmployee(request, overrides);
  for (const typeId of MONTEUR_MANDATORY) {
    await addQualification(request, employee.id, typeId);
  }
  return api.get<Employee>(request, `/api/employees/${employee.id}`);
}

export async function createVehicle(
  request: APIRequestContext,
  overrides: Record<string, unknown> = {}
): Promise<{ id: string; license_plate: string; driver_alert: string | null; due_state: string }> {
  return api.post(request, "/api/vehicles", {
    branch_id: BRANCH,
    license_plate: unique("RS-E2E").replace(/\s+/g, "-").slice(0, 20),
    brand: "Mercedes",
    model: "Sprinter",
    vehicle_type: "Transporter",
    hu_due_date: isoDay(400),
    uvv_next_check: isoDay(400),
    service_due_date: isoDay(400),
    ...overrides,
  });
}

export async function createRecord(
  request: APIRequestContext,
  overrides: Record<string, unknown> = {}
): Promise<{ id: string; title: string }> {
  return api.post(request, "/api/compliance-records", {
    title: unique("E2E Pflicht"),
    category: "training_instruction",
    branch_id: BRANCH,
    owner_user_id: MANAGER,
    legal_basis: "DGUV Vorschrift 1",
    control_type: "training",
    priority: "high",
    status: "open",
    recurrence: "yearly",
    due_date: isoDay(30),
    review_date: isoDay(30),
    tags: [],
    scope_type: "branch",
    ...overrides,
  });
}
