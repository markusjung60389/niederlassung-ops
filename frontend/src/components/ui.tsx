import React from "react";
import { Search, X } from "lucide-react";
import { errorMessage } from "../api";

/* --------------------------------------------------------------------------
 * Formatting
 * ----------------------------------------------------------------------- */

export function formatDate(value?: string | null) {
  if (!value) return "-";
  // Date-only values must be read as local time; `new Date("2026-09-01")` is
  // parsed as UTC midnight and renders as the previous day west of UTC.
  const parsed = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00`) : new Date(value);
  return Number.isNaN(parsed.getTime()) ? "-" : new Intl.DateTimeFormat("de-DE").format(parsed);
}

export function formatEuro(value: number) {
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatBytes(value?: number | null) {
  if (!value) return "-";
  const units = ["B", "kB", "MB", "GB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export function splitCsv(value: FormDataEntryValue | null) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function emptyToNull(value: FormDataEntryValue | null) {
  const text = String(value || "").trim();
  return text ? text : null;
}

export function numberOrNull(value: FormDataEntryValue | null) {
  const text = String(value || "").trim();
  return text ? Number(text) : null;
}

/** Days until a date, negative when it has passed. */
export function daysUntil(value?: string | null): number | null {
  if (!value) return null;
  const target = new Date(`${value}T00:00:00`);
  if (Number.isNaN(target.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}

/* --------------------------------------------------------------------------
 * Status
 * ----------------------------------------------------------------------- */

export type Tone = "ok" | "warn" | "danger" | "muted" | "info";

/** Backend traffic-light value to the design's tone vocabulary. */
export function toneOf(state?: string | null): Tone {
  if (state === "red") return "danger";
  if (state === "yellow") return "warn";
  if (state === "green") return "ok";
  return "muted";
}

export function Pill({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <span className={`pds-pill pds-pill--${tone}`}>
      <span className="pds-pill__dot" />
      {children}
    </span>
  );
}

/**
 * Date with a tone.
 *
 * Colour alone never carries the message - overdue dates are also bold and
 * carry a title, so the state survives a black-and-white printout and a
 * colour-blind reader (Styleguide section 9).
 */
export function DueDate({ value, tone }: { value?: string | null; tone?: Tone }) {
  const days = daysUntil(value);
  const derived: Tone =
    tone ?? (days === null ? "muted" : days < 0 ? "danger" : days <= 30 ? "warn" : "ok");
  const suffix = derived === "danger" ? " is-red" : derived === "warn" ? " is-yellow" : "";
  const hint =
    days === null
      ? undefined
      : days < 0
        ? `seit ${Math.abs(days)} Tagen ueberfaellig`
        : `in ${days} Tagen faellig`;
  return (
    <span className={`ops-date${value ? suffix : " is-muted"}`} title={hint}>
      {formatDate(value)}
    </span>
  );
}

/* --------------------------------------------------------------------------
 * Page furniture
 * ----------------------------------------------------------------------- */

export function Section({
  title,
  actions,
  flush = false,
  children,
}: {
  title: string;
  actions?: React.ReactNode;
  flush?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className="ops-section">
      <div className="ops-section__head">
        <h2 className="ops-section__title">{title}</h2>
        {actions && <div className="ops-row ops-spacer">{actions}</div>}
      </div>
      <div className={`ops-section__body${flush ? " ops-section__body--flush" : ""}`}>{children}</div>
    </section>
  );
}

export function SearchField({
  value,
  onChange,
  placeholder = "Suchen...",
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="pds-search">
      <Search className="pds-search__icon" size={15} />
      <input
        className="pds-input"
        type="search"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
      {value && (
        <button
          type="button"
          className="pds-btn pds-btn--link"
          style={{ position: "absolute", right: 10 }}
          onClick={() => onChange("")}
          aria-label="Suche leeren"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}

/** Segment control. Segments always carry a count (Styleguide 7.3). */
export function Segments<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { key: T; label: string; count: number }[];
  onChange: (next: T) => void;
}) {
  return (
    <div className="pds-segment" role="tablist">
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          role="tab"
          aria-selected={option.key === value}
          className={`pds-segment__btn${option.key === value ? " is-active" : ""}`}
          onClick={() => onChange(option.key)}
        >
          {option.label} &middot; {option.count}
        </button>
      ))}
    </div>
  );
}

export function Banner({
  tone = "info",
  children,
}: {
  tone?: "info" | "warn" | "danger";
  children: React.ReactNode;
}) {
  return (
    <div className={`pds-banner${tone === "info" ? "" : ` pds-banner--${tone}`}`}>{children}</div>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="ops-empty">{children}</div>;
}

/* --------------------------------------------------------------------------
 * Form fields
 * ----------------------------------------------------------------------- */

export function Field({
  label,
  children,
  span,
}: {
  label: string;
  children: React.ReactNode;
  span?: boolean;
}) {
  return (
    <label className="pds-field" style={span ? { gridColumn: "1 / -1" } : undefined}>
      <span className="pds-label">{label}</span>
      {children}
    </label>
  );
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`pds-input ${props.className ?? ""}`.trim()} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`pds-select ${props.className ?? ""}`.trim()} />;
}

export function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`pds-textarea ${props.className ?? ""}`.trim()} />;
}

export function Checkbox({
  name,
  label,
  defaultChecked,
}: {
  name: string;
  label: string;
  defaultChecked?: boolean;
}) {
  return (
    <label className="ops-check">
      <input type="checkbox" name={name} defaultChecked={defaultChecked} />
      {label}
    </label>
  );
}

export function Fieldset({ legend, children }: { legend: string; children: React.ReactNode }) {
  return (
    <fieldset className="ops-fieldset">
      <legend>{legend}</legend>
      {children}
    </fieldset>
  );
}

/* --------------------------------------------------------------------------
 * Async state
 * ----------------------------------------------------------------------- */

/**
 * Runs a form submission, keeping the entered values when the request fails.
 * The original version reset the form unconditionally, so a rejected save
 * looked identical to a successful one.
 */
export function useSubmit(onSuccess: () => void) {
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const run = React.useCallback(
    async (form: HTMLFormElement | null, action: () => Promise<void>) => {
      setBusy(true);
      setError(null);
      try {
        await action();
        form?.reset();
        onSuccess();
      } catch (caught) {
        setError(errorMessage(caught));
      } finally {
        setBusy(false);
      }
    },
    [onSuccess]
  );

  return { error, busy, run, setError };
}

/** Same guarantees as useSubmit, for buttons rather than forms. */
export function useAction(onSuccess: () => void) {
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const run = React.useCallback(
    async (action: () => Promise<void>) => {
      setBusy(true);
      setError(null);
      try {
        await action();
        onSuccess();
      } catch (caught) {
        setError(errorMessage(caught));
      } finally {
        setBusy(false);
      }
    },
    [onSuccess]
  );

  return { error, busy, run, setError };
}

export function FormStatus({
  error,
  busy,
  busyLabel = "Wird gespeichert...",
}: {
  error: string | null;
  busy: boolean;
  busyLabel?: string;
}) {
  if (busy) return <div className="pds-banner">{busyLabel}</div>;
  if (error) return <div className="pds-banner pds-banner--danger">Fehlgeschlagen: {error}</div>;
  return null;
}

/**
 * Toast: dark, centred, ~2.6s, not clickable (Styleguide 7.9).
 *
 * Saving used to give no feedback at all - the dialog closed and the table
 * silently reloaded.
 */
export function useToast() {
  const [message, setMessage] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(() => setMessage(null), 2600);
    return () => window.clearTimeout(timer);
  }, [message]);

  const node = message ? (
    <div className="pds-toast-layer">
      <span className="pds-toast">{message}</span>
    </div>
  ) : null;

  return { show: setMessage, node };
}
