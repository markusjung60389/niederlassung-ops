import React from "react";
import ReactDOM from "react-dom/client";
import {
  AlertTriangle,
  BriefcaseBusiness,
  CalendarClock,
  ClipboardCheck,
  FileCheck2,
  Gauge,
  NotebookPen,
  ShieldCheck,
  UserRoundCheck,
  Wrench,
} from "lucide-react";
import { apiGet, apiPost, errorMessage } from "./api";
import { AUTH_MODE, getDevUserId, setDevUserId } from "./auth";
import {
  can,
  type Action,
  type Assessment,
  type Bootstrap,
  type Cockpit,
  type DevUser,
  type Employee,
  type Principal,
  type RecordItem,
  type Reminder,
  type State,
  type Vehicle,
} from "./types";
import "./styles.css";

const EMPTY_BOOTSTRAP: Bootstrap = { branches: [], users: [], auth_mode: AUTH_MODE, permissions: [] };

function formatDate(value?: string | null) {
  if (!value) return "-";
  // Date-only values must be read as local time; `new Date("2026-09-01")` is
  // parsed as UTC midnight and renders as the previous day west of UTC.
  const parsed = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00`) : new Date(value);
  return Number.isNaN(parsed.getTime()) ? "-" : new Intl.DateTimeFormat("de-DE").format(parsed);
}

function splitCsv(value: FormDataEntryValue | null) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function emptyToNull(value: FormDataEntryValue | null) {
  const text = String(value || "").trim();
  return text ? text : null;
}

function Badge({ state, children }: { state: State | string; children: React.ReactNode }) {
  return <span className={`badge ${state}`}>{children}</span>;
}

function Panel({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="panel">
      <div className="panelTitle">
        {icon}
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Placeholder({ title, icon, lines }: { title: string; icon: React.ReactNode; lines: string[] }) {
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
 * The previous version reset the form unconditionally, so a rejected save
 * looked identical to a successful one.
 */
function useSubmit(onSuccess: () => void) {
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

function FormStatus({ error, busy }: { error: string | null; busy: boolean }) {
  if (busy) return <div className="notice">Wird gespeichert...</div>;
  if (error) return <div className="notice danger">Speichern fehlgeschlagen: {error}</div>;
  return null;
}

// --------------------------------------------------------------------------
// Identity
// --------------------------------------------------------------------------

function useIdentity() {
  const [principal, setPrincipal] = React.useState<Principal | null>(null);
  const [devUsers, setDevUsers] = React.useState<DevUser[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const resolve = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (AUTH_MODE === "dev") {
        const users = await apiGet<DevUser[]>("/api/auth/dev-users");
        setDevUsers(users);
        if (!getDevUserId() && users.length) setDevUserId(users[0].id);
      }
      setPrincipal(await apiGet<Principal>("/api/auth/me"));
    } catch (caught) {
      setPrincipal(null);
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    resolve();
  }, [resolve]);

  const selectUser = React.useCallback(
    (userId: string) => {
      setDevUserId(userId);
      resolve();
    },
    [resolve]
  );

  return { principal, devUsers, loading, error, selectUser, retry: resolve };
}

function IdentityBar({
  principal,
  devUsers,
  onSelect,
}: {
  principal: Principal;
  devUsers: DevUser[];
  onSelect: (userId: string) => void;
}) {
  return (
    <div className="identity">
      <ShieldCheck size={16} />
      <span>
        {principal.display_name}
        {principal.role_name ? ` / ${principal.role_name}` : ""}
      </span>
      {AUTH_MODE === "dev" && devUsers.length > 0 && (
        <select value={principal.user_id} onChange={(event) => onSelect(event.target.value)} title="Rolle wechseln (nur Entwicklungsmodus)">
          {devUsers.map((user) => (
            <option key={user.id} value={user.id}>
              {user.display_name}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}

function SignInScreen({ error, onRetry }: { error: string | null; onRetry: () => void }) {
  return (
    <div className="shell signin">
      <section className="panel">
        <div className="panelTitle">
          <ShieldCheck size={18} />
          <h2>Anmeldung erforderlich</h2>
        </div>
        <p>
          {AUTH_MODE === "azure_ad"
            ? "Die Anmeldung ueber Microsoft Entra ID ist noch nicht aktiviert. Siehe docs/azure-ad-setup.md."
            : "Es konnte keine Identitaet ermittelt werden. Laeuft das Backend und ist ein Benutzer vorhanden?"}
        </p>
        {error && <div className="notice danger">{error}</div>}
        <button onClick={onRetry}>Erneut versuchen</button>
      </section>
    </div>
  );
}

// --------------------------------------------------------------------------
// Data
// --------------------------------------------------------------------------

function useOpsData(permissions: string[]) {
  const [cockpit, setCockpit] = React.useState<Cockpit | null>(null);
  const [assessments, setAssessments] = React.useState<Assessment[]>([]);
  const [records, setRecords] = React.useState<RecordItem[]>([]);
  const [actions, setActions] = React.useState<Action[]>([]);
  const [employees, setEmployees] = React.useState<Employee[]>([]);
  const [vehicles, setVehicles] = React.useState<Vehicle[]>([]);
  const [reminders, setReminders] = React.useState<Reminder[]>([]);
  const [bootstrap, setBootstrap] = React.useState<Bootstrap>(EMPTY_BOOTSTRAP);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const key = permissions.join(",");

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      // Only the endpoints the caller is allowed to see are requested, so a
      // restricted role gets an empty section instead of a wall of 403s.
      const mayCompliance = can(permissions, "compliance:read");
      const mayPersonnel = can(permissions, "personnel:read");
      const mayFleet = can(permissions, "fleet:read");
      const mayAssessment = can(permissions, "assessment:read");

      const [bootstrapData, cockpitData, assessmentData, recordData, actionData, employeeData, vehicleData, reminderData] =
        await Promise.all([
          apiGet<Bootstrap>("/api/bootstrap"),
          mayCompliance ? apiGet<Cockpit>("/api/cockpit") : Promise.resolve(null),
          mayAssessment ? apiGet<Assessment[]>("/api/branch-assessments") : Promise.resolve([]),
          mayCompliance ? apiGet<RecordItem[]>("/api/compliance-records") : Promise.resolve([]),
          mayCompliance ? apiGet<Action[]>("/api/actions") : Promise.resolve([]),
          mayPersonnel ? apiGet<Employee[]>("/api/employees") : Promise.resolve([]),
          mayFleet ? apiGet<Vehicle[]>("/api/vehicles") : Promise.resolve([]),
          mayPersonnel || mayFleet ? apiGet<Reminder[]>("/api/reminders") : Promise.resolve([]),
        ]);

      setBootstrap(bootstrapData);
      setCockpit(cockpitData);
      setAssessments(assessmentData);
      setRecords(recordData);
      setActions(actionData);
      setEmployees(employeeData);
      setVehicles(vehicleData);
      setReminders(reminderData);
      setError(null);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
    // `permissions` is a fresh array on every render; the joined key is stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  React.useEffect(() => {
    load();
  }, [load]);

  return { cockpit, assessments, records, actions, employees, vehicles, reminders, bootstrap, loading, error, reload: load };
}

// --------------------------------------------------------------------------
// Shell
// --------------------------------------------------------------------------

const NAV: [string, typeof Gauge, string, string | null][] = [
  ["cockpit", Gauge, "Cockpit", "compliance:read"],
  ["assessment", NotebookPen, "Bestandsaufnahme", "assessment:read"],
  ["employees", UserRoundCheck, "Mitarbeiter", "personnel:read"],
  ["vehicles", Wrench, "Fahrzeuge", "fleet:read"],
  ["compliance", ClipboardCheck, "Compliance", "compliance:read"],
  ["sales", BriefcaseBusiness, "Vertrieb", null],
];

const TITLES: Record<string, string> = {
  cockpit: "Leitercockpit",
  assessment: "Bestandsaufnahme",
  employees: "Mitarbeiter",
  vehicles: "Fahrzeuge",
  compliance: "Compliance",
  sales: "Vertrieb",
};

function App() {
  const identity = useIdentity();

  if (identity.loading) return <div className="shell signin"><div className="notice">Anmeldung wird geprueft...</div></div>;
  if (!identity.principal) return <SignInScreen error={identity.error} onRetry={identity.retry} />;

  return <Workspace principal={identity.principal} devUsers={identity.devUsers} onSelectUser={identity.selectUser} />;
}

function Workspace({
  principal,
  devUsers,
  onSelectUser,
}: {
  principal: Principal;
  devUsers: DevUser[];
  onSelectUser: (userId: string) => void;
}) {
  const data = useOpsData(principal.permissions);
  const visible = NAV.filter(([, , , permission]) => !permission || can(principal.permissions, permission));
  const [view, setView] = React.useState(visible[0]?.[0] ?? "sales");

  React.useEffect(() => {
    if (!visible.some(([key]) => key === view)) setView(visible[0]?.[0] ?? "sales");
  }, [visible, view]);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Gauge size={22} />
          <div>
            <strong>Remscheid Ops</strong>
            <span>Niederlassungsleitung</span>
          </div>
        </div>
        <nav>
          {visible.map(([key, Icon, label]) => (
            <button key={key} className={view === key ? "active" : ""} onClick={() => setView(key)}>
              <Icon size={18} />
              {label}
            </button>
          ))}
        </nav>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <h1>{TITLES[view]}</h1>
            <p>Objekte, Fristen und Erinnerungen fuer die Fuehrung der Niederlassung.</p>
          </div>
          <IdentityBar principal={principal} devUsers={devUsers} onSelect={onSelectUser} />
          <button className="iconButton" title="Daten neu laden" onClick={data.reload}>
            <FileCheck2 size={18} />
          </button>
        </header>

        {data.loading && <div className="notice">Daten werden geladen...</div>}
        {data.error && <div className="notice danger">Backend nicht erreichbar: {data.error}</div>}

        {!data.loading && !data.error && (
          <>
            {view === "cockpit" && data.cockpit && (
              <CockpitView
                cockpit={data.cockpit}
                assessments={data.assessments}
                reminders={data.reminders}
                employees={data.employees}
                vehicles={data.vehicles}
              />
            )}
            {view === "assessment" && (
              <AssessmentView
                assessments={data.assessments}
                bootstrap={data.bootstrap}
                permissions={principal.permissions}
                onSaved={data.reload}
              />
            )}
            {view === "employees" && (
              <EmployeeView
                employees={data.employees}
                bootstrap={data.bootstrap}
                permissions={principal.permissions}
                onReload={data.reload}
              />
            )}
            {view === "vehicles" && (
              <VehicleView
                vehicles={data.vehicles}
                employees={data.employees}
                bootstrap={data.bootstrap}
                permissions={principal.permissions}
                onReload={data.reload}
              />
            )}
            {view === "compliance" && (
              <ComplianceView
                records={data.records}
                actions={data.actions}
                bootstrap={data.bootstrap}
                permissions={principal.permissions}
                onReload={data.reload}
              />
            )}
            {view === "sales" && (
              <Placeholder
                title="Vertrieb / Pipeline"
                icon={<BriefcaseBusiness />}
                lines={[
                  "Noch keine Vertriebsdaten erfasst.",
                  "Accounts und Opportunities haben derzeit keine API und keine Erfassungsmaske.",
                ]}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}

// --------------------------------------------------------------------------
// Cockpit
// --------------------------------------------------------------------------

function CockpitView({
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

// --------------------------------------------------------------------------
// Assessment
// --------------------------------------------------------------------------

function AssessmentView({
  assessments,
  bootstrap,
  permissions,
  onSaved,
}: {
  assessments: Assessment[];
  bootstrap: Bootstrap;
  permissions: string[];
  onSaved: () => void;
}) {
  const latest = assessments[0];
  return (
    <div className="grid detailLayout">
      <section className="stack">
        {can(permissions, "assessment:write") && <AssessmentForm bootstrap={bootstrap} onSaved={onSaved} />}
        {assessments.length > 0 && (
          <Panel title="Erfasste Bestandsaufnahmen" icon={<NotebookPen size={18} />}>
            <AssessmentTable assessments={assessments} />
          </Panel>
        )}
      </section>
      <aside className="detail">
        <div className="detailHeader">
          <Badge state={latest ? "green" : "yellow"}>{latest ? "erfasst" : "offen"}</Badge>
          <h2>{latest?.title || "Noch keine Bestandsaufnahme"}</h2>
          <p>{latest ? formatDate(latest.assessment_date) : ""}</p>
        </div>
        {latest ? (
          <AssessmentSummary assessment={latest} />
        ) : (
          <div className="empty">Bitte die erste Bestandsaufnahme erfassen.</div>
        )}
      </aside>
    </div>
  );
}

function AssessmentForm({ bootstrap, onSaved }: { bootstrap: Bootstrap; onSaved: () => void }) {
  const { error, busy, run } = useSubmit(onSaved);
  const branchId = bootstrap.branches[0]?.id;
  const userId = bootstrap.users[0]?.id;

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const next_actions = String(data.get("next_actions_text") || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((title) => ({ title }));

    run(form, async () => {
      if (!branchId) throw new Error("Keine Niederlassung verfuegbar.");
      await apiPost("/api/branch-assessments", {
        branch_id: branchId,
        created_by: userId ?? null,
        title: data.get("title"),
        assessment_date: data.get("assessment_date"),
        team_structure: emptyToNull(data.get("team_structure")),
        customer_clusters: emptyToNull(data.get("customer_clusters")),
        service_portfolio: emptyToNull(data.get("service_portfolio")),
        project_types: emptyToNull(data.get("project_types")),
        service_share: emptyToNull(data.get("service_share")),
        main_problems: emptyToNull(data.get("main_problems")),
        notes: emptyToNull(data.get("notes")),
        next_actions,
        management_ratings: {
          compliance: data.get("rating_compliance"),
          personal: data.get("rating_personal"),
          service: data.get("rating_service"),
          sales: data.get("rating_sales"),
          operations: data.get("rating_operations"),
        },
      });
    });
  }

  return (
    <form className="form" onSubmit={submit}>
      <h2>Bestandsaufnahme erfassen</h2>
      <div className="formGrid">
        <input name="title" placeholder="Titel" defaultValue="Bestandsaufnahme Remscheid" required />
        <label>
          Datum
          <input name="assessment_date" type="date" defaultValue={new Date().toISOString().slice(0, 10)} required />
        </label>
      </div>
      <textarea name="team_structure" placeholder="Teamstruktur, Rollen, Verantwortliche" />
      <textarea name="customer_clusters" placeholder="Kundencluster und wichtige Accounts" />
      <textarea name="service_portfolio" placeholder="Leistungsportfolio" />
      <textarea name="project_types" placeholder="Projektarten und typische Baustellen" />
      <input name="service_share" placeholder="Service-/Wartungsanteil" />
      <textarea name="main_problems" placeholder="Aktuelle Hauptprobleme" />
      <div className="formGrid">
        {["compliance", "personal", "service", "sales", "operations"].map((key) => (
          <label key={key}>
            {key}
            <select name={`rating_${key}`} defaultValue="yellow">
              <option value="green">gruen</option>
              <option value="yellow">gelb</option>
              <option value="red">rot</option>
            </select>
          </label>
        ))}
      </div>
      <textarea name="next_actions_text" placeholder="Massnahmen, eine pro Zeile" />
      <textarea name="notes" placeholder="Bestandsaufnahme-Text / erzeugte Notizen" />
      <FormStatus error={error} busy={busy} />
      <button disabled={busy}>Bestandsaufnahme speichern</button>
    </form>
  );
}

function AssessmentTable({ assessments }: { assessments: Assessment[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Datum</th>
          <th>Titel</th>
          <th>Personal</th>
        </tr>
      </thead>
      <tbody>
        {assessments.map((item) => (
          <tr key={item.id}>
            <td>{formatDate(item.assessment_date)}</td>
            <td>
              <strong>{item.title}</strong>
              <span>{item.main_problems || "-"}</span>
            </td>
            <td>
              <Badge state={item.management_ratings?.personal || "yellow"}>
                {item.management_ratings?.personal || "offen"}
              </Badge>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AssessmentSummary({ assessment }: { assessment: Assessment }) {
  return (
    <div className="stack">
      <dl>
        <dt>Team</dt>
        <dd>{assessment.team_structure || "-"}</dd>
        <dt>Kunden</dt>
        <dd>{assessment.customer_clusters || "-"}</dd>
        <dt>Portfolio</dt>
        <dd>{assessment.service_portfolio || "-"}</dd>
        <dt>Probleme</dt>
        <dd>{assessment.main_problems || "-"}</dd>
      </dl>
      <h3>Ampeln</h3>
      <div className="chips">
        {Object.entries(assessment.management_ratings || {}).map(([key, value]) => (
          <span key={key}>
            {key}: {value}
          </span>
        ))}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------
// Employees
// --------------------------------------------------------------------------

function EmployeeView({
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
  return (
    <section className="stack">
      {can(permissions, "personnel:write") && <EmployeeForm bootstrap={bootstrap} onSaved={onReload} />}
      <div className="grid two">
        {employees.map((employee) => (
          <Panel key={employee.id} title={employee.full_name} icon={<UserRoundCheck size={18} />}>
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
        <input name="full_name" placeholder="Name" required />
        <input name="role" placeholder="Rolle" required />
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

// --------------------------------------------------------------------------
// Vehicles
// --------------------------------------------------------------------------

function VehicleView({
  vehicles,
  employees,
  bootstrap,
  permissions,
  onReload,
}: {
  vehicles: Vehicle[];
  employees: Employee[];
  bootstrap: Bootstrap;
  permissions: string[];
  onReload: () => void;
}) {
  return (
    <section className="stack">
      {can(permissions, "fleet:write") && (
        <VehicleForm employees={employees} bootstrap={bootstrap} onSaved={onReload} />
      )}
      <div className="grid two">
        {vehicles.map((vehicle) => (
          <Panel key={vehicle.id} title={vehicle.license_plate} icon={<Wrench size={18} />}>
            <dl>
              <dt>Fahrzeug</dt>
              <dd>
                {vehicle.brand || "-"} {vehicle.model || ""} / {vehicle.vehicle_type || "-"}
              </dd>
              <dt>HU</dt>
              <dd>{formatDate(vehicle.hu_due_date)}</dd>
              <dt>UVV</dt>
              <dd>{formatDate(vehicle.uvv_next_check)}</dd>
              <dt>Service</dt>
              <dd>{formatDate(vehicle.service_due_date)}</dd>
              <dt>Reifen</dt>
              <dd>
                {vehicle.tire_type || "-"} / Wechsel {formatDate(vehicle.tire_change_due_date)}
              </dd>
              <dt>Versicherung</dt>
              <dd>{formatDate(vehicle.insurance_valid_until)}</dd>
            </dl>
            <div className="chips">
              {vehicle.equipment.map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          </Panel>
        ))}
      </div>
    </section>
  );
}

function VehicleForm({
  employees,
  bootstrap,
  onSaved,
}: {
  employees: Employee[];
  bootstrap: Bootstrap;
  onSaved: () => void;
}) {
  const { error, busy, run } = useSubmit(onSaved);
  const branchId = bootstrap.branches[0]?.id;

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);

    run(form, async () => {
      if (!branchId) throw new Error("Keine Niederlassung verfuegbar.");
      await apiPost("/api/vehicles", {
        branch_id: branchId,
        license_plate: data.get("license_plate"),
        brand: emptyToNull(data.get("brand")),
        model: emptyToNull(data.get("model")),
        vehicle_type: emptyToNull(data.get("vehicle_type")),
        vin: emptyToNull(data.get("vin")),
        first_registration: emptyToNull(data.get("first_registration")),
        ownership_type: emptyToNull(data.get("ownership_type")),
        assigned_employee_id: emptyToNull(data.get("assigned_employee_id")),
        mileage: data.get("mileage") ? Number(data.get("mileage")) : null,
        hu_due_date: emptyToNull(data.get("hu_due_date")),
        uvv_last_check: emptyToNull(data.get("uvv_last_check")),
        uvv_next_check: emptyToNull(data.get("uvv_next_check")),
        service_due_date: emptyToNull(data.get("service_due_date")),
        tire_type: emptyToNull(data.get("tire_type")),
        tire_change_due_date: emptyToNull(data.get("tire_change_due_date")),
        insurance_valid_until: emptyToNull(data.get("insurance_valid_until")),
        fuel_card_number: emptyToNull(data.get("fuel_card_number")),
        equipment: splitCsv(data.get("equipment")),
        notes: emptyToNull(data.get("notes")),
      });
    });
  }

  return (
    <form className="form" onSubmit={submit}>
      <h2>Fahrzeug erfassen</h2>
      <div className="formGrid">
        <input name="license_plate" placeholder="Kennzeichen" required />
        <input name="brand" placeholder="Marke" />
        <input name="model" placeholder="Modell / Typ" />
        <input name="vehicle_type" placeholder="Art, z. B. Transporter" />
        <input name="vin" placeholder="FIN/VIN" />
        <label>
          Erstzulassung
          <input name="first_registration" type="date" />
        </label>
        <select name="ownership_type" defaultValue="">
          <option value="">Eigentum/Leasing</option>
          <option value="Eigentum">Eigentum</option>
          <option value="Leasing">Leasing</option>
          <option value="Miete">Miete</option>
        </select>
        <select name="assigned_employee_id" defaultValue="">
          <option value="">Zugeordnet an</option>
          {employees.map((employee) => (
            <option key={employee.id} value={employee.id}>
              {employee.full_name}
            </option>
          ))}
        </select>
        <input name="mileage" type="number" placeholder="Kilometerstand" />
      </div>
      <div className="formGrid">
        <label>
          HU faellig
          <input name="hu_due_date" type="date" />
        </label>
        <label>
          Letzte UVV
          <input name="uvv_last_check" type="date" />
        </label>
        <label>
          Naechste UVV
          <input name="uvv_next_check" type="date" />
        </label>
        <label>
          Service faellig
          <input name="service_due_date" type="date" />
        </label>
        <select name="tire_type" defaultValue="">
          <option value="">Reifen</option>
          <option>Sommer</option>
          <option>Winter</option>
          <option>Ganzjahr</option>
        </select>
        <label>
          Reifenwechsel
          <input name="tire_change_due_date" type="date" />
        </label>
        <label>
          Versicherung bis
          <input name="insurance_valid_until" type="date" />
        </label>
        <input name="fuel_card_number" placeholder="Tankkarte" />
      </div>
      <input name="equipment" placeholder="Ausstattung, z. B. Leiter, Feuerloescher, Verbandkasten" />
      <textarea name="notes" placeholder="Notizen / Besonderheiten" />
      <FormStatus error={error} busy={busy} />
      <button disabled={busy}>Fahrzeug speichern</button>
    </form>
  );
}

// --------------------------------------------------------------------------
// Compliance
// --------------------------------------------------------------------------

function ComplianceView({
  records,
  actions,
  bootstrap,
  permissions,
  onReload,
}: {
  records: RecordItem[];
  actions: Action[];
  bootstrap: Bootstrap;
  permissions: string[];
  onReload: () => void;
}) {
  return (
    <section className="stack">
      {can(permissions, "compliance:write") && <CreateRecordForm bootstrap={bootstrap} onCreated={onReload} />}
      <Panel title="Compliance-Records" icon={<ClipboardCheck size={18} />}>
        <RecordTable records={records} />
      </Panel>
      <Panel title="Massnahmen" icon={<AlertTriangle size={18} />}>
        <ActionTable actions={actions} records={records} />
      </Panel>
    </section>
  );
}

function RecordTable({ records }: { records: RecordItem[] }) {
  if (!records.length) return <div className="empty">Keine Eintraege erfasst.</div>;
  return (
    <table>
      <thead>
        <tr>
          <th>Status</th>
          <th>Titel</th>
          <th>Faellig</th>
        </tr>
      </thead>
      <tbody>
        {records.map((record) => (
          <tr key={record.id}>
            <td>
              <Badge state={record.due_state}>{record.priority}</Badge>
            </td>
            <td>
              <strong>{record.title}</strong>
              <span>{record.category}</span>
            </td>
            <td>{formatDate(record.due_date)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CreateRecordForm({ bootstrap, onCreated }: { bootstrap: Bootstrap; onCreated: () => void }) {
  const { error, busy, run } = useSubmit(onCreated);
  const branchId = bootstrap.branches[0]?.id;
  const ownerId = bootstrap.users[0]?.id;

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);

    run(form, async () => {
      if (!branchId || !ownerId) throw new Error("Niederlassung oder Verantwortlicher fehlt.");
      await apiPost("/api/compliance-records", {
        title: data.get("title"),
        category: data.get("category"),
        priority: data.get("priority"),
        status: data.get("status"),
        control_type: data.get("control_type"),
        legal_basis: data.get("legal_basis"),
        due_date: data.get("due_date"),
        review_date: data.get("review_date"),
        risk_if_missing: emptyToNull(data.get("risk_if_missing")),
        branch_id: branchId,
        owner_user_id: ownerId,
        tags: [],
        scope_type: "branch",
        recurrence: "yearly",
      });
    });
  }

  return (
    <form className="form" onSubmit={submit}>
      <h2>Compliance-Thema erfassen</h2>
      <input name="title" placeholder="Titel" required />
      <div className="formGrid">
        <select name="category" defaultValue="training_instruction">
          <option value="training_instruction">Unterweisung</option>
          <option value="risk_assessment">Gefaehrdungsbeurteilung</option>
          <option value="tools_and_equipment_inspection">DGUV / Arbeitsmittel</option>
          <option value="first_aid">Erste Hilfe</option>
        </select>
        <select name="priority" defaultValue="high">
          <option>low</option>
          <option>medium</option>
          <option>high</option>
          <option>critical</option>
        </select>
        <select name="status" defaultValue="open">
          <option>open</option>
          <option>in_progress</option>
          <option>compliant</option>
          <option>non_compliant</option>
        </select>
        <select name="control_type" defaultValue="training">
          <option>document</option>
          <option>training</option>
          <option>inspection</option>
          <option>medical</option>
          <option>process</option>
          <option>incident</option>
          <option>approval</option>
        </select>
      </div>
      <input name="legal_basis" placeholder="Rechtsgrundlage" required />
      <div className="formGrid">
        <label>
          Faellig
          <input name="due_date" type="date" required />
        </label>
        <label>
          Review
          <input name="review_date" type="date" required />
        </label>
      </div>
      <textarea name="risk_if_missing" placeholder="Risiko bei fehlendem Nachweis" />
      <FormStatus error={error} busy={busy} />
      <button disabled={busy}>Speichern</button>
    </form>
  );
}

function ActionTable({ actions, records }: { actions: Action[]; records: RecordItem[] }) {
  if (!actions.length) return <div className="empty">Keine offenen Massnahmen erfasst.</div>;
  return (
    <table>
      <thead>
        <tr>
          <th>Status</th>
          <th>Massnahme</th>
          <th>Record</th>
          <th>Faellig</th>
        </tr>
      </thead>
      <tbody>
        {actions.map((action) => (
          <tr key={action.id}>
            <td>
              <Badge state={action.due_state}>{action.status}</Badge>
            </td>
            <td>
              <strong>{action.title}</strong>
              <span>{action.priority}</span>
            </td>
            <td>{records.find((record) => record.id === action.compliance_record_id)?.title || action.compliance_record_id}</td>
            <td>{formatDate(action.due_date)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
