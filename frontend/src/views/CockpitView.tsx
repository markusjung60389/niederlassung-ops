import React from "react";
import { TriangleAlert } from "lucide-react";
import { label } from "../labels";
import type { Cockpit, Employee, Reminder, Vehicle } from "../types";
import { Cell, Row, Table, TitleCell } from "../components/Table";
import {
  DueDate,
  EmptyState,
  Pill,
  Section,
  Segments,
  daysUntil,
  formatEuro,
  toneOf,
} from "../components/ui";

/**
 * The cockpit as a work list.
 *
 * It used to be a wall of figures plus a full roster of every employee and
 * vehicle without any status - at thirty people that is a list of names, not
 * an answer. What a branch manager needs first is what is overdue, what is due
 * this month, and who cannot be assigned today.
 */

const WORK_COLUMNS = "104px minmax(0,2fr) minmax(0,1fr) 120px";
type Window = "overdue" | "soon" | "later";

export function CockpitView({
  cockpit,
  reminders,
  employees,
  vehicles,
  onNavigate,
}: {
  cockpit: Cockpit;
  reminders: Reminder[];
  employees: Employee[];
  vehicles: Vehicle[];
  onNavigate: (view: string) => void;
}) {
  const [windowFilter, setWindowFilter] = React.useState<Window>("overdue");

  const bucket = (item: Reminder): Window => {
    const days = daysUntil(item.due_date);
    if (days === null || days < 0) return "overdue";
    return days <= 30 ? "soon" : "later";
  };

  const counts = {
    overdue: reminders.filter((item) => bucket(item) === "overdue").length,
    soon: reminders.filter((item) => bucket(item) === "soon").length,
    later: reminders.filter((item) => bucket(item) === "later").length,
  };
  const work = reminders.filter((item) => bucket(item) === windowFilter);

  const blocked = employees.filter((item) => item.readiness === "blocked");
  const driverAlerts = vehicles.filter((item) => item.driver_alert);
  const firstAiders = cockpit.first_aiders;

  return (
    <section className="ops-stack">
      <div className="ops-metrics">
        {cockpit.metrics.map((metric) => (
          <div key={metric.label} className={`ops-metric is-${metric.state}`}>
            <span className="ops-metric__label">{metric.label}</span>
            <strong className="ops-metric__value">
              {metric.label.includes("EUR") ? formatEuro(metric.value) : metric.value}
            </strong>
          </div>
        ))}
      </div>

      {blocked.length > 0 && (
        <div className="pds-banner pds-banner--warn">
          <TriangleAlert size={15} />
          <span>
            {blocked.length === 1
              ? `${blocked[0].full_name} ist nicht einsatzfaehig.`
              : `${blocked.length} Mitarbeiter sind nicht einsatzfaehig.`}{" "}
            Pflichtqualifikationen fehlen oder sind abgelaufen.
          </span>
          <button
            type="button"
            className="pds-btn pds-btn--link"
            onClick={() => onNavigate("qualifikationen")}
          >
            Zur Qualifikationsmatrix
          </button>
        </div>
      )}

      {driverAlerts.length > 0 && (
        <div className="pds-banner pds-banner--warn">
          <TriangleAlert size={15} />
          <span>
            {driverAlerts.length} Fahrzeug(e) mit ueberfaelliger Fuehrerscheinkontrolle des
            zugeordneten Fahrers &ndash; Halterhaftung.
          </span>
          <button type="button" className="pds-btn pds-btn--link" onClick={() => onNavigate("fahrzeuge")}>
            Zu den Fahrzeugen
          </button>
        </div>
      )}

      <Section
        title="Was ansteht"
        actions={
          <Segments<Window>
            value={windowFilter}
            onChange={setWindowFilter}
            options={[
              { key: "overdue", label: "Ueberfaellig", count: counts.overdue },
              { key: "soon", label: "30 Tage", count: counts.soon },
              { key: "later", label: "Spaeter", count: counts.later },
            ]}
          />
        }
        flush
      >
        <Table
          columns={WORK_COLUMNS}
          minWidth={700}
          head={["Status", "Thema", "Bereich", "Faellig"]}
          empty={
            windowFilter === "overdue"
              ? "Nichts ueberfaellig."
              : "In diesem Zeitraum ist nichts faellig."
          }
        >
          {work.map((item) => (
            <Row
              key={`${item.source_type}-${item.source_id}-${item.title}`}
              columns={WORK_COLUMNS}
              onOpen={() =>
                onNavigate(item.source_type === "vehicle" ? "fahrzeuge" : "mitarbeiter")
              }
              title="Zum Bereich springen"
            >
              <Cell>
                <Pill tone={toneOf(item.state)}>
                  {item.state === "red" ? "ueberfaellig" : item.state === "yellow" ? "bald" : "offen"}
                </Pill>
              </Cell>
              <TitleCell title={item.title} meta={item.owner_hint ?? undefined} />
              <Cell>
                <span className="pds-meta">{label.sourceType(item.source_type)}</span>
              </Cell>
              <Cell>
                <DueDate value={item.due_date} />
              </Cell>
            </Row>
          ))}
        </Table>
      </Section>

      <div className="ops-metrics" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))" }}>
        <Section title="Einsatzfaehigkeit">
          {employees.length ? (
            <dl className="ops-facts">
              <dt>Nicht einsatzfaehig</dt>
              <dd>
                <Pill tone={cockpit.blocked_employees ? "danger" : "ok"}>
                  {cockpit.blocked_employees} von {employees.length}
                </Pill>
              </dd>
              <dt>Eingeschraenkt</dt>
              <dd>
                <Pill tone={cockpit.limited_employees ? "warn" : "ok"}>
                  {cockpit.limited_employees}
                </Pill>
              </dd>
              {firstAiders && (
                <>
                  <dt>Ersthelfer</dt>
                  <dd>
                    <Pill tone={toneOf(firstAiders.state)}>
                      {firstAiders.trained} von {firstAiders.required} erforderlich
                    </Pill>
                  </dd>
                </>
              )}
            </dl>
          ) : (
            <EmptyState>Noch keine Mitarbeiter erfasst.</EmptyState>
          )}
        </Section>

        <Section title="Nicht einsatzfaehig">
          {blocked.length ? (
            <ul style={{ display: "grid", gap: 8, listStyle: "none", margin: 0, padding: 0 }}>
              {blocked.slice(0, 6).map((employee) => (
                <li key={employee.id}>
                  <span className="ops-cell__title">{employee.full_name}</span>
                  <span className="ops-cell__meta">
                    {employee.job_role_name ?? employee.role} &middot; {employee.next_due_title}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState>Alle Mitarbeiter sind einsatzfaehig.</EmptyState>
          )}
        </Section>
      </div>
    </section>
  );
}
