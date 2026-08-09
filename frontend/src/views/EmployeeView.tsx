import React from "react";
import { Eye, Pencil, Plus, Trash2, TriangleAlert } from "lucide-react";
import { ApiError, apiDelete, apiPatch, apiPost, apiStepUp, errorMessage } from "../api";
import { label, requirementTone } from "../labels";
import {
  can,
  type Branch,
  type Employee,
  type JobRole,
  type Qualification,
  type QualificationType,
  type RequirementState,
  type Salary,
} from "../types";
import { ActionCell, Cell, Row, Table, TitleCell } from "../components/Table";
import { ConfirmDialog, Modal } from "../components/Modal";
import {
  Checkbox,
  DueDate,
  EmptyState,
  Field,
  Fieldset,
  FormStatus,
  Pill,
  SearchField,
  Segments,
  Select,
  TextArea,
  TextInput,
  emptyToNull,
  formatDate,
  formatEuro,
  numberOrNull,
  splitCsv,
  toneOf,
  useAction,
  useSubmit,
} from "../components/ui";

const COLUMNS = "128px minmax(0,1.5fr) minmax(0,1fr) minmax(0,1.3fr) 132px 92px";
type Filter = "all" | "blocked" | "limited" | "inactive";

export function EmployeeView({
  employees,
  jobRoles,
  qualificationTypes,
  branches,
  branchId,
  permissions,
  onReload,
  onToast,
}: {
  employees: Employee[];
  jobRoles: JobRole[];
  qualificationTypes: QualificationType[];
  branches: Branch[];
  /** The selected branch, or null while every branch is shown at once. */
  branchId: string | null;
  permissions: string[];
  onReload: () => void;
  onToast: (message: string) => void;
}) {
  const mayWrite = can(permissions, "personnel:write");
  const [filter, setFilter] = React.useState<Filter>("all");
  const [search, setSearch] = React.useState("");
  const [editing, setEditing] = React.useState<Employee | null | "new">(null);
  const [detail, setDetail] = React.useState<string | null>(null);
  const [confirm, setConfirm] = React.useState<Employee | null>(null);
  const remove = useAction(() => {
    setConfirm(null);
    onToast("Mitarbeiter geloescht");
    onReload();
  });

  const counts = {
    all: employees.filter((item) => item.status === "active").length,
    blocked: employees.filter((item) => item.status === "active" && item.readiness === "blocked").length,
    limited: employees.filter((item) => item.status === "active" && item.readiness === "limited").length,
    inactive: employees.filter((item) => item.status !== "active").length,
  };

  const visible = employees
    .filter((item) => {
      if (filter === "inactive") return item.status !== "active";
      if (item.status !== "active") return false;
      if (filter === "blocked") return item.readiness === "blocked";
      if (filter === "limited") return item.readiness === "limited";
      return true;
    })
    .filter((item) => {
      const needle = search.trim().toLowerCase();
      if (!needle) return true;
      return [item.full_name, item.job_role_name ?? item.role, item.team ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    });

  const selected = employees.find((item) => item.id === detail) ?? null;

  return (
    <section className="ops-stack">
      <div className="ops-row ops-row--between">
        <Segments<Filter>
          value={filter}
          onChange={setFilter}
          options={[
            { key: "all", label: "Aktiv", count: counts.all },
            { key: "blocked", label: "Nicht einsatzfaehig", count: counts.blocked },
            { key: "limited", label: "Eingeschraenkt", count: counts.limited },
            { key: "inactive", label: "Ausgeschieden", count: counts.inactive },
          ]}
        />
        <div className="ops-row ops-spacer">
          <SearchField value={search} onChange={setSearch} placeholder="Name, Funktion, Team" />
          {mayWrite && (
            <button
              type="button"
              className="pds-btn pds-btn--primary pds-btn--sm"
              onClick={() => setEditing("new")}
            >
              <Plus size={15} /> Mitarbeiter
            </button>
          )}
        </div>
      </div>

      <FormStatus error={remove.error} busy={remove.busy} busyLabel="Wird geloescht..." />

      <Table
        columns={COLUMNS}
        empty={search ? "Kein Treffer fuer die Suche." : "Noch keine Mitarbeiter erfasst."}
        head={["Status", "Mitarbeiter", "Funktion", "Naechste Frist", "Qualifikationen", ""]}
      >
        {visible.map((employee) => (
          <Row
            key={employee.id}
            columns={COLUMNS}
            onOpen={() => setDetail(employee.id)}
            title="Details oeffnen"
          >
            <Cell>
              <Pill tone={toneOf(employee.due_state)}>{label.readiness(employee.readiness)}</Pill>
            </Cell>
            <TitleCell
              title={employee.full_name}
              meta={
                employee.status === "active"
                  ? employee.team || "ohne Team"
                  : `ausgeschieden ${formatDate(employee.exit_date)}`
              }
            />
            <TitleCell
              title={employee.job_role_name ?? employee.role}
              meta={employee.job_role_name ? undefined : "keine Funktion zugeordnet"}
            />
            <Cell title={employee.next_due_title ?? undefined}>
              {employee.next_due_title ? (
                <>
                  <span className="ops-cell__title">{employee.next_due_title}</span>
                  <span className="ops-cell__meta">
                    <DueDate value={employee.next_due_date} />
                  </span>
                </>
              ) : (
                <span className="ops-cell__meta">nichts offen</span>
              )}
            </Cell>
            <Cell>
              <span className="ops-date">
                {employee.requirements.length - employee.open_requirements} / {employee.requirements.length}
              </span>
            </Cell>
            <ActionCell>
              {mayWrite && (
                <>
                  <button
                    type="button"
                    className="pds-icon-btn"
                    aria-label={`${employee.full_name} bearbeiten`}
                    onClick={() => setEditing(employee)}
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    type="button"
                    className="pds-icon-btn pds-icon-btn--danger"
                    aria-label={`${employee.full_name} loeschen`}
                    onClick={() => setConfirm(employee)}
                  >
                    <Trash2 size={14} />
                  </button>
                </>
              )}
            </ActionCell>
          </Row>
        ))}
      </Table>

      {editing && (
        <EmployeeDialog
          employee={editing === "new" ? null : editing}
          jobRoles={jobRoles}
          branches={branches}
          branchId={branchId}
          onClose={() => setEditing(null)}
          onSaved={(message) => {
            setEditing(null);
            onToast(message);
            onReload();
          }}
        />
      )}

      {selected && (
        <EmployeeDetail
          employee={selected}
          qualificationTypes={qualificationTypes}
          branches={branches}
          branchId={branchId}
          permissions={permissions}
          mayWrite={mayWrite}
          onClose={() => setDetail(null)}
          onChanged={(message) => {
            onToast(message);
            onReload();
          }}
        />
      )}

      <ConfirmDialog
        open={confirm !== null}
        title="Mitarbeiter loeschen"
        busy={remove.busy}
        body={
          <>
            <p>
              <strong>{confirm?.full_name}</strong> wird mit Pflichtenprofil und{" "}
              {confirm?.qualifications.length ?? 0} Qualifikation(en) entfernt.
            </p>
            <div className="pds-banner pds-banner--warn" style={{ marginTop: 12 }}>
              <TriangleAlert size={15} />
              Nachweise unterliegen Aufbewahrungsfristen. Fuer ausgeschiedene Mitarbeiter ist
              &bdquo;Status: ausgeschieden&ldquo; der richtige Weg &ndash; der Datensatz bleibt
              auffindbar, loest aber keine Erinnerungen mehr aus.
            </div>
          </>
        }
        onCancel={() => setConfirm(null)}
        onConfirm={() => confirm && remove.run(() => apiDelete(`/api/employees/${confirm.id}`))}
      />
    </section>
  );
}

/* --------------------------------------------------------------------------
 * Create and edit
 * ----------------------------------------------------------------------- */

function EmployeeDialog({
  employee,
  jobRoles,
  branches,
  branchId,
  onClose,
  onSaved,
}: {
  employee: Employee | null;
  jobRoles: JobRole[];
  branches: Branch[];
  branchId: string | null;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const formRef = React.useRef<HTMLFormElement>(null);
  const [dirty, setDirty] = React.useState(false);
  const { error, busy, run } = useSubmit(() => onSaved(employee ? "Aenderungen gespeichert" : "Mitarbeiter angelegt"));
  const profile = employee?.profile ?? null;
  // While no branch is selected there is nothing to guess from, so the form
  // asks - creating somebody in the wrong branch is tedious to undo.
  const [homeBranch, setHomeBranch] = React.useState(
    employee?.branch_id ?? branchId ?? branches[0]?.id ?? ""
  );

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);

    run(form, async () => {
      if (!homeBranch) throw new Error("Keine Niederlassung verfuegbar.");
      const core = {
        full_name: data.get("full_name"),
        role: String(data.get("role") || "").trim() || "Mitarbeiter",
        job_role_id: emptyToNull(data.get("job_role_id")),
        team: emptyToNull(data.get("team")),
        start_date: emptyToNull(data.get("start_date")),
        status: data.get("status"),
        exit_date: emptyToNull(data.get("exit_date")),
        first_aider: data.get("first_aider") === "on",
        skills: splitCsv(data.get("skills")),
        notes: emptyToNull(data.get("notes")),
      };

      const saved = employee
        ? await apiPatch<Employee>(`/api/employees/${employee.id}`, core)
        : // The profile is only sent once the employee exists, so a failed
          // first call cannot silently discard it.
          await apiPost<Employee>("/api/employees", { branch_id: homeBranch, ...core });

      const profileFields = {
        contract_type: data.get("contract_type"),
        contract_start: emptyToNull(data.get("contract_start")),
        contract_end: emptyToNull(data.get("contract_end")),
        probation_until: emptyToNull(data.get("probation_until")),
        residence_permit_required: data.get("residence_permit_required") === "on",
        residence_permit_type: emptyToNull(data.get("residence_permit_type")),
        residence_permit_valid_until: emptyToNull(data.get("residence_permit_valid_until")),
        work_permit_note: emptyToNull(data.get("work_permit_note")),
        ppe_issued_at: emptyToNull(data.get("ppe_issued_at")),
      };
      const touched = Object.values(profileFields).some(
        (value) => value !== null && value !== false && value !== "unbefristet"
      );
      if (!profile && !touched) return;

      // The endpoint replaces the whole profile, so the fields this form no
      // longer edits - the training dates that became qualifications - have to
      // be carried over. Sending only the visible ones would blank them.
      await apiPost("/api/employee-profiles", {
        ...(profile ?? {}),
        employee_id: saved.id,
        ...profileFields,
      });
    });
  }

  return (
    <Modal
      open
      title={employee ? `${employee.full_name} bearbeiten` : "Mitarbeiter anlegen"}
      subtitle="Schulungen und Fahrerlaubnis werden als Qualifikationen im Detail gepflegt."
      onClose={onClose}
      closeGuard={() =>
        !dirty || window.confirm("Eingaben verwerfen? Die Aenderungen sind noch nicht gespeichert.")
      }
      footer={
        <>
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
            Abbrechen
          </button>
          <span className="ops-spacer" />
          <button
            type="submit"
            form="employee-form"
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gespeichert..." : "Speichern"}
          </button>
        </>
      }
    >
      <form
        id="employee-form"
        ref={formRef}
        className="ops-dialog__body"
        onSubmit={submit}
        onChange={() => setDirty(true)}
      >
        <FormStatus error={error} busy={false} />

        <Fieldset legend="Stammdaten">
          <div className="ops-grid">
            {!employee && branches.length > 1 && (
              <Field label="Heimat-Niederlassung">
                <Select
                  value={homeBranch}
                  onChange={(event) => setHomeBranch(event.target.value)}
                  required
                >
                  {branches.map((branch) => (
                    <option key={branch.id} value={branch.id}>
                      {branch.name}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            <Field label="Name">
              <TextInput name="full_name" required minLength={2} defaultValue={employee?.full_name} />
            </Field>
            <Field label="Funktion">
              <Select name="job_role_id" defaultValue={employee?.job_role_id ?? ""}>
                <option value="">ohne Funktion</option>
                {jobRoles.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Bezeichnung (frei)">
              <TextInput name="role" defaultValue={employee?.role} placeholder="z. B. Monteur" />
            </Field>
            <Field label="Team">
              <TextInput name="team" defaultValue={employee?.team ?? ""} />
            </Field>
            <Field label="Eintritt">
              <TextInput type="date" name="start_date" defaultValue={employee?.start_date ?? ""} />
            </Field>
            <Field label="Status">
              <Select name="status" defaultValue={employee?.status ?? "active"}>
                <option value="active">aktiv</option>
                <option value="inactive">ausgeschieden</option>
              </Select>
            </Field>
            <Field label="Austritt">
              <TextInput type="date" name="exit_date" defaultValue={employee?.exit_date ?? ""} />
            </Field>
            <Field label="Skills (kommagetrennt)">
              <TextInput name="skills" defaultValue={employee?.skills.join(", ")} />
            </Field>
          </div>
          <Checkbox name="first_aider" label="Benannter Ersthelfer" defaultChecked={employee?.first_aider} />
        </Fieldset>

        <Fieldset legend="Vertrag">
          <div className="ops-grid">
            <Field label="Vertragsart">
              <Select name="contract_type" defaultValue={profile?.contract_type ?? "unbefristet"}>
                <option value="unbefristet">unbefristet</option>
                <option value="befristet">befristet</option>
                <option value="probezeit/praktikum">Probezeit/Praktikum</option>
              </Select>
            </Field>
            <Field label="Vertragsbeginn">
              <TextInput type="date" name="contract_start" defaultValue={profile?.contract_start ?? ""} />
            </Field>
            <Field label="Befristet bis">
              <TextInput type="date" name="contract_end" defaultValue={profile?.contract_end ?? ""} />
            </Field>
            <Field label="Probezeit bis">
              <TextInput type="date" name="probation_until" defaultValue={profile?.probation_until ?? ""} />
            </Field>
          </div>
        </Fieldset>

        <Fieldset legend="Aufenthalt und Arbeitserlaubnis">
          <Checkbox
            name="residence_permit_required"
            label="Aufenthalts-/Arbeitserlaubnis ist relevant"
            defaultChecked={profile?.residence_permit_required}
          />
          <div className="ops-grid">
            <Field label="Art des Titels">
              <TextInput name="residence_permit_type" defaultValue={profile?.residence_permit_type ?? ""} />
            </Field>
            <Field label="Gueltig bis">
              <TextInput
                type="date"
                name="residence_permit_valid_until"
                defaultValue={profile?.residence_permit_valid_until ?? ""}
              />
            </Field>
            <Field label="Arbeitsgenehmigung / Notiz" span>
              <TextInput name="work_permit_note" defaultValue={profile?.work_permit_note ?? ""} />
            </Field>
          </div>
        </Fieldset>

        <Fieldset legend="Ausruestung und Notizen">
          <div className="ops-grid">
            <Field label="PSA ausgegeben am">
              <TextInput type="date" name="ppe_issued_at" defaultValue={profile?.ppe_issued_at ?? ""} />
            </Field>
          </div>
          <Field label="Notizen" span>
            <TextArea name="notes" defaultValue={employee?.notes ?? ""} />
          </Field>
        </Fieldset>
      </form>
    </Modal>
  );
}

/* --------------------------------------------------------------------------
 * Pay
 * ----------------------------------------------------------------------- */

/**
 * Pay, behind a button and a second confirmation.
 *
 * Deliberately not loaded with the rest of the dialog: an amount that is
 * fetched every time somebody opens an employee is an amount that gets read
 * over shoulders, and every read is recorded. It is fetched when it is
 * actually wanted, and the backend answers the first attempt with a challenge
 * that sends the user through a fresh Microsoft confirmation.
 */
function SalaryPanel({
  employee,
  mayWrite,
  onChanged,
}: {
  employee: Employee;
  mayWrite: boolean;
  onChanged: (message: string) => void;
}) {
  const [salary, setSalary] = React.useState<Salary | null>(null);
  const [state, setState] = React.useState<"hidden" | "loading" | "confirm" | "shown" | "empty">(
    "hidden"
  );
  const [problem, setProblem] = React.useState<string | null>(null);
  const [editing, setEditing] = React.useState(false);

  const load = React.useCallback(async () => {
    setState("loading");
    setProblem(null);
    try {
      const result = await apiStepUp<Salary>(
        `/api/employees/${employee.id}/salary`,
        {},
        () => setState("confirm")
      );
      setSalary(result);
      setState("shown");
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 404) {
        setSalary(null);
        setState("empty");
        return;
      }
      setProblem(errorMessage(caught));
      setState("hidden");
    }
  }, [employee.id]);

  return (
    <div>
      <h3 className="pds-label pds-label--micro" style={{ marginBottom: 8 }}>
        Entgelt
      </h3>
      {problem && <div className="pds-banner pds-banner--danger">{problem}</div>}
      {state === "confirm" && (
        <div className="pds-banner">
          Bitte die Anmeldung im Microsoft-Fenster bestaetigen.
        </div>
      )}

      {state === "hidden" && (
        <>
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={load}>
            <Eye size={15} /> Entgelt anzeigen
          </button>
          <p className="pds-meta" style={{ marginTop: 8 }}>
            Verlangt eine zusaetzliche Bestaetigung. Jeder Zugriff wird protokolliert.
          </p>
        </>
      )}
      {state === "loading" && <div className="pds-banner">Wird geladen...</div>}

      {state === "empty" && (
        <>
          <p className="pds-meta">Fuer diese Person ist kein Entgelt hinterlegt.</p>
          {mayWrite && (
            <button
              type="button"
              className="pds-btn pds-btn--outline pds-btn--sm"
              onClick={() => setEditing(true)}
            >
              <Plus size={15} /> Entgelt erfassen
            </button>
          )}
        </>
      )}

      {state === "shown" && salary && (
        <>
          <dl className="ops-facts">
            <dt>{salary.period === "monthly" ? "Monatsbrutto" : "Stundensatz"}</dt>
            <dd className="ops-date">{formatEuro(salary.amount)}</dd>
            <dt>Wochenstunden</dt>
            <dd className="ops-date">{salary.hours_per_week ?? "-"}</dd>
            <dt>Gueltig ab</dt>
            <dd>{formatDate(salary.valid_from)}</dd>
            {salary.note && (
              <>
                <dt>Notiz</dt>
                <dd>{salary.note}</dd>
              </>
            )}
            <dt>Zuletzt geaendert</dt>
            <dd>{formatDate(salary.updated_at)}</dd>
          </dl>
          {mayWrite && (
            <button
              type="button"
              className="pds-btn pds-btn--outline pds-btn--sm"
              onClick={() => setEditing(true)}
            >
              <Pencil size={14} /> Entgelt aendern
            </button>
          )}
        </>
      )}

      {editing && (
        <SalaryDialog
          employee={employee}
          salary={salary}
          onClose={() => setEditing(false)}
          onSaved={(saved) => {
            setEditing(false);
            setSalary(saved);
            setState("shown");
            onChanged("Entgelt gespeichert");
          }}
        />
      )}
    </div>
  );
}

function SalaryDialog({
  employee,
  salary,
  onClose,
  onSaved,
}: {
  employee: Employee;
  salary: Salary | null;
  onClose: () => void;
  onSaved: (saved: Salary) => void;
}) {
  const [busy, setBusy] = React.useState(false);
  const [problem, setProblem] = React.useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setProblem(null);
    try {
      const saved = await apiStepUp<Salary>(`/api/employees/${employee.id}/salary`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          amount: Number(data.get("amount")),
          period: data.get("period"),
          hours_per_week: numberOrNull(data.get("hours_per_week")),
          valid_from: data.get("valid_from"),
          note: emptyToNull(data.get("note")),
        }),
      });
      onSaved(saved);
    } catch (caught) {
      setProblem(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      size="sm"
      title={salary ? "Entgelt aendern" : "Entgelt erfassen"}
      subtitle={employee.full_name}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
            Abbrechen
          </button>
          <span className="ops-spacer" />
          <button
            type="submit"
            form="salary-form"
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gespeichert..." : "Speichern"}
          </button>
        </>
      }
    >
      <form id="salary-form" className="ops-dialog__body" onSubmit={submit}>
        <FormStatus error={problem} busy={false} />
        <div className="ops-grid">
          <Field label="Art">
            <Select name="period" defaultValue={salary?.period ?? "monthly"}>
              <option value="monthly">Monatsbrutto</option>
              <option value="hourly">Stundensatz</option>
            </Select>
          </Field>
          <Field label="Betrag in EUR">
            <TextInput
              type="number"
              name="amount"
              min={1}
              step="0.01"
              required
              defaultValue={salary?.amount ?? ""}
            />
          </Field>
          <Field label="Wochenstunden">
            <TextInput
              type="number"
              name="hours_per_week"
              min={1}
              max={80}
              step="0.5"
              defaultValue={salary?.hours_per_week ?? ""}
            />
          </Field>
          <Field label="Gueltig ab">
            <TextInput
              type="date"
              name="valid_from"
              required
              defaultValue={salary?.valid_from ?? ""}
            />
          </Field>
        </div>
        <Field label="Notiz" span>
          <TextArea name="note" defaultValue={salary?.note ?? ""} />
        </Field>
        <p className="pds-meta">
          Der Betrag steht nicht im Aenderungsprotokoll - dort wird nur vermerkt, dass und von wem
          er geaendert wurde.
        </p>
      </form>
    </Modal>
  );
}

/* --------------------------------------------------------------------------
 * Deployments
 * ----------------------------------------------------------------------- */

/**
 * Which branches somebody works in.
 *
 * Requirements add up across them rather than being replaced: a person
 * deployed in two branches has to satisfy both sets. Anything else would turn
 * an exception granted in one branch into a licence to work in the other.
 */
function Deployments({
  employee,
  branches,
  mayWrite,
  onChanged,
}: {
  employee: Employee;
  branches: Branch[];
  mayWrite: boolean;
  onChanged: (message: string) => void;
}) {
  const [adding, setAdding] = React.useState("");
  const assign = useAction(() => {
    setAdding("");
    onChanged("Einsatzort gespeichert");
  });
  const available = branches.filter(
    (branch) => branch.id !== employee.branch_id && !employee.branch_ids.includes(branch.id)
  );

  return (
    <div>
      <h3 className="pds-label pds-label--micro" style={{ marginBottom: 8 }}>
        Einsatzorte
      </h3>
      <FormStatus error={assign.error} busy={assign.busy} busyLabel="Wird gespeichert..." />
      <div className="ops-chips">
        {branches
          .filter((branch) => employee.branch_ids.includes(branch.id))
          .map((branch) => {
            const home = branch.id === employee.branch_id;
            const readiness = employee.readiness_by_branch[branch.id];
            return (
              <span key={branch.id} className="pds-tag" title={label.readiness(readiness)}>
                {branch.name}
                {home ? " (Heimat)" : ""}
                {readiness && readiness !== "ready" ? ` · ${label.readiness(readiness)}` : ""}
                {mayWrite && !home && (
                  <button
                    type="button"
                    className="pds-btn pds-btn--link"
                    style={{ marginLeft: 6 }}
                    aria-label={`Einsatz in ${branch.name} beenden`}
                    onClick={() =>
                      assign.run(() =>
                        apiDelete(`/api/employees/${employee.id}/branches/${branch.id}`)
                      )
                    }
                  >
                    entfernen
                  </button>
                )}
              </span>
            );
          })}
      </div>
      {mayWrite && available.length > 0 && (
        <div className="ops-row" style={{ marginTop: 10 }}>
          <Select
            value={adding}
            aria-label="Weitere Niederlassung"
            onChange={(event) => setAdding(event.target.value)}
          >
            <option value="">weitere Niederlassung...</option>
            {available.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </Select>
          <button
            type="button"
            className="pds-btn pds-btn--outline pds-btn--sm"
            disabled={!adding || assign.busy}
            onClick={() =>
              assign.run(() =>
                apiPost(`/api/employees/${employee.id}/branches`, { branch_id: adding })
              )
            }
          >
            <Plus size={15} /> Einsatzort
          </button>
        </div>
      )}
    </div>
  );
}

/* --------------------------------------------------------------------------
 * Detail: requirements and qualifications
 * ----------------------------------------------------------------------- */

function EmployeeDetail({
  employee,
  qualificationTypes,
  branches,
  branchId,
  permissions,
  mayWrite,
  onClose,
  onChanged,
}: {
  employee: Employee;
  qualificationTypes: QualificationType[];
  branches: Branch[];
  branchId: string | null;
  permissions: string[];
  mayWrite: boolean;
  onClose: () => void;
  onChanged: (message: string) => void;
}) {
  const [recording, setRecording] = React.useState<RequirementState | "free" | null>(null);
  const profile = employee.profile;

  return (
    <>
      <Modal
        open
        size="lg"
        title={employee.full_name}
        subtitle={
          <>
            {employee.job_role_name ?? employee.role}
            {employee.team ? ` · ${employee.team}` : ""} · seit {formatDate(employee.start_date)}
            {branchId && branches.length > 1
              ? ` · Beurteilung fuer ${branches.find((item) => item.id === branchId)?.name ?? ""}`
              : ""}
          </>
        }
        onClose={onClose}
        footer={
          <>
            <Pill tone={toneOf(employee.due_state)}>{label.readiness(employee.readiness)}</Pill>
            <span className="pds-meta">
              {employee.open_requirements} von {employee.requirements.length} Anforderungen offen
            </span>
            <span className="ops-spacer" />
            <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
              Schliessen
            </button>
          </>
        }
      >
        <div className="ops-dialog__body">
          {employee.readiness === "blocked" && (
            <div className="pds-banner pds-banner--warn">
              <TriangleAlert size={15} />
              Pflichtqualifikationen fehlen oder sind abgelaufen &ndash; kein Einsatz in dieser
              Funktion.
            </div>
          )}

          {can(permissions, "salary:read") && (
            <SalaryPanel
              employee={employee}
              mayWrite={can(permissions, "salary:write")}
              onChanged={onChanged}
            />
          )}

          {branches.length > 1 && (
            <Deployments
              employee={employee}
              branches={branches}
              mayWrite={mayWrite}
              onChanged={onChanged}
            />
          )}

          <RequirementList
            requirements={employee.requirements}
            mayWrite={mayWrite}
            onRecord={setRecording}
          />

          <FreeQualifications employee={employee} mayWrite={mayWrite} onChanged={onChanged} />

          {mayWrite && (
            <button
              type="button"
              className="pds-btn pds-btn--outline pds-btn--sm"
              onClick={() => setRecording("free")}
            >
              <Plus size={15} /> Weitere Qualifikation erfassen
            </button>
          )}

          <div>
            <h3 className="pds-label pds-label--micro" style={{ marginBottom: 8 }}>
              Vertrag und Aufenthalt
            </h3>
            <dl className="ops-facts">
              <dt>Vertrag</dt>
              <dd>
                {profile?.contract_type ?? "-"}
                {profile?.contract_end ? ` bis ${formatDate(profile.contract_end)}` : ""}
              </dd>
              <dt>Probezeit</dt>
              <dd>{formatDate(profile?.probation_until)}</dd>
              <dt>Aufenthaltstitel</dt>
              <dd>
                {profile?.residence_permit_required
                  ? `${profile.residence_permit_type || "erfasst"} bis ${formatDate(
                      profile.residence_permit_valid_until
                    )}`
                  : "nicht relevant"}
              </dd>
              <dt>PSA ausgegeben</dt>
              <dd>{formatDate(profile?.ppe_issued_at)}</dd>
              <dt>Ersthelfer</dt>
              <dd>{employee.first_aider ? "ja" : "nein"}</dd>
              <dt>Skills</dt>
              <dd>
                {employee.skills.length ? (
                  <span className="ops-chips">
                    {employee.skills.map((skill) => (
                      <span key={skill} className="pds-tag">
                        {skill}
                      </span>
                    ))}
                  </span>
                ) : (
                  "-"
                )}
              </dd>
              {employee.notes && (
                <>
                  <dt>Notizen</dt>
                  <dd>{employee.notes}</dd>
                </>
              )}
            </dl>
          </div>
        </div>
      </Modal>

      {recording && (
        <QualificationDialog
          employee={employee}
          requirement={recording === "free" ? null : recording}
          qualificationTypes={qualificationTypes}
          onClose={() => setRecording(null)}
          onSaved={() => {
            setRecording(null);
            onChanged("Qualifikation erfasst");
          }}
        />
      )}
    </>
  );
}

const REQUIREMENT_COLUMNS = "minmax(0,1.6fr) 96px 110px 120px 130px";

function RequirementList({
  requirements,
  mayWrite,
  onRecord,
}: {
  requirements: RequirementState[];
  mayWrite: boolean;
  onRecord: (requirement: RequirementState) => void;
}) {
  if (!requirements.length) {
    return (
      <EmptyState>
        Keine Funktion zugeordnet &ndash; ohne Funktion ist nicht bestimmbar, was gefordert ist.
      </EmptyState>
    );
  }

  return (
    <div>
      <h3 className="pds-label pds-label--micro" style={{ marginBottom: 8 }}>
        Anforderungen aus der Funktion
      </h3>
      <Table
        columns={REQUIREMENT_COLUMNS}
        minWidth={620}
        head={["Qualifikation", "Pflicht", "Gueltig bis", "Status", ""]}
      >
        {requirements.map((requirement) => (
          <Row key={requirement.qualification_type_id} columns={REQUIREMENT_COLUMNS}>
            <TitleCell
              title={requirement.name}
              meta={label.qualificationCategory(requirement.category)}
            />
            <Cell>
              <span className="pds-meta">{requirement.mandatory ? "Pflicht" : "optional"}</span>
            </Cell>
            <Cell>
              <DueDate value={requirement.valid_until} />
            </Cell>
            <Cell>
              <Pill tone={requirementTone(requirement.state)}>{label.requirement(requirement.state)}</Pill>
            </Cell>
            <ActionCell>
              {mayWrite && (
                <button
                  type="button"
                  className="pds-btn pds-btn--outline pds-btn--sm"
                  onClick={() => onRecord(requirement)}
                >
                  {requirement.state === "missing" ? "Erfassen" : "Auffrischen"}
                </button>
              )}
            </ActionCell>
          </Row>
        ))}
      </Table>
    </div>
  );
}

const FREE_COLUMNS = "minmax(0,1.8fr) 120px 120px 72px";

/** Qualifications that do not answer a requirement of the assigned function. */
function FreeQualifications({
  employee,
  mayWrite,
  onChanged,
}: {
  employee: Employee;
  mayWrite: boolean;
  onChanged: (message: string) => void;
}) {
  const required = new Set(employee.requirements.map((item) => item.qualification_type_id));
  const others = employee.qualifications.filter(
    (item) => !item.qualification_type_id || !required.has(item.qualification_type_id)
  );
  const remove = useAction(() => onChanged("Qualifikation entfernt"));

  if (!others.length) return null;
  return (
    <div>
      <h3 className="pds-label pds-label--micro" style={{ marginBottom: 8 }}>
        Weitere Qualifikationen
      </h3>
      <FormStatus error={remove.error} busy={remove.busy} busyLabel="Wird entfernt..." />
      <Table columns={FREE_COLUMNS} minWidth={560} head={["Qualifikation", "Erworben", "Gueltig bis", ""]}>
        {others.map((item: Qualification) => (
          <Row key={item.id} columns={FREE_COLUMNS}>
            <TitleCell title={item.title} meta={item.qualification_type} />
            <Cell>
              <span className="ops-date">{formatDate(item.issued_on)}</span>
            </Cell>
            <Cell>
              <DueDate value={item.valid_until} />
            </Cell>
            <ActionCell>
              {mayWrite && (
                <button
                  type="button"
                  className="pds-icon-btn pds-icon-btn--danger"
                  aria-label={`${item.title} entfernen`}
                  onClick={() => remove.run(() => apiDelete(`/api/employee-qualifications/${item.id}`))}
                >
                  <Trash2 size={14} />
                </button>
              )}
            </ActionCell>
          </Row>
        ))}
      </Table>
    </div>
  );
}

/* --------------------------------------------------------------------------
 * Recording a qualification
 * ----------------------------------------------------------------------- */

function QualificationDialog({
  employee,
  requirement,
  qualificationTypes,
  onClose,
  onSaved,
}: {
  employee: Employee;
  requirement: RequirementState | null;
  qualificationTypes: QualificationType[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const { error, busy, run } = useSubmit(onSaved);
  const [typeId, setTypeId] = React.useState(requirement?.qualification_type_id ?? "");
  const kind = qualificationTypes.find((item) => item.id === typeId) ?? null;

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(form, async () => {
      // The selected type comes from state, not from the form: when the dialog
      // is opened from a requirement the select is disabled so it cannot be
      // changed, and a disabled control is never submitted.
      const title = emptyToNull(data.get("title"));
      if (!typeId && !title) throw new Error("Bitte eine Qualifikation waehlen oder benennen.");
      await apiPost("/api/employee-qualifications", {
        employee_id: employee.id,
        qualification_type_id: typeId || null,
        // Title and kind come from the catalogue when one is selected; a free
        // entry has to carry both itself.
        title,
        qualification_type: typeId ? null : "sonstige",
        issued_on: emptyToNull(data.get("issued_on")),
        valid_until: emptyToNull(data.get("valid_until")),
      });
    });
  }

  return (
    <Modal
      open
      title={requirement ? `${requirement.name} erfassen` : "Qualifikation erfassen"}
      subtitle={`fuer ${employee.full_name}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
            Abbrechen
          </button>
          <span className="ops-spacer" />
          <button
            type="submit"
            form="qualification-form"
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gespeichert..." : "Speichern"}
          </button>
        </>
      }
    >
      <form id="qualification-form" className="ops-dialog__body" onSubmit={submit}>
        <FormStatus error={error} busy={false} />

        <Field label="Qualifikation">
          <Select
            name="qualification_type_id"
            value={typeId}
            onChange={(event) => setTypeId(event.target.value)}
            disabled={requirement !== null}
          >
            <option value="">freie Bezeichnung</option>
            {qualificationTypes.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </Select>
        </Field>

        {kind ? (
          <div className="pds-banner">
            {kind.validity_months
              ? `Gueltigkeit ${kind.validity_months} Monate - das Ablaufdatum wird aus dem Kursdatum berechnet.`
              : "Ohne feste Gueltigkeitsdauer."}
            {kind.legal_basis ? ` Grundlage: ${kind.legal_basis}.` : ""}
          </div>
        ) : (
          <Field label="Bezeichnung">
            <TextInput name="title" minLength={2} placeholder="z. B. Schweissschein" />
          </Field>
        )}

        <div className="ops-grid">
          <Field label={kind?.validity_months ? "Kurs-/Pruefdatum" : "Erworben am"}>
            <TextInput type="date" name="issued_on" />
          </Field>
          <Field label="Gueltig bis (optional)">
            <TextInput type="date" name="valid_until" />
          </Field>
        </div>

        {kind?.evidence_required && (
          <div className="pds-banner pds-banner--warn">
            <TriangleAlert size={15} />
            Fuer diese Qualifikation ist ein Nachweis vorgesehen. Ohne hinterlegtes Dokument bleibt
            sie als &bdquo;Nachweis fehlt&ldquo; gefuehrt.
          </div>
        )}
      </form>
    </Modal>
  );
}
