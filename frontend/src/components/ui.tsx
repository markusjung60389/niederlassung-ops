import React from "react";
import { errorMessage } from "../api";
import type { State } from "../types";

export function formatDate(value?: string | null) {
  if (!value) return "-";
  // Date-only values must be read as local time; `new Date("2026-09-01")` is
  // parsed as UTC midnight and renders as the previous day west of UTC.
  const parsed = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00`) : new Date(value);
  return Number.isNaN(parsed.getTime()) ? "-" : new Intl.DateTimeFormat("de-DE").format(parsed);
}

export function formatEuro(value: number) {
  return new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(value);
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

export function Badge({ state, children }: { state: State | string; children: React.ReactNode }) {
  return <span className={`badge ${state}`}>{children}</span>;
}

export function Panel({
  title,
  icon,
  actions,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panelTitle">
        {icon}
        <h2>{title}</h2>
        {actions && <div className="panelActions">{actions}</div>}
      </div>
      {children}
    </section>
  );
}

export function Placeholder({ title, icon, lines }: { title: string; icon: React.ReactNode; lines: string[] }) {
  return (
    <Panel title={title} icon={icon}>
      {lines.map((line) => (
        <p key={line}>{line}</p>
      ))}
    </Panel>
  );
}

/**
 * Runs a form submission, keeping the entered values when the request fails.
 * The original version reset the form unconditionally, so a rejected save
 * looked identical to a successful one.
 */
export function useSubmit(onSuccess: () => void) {
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const run = React.useCallback(
    async (form: HTMLFormElement, action: () => Promise<void>) => {
      setBusy(true);
      setError(null);
      try {
        await action();
        form.reset();
        onSuccess();
      } catch (caught) {
        setError(errorMessage(caught));
      } finally {
        setBusy(false);
      }
    },
    [onSuccess]
  );

  return { error, busy, run };
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

  return { error, busy, run };
}

export function FormStatus({ error, busy, busyLabel = "Wird gespeichert..." }: { error: string | null; busy: boolean; busyLabel?: string }) {
  if (busy) return <div className="notice">{busyLabel}</div>;
  if (error) return <div className="notice danger">Fehlgeschlagen: {error}</div>;
  return null;
}

export function DeleteButton({
  label,
  confirmText,
  onConfirm,
}: {
  label: string;
  confirmText: string;
  onConfirm: () => void;
}) {
  return (
    <button
      type="button"
      className="danger"
      onClick={() => {
        if (window.confirm(confirmText)) onConfirm();
      }}
    >
      {label}
    </button>
  );
}
