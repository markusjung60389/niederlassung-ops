import React from "react";

/**
 * Werkbank table: a CSS grid, not a `<table>`.
 *
 * Only a grid lets column widths mix `fr` and pixels while every cell still
 * truncates cleanly, which is what the design calls for (Styleguide 7.5).
 * Accessibility comes from the ARIA grid roles rather than table semantics.
 */

export function Table({
  columns,
  head,
  children,
  empty,
  minWidth = 880,
}: {
  /** grid-template-columns, e.g. "110px minmax(0,1.6fr) 120px 40px". */
  columns: string;
  head: React.ReactNode[];
  children: React.ReactNode;
  empty?: string;
  minWidth?: number;
}) {
  const rows = React.Children.toArray(children);
  return (
    <div className="ops-scroll">
      <div className="pds-table" role="grid" style={{ minWidth }}>
        <div className="pds-table__head" role="row" style={{ gridTemplateColumns: columns }}>
          {head.map((cell, index) => (
            <span key={index} role="columnheader" className="ops-cell">
              {cell}
            </span>
          ))}
        </div>
        {rows.length ? rows : <div className="pds-table__empty">{empty ?? "Keine Eintraege."}</div>}
      </div>
    </div>
  );
}

export function Row({
  columns,
  onOpen,
  children,
  title,
}: {
  columns: string;
  /** Omitted for rows without a detail view; the row is then not clickable. */
  onOpen?: () => void;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <div
      role="row"
      className={`pds-table__row${onOpen ? "" : " is-static"}`}
      style={{ gridTemplateColumns: columns }}
      tabIndex={onOpen ? 0 : undefined}
      title={title}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (!onOpen) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
    >
      {children}
    </div>
  );
}

export function Cell({
  children,
  className = "",
  title,
}: {
  children: React.ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span role="gridcell" className={`ops-cell ${className}`.trim()} title={title}>
      {children}
    </span>
  );
}

/** Two-line cell: bold primary line, muted secondary line. */
export function TitleCell({ title, meta }: { title: string; meta?: React.ReactNode }) {
  return (
    <span role="gridcell" className="ops-cell">
      <span className="ops-cell__title" title={title}>
        {title}
      </span>
      {meta !== undefined && meta !== null && <span className="ops-cell__meta">{meta}</span>}
    </span>
  );
}

/**
 * Row actions.
 *
 * `stopPropagation` matters: without it, pressing Delete would also open the
 * detail dialog underneath.
 */
export function ActionCell({ children }: { children: React.ReactNode }) {
  return (
    <span
      role="gridcell"
      className="ops-cell ops-cell--actions"
      onClick={(event) => event.stopPropagation()}
    >
      {children}
    </span>
  );
}
