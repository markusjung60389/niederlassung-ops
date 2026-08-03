import { CalendarClock, NotebookPen, UserRoundCheck, Wrench } from "lucide-react";
import type { Assessment, Cockpit, Employee, Reminder, Vehicle } from "../types";
import { Badge, Panel, formatDate } from "../components/ui";
import { AssessmentSummary } from "./AssessmentView";

export function CockpitView({
  cockpit,
  assessments,
  reminders,
  employees,
  vehicles,
}: {
  cockpit: Cockpit;
  assessments: Assessment[];
  reminders: Reminder[];
  employees: Employee[];
  vehicles: Vehicle[];
}) {
  return (
    <section className="stack">
      <div className="metrics">
        {cockpit.metrics.map((metric) => (
          <div className="metric" key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <Badge state={metric.state}>{metric.state}</Badge>
          </div>
        ))}
      </div>
      <div className="grid two">
        <Panel title="Akute Erinnerungen" icon={<CalendarClock size={18} />}>
          <ReminderList reminders={reminders} />
        </Panel>
        <Panel title="Mitarbeiterstatus" icon={<UserRoundCheck size={18} />}>
          <p>{employees.length} Mitarbeiter erfasst.</p>
          <ul className="list">
            {employees.map((employee) => (
              <li key={employee.id}>
                <strong>{employee.full_name}</strong>
                <span>
                  {employee.role} / {employee.profile ? "Pflichtenprofil erfasst" : "Pflichtenprofil offen"}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Fuhrparkstatus" icon={<Wrench size={18} />}>
          <p>{vehicles.length} Fahrzeuge erfasst.</p>
          <ul className="list">
            {vehicles.map((vehicle) => (
              <li key={vehicle.id}>
                <strong>{vehicle.license_plate}</strong>
                <span>
                  {vehicle.brand || "-"} {vehicle.model || ""} / Reifenwechsel {formatDate(vehicle.tire_change_due_date)}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Letzte Bestandsaufnahme" icon={<NotebookPen size={18} />}>
          {assessments[0] ? (
            <AssessmentSummary assessment={assessments[0]} />
          ) : (
            <div className="empty">Noch keine Bestandsaufnahme erfasst.</div>
          )}
        </Panel>
      </div>
    </section>
  );
}

function ReminderList({ reminders }: { reminders: Reminder[] }) {
  if (!reminders.length) return <div className="empty">Keine faelligen Erinnerungen.</div>;
  return (
    <table>
      <thead>
        <tr>
          <th>Status</th>
          <th>Thema</th>
          <th>Faellig</th>
        </tr>
      </thead>
      <tbody>
        {reminders.map((item) => (
          <tr key={`${item.source_type}-${item.source_id}-${item.title}`}>
            <td>
              <Badge state={item.state}>{item.state}</Badge>
            </td>
            <td>
              <strong>{item.title}</strong>
              <span>{item.source_type}</span>
            </td>
            <td>{formatDate(item.due_date)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
