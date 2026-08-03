import React from "react";
import ReactDOM from "react-dom/client";
import {
  BriefcaseBusiness,
  ClipboardCheck,
  FileCheck2,
  Gauge,
  NotebookPen,
  ShieldCheck,
  UserRoundCheck,
  Wrench,
} from "lucide-react";
import { apiGet, errorMessage } from "./api";
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
  type Vehicle,
} from "./types";
import { AssessmentView } from "./views/AssessmentView";
import { CockpitView } from "./views/CockpitView";
import { ComplianceView } from "./views/ComplianceView";
import { EmployeeView } from "./views/EmployeeView";
import { SalesView } from "./views/SalesView";
import { VehicleView } from "./views/VehicleView";
import "./styles.css";

const EMPTY_BOOTSTRAP: Bootstrap = { branches: [], users: [], auth_mode: AUTH_MODE, permissions: [] };

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
        <select
          value={principal.user_id}
          onChange={(event) => onSelect(event.target.value)}
          title="Rolle wechseln (nur Entwicklungsmodus)"
        >
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

      const [
        bootstrapData,
        cockpitData,
        assessmentData,
        recordData,
        actionData,
        employeeData,
        vehicleData,
        reminderData,
      ] = await Promise.all([
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

  return {
    cockpit,
    assessments,
    records,
    actions,
    employees,
    vehicles,
    reminders,
    bootstrap,
    loading,
    error,
    reload: load,
  };
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
  ["sales", BriefcaseBusiness, "Vertrieb", "sales:read"],
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

  if (identity.loading) {
    return (
      <div className="shell signin">
        <div className="notice">Anmeldung wird geprueft...</div>
      </div>
    );
  }
  if (!identity.principal) return <SignInScreen error={identity.error} onRetry={identity.retry} />;

  return (
    <Workspace principal={identity.principal} devUsers={identity.devUsers} onSelectUser={identity.selectUser} />
  );
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
  const [view, setView] = React.useState(visible[0]?.[0] ?? "cockpit");

  React.useEffect(() => {
    if (!visible.some(([key]) => key === view)) setView(visible[0]?.[0] ?? "cockpit");
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
              <SalesView bootstrap={data.bootstrap} permissions={principal.permissions} />
            )}
          </>
        )}
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
