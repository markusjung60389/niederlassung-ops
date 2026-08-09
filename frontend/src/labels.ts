/**
 * German labels for the values the API stores in English.
 *
 * Previously the raw enum reached the screen: a branch manager read
 * "training_instruction / non_compliant" in the compliance list. One mapping
 * for the whole application, so the same value is never named two ways.
 */

const CATEGORY: Record<string, string> = {
  training_instruction: "Unterweisung",
  risk_assessment: "Gefaehrdungsbeurteilung",
  tools_and_equipment_inspection: "Arbeitsmittelpruefung",
  first_aid: "Erste Hilfe",
  occupational_health: "Arbeitsmedizin",
  electrical_safety: "Elektrosicherheit",
  documentation: "Dokumentation",
};

const STATUS: Record<string, string> = {
  open: "offen",
  in_progress: "in Arbeit",
  compliant: "erfuellt",
  non_compliant: "nicht erfuellt",
  waived: "ausgesetzt",
  expired: "abgelaufen",
  done: "erledigt",
  cancelled: "abgebrochen",
  blocked: "blockiert",
};

const PRIORITY: Record<string, string> = {
  low: "niedrig",
  medium: "mittel",
  high: "hoch",
  critical: "kritisch",
};

const CONTROL_TYPE: Record<string, string> = {
  document: "Dokument",
  training: "Schulung",
  inspection: "Pruefung",
  medical: "Vorsorge",
  process: "Prozess",
  incident: "Ereignis",
  approval: "Freigabe",
};

const RECURRENCE: Record<string, string> = {
  one_time: "einmalig",
  monthly: "monatlich",
  quarterly: "quartalsweise",
  yearly: "jaehrlich",
  event_based: "anlassbezogen",
};

const REQUIREMENT: Record<string, string> = {
  ok: "gueltig",
  expiring: "laeuft ab",
  expired: "abgelaufen",
  missing: "fehlt",
  undated: "ohne Datum",
  evidence_missing: "Nachweis fehlt",
  not_required: "nicht gefordert",
};

const READINESS: Record<string, string> = {
  ready: "einsatzfaehig",
  limited: "eingeschraenkt",
  blocked: "nicht einsatzfaehig",
};

const QUALIFICATION_CATEGORY: Record<string, string> = {
  licence: "Fahrerlaubnis",
  training: "Schulung",
  medical: "Vorsorge",
  instruction: "Unterweisung",
  qualification: "Qualifikation",
};

const SOURCE_TYPE: Record<string, string> = {
  employee: "Mitarbeiter",
  employee_qualification: "Qualifikation",
  vehicle: "Fahrzeug",
};

const EMPLOYEE_STATUS: Record<string, string> = {
  active: "aktiv",
  inactive: "ausgeschieden",
};

function lookup(table: Record<string, string>, value?: string | null): string {
  if (!value) return "-";
  return table[value] ?? value;
}

export const label = {
  category: (value?: string | null) => lookup(CATEGORY, value),
  status: (value?: string | null) => lookup(STATUS, value),
  priority: (value?: string | null) => lookup(PRIORITY, value),
  controlType: (value?: string | null) => lookup(CONTROL_TYPE, value),
  recurrence: (value?: string | null) => lookup(RECURRENCE, value),
  requirement: (value?: string | null) => lookup(REQUIREMENT, value),
  readiness: (value?: string | null) => lookup(READINESS, value),
  qualificationCategory: (value?: string | null) => lookup(QUALIFICATION_CATEGORY, value),
  sourceType: (value?: string | null) => lookup(SOURCE_TYPE, value),
  employeeStatus: (value?: string | null) => lookup(EMPLOYEE_STATUS, value),
};

/** Select options, in the order a form should offer them. */
export const options = {
  category: Object.entries(CATEGORY),
  status: [
    ["open", STATUS.open],
    ["in_progress", STATUS.in_progress],
    ["compliant", STATUS.compliant],
    ["non_compliant", STATUS.non_compliant],
  ] as [string, string][],
  priority: Object.entries(PRIORITY),
  controlType: Object.entries(CONTROL_TYPE),
  recurrence: Object.entries(RECURRENCE),
  qualificationCategory: Object.entries(QUALIFICATION_CATEGORY),
};

/**
 * Tone per requirement state.
 *
 * Amber, not red, for anything merely incomplete - red stays reserved for
 * what actually stops an assignment (Styleguide section 3). An optional
 * qualification nobody holds is not a gap either, so it stays neutral;
 * marking it red would leave the matrix permanently alarming.
 */
export function requirementTone(
  state: string,
  mandatory = true
): "ok" | "warn" | "danger" | "muted" {
  if (state === "ok") return "ok";
  if (state === "not_required") return "muted";
  if (state === "missing" && !mandatory) return "muted";
  if (state === "missing" || state === "expired" || state === "undated") return "danger";
  return "warn";
}

/** Single character shown in the matrix, so the state reads without colour. */
export function requirementMark(state: string): string {
  switch (state) {
    case "ok":
      return "OK";
    case "expiring":
      return "!";
    case "evidence_missing":
      return "?";
    case "expired":
      return "X";
    case "undated":
      return "~";
    case "missing":
      return "-";
    default:
      // "not_required": a neutral dot, so no cell in the matrix reads as
      // missing data.
      return "·";
  }
}
