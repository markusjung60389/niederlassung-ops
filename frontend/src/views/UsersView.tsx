import React from "react";
import { KeyRound, LockOpen, Pencil, Plus, Trash2 } from "lucide-react";
import { apiDelete, apiGet, apiPatch, apiPost } from "../api";
import {
  can,
  type Account,
  type Branch,
  type PermissionInfo,
  type RoleInfo,
} from "../types";
import { ActionCell, Cell, Row, Table, TitleCell } from "../components/Table";
import { ConfirmDialog, Modal } from "../components/Modal";
import {
  Field,
  Fieldset,
  FormStatus,
  Pill,
  SearchField,
  Section,
  Segments,
  Select,
  TextArea,
  TextInput,
  emptyToNull,
  formatDate,
  useAction,
  useSubmit,
} from "../components/ui";

/**
 * Accounts, roles and permissions.
 *
 * Two questions per person, kept apart on purpose: the role says *what*
 * somebody may do, the branch assignment *where*. Merging them would mean one
 * role per branch, and four branches later nobody dares touch the list.
 */

const USER_COLUMNS = "minmax(0,1.4fr) minmax(0,1fr) minmax(0,1.2fr) 132px 116px 116px";
const ROLE_COLUMNS = "minmax(0,1fr) minmax(0,2fr) 96px 88px";
type Filter = "active" | "inactive" | "password";

export function UsersView({
  branches,
  permissions,
  currentUserId,
  onToast,
}: {
  branches: Branch[];
  permissions: string[];
  currentUserId: string;
  onToast: (message: string) => void;
}) {
  const mayWrite = can(permissions, "user:write");
  const [users, setUsers] = React.useState<Account[]>([]);
  const [roles, setRoles] = React.useState<RoleInfo[]>([]);
  const [catalogue, setCatalogue] = React.useState<PermissionInfo[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [filter, setFilter] = React.useState<Filter>("active");
  const [search, setSearch] = React.useState("");
  const [editing, setEditing] = React.useState<Account | null | "new">(null);
  const [password, setPassword] = React.useState<Account | null>(null);
  const [role, setRole] = React.useState<RoleInfo | null | "new">(null);
  const [confirm, setConfirm] = React.useState<Account | null>(null);

  const load = React.useCallback(async () => {
    try {
      const [userData, roleData, permissionData] = await Promise.all([
        apiGet<Account[]>("/api/users"),
        apiGet<RoleInfo[]>("/api/roles"),
        apiGet<PermissionInfo[]>("/api/permissions"),
      ]);
      setUsers(userData);
      setRoles(roleData);
      setCatalogue(permissionData);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unbekannter Fehler");
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const remove = useAction(() => {
    setConfirm(null);
    onToast("Konto geloescht");
    load();
  });
  const unlock = useAction(() => {
    onToast("Sperre aufgehoben");
    load();
  });

  const counts = {
    active: users.filter((item) => item.is_active).length,
    inactive: users.filter((item) => !item.is_active).length,
    password: users.filter((item) => item.has_password).length,
  };
  const visible = users
    .filter((item) => {
      if (filter === "inactive") return !item.is_active;
      if (filter === "password") return item.has_password;
      return item.is_active;
    })
    .filter((item) => {
      const needle = search.trim().toLowerCase();
      if (!needle) return true;
      return [item.display_name, item.email, item.role_name ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    });

  const branchLabel = (item: Account) => {
    if (item.all_branches) return "alle Niederlassungen";
    if (!item.branch_ids.length) return "keine Niederlassung";
    return item.branch_ids
      .map((id) => branches.find((branch) => branch.id === id)?.name ?? id)
      .join(", ");
  };

  return (
    <section className="ops-stack">
      {error && <div className="pds-banner pds-banner--danger">{error}</div>}

      <div className="ops-row ops-row--between">
        <Segments<Filter>
          value={filter}
          onChange={setFilter}
          options={[
            { key: "active", label: "Aktiv", count: counts.active },
            { key: "inactive", label: "Deaktiviert", count: counts.inactive },
            { key: "password", label: "Mit Passwort", count: counts.password },
          ]}
        />
        <div className="ops-row ops-spacer">
          <SearchField value={search} onChange={setSearch} placeholder="Name, E-Mail, Rolle" />
          {mayWrite && (
            <button
              type="button"
              className="pds-btn pds-btn--primary pds-btn--sm"
              onClick={() => setEditing("new")}
            >
              <Plus size={15} /> Benutzer
            </button>
          )}
        </div>
      </div>

      <FormStatus error={remove.error ?? unlock.error} busy={remove.busy} busyLabel="Wird geloescht..." />

      <Table
        columns={USER_COLUMNS}
        minWidth={1020}
        empty="Keine Konten in dieser Auswahl."
        head={["Benutzer", "Rolle", "Niederlassungen", "Anmeldung", "Zuletzt aktiv", ""]}
      >
        {visible.map((user) => (
          <Row key={user.id} columns={USER_COLUMNS}>
            <TitleCell
              title={user.display_name}
              meta={
                <>
                  {user.email}
                  {user.id === currentUserId && " · das bin ich"}
                </>
              }
            />
            <Cell>
              {user.role_name ? (
                <Pill tone="info">{user.role_name}</Pill>
              ) : (
                <Pill tone="warn">ohne Rolle</Pill>
              )}
            </Cell>
            <Cell title={branchLabel(user)}>
              <span className={user.all_branches || user.branch_ids.length ? "" : "pds-meta"}>
                {branchLabel(user)}
              </span>
            </Cell>
            <Cell>
              {user.external_id && <span className="ops-cell__title">Microsoft</span>}
              {user.has_password && (
                <span className={user.external_id ? "ops-cell__meta" : "ops-cell__title"}>
                  Passwort
                  {user.must_change_password && " (Start)"}
                </span>
              )}
              {!user.external_id && !user.has_password && (
                <span className="pds-meta">noch nie angemeldet</span>
              )}
              {user.locked_until && (
                <span className="ops-cell__meta" style={{ color: "var(--pds-amber-text)" }}>
                  gesperrt
                </span>
              )}
            </Cell>
            <Cell className="ops-date">{user.last_login_at ? formatDate(user.last_login_at) : "-"}</Cell>
            <ActionCell>
              {mayWrite && (
                <>
                  {user.locked_until && (
                    <button
                      type="button"
                      className="pds-icon-btn"
                      title="Sperre aufheben"
                      aria-label={`Sperre von ${user.display_name} aufheben`}
                      onClick={() => unlock.run(() => apiPost(`/api/users/${user.id}/unlock`, {}))}
                    >
                      <LockOpen size={14} />
                    </button>
                  )}
                  <button
                    type="button"
                    className="pds-icon-btn"
                    title="Passwort setzen"
                    aria-label={`Passwort fuer ${user.display_name} setzen`}
                    onClick={() => setPassword(user)}
                  >
                    <KeyRound size={14} />
                  </button>
                  <button
                    type="button"
                    className="pds-icon-btn"
                    aria-label={`${user.display_name} bearbeiten`}
                    onClick={() => setEditing(user)}
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    type="button"
                    className="pds-icon-btn pds-icon-btn--danger"
                    aria-label={`${user.display_name} loeschen`}
                    onClick={() => setConfirm(user)}
                  >
                    <Trash2 size={14} />
                  </button>
                </>
              )}
            </ActionCell>
          </Row>
        ))}
      </Table>

      <Section
        title="Rollen"
        actions={
          mayWrite ? (
            <button
              type="button"
              className="pds-btn pds-btn--outline pds-btn--sm"
              onClick={() => setRole("new")}
            >
              <Plus size={15} /> Eigene Rolle
            </button>
          ) : undefined
        }
        flush
      >
        <Table
          columns={ROLE_COLUMNS}
          minWidth={880}
          empty="Keine Rollen."
          head={["Rolle", "Berechtigungen", "Konten", ""]}
        >
          {roles.map((item) => (
            <Row key={item.id} columns={ROLE_COLUMNS}>
              <TitleCell
                title={item.name}
                meta={item.system ? "Standardrolle" : (item.description ?? "eigene Rolle")}
              />
              <Cell title={item.permissions.join(", ")}>
                {item.permissions.includes("*") ? (
                  <Pill tone="warn">alle Berechtigungen</Pill>
                ) : (
                  <span className="pds-meta">
                    {item.permissions.length} Berechtigung(en):{" "}
                    {item.permissions.slice(0, 4).join(", ")}
                    {item.permissions.length > 4 ? " ..." : ""}
                  </span>
                )}
              </Cell>
              <Cell className="ops-date">{item.user_count}</Cell>
              <ActionCell>
                {mayWrite && !item.system && (
                  <button
                    type="button"
                    className="pds-icon-btn"
                    aria-label={`Rolle ${item.name} bearbeiten`}
                    onClick={() => setRole(item)}
                  >
                    <Pencil size={14} />
                  </button>
                )}
              </ActionCell>
            </Row>
          ))}
        </Table>
      </Section>

      {editing && (
        <UserDialog
          user={editing === "new" ? null : editing}
          roles={roles}
          branches={branches}
          onClose={() => setEditing(null)}
          onSaved={(message) => {
            setEditing(null);
            onToast(message);
            load();
          }}
        />
      )}

      {password && (
        <SetPasswordDialog
          user={password}
          onClose={() => setPassword(null)}
          onSaved={() => {
            setPassword(null);
            onToast("Passwort gesetzt");
            load();
          }}
        />
      )}

      {role && (
        <RoleDialog
          role={role === "new" ? null : role}
          catalogue={catalogue}
          onClose={() => setRole(null)}
          onSaved={(message) => {
            setRole(null);
            onToast(message);
            load();
          }}
        />
      )}

      <ConfirmDialog
        open={confirm !== null}
        title="Konto loeschen"
        busy={remove.busy}
        body={
          <>
            <p>
              <strong>{confirm?.display_name}</strong> wird entfernt.
            </p>
            <div className="pds-banner pds-banner--warn" style={{ marginTop: 12 }}>
              Sobald das Konto irgendwo als Verantwortlicher steht oder etwas im Protokoll
              hinterlassen hat, ist Deaktivieren der richtige Weg &ndash; dann bleibt
              nachvollziehbar, wer was getan hat.
            </div>
          </>
        }
        onCancel={() => setConfirm(null)}
        onConfirm={() => confirm && remove.run(() => apiDelete(`/api/users/${confirm.id}`))}
      />
    </section>
  );
}

/* --------------------------------------------------------------------------
 * Accounts
 * ----------------------------------------------------------------------- */

function UserDialog({
  user,
  roles,
  branches,
  onClose,
  onSaved,
}: {
  user: Account | null;
  roles: RoleInfo[];
  branches: Branch[];
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const { error, busy, run } = useSubmit(() =>
    onSaved(user ? "Konto gespeichert" : "Konto angelegt")
  );
  const [allBranches, setAllBranches] = React.useState(user?.all_branches ?? false);
  const [selected, setSelected] = React.useState<string[]>(user?.branch_ids ?? []);

  function toggle(branchId: string) {
    setSelected((current) =>
      current.includes(branchId)
        ? current.filter((item) => item !== branchId)
        : [...current, branchId]
    );
  }

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(form, async () => {
      const payload = {
        display_name: data.get("display_name"),
        email: String(data.get("email") || "").trim(),
        role_id: emptyToNull(data.get("role_id")),
        all_branches: allBranches,
        branch_ids: allBranches ? [] : selected,
      };
      if (user) {
        await apiPatch(`/api/users/${user.id}`, {
          ...payload,
          is_active: data.get("is_active") === "active",
        });
      } else {
        await apiPost("/api/users", {
          ...payload,
          password: emptyToNull(data.get("password")),
        });
      }
    });
  }

  return (
    <Modal
      open
      title={user ? `${user.display_name} bearbeiten` : "Benutzer anlegen"}
      subtitle="Die Rolle entscheidet, was jemand darf. Die Niederlassungen entscheiden, wo."
      onClose={onClose}
      footer={
        <>
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
            Abbrechen
          </button>
          <span className="ops-spacer" />
          <button
            type="submit"
            form="user-form"
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gespeichert..." : "Speichern"}
          </button>
        </>
      }
    >
      <form id="user-form" className="ops-dialog__body" onSubmit={submit}>
        <FormStatus error={error} busy={false} />

        <Fieldset legend="Konto">
          <div className="ops-grid">
            <Field label="Name">
              <TextInput name="display_name" required minLength={2} defaultValue={user?.display_name} />
            </Field>
            <Field label="E-Mail (Anmeldung)">
              <TextInput name="email" type="email" required defaultValue={user?.email} />
            </Field>
            <Field label="Rolle">
              <Select name="role_id" defaultValue={user?.role_id ?? ""}>
                <option value="">ohne Rolle (kein Zugriff)</option>
                {roles.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name}
                  </option>
                ))}
              </Select>
            </Field>
            {user && (
              <Field label="Status">
                <Select name="is_active" defaultValue={user.is_active ? "active" : "inactive"}>
                  <option value="active">aktiv</option>
                  <option value="inactive">deaktiviert</option>
                </Select>
              </Field>
            )}
            {!user && (
              <Field label="Passwort (optional)">
                <TextInput
                  name="password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="leer = nur Microsoft-Anmeldung"
                />
              </Field>
            )}
          </div>
          {!user && (
            <p className="pds-meta">
              Ohne Passwort meldet sich das Konto ueber Microsoft an - der Normalfall. Ein hier
              gesetztes Passwort ist ein Startpasswort und muss bei der ersten Anmeldung geaendert
              werden.
            </p>
          )}
        </Fieldset>

        <Fieldset legend="Niederlassungen">
          <label className="ops-check">
            <input
              type="checkbox"
              checked={allBranches}
              onChange={(event) => setAllBranches(event.target.checked)}
            />
            Alle Niederlassungen (auch kuenftige)
          </label>
          {!allBranches && (
            <div className="ops-chips" style={{ marginTop: 10 }}>
              {branches.map((branch) => (
                <label key={branch.id} className="ops-check">
                  <input
                    type="checkbox"
                    checked={selected.includes(branch.id)}
                    onChange={() => toggle(branch.id)}
                  />
                  {branch.name}
                </label>
              ))}
            </div>
          )}
          <p className="pds-meta">
            Ohne Zuordnung sieht das Konto nichts. Das ist Absicht: Aufenthaltstitel und
            Vorsorgetermine gehen eine fremde Niederlassung nichts an.
          </p>
        </Fieldset>
      </form>
    </Modal>
  );
}

function SetPasswordDialog({
  user,
  onClose,
  onSaved,
}: {
  user: Account;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { error, busy, run } = useSubmit(onSaved);
  const clear = useAction(onSaved);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(form, async () => {
      await apiPost(`/api/users/${user.id}/password`, {
        new_password: String(data.get("new_password") || ""),
        must_change: true,
      });
    });
  }

  return (
    <Modal
      open
      size="sm"
      title="Passwort setzen"
      subtitle={`${user.display_name} · ${user.email}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
            Abbrechen
          </button>
          <span className="ops-spacer" />
          <button
            type="submit"
            form="set-password-form"
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gesetzt..." : "Setzen"}
          </button>
        </>
      }
    >
      <form id="set-password-form" className="ops-dialog__body" onSubmit={submit}>
        <FormStatus error={error ?? clear.error} busy={false} />
        <p className="pds-meta">
          Das Passwort ist ein Startpasswort: es muss bei der naechsten Anmeldung geaendert werden,
          und bis dahin ist ausser dieser Aenderung nichts moeglich.
        </p>
        <Field label="Neues Passwort" span>
          <TextInput name="new_password" type="password" required autoComplete="new-password" autoFocus />
        </Field>
        {user.has_password && (
          <button
            type="button"
            className="pds-btn pds-btn--link"
            disabled={clear.busy}
            onClick={() => clear.run(() => apiDelete(`/api/users/${user.id}/password`))}
          >
            Passwort-Anmeldung fuer dieses Konto entfernen
          </button>
        )}
      </form>
    </Modal>
  );
}

/* --------------------------------------------------------------------------
 * Roles
 * ----------------------------------------------------------------------- */

function RoleDialog({
  role,
  catalogue,
  onClose,
  onSaved,
}: {
  role: RoleInfo | null;
  catalogue: PermissionInfo[];
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const { error, busy, run } = useSubmit(() => onSaved(role ? "Rolle gespeichert" : "Rolle angelegt"));
  const remove = useAction(() => onSaved("Rolle geloescht"));
  const [selected, setSelected] = React.useState<string[]>(role?.permissions ?? []);

  const areas = catalogue.reduce<Record<string, PermissionInfo[]>>((groups, item) => {
    (groups[item.area] ??= []).push(item);
    return groups;
  }, {});

  function toggle(key: string) {
    setSelected((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key]
    );
  }

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(form, async () => {
      const payload = {
        name: data.get("name"),
        description: emptyToNull(data.get("description")),
        permissions: selected,
      };
      if (role) await apiPatch(`/api/roles/${role.id}`, payload);
      else await apiPost("/api/roles", payload);
    });
  }

  return (
    <Modal
      open
      size="lg"
      title={role ? `Rolle ${role.name}` : "Eigene Rolle anlegen"}
      subtitle="Die Standardrollen kommen aus dem Programm und lassen sich nicht aendern."
      onClose={onClose}
      footer={
        <>
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
            Abbrechen
          </button>
          {role && (
            <button
              type="button"
              className="pds-btn pds-btn--danger pds-btn--sm"
              disabled={remove.busy}
              onClick={() => remove.run(() => apiDelete(`/api/roles/${role.id}`))}
            >
              <Trash2 size={14} /> Loeschen
            </button>
          )}
          <span className="ops-spacer" />
          <button
            type="submit"
            form="role-form"
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gespeichert..." : "Speichern"}
          </button>
        </>
      }
    >
      <form id="role-form" className="ops-dialog__body" onSubmit={submit}>
        <FormStatus error={error ?? remove.error} busy={false} />
        <div className="ops-grid">
          <Field label="Name">
            <TextInput name="name" required minLength={2} defaultValue={role?.name} />
          </Field>
        </div>
        <Field label="Wofuer ist die Rolle da?" span>
          <TextArea name="description" defaultValue={role?.description ?? ""} />
        </Field>

        {Object.entries(areas).map(([area, entries]) => (
          <Fieldset key={area} legend={area}>
            {entries.map((entry) => (
              <label key={entry.key} className="ops-check ops-check--block">
                <input
                  type="checkbox"
                  checked={selected.includes(entry.key)}
                  onChange={() => toggle(entry.key)}
                />
                <span>
                  <span className="ops-cell__title">{entry.label}</span>
                  <span className="ops-cell__meta">{entry.description}</span>
                </span>
              </label>
            ))}
          </Fieldset>
        ))}
      </form>
    </Modal>
  );
}
