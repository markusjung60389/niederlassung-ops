import React from "react";
import { label, requirementMark, requirementTone } from "../labels";
import type { QualificationMatrix, Readiness } from "../types";
import { EmptyState, Pill, SearchField, Segments, formatDate, toneOf } from "../components/ui";

/**
 * Employees against qualification types.
 *
 * The screen a branch manager actually plans from: one look shows who cannot
 * be assigned, and which refreshers fall in the same quarter and can be booked
 * as one course.
 */

const TONE_BY_READINESS: Record<Readiness, "green" | "yellow" | "red"> = {
  ready: "green",
  limited: "yellow",
  blocked: "red",
};

type Filter = "all" | "blocked" | "open";

export function MatrixView({ matrix }: { matrix: QualificationMatrix | null }) {
  const [filter, setFilter] = React.useState<Filter>("all");
  const [search, setSearch] = React.useState("");

  if (!matrix || !matrix.rows.length) {
    return (
      <EmptyState>
        Noch keine Mitarbeiter mit zugeordneter Funktion &ndash; ohne Funktion ist nicht bestimmbar,
        welche Qualifikationen gefordert sind.
      </EmptyState>
    );
  }

  const hasOpen = (row: QualificationMatrix["rows"][number]) =>
    row.cells.some((cell) => cell.state !== "ok" && cell.state !== "not_required");

  const counts = {
    all: matrix.rows.length,
    blocked: matrix.rows.filter((row) => row.readiness === "blocked").length,
    open: matrix.rows.filter(hasOpen).length,
  };

  const rows = matrix.rows
    .filter((row) => {
      if (filter === "blocked") return row.readiness === "blocked";
      if (filter === "open") return hasOpen(row);
      return true;
    })
    .filter((row) => {
      const needle = search.trim().toLowerCase();
      if (!needle) return true;
      return `${row.full_name} ${row.job_role_name ?? ""}`.toLowerCase().includes(needle);
    });

  return (
    <section className="ops-stack">
      <div className="ops-row ops-row--between">
        <Segments<Filter>
          value={filter}
          onChange={setFilter}
          options={[
            { key: "all", label: "Alle", count: counts.all },
            { key: "blocked", label: "Nicht einsatzfaehig", count: counts.blocked },
            { key: "open", label: "Mit Luecken", count: counts.open },
          ]}
        />
        <div className="ops-row ops-spacer">
          <SearchField value={search} onChange={setSearch} placeholder="Name oder Funktion" />
        </div>
      </div>

      <div className="pds-banner">
        <strong>OK</strong> gueltig &middot; <strong>!</strong> laeuft ab &middot; <strong>?</strong>{" "}
        Nachweis fehlt &middot; <strong>X</strong> abgelaufen &middot; <strong>~</strong> ohne Datum
        &middot; <strong>&ndash;</strong> fehlt. Pflichtanforderungen sind fett gesetzt.
      </div>

      <div className="pds-table ops-scroll">
        <table className="ops-matrix">
          <thead>
            <tr>
              <th className="ops-matrix__person">Mitarbeiter</th>
              <th>Einsatz</th>
              {matrix.qualification_types.map((kind) => (
                <th key={kind.id} className="ops-matrix__kind" title={kind.legal_basis ?? kind.name}>
                  {kind.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.employee_id}>
                <td className="ops-matrix__person">
                  <span className="ops-cell__title">{row.full_name}</span>
                  <span className="ops-cell__meta">{row.job_role_name ?? "ohne Funktion"}</span>
                </td>
                <td>
                  <Pill tone={toneOf(TONE_BY_READINESS[row.readiness])}>
                    {label.readiness(row.readiness)}
                  </Pill>
                </td>
                {row.cells.map((cell) => (
                  <td key={cell.qualification_type_id} className="ops-matrix__cell">
                    <span
                      className={`ops-mark ops-mark--${requirementTone(cell.state, cell.mandatory)}`}
                      style={cell.mandatory ? undefined : { fontWeight: 400, opacity: 0.75 }}
                      title={`${label.requirement(cell.state)}${
                        cell.valid_until ? ` bis ${formatDate(cell.valid_until)}` : ""
                      }${cell.mandatory ? " (Pflicht)" : " (optional)"}`}
                    >
                      {requirementMark(cell.state)}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
