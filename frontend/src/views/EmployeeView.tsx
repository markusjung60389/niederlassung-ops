import React from "react";
import { UserRoundCheck } from "lucide-react";
import { apiDelete, apiPost } from "../api";
import { can, type Bootstrap, type Employee } from "../types";
import {
  DeleteButton,
  FormStatus,
  Panel,
  emptyToNull,
  formatDate,
  splitCsv,
  useAction,
  useSubmit,
} from "../components/ui";

export function EmployeeView({
  employees,
  bootstrap,
  permissions,
  onReload,
}: {
  employees: Employee[];
  bootstrap: Bootstrap;
  permissions: string[];
  onReload: () => void;
}) {
  const mayWrite = can(permissions, "personnel:write");
  const remove = useAction(onReload);

  return (
    <section className="stack">
      {mayWrite && <EmployeeForm bootstrap={bootstrap} onSaved={onReload} />}
      <FormStatus error={remove.error} busy={remove.busy} busyLabel="Wird geloescht..." />
      <div className="grid two">
        {employees.map((employee) => (
          <Panel
            key={employee.id}
            title={employee.full_name}
            icon={<UserRoundCheck size={18} />}
            actions={
              mayWrite ? (
                <DeleteButton
                  label="Loeschen"
                  confirmText={`"${employee.full_name}" mit Pflichtenprofil und Qualifikationen loeschen?`}
                  onConfirm={() => remove.run(() => apiDelete(`/api/employees/${employee.id}`))}
                />
              ) : undefined
            }
          >
            <EmployeeSummary employee={employee} />
          </Panel>
        ))}
      </div>
    </section>
  );
}

function EmployeeSummary({ employee }: { employee: Employee }) {
  const profile = employee.profile;
  return (
    <div className="stack">
      <div className="person">
        <strong>{employee.role}</strong>
        <span>
          {employee.team || "-"} / Start {formatDate(employee.start_date)}
        </span>
      </div>
      <div className="chips">
        {employee.skills.map((skill) => (
          <span key={skill}>{skill}</span>
        ))}
      </div>
      {profile ? (
        <dl>
          <dt>Vertrag</dt>
          <dd>
            {profile.contract_type} bis {formatDate(profile.contract_end)}
          </dd>
          <dt>Aufenthalt</dt>
          <dd>
            {profile.residence_permit_required
              ? `${profile.residence_permit_type || "pflichtig"} bis ${formatDate(profile.residence_permit_valid_until)}`
              : "nicht erfasst/pflichtig"}
          </dd>
          <dt>Fuehrerschein</dt>
          <dd>
            {profile.driver_license_required
              ? `${profile.driver_license_classes.join(", ")} / Kontrolle ${formatDate(profile.driver_license_next_check)}`
              : "nicht benoetigt"}
          </dd>
          <dt>EH / IPAF</dt>
          <dd>
            {formatDate(profile.first_aid_valid_until)} / {formatDate(profile.ipaf_valid_until)}
          </dd>
          <dt>Unterweisung</dt>
          <dd>{formatDate(profile.general_instruction_next)}</dd>
          <dt>Vorsorge</dt>
          <dd>{formatDate(profile.occupational_health_next)}</dd>
        </dl>
      ) : (
        <div className="empty">Pflichtenprofil noch nicht erfasst.</div>
      )}
    </div>
  );
}

function EmployeeForm({ bootstrap, onSaved }: { bootstrap: Bootstrap; onSaved: () => void }) {
  const { error, busy, run } = useSubmit(onSaved);
  const branchId = bootstrap.branches[0]?.id;

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);

    run(form, async () => {
      if (!branchId) throw new Error("Keine Niederlassung verfuegbar.");
      // The profile is only sent once the employee exists. Previously both
      // requests were fired blind, so a failed first call silently discarded
      // the entire compliance profile.
      const employee = await apiPost<Employee>("/api/employees", {
        branch_id: branchId,
        full_name: data.get("full_name"),
        role: data.get("role"),
        team: emptyToNull(data.get("team")),
        start_date: emptyToNull(data.get("start_date")),
        first_aider: data.get("first_aider") === "on",
        skills: splitCsv(data.get("skills")),
      });

      await apiPost("/api/employee-profiles", {
        employee_id: employee.id,
        contract_type: data.get("contract_type"),
        contract_start: emptyToNull(data.get("contract_start")),
        contract_end: emptyToNull(data.get("contract_end")),
        probation_until: emptyToNull(data.get("probation_until")),
        residence_permit_required: data.get("residence_permit_required") === "on",
        residence_permit_type: emptyToNull(data.get("residence_permit_type")),
        residence_permit_valid_until: emptyToNull(data.get("residence_permit_valid_until")),
        work_permit_note: emptyToNull(data.get("work_permit_note")),
        driver_license_required: data.get("driver_license_required") === "on",
        driver_license_classes: splitCsv(data.get("driver_license_classes")),
        driver_license_last_check: emptyToNull(data.get("driver_license_last_check")),
        driver_license_next_check: emptyToNull(data.get("driver_license_next_check")),
        first_aid_last_course: emptyToNull(data.get("first_aid_last_course")),
        first_aid_valid_until: emptyToNull(data.get("first_aid_valid_until")),
        ipaf_last_training: emptyToNull(data.get("ipaf_last_training")),
        ipaf_valid_until: emptyToNull(data.get("ipaf_valid_until")),
        general_instruction_last: emptyToNull(data.get("general_instruction_last")),
        general_instruction_next: emptyToNull(data.get("general_instruction_next")),
        occupational_health_required: data.get("occupational_health_required") === "on",
        occupational_health_last: emptyToNull(data.get("occupational_health_last")),
        occupational_health_next: emptyToNull(data.get("occupational_health_next")),
        ppe_issued_at: emptyToNull(data.get("ppe_issued_at")),
        notes: emptyToNull(data.get("notes")),
      });
    });
  }

  return (
    <form className="form" onSubmit={submit}>
      <h2>Mitarbeiter + Pflichtenprofil erfassen</h2>
      <div className="formGrid">
        <input name="full_name" placeholder="Name" required minLength={2} />
        <input name="role" placeholder="Rolle" required minLength={2} />
        <input name="team" placeholder="Team" />
        <label>
          Eintritt
          <input name="start_date" type="date" />
        </label>
        <input name="skills" placeholder="Skills, kommagetrennt" />
        <label>
          Vertrag
          <select name="contract_type" defaultValue="unbefristet">
            <option value="unbefristet">unbefristet</option>
            <option value="befristet">befristet</option>
            <option value="probezeit/praktikum">Probezeit/Praktikum</option>
          </select>
        </label>
        <label>
          Vertragsbeginn
          <input name="contract_start" type="date" />
        </label>
        <label>
          Befristet bis
          <input name="contract_end" type="date" />
        </label>
        <label>
          Probezeit bis
          <input name="probation_until" type="date" />
        </label>
      </div>
      <div className="formGrid">
        <label>
          <input name="residence_permit_required" type="checkbox" /> Aufenthalt/Arbeitserlaubnis relevant
        </label>
        <input name="residence_permit_type" placeholder="Art Aufenthaltstitel" />
        <label>
          Aufenthalt gueltig bis
          <input name="residence_permit_valid_until" type="date" />
        </label>
        <input name="work_permit_note" placeholder="Arbeitsgenehmigung/Notiz" />
      </div>
      <div className="formGrid">
        <label>
          <input name="driver_license_required" type="checkbox" /> Fuehrerschein erforderlich
        </label>
        <input name="driver_license_classes" placeholder="Klassen, z. B. B, BE" />
        <label>
          Letzte Kontrolle
          <input name="driver_license_last_check" type="date" />
        </label>
        <label>
          Naechste Kontrolle
          <input name="driver_license_next_check" type="date" />
        </label>
      </div>
      <div className="formGrid">
        <label>
          Letzter EH-Kurs
          <input name="first_aid_last_course" type="date" />
        </label>
        <label>
          EH gueltig bis
          <input name="first_aid_valid_until" type="date" />
        </label>
        <label>
          Letzte IPAF
          <input name="ipaf_last_training" type="date" />
        </label>
        <label>
          IPAF gueltig bis
          <input name="ipaf_valid_until" type="date" />
        </label>
        <label>
          Letzte Unterweisung
          <input name="general_instruction_last" type="date" />
        </label>
        <label>
          Naechste Unterweisung
          <input name="general_instruction_next" type="date" />
        </label>
        <label>
          <input name="occupational_health_required" type="checkbox" /> Arbeitsmedizin relevant
        </label>
        <label>
          Naechste Vorsorge
          <input name="occupational_health_next" type="date" />
        </label>
        <label>
          PSA ausgegeben
          <input name="ppe_issued_at" type="date" />
        </label>
      </div>
      <textarea name="notes" placeholder="Weitere Pflichten, Dokumente, Besonderheiten" />
      <FormStatus error={error} busy={busy} />
      <button disabled={busy}>Mitarbeiter speichern</button>
    </form>
  );
}
