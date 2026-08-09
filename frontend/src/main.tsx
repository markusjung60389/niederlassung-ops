import React from "react";
import ReactDOM from "react-dom/client";
import { RefreshCw, ShieldCheck } from "lucide-react";
import { apiGet, errorMessage } from "./api";
import { AUTH_MODE, getDevUserId, setDevUserId } from "./auth";
import { useHashRoute } from "./router";
import {
  can,
  type Action,
  type Assessment,
  type Bootstrap,
  type Cockpit,
  type DevUser,
  type Employee,
  type JobRole,
  type Principal,
  type QualificationMatrix,
  type QualificationType,
  type RecordItem,
  type Reminder,
  type Vehicle,
} from "./types";
import { AssessmentView } from "./views/AssessmentView";
import { CatalogView } from "./views/CatalogView";
import { CockpitView } from "./views/CockpitView";
import { ComplianceView } from "./views/ComplianceView";
import { EmployeeView } from "./views/EmployeeView";
import { MatrixView } from "./views/MatrixView";
import { SalesView } from "./views/SalesView";
import { VehicleView } from "./views/VehicleView";
import { useToast } from "./components/ui";
import "@fontsource/archivo/400.css";
import "@fontsource/archivo/500.css";
import "@fontsource/archivo/600.css";
import "@fontsource/archivo/700.css";
import "@fontsource/archivo/800.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-mono/600.css";
import "./styles.css";

const VERSION = "1.1.0";
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

function SignInScreen({ error, onRetry }: { error: string | null; onRetry: () => void }) {
  return (
    <div className="ops-signin">
      <section className="pds-card">
        <div className="ops-row">
          <ShieldCheck size={18} />
          <h1 className="pds-page__title" style={{ fontSize: 20 }}>
            Anmeldung erforderlich
          </h1>
        </div>
        <p className="pds-meta">
          {AUTH_MODE === "azure_ad"
            ? "Die Anmeldung ueber Microsoft Entra ID ist noch nicht aktiviert. Siehe docs/azure-ad-setup.md."
            : "Es konnte keine Identitaet ermittelt werden. Laeuft das Backend und ist ein Benutzer vorhanden?"}
        </p>
        {error && <div className="pds-banner pds-banner--danger">{error}</div>}
        <div>
          <button type="button" className="pds-btn pds-btn--primary pds-btn--sm" onClick={onRetry}>
            Erneut versuchen
          </button>
        </div>
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
  const [jobRoles, setJobRoles] = React.useState<JobRole[]>([]);
  const [qualificationTypes, setQualificationTypes] = React.useState<QualificationType[]>([]);
  const [matrix, setMatrix] = React.useState<QualificationMatrix | null>(null);
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
        jobRoleData,
        typeData,
        matrixData,
      ] = await Promise.all([
        apiGet<Bootstrap>("/api/bootstrap"),
        mayCompliance ? apiGet<Cockpit>("/api/cockpit") : Promise.resolve(null),
        mayAssessment ? apiGet<Assessment[]>("/api/branch-assessments") : Promise.resolve([]),
        mayCompliance ? apiGet<RecordItem[]>("/api/compliance-records") : Promise.resolve([]),
        mayCompliance ? apiGet<Action[]>("/api/actions") : Promise.resolve([]),
        // Departed staff stay reachable through the "Ausgeschieden" segment.
        mayPersonnel
          ? apiGet<Employee[]>("/api/employees?include_inactive=true")
          : Promise.resolve([]),
        mayFleet ? apiGet<Vehicle[]>("/api/vehicles") : Promise.resolve([]),
        mayPersonnel || mayFleet ? apiGet<Reminder[]>("/api/reminders") : Promise.resolve([]),
        mayPersonnel ? apiGet<JobRole[]>("/api/job-roles") : Promise.resolve([]),
        mayPersonnel ? apiGet<QualificationType[]>("/api/qualification-types") : Promise.resolve([]),
        mayPersonnel
          ? apiGet<QualificationMatrix>("/api/qualification-matrix")
          : Promise.resolve(null),
      ]);

      setBootstrap(bootstrapData);
      setCockpit(cockpitData);
      setAssessments(assessmentData);
      setRecords(recordData);
      setActions(actionData);
      setEmployees(employeeData);
      setVehicles(vehicleData);
      setReminders(reminderData);
      setJobRoles(jobRoleData);
      setQualificationTypes(typeData);
      setMatrix(matrixData);
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
    jobRoles,
    qualificationTypes,
    matrix,
    bootstrap,
    loading,
    error,
    reload: load,
  };
}

// --------------------------------------------------------------------------
// Shell
// --------------------------------------------------------------------------

type NavEntry = { key: string; label: string; permission: string | null; title: string; lead: string };

const NAV: NavEntry[] = [
  {
    key: "cockpit",
    label: "Cockpit",
    permission: "compliance:read",
    title: "Leitercockpit",
    lead: "Was ueberfaellig ist, was ansteht und wer heute einsetzbar ist.",
  },
  {
    key: "mitarbeiter",
    label: "Mitarbeiter",
    permission: "personnel:read",
    title: "Mitarbeiter",
    lead: "Stammdaten, Pflichtenprofil und die Qualifikationen je Funktion.",
  },
  {
    key: "qualifikationen",
    label: "Qualifikationen",
    permission: "personnel:read",
    title: "Qualifikationsmatrix",
    lead: "Wer welche Anforderung der eigenen Funktion erfuellt - und wer nicht.",
  },
  {
    key: "fahrzeuge",
    label: "Fahrzeuge",
    permission: "fleet:read",
    title: "Fahrzeuge",
    lead: "HU, UVV, Service und die Zuordnung zum Fahrer.",
  },
  {
    key: "compliance",
    label: "Compliance",
    permission: "compliance:read",
    title: "Compliance",
    lead: "Pflichten der Niederlassung mit Nachweis und Massnahme.",
  },
  {
    key: "bestandsaufnahme",
    label: "Bestandsaufnahme",
    permission: "assessment:read",
    title: "Bestandsaufnahme",
    lead: "Der Stand der Niederlassung zum Stichtag.",
  },
  {
    key: "stammdaten",
    label: "Stammdaten",
    permission: "personnel:read",
    title: "Stammdaten",
    lead: "Funktionen, geforderte Qualifikationen und der Katalog dahinter.",
  },
  {
    key: "vertrieb",
    label: "Vertrieb",
    permission: "sales:read",
    title: "Vertrieb",
    lead: "Kunden, Chancen und Servicevertraege.",
  },
];

function App() {
  const identity = useIdentity();

  if (identity.loading) {
    return (
      <div className="ops-signin">
        <div className="pds-banner">Anmeldung wird geprueft...</div>
      </div>
    );
  }
  if (!identity.principal) return <SignInScreen error={identity.error} onRetry={identity.retry} />;

  return (
    <Workspace
      principal={identity.principal}
      devUsers={identity.devUsers}
      onSelectUser={identity.selectUser}
    />
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
  const toast = useToast();
  const visible = NAV.filter((entry) => !entry.permission || can(principal.permissions, entry.permission));
  const fallback = visible[0]?.key ?? "cockpit";
  const [route, navigate] = useHashRoute(fallback);
  const active = visible.find((entry) => entry.key === route) ?? visible[0];

  React.useEffect(() => {
    if (!visible.some((entry) => entry.key === route)) navigate(fallback);
  }, [visible, route, fallback, navigate]);

  const overdue = data.reminders.filter((item) => item.state === "red").length;

  return (
    <div className="pds-shell">
      <header className="pds-topbar">
        <div className="pds-topbar__brand">
          <span className="pds-logo">BS</span>
          <span className="pds-version">v{VERSION}</span>
          <nav className="pds-nav">
            {visible.map((entry) => (
              <button
                key={entry.key}
                type="button"
                className={`pds-nav__link${entry.key === active?.key ? " is-active" : ""}`}
                onClick={() => navigate(entry.key)}
              >
                {entry.label}
                {entry.key === "cockpit" && overdue > 0 && (
                  <span className="pds-nav__count">{overdue}</span>
                )}
              </button>
            ))}
          </nav>
        </div>
        <div className="ops-row">
          {/* The role goes in the tooltip: spelled out it pushes the reload
              button off the bar on a 1440px screen. */}
          <span
            className="ops-identity"
            title={`${principal.display_name}${principal.role_name ? ` · ${principal.role_name}` : ""}`}
          >
            <ShieldCheck size={15} />
            {principal.display_name}
          </span>
          {AUTH_MODE === "dev" && devUsers.length > 0 && (
            <select
              className="pds-select pds-input--sm"
              style={{ width: 210 }}
              value={principal.user_id}
              onChange={(event) => onSelectUser(event.target.value)}
              title="Rolle wechseln (nur Entwicklungsmodus)"
            >
              {devUsers.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.display_name}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            className="pds-icon-btn"
            title="Daten neu laden"
            aria-label="Daten neu laden"
            onClick={data.reload}
          >
            <RefreshCw size={15} />
          </button>
        </div>
      </header>

      <main className="pds-page">
        <div className="pds-page__head">
          <div style={{ minWidth: 0 }}>
            <h1 className="pds-page__title">{active?.title ?? "Remscheid Ops"}</h1>
            <p className="pds-page__subtitle">{active?.lead ?? ""}</p>
          </div>
        </div>

        {data.loading && <div className="pds-banner">Daten werden geladen...</div>}
        {data.error && (
          <div className="pds-banner pds-banner--danger">Backend nicht erreichbar: {data.error}</div>
        )}

        {!data.loading && !data.error && (
          <>
            {route === "cockpit" && data.cockpit && (
              <CockpitView
                cockpit={data.cockpit}
                reminders={data.reminders}
                employees={data.employees.filter((item) => item.status === "active")}
                vehicles={data.vehicles}
                onNavigate={navigate}
              />
            )}
            {route === "mitarbeiter" && (
              <EmployeeView
                employees={data.employees}
                jobRoles={data.jobRoles}
                qualificationTypes={data.qualificationTypes}
                bootstrap={data.bootstrap}
                permissions={principal.permissions}
                onReload={data.reload}
                onToast={toast.show}
              />
            )}
            {route === "qualifikationen" && <MatrixView matrix={data.matrix} />}
            {route === "fahrzeuge" && (
              <VehicleView
                vehicles={data.vehicles}
                employees={data.employees.filter((item) => item.status === "active")}
                bootstrap={data.bootstrap}
                permissions={principal.permissions}
                onReload={data.reload}
                onToast={toast.show}
              />
            )}
            {route === "compliance" && (
              <ComplianceView
                records={data.records}
                actions={data.actions}
                bootstrap={data.bootstrap}
                permissions={principal.permissions}
                onReload={data.reload}
                onToast={toast.show}
              />
            )}
            {route === "bestandsaufnahme" && (
              <AssessmentView
                assessments={data.assessments}
                bootstrap={data.bootstrap}
                permissions={principal.permissions}
                onSaved={data.reload}
                onToast={toast.show}
              />
            )}
            {route === "stammdaten" && (
              <CatalogView
                jobRoles={data.jobRoles}
                qualificationTypes={data.qualificationTypes}
                permissions={principal.permissions}
                onReload={data.reload}
                onToast={toast.show}
              />
            )}
            {route === "vertrieb" && (
              <SalesView
                bootstrap={data.bootstrap}
                permissions={principal.permissions}
                onToast={toast.show}
              />
            )}
          </>
        )}
      </main>
      {toast.node}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
