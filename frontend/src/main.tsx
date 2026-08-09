import React from "react";
import ReactDOM from "react-dom/client";
import { Building2, KeyRound, LogOut, RefreshCw, ShieldCheck } from "lucide-react";
import { ApiError, apiGet, apiPost, errorMessage } from "./api";
import {
  AUTH_MODE,
  clearSignedOut,
  forgetIdentity,
  getDevUserId,
  getSession,
  hasAzureSession,
  isSignedOut,
  setDevUserId,
  setSession,
  signOutAzure,
} from "./auth";
import { useHashRoute } from "./router";
import {
  can,
  type Action,
  type Assessment,
  type Bootstrap,
  type Branch,
  type Cockpit,
  type ComplianceRule,
  type DevUser,
  type Employee,
  type JobRole,
  type PortfolioRow,
  type Principal,
  type QualificationMatrix,
  type QualificationType,
  type RecordItem,
  type Reminder,
  type RequirementOverride,
  type Vehicle,
} from "./types";
import { PasswordDialog, SignInScreen } from "./components/Login";
import { AssessmentView } from "./views/AssessmentView";
import { CatalogView } from "./views/CatalogView";
import { CockpitView } from "./views/CockpitView";
import { ComplianceView } from "./views/ComplianceView";
import { EmployeeView } from "./views/EmployeeView";
import { MatrixView } from "./views/MatrixView";
import { PortfolioView } from "./views/PortfolioView";
import { RulesView } from "./views/RulesView";
import { UsersView } from "./views/UsersView";
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

const VERSION = "1.2.0";
const EMPTY_BOOTSTRAP: Bootstrap = { branches: [], users: [], auth_mode: AUTH_MODE, permissions: [] };

/** URL segment for a branch: the short code where there is one. */
export function branchKey(branch: Branch): string {
  return (branch.code || branch.id).toLowerCase();
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
        if (!getSession() && !getDevUserId() && users.length && !isSignedOut()) {
          setDevUserId(users[0].id);
        }
      }
      // Signed out on purpose: show the sign-in screen rather than picking an
      // identity again behind the user's back.
      if (isSignedOut() && !getSession()) {
        setPrincipal(null);
        return;
      }
      // Nothing to identify with: show the sign-in screen instead of asking
      // the API a question it can only answer with 401.
      if (AUTH_MODE === "azure_ad" && !getSession() && !hasAzureSession()) {
        setPrincipal(null);
        return;
      }
      setPrincipal(await apiGet<Principal>("/api/auth/me"));
    } catch (caught) {
      setPrincipal(null);
      // An expired or retired session is not an error worth showing: it means
      // "please sign in again", and the screen behind this says so.
      if (caught instanceof ApiError && caught.status === 401) setSession(null);
      else setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    resolve();
  }, [resolve]);

  const selectUser = React.useCallback(
    (userId: string) => {
      // Picking a dev identity replaces a password session, otherwise the
      // switch in the topbar would silently do nothing.
      setSession(null);
      setDevUserId(userId);
      resolve();
    },
    [resolve]
  );

  const signOut = React.useCallback(async () => {
    try {
      if (getSession()) await apiPost("/api/auth/logout", {});
      await signOutAzure();
    } catch {
      /* signing out locally is what matters; the token expires either way */
    }
    forgetIdentity();
    setPrincipal(null);
    window.location.reload();
  }, []);

  return { principal, devUsers, loading, error, selectUser, signOut, retry: resolve };
}

// --------------------------------------------------------------------------
// Data
// --------------------------------------------------------------------------

/**
 * The branches the caller may work in.
 *
 * Loaded before everything else: which branch is selected decides what every
 * other request asks for, so it cannot be part of the same round trip.
 */
function useBootstrap() {
  const [data, setData] = React.useState<Bootstrap>(EMPTY_BOOTSTRAP);
  const [ready, setReady] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try {
      setData(await apiGet<Bootstrap>("/api/bootstrap"));
      setError(null);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setReady(true);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  return { data, ready, error, reload: load };
}

function useOpsData(permissions: string[], branchId: string | null) {
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
  const [portfolio, setPortfolio] = React.useState<PortfolioRow[]>([]);
  const [rules, setRules] = React.useState<ComplianceRule[]>([]);
  const [overrides, setOverrides] = React.useState<RequirementOverride[]>([]);
  const [loading, setLoading] = React.useState(true);
  // Set after the first successful load. Every save triggers a reload, and
  // replacing the whole content area with a loading notice would unmount the
  // dialog that caused it - the record would be saved and the dialog would
  // vanish mid-edit.
  const [ready, setReady] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const key = permissions.join(",");
  // Every load is numbered. Switching the branch starts a second load while
  // the first is still running, and without this the slower unscoped answer
  // would overwrite the scoped one - the list then shows branches the switcher
  // says are not selected.
  const generation = React.useRef(0);

  const load = React.useCallback(async () => {
    const mine = ++generation.current;
    setLoading(true);
    try {
      // Only the endpoints the caller is allowed to see are requested, so a
      // restricted role gets an empty section instead of a wall of 403s.
      const mayCompliance = can(permissions, "compliance:read");
      const mayPersonnel = can(permissions, "personnel:read");
      const mayFleet = can(permissions, "fleet:read");
      const mayAssessment = can(permissions, "assessment:read");
      const mayRules = can(permissions, "rule:read");
      const mayBranches = can(permissions, "branch:read");
      // No branch selected means "every branch I may see"; the backend applies
      // the same scope either way, so this only narrows, never widens.
      const scope = branchId ? `branch_id=${encodeURIComponent(branchId)}` : "";
      const query = scope ? `?${scope}` : "";

      const [
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
        portfolioData,
        ruleData,
        overrideData,
      ] = await Promise.all([
        mayCompliance ? apiGet<Cockpit>(`/api/cockpit${query}`) : Promise.resolve(null),
        mayAssessment ? apiGet<Assessment[]>(`/api/branch-assessments${query}`) : Promise.resolve([]),
        mayCompliance ? apiGet<RecordItem[]>(`/api/compliance-records${query}`) : Promise.resolve([]),
        mayCompliance ? apiGet<Action[]>(`/api/actions${query}`) : Promise.resolve([]),
        // Departed staff stay reachable through the "Ausgeschieden" segment.
        mayPersonnel
          ? apiGet<Employee[]>(`/api/employees?include_inactive=true&${scope}`)
          : Promise.resolve([]),
        mayFleet ? apiGet<Vehicle[]>(`/api/vehicles${query}`) : Promise.resolve([]),
        mayPersonnel || mayFleet ? apiGet<Reminder[]>(`/api/reminders${query}`) : Promise.resolve([]),
        mayPersonnel ? apiGet<JobRole[]>(`/api/job-roles${query}`) : Promise.resolve([]),
        mayPersonnel
          ? apiGet<QualificationType[]>(`/api/qualification-types${query}`)
          : Promise.resolve([]),
        mayPersonnel
          ? apiGet<QualificationMatrix>(`/api/qualification-matrix${query}`)
          : Promise.resolve(null),
        mayBranches ? apiGet<PortfolioRow[]>("/api/portfolio") : Promise.resolve([]),
        mayRules ? apiGet<ComplianceRule[]>(`/api/compliance-rules${query}`) : Promise.resolve([]),
        mayRules
          ? apiGet<RequirementOverride[]>(`/api/requirement-overrides${query}`)
          : Promise.resolve([]),
      ]);

      if (mine !== generation.current) return;
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
      setPortfolio(portfolioData);
      setRules(ruleData);
      setOverrides(overrideData);
      setError(null);
      setReady(true);
    } catch (caught) {
      if (mine === generation.current) setError(errorMessage(caught));
    } finally {
      if (mine === generation.current) setLoading(false);
    }
    // `permissions` is a fresh array on every render; the joined key is stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, branchId]);

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
    portfolio,
    rules,
    overrides,
    loading,
    ready,
    error,
    reload: load,
  };
}

// --------------------------------------------------------------------------
// Shell
// --------------------------------------------------------------------------

type NavEntry = {
  key: string;
  label: string;
  permission: string | null;
  title: string;
  lead: string;
  /** Pointless with a single branch, so it only appears with several. */
  multiBranchOnly?: boolean;
};

const NAV: NavEntry[] = [
  {
    key: "niederlassungen",
    label: "Niederlassungen",
    permission: "branch:read",
    title: "Niederlassungen",
    lead: "Alle Standorte nebeneinander - und die Ausnahmen, die vor Ort gesetzt wurden.",
    multiBranchOnly: true,
  },
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
    lead: "HU, UVV, Service, Fahrer - und wo das Fahrzeug gerade steht.",
  },
  {
    key: "compliance",
    label: "Compliance",
    permission: "compliance:read",
    title: "Compliance",
    lead: "Pflichten der Niederlassung mit Nachweis und Massnahme.",
  },
  {
    key: "vorgaben",
    label: "Vorgaben",
    permission: "rule:read",
    title: "Vorgaben",
    lead: "Regeln der Gruppe und der eigenen Niederlassung - und wer sie aendern darf.",
  },
  {
    key: "bestandsaufnahme",
    label: "Bestandsaufnahme",
    permission: "assessment:read",
    title: "Bestandsaufnahme",
    lead: "Der Stand der Niederlassung zum Stichtag.",
  },
  {
    key: "benutzer",
    label: "Benutzer",
    permission: "user:read",
    title: "Benutzer und Rollen",
    lead: "Wer sich anmelden darf, was er darf und in welcher Niederlassung.",
  },
  {
    key: "stammdaten",
    label: "Stammdaten",
    permission: "personnel:read",
    title: "Stammdaten",
    lead: "Funktionen, geforderte Qualifikationen und der Katalog dahinter.",
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
  if (!identity.principal) {
    return (
      <SignInScreen
        error={identity.error}
        devUsers={identity.devUsers}
        onSignedIn={identity.retry}
        onSelectUser={identity.selectUser}
        onRetry={identity.retry}
      />
    );
  }
  // The start password is still in place: the API answers nothing else, so
  // neither does the application.
  if (identity.principal.must_change_password) {
    return (
      <div className="ops-signin">
        <PasswordDialog forced onClose={() => undefined} onChanged={identity.retry} />
      </div>
    );
  }

  return (
    <Workspace
      principal={identity.principal}
      devUsers={identity.devUsers}
      onSelectUser={identity.selectUser}
      onSignOut={identity.signOut}
    />
  );
}

function Workspace({
  principal,
  devUsers,
  onSelectUser,
  onSignOut,
}: {
  principal: Principal;
  devUsers: DevUser[];
  onSelectUser: (userId: string) => void;
  onSignOut: () => void;
}) {
  const [changingPassword, setChangingPassword] = React.useState(false);
  const bootstrap = useBootstrap();
  const branches = bootstrap.data.branches;
  const multiBranch = branches.length > 1;

  const visible = NAV.filter(
    (entry) =>
      (!entry.permission || can(principal.permissions, entry.permission)) &&
      (!entry.multiBranchOnly || multiBranch)
  );
  const fallback = visible[0]?.key ?? "cockpit";
  const [route, navigate] = useHashRoute(fallback);

  // An unknown key in the URL selects nothing rather than silently falling
  // back to a branch the link was not about.
  const wanted = route.branch?.toLowerCase() ?? null;
  const selected = wanted
    ? branches.find((branch) => branchKey(branch) === wanted) ?? null
    : null;
  const branchId = selected?.id ?? (multiBranch ? null : branches[0]?.id ?? null);

  const data = useOpsData(principal.permissions, branchId);
  const toast = useToast();
  const active = visible.find((entry) => entry.key === route.view) ?? visible[0];

  React.useEffect(() => {
    if (bootstrap.ready && visible.length && !visible.some((entry) => entry.key === route.view)) {
      navigate({ view: fallback });
    }
  }, [bootstrap.ready, visible, route.view, fallback, navigate]);

  const overdue = data.reminders.filter((item) => item.state === "red").length;
  const newExceptions = data.portfolio.reduce((sum, row) => sum + row.new_exceptions, 0);

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
                onClick={() => navigate({ view: entry.key })}
              >
                {entry.label}
                {entry.key === "cockpit" && overdue > 0 && (
                  <span className="pds-nav__count">{overdue}</span>
                )}
                {entry.key === "niederlassungen" && newExceptions > 0 && (
                  <span className="pds-nav__count">{newExceptions}</span>
                )}
              </button>
            ))}
          </nav>
        </div>
        <div className="ops-row">
          {multiBranch && (
            <label className="ops-branch" title="Niederlassung waehlen">
              <Building2 size={15} />
              <select
                className="pds-select pds-input--sm"
                aria-label="Niederlassung"
                value={selected ? branchKey(selected) : ""}
                onChange={(event) => navigate({ branch: event.target.value || null })}
              >
                <option value="">Alle Niederlassungen</option>
                {branches.map((branch) => (
                  <option key={branch.id} value={branchKey(branch)}>
                    {branch.name}
                  </option>
                ))}
              </select>
            </label>
          )}
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
            onClick={() => {
              bootstrap.reload();
              data.reload();
            }}
          >
            <RefreshCw size={15} />
          </button>
          {principal.source === "password" && (
            <button
              type="button"
              className="pds-icon-btn"
              title="Passwort aendern"
              aria-label="Passwort aendern"
              onClick={() => setChangingPassword(true)}
            >
              <KeyRound size={15} />
            </button>
          )}
          <button
            type="button"
            className="pds-icon-btn"
            title="Abmelden"
            aria-label="Abmelden"
            onClick={onSignOut}
          >
            <LogOut size={15} />
          </button>
        </div>
      </header>

      <main className="pds-page">
        <div className="pds-page__head">
          <div style={{ minWidth: 0 }}>
            <h1 className="pds-page__title">{active?.title ?? "Ops"}</h1>
            <p className="pds-page__subtitle">{active?.lead ?? ""}</p>
          </div>
          {multiBranch && (
            <span className="pds-tag" title="Aktuell ausgewaehlte Niederlassung">
              {selected ? selected.name : "Alle Niederlassungen"}
            </span>
          )}
        </div>

        {data.loading && !data.ready && <div className="pds-banner">Daten werden geladen...</div>}
        {(data.error || bootstrap.error) && (
          <div className="pds-banner pds-banner--danger">
            Backend nicht erreichbar: {data.error ?? bootstrap.error}
          </div>
        )}

        {data.ready && !data.error && (
          <>
            {route.view === "niederlassungen" && (
              <PortfolioView
                rows={data.portfolio}
                overrides={data.overrides}
                branches={branches}
                permissions={principal.permissions}
                onOpenBranch={(branch) => navigate({ view: "cockpit", branch: branchKey(branch) })}
                onReload={data.reload}
                onToast={toast.show}
              />
            )}
            {route.view === "cockpit" && data.cockpit && (
              <CockpitView
                cockpit={data.cockpit}
                reminders={data.reminders}
                employees={data.employees.filter((item) => item.status === "active")}
                vehicles={data.vehicles}
                onNavigate={(view) => navigate({ view })}
              />
            )}
            {route.view === "mitarbeiter" && (
              <EmployeeView
                employees={data.employees}
                jobRoles={data.jobRoles}
                qualificationTypes={data.qualificationTypes}
                branches={branches}
                branchId={branchId}
                permissions={principal.permissions}
                onReload={data.reload}
                onToast={toast.show}
              />
            )}
            {route.view === "qualifikationen" && <MatrixView matrix={data.matrix} />}
            {route.view === "fahrzeuge" && (
              <VehicleView
                vehicles={data.vehicles}
                employees={data.employees.filter((item) => item.status === "active")}
                branches={branches}
                branchId={branchId}
                permissions={principal.permissions}
                onReload={data.reload}
                onToast={toast.show}
              />
            )}
            {route.view === "compliance" && (
              <ComplianceView
                records={data.records}
                actions={data.actions}
                bootstrap={bootstrap.data}
                branchId={branchId}
                permissions={principal.permissions}
                onReload={data.reload}
                onToast={toast.show}
              />
            )}
            {route.view === "vorgaben" && (
              <RulesView
                rules={data.rules}
                branches={branches}
                branchId={branchId}
                permissions={principal.permissions}
                onReload={data.reload}
                onToast={toast.show}
              />
            )}
            {route.view === "bestandsaufnahme" && (
              <AssessmentView
                assessments={data.assessments}
                bootstrap={bootstrap.data}
                permissions={principal.permissions}
                onSaved={data.reload}
                onToast={toast.show}
              />
            )}
            {route.view === "benutzer" && (
              <UsersView
                branches={branches}
                permissions={principal.permissions}
                currentUserId={principal.user_id}
                onToast={toast.show}
              />
            )}
            {route.view === "stammdaten" && (
              <CatalogView
                jobRoles={data.jobRoles}
                qualificationTypes={data.qualificationTypes}
                branches={branches}
                branchId={branchId}
                permissions={principal.permissions}
                onReload={data.reload}
                onToast={toast.show}
              />
            )}
          </>
        )}
      </main>
      {changingPassword && (
        <PasswordDialog
          forced={false}
          onClose={() => setChangingPassword(false)}
          onChanged={() => {
            setChangingPassword(false);
            toast.show("Passwort geaendert");
          }}
        />
      )}
      {toast.node}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
