import React from "react";
import { Check, Plus, Trash2 } from "lucide-react";
import { apiDelete, apiPatch, apiPost } from "../api";
import { label, options } from "../labels";
import { can, type Branch, type JobRole, type QualificationType } from "../types";
import { ActionCell, Cell, Row, Table, TitleCell } from "../components/Table";
import { ConfirmDialog, Modal } from "../components/Modal";
import {
  Field,
  FormStatus,
  Pill,
  Section,
  Select,
  TextArea,
  TextInput,
  emptyToNull,
  numberOrNull,
  useAction,
  useSubmit,
} from "../components/ui";

/**
 * Reference data: which qualifications exist, and which function requires
 * which of them.
 *
 * Editable on purpose - a branch that takes on a new trade adds the
 * qualification here instead of waiting for a release.
 */

const TYPE_COLUMNS = "minmax(0,1.6fr) 120px 110px 120px minmax(0,1.2fr) 64px";
const ROLE_COLUMNS = "minmax(0,1fr) 96px";

export function CatalogView({
  jobRoles,
  qualificationTypes,
  branches,
  branchId,
  permissions,
  onReload,
  onToast,
}: {
  jobRoles: JobRole[];
  qualificationTypes: QualificationType[];
  branches: Branch[];
  branchId: string | null;
  permissions: string[];
  onReload: () => void;
  onToast: (message: string) => void;
}) {
  const mayWrite = can(permissions, "personnel:write");
  // Group entries reach branches this caller may not be responsible for, so
  // creating or changing one is the area manager's.
  const mayGovern = can(permissions, "rule:write");
  const [newType, setNewType] = React.useState(false);
  const [editingRole, setEditingRole] = React.useState<JobRole | null>(null);
  const [confirmType, setConfirmType] = React.useState<QualificationType | null>(null);
  const remove = useAction(() => {
    setConfirmType(null);
    onToast("Qualifikationsart entfernt");
    onReload();
  });

  return (
    <section className="ops-stack">
      <Section
        title="Funktionen und ihre Anforderungen"
        actions={<span className="pds-meta">{jobRoles.length} Funktionen</span>}
        flush
      >
        <Table
          columns={ROLE_COLUMNS}
          minWidth={520}
          head={["Funktion", "Mitarbeiter"]}
          empty="Keine Funktionen angelegt."
        >
          {jobRoles.map((role) => (
            <Row
              key={role.id}
              columns={ROLE_COLUMNS}
              onOpen={() => setEditingRole(role)}
              title="Anforderungen bearbeiten"
            >
              <span role="gridcell" className="ops-cell ops-cell--wrap">
                <span className="ops-cell__title">
                  {role.name}
                  {branches.length > 1 && (
                    <span className="pds-tag" style={{ marginLeft: 8 }}>
                      {role.branch_id
                        ? branches.find((item) => item.id === role.branch_id)?.name ?? "Niederlassung"
                        : "Gruppe"}
                    </span>
                  )}
                </span>
                <span className="ops-chips" style={{ marginTop: 6 }}>
                  {role.requirements.length ? (
                    role.requirements.map((requirement) => (
                      <span
                        key={requirement.id}
                        className={`pds-pill pds-pill--${requirement.mandatory ? "info" : "muted"}`}
                      >
                        {requirement.qualification_name}
                        {requirement.mandatory ? "" : " (optional)"}
                      </span>
                    ))
                  ) : (
                    <span className="pds-meta">keine Anforderungen hinterlegt</span>
                  )}
                </span>
              </span>
              <Cell>
                <span className="ops-date">{role.employee_count}</span>
              </Cell>
            </Row>
          ))}
        </Table>
      </Section>

      <Section
        title="Qualifikationsarten"
        actions={
          mayWrite ? (
            <button
              type="button"
              className="pds-btn pds-btn--primary pds-btn--sm"
              onClick={() => setNewType(true)}
            >
              <Plus size={15} /> Qualifikationsart
            </button>
          ) : undefined
        }
        flush
      >
        <FormStatus error={remove.error} busy={remove.busy} busyLabel="Wird entfernt..." />
        <Table
          columns={TYPE_COLUMNS}
          head={["Qualifikation", "Kategorie", "Gueltigkeit", "Vorwarnung", "Rechtsgrundlage", ""]}
          empty="Katalog ist leer."
        >
          {qualificationTypes.map((kind) => (
            <Row key={kind.id} columns={TYPE_COLUMNS}>
              <TitleCell
                title={kind.name}
                meta={
                  branches.length > 1
                    ? `${kind.code} · ${
                        kind.branch_id
                          ? branches.find((item) => item.id === kind.branch_id)?.name ?? "Niederlassung"
                          : "Gruppenkatalog"
                      }`
                    : kind.code
                }
              />
              <Cell>
                <span className="pds-meta">{label.qualificationCategory(kind.category)}</span>
              </Cell>
              <Cell>
                <span className="ops-date">
                  {kind.validity_months ? `${kind.validity_months} Monate` : "unbefristet"}
                </span>
              </Cell>
              <Cell>
                <span className="ops-date">{kind.reminder_days} Tage</span>
              </Cell>
              <Cell title={kind.legal_basis ?? undefined}>
                <span className="pds-meta">{kind.legal_basis ?? "-"}</span>
              </Cell>
              <ActionCell>
                {mayWrite && (
                  <button
                    type="button"
                    className="pds-icon-btn pds-icon-btn--danger"
                    aria-label={`${kind.name} entfernen`}
                    onClick={() => setConfirmType(kind)}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </ActionCell>
            </Row>
          ))}
        </Table>
      </Section>

      {newType && (
        <QualificationTypeDialog
          branches={branches}
          branchId={branchId}
          mayGovern={mayGovern}
          onClose={() => setNewType(false)}
          onSaved={() => {
            setNewType(false);
            onToast("Qualifikationsart angelegt");
            onReload();
          }}
        />
      )}

      {editingRole && (
        <RequirementDialog
          role={jobRoles.find((item) => item.id === editingRole.id) ?? editingRole}
          qualificationTypes={qualificationTypes}
          branchId={branchId}
          mayWrite={mayWrite}
          mayGovern={mayGovern}
          onClose={() => setEditingRole(null)}
          onChanged={() => {
            onToast("Anforderungen aktualisiert");
            onReload();
          }}
        />
      )}

      <ConfirmDialog
        open={confirmType !== null}
        title="Qualifikationsart entfernen"
        confirmLabel="Entfernen"
        busy={remove.busy}
        body={
          <p>
            <strong>{confirmType?.name}</strong> wird aus dem Katalog entfernt. Das ist nur moeglich,
            solange keine Funktion sie fordert und sie bei niemandem erfasst ist.
          </p>
        }
        onCancel={() => setConfirmType(null)}
        onConfirm={() =>
          confirmType && remove.run(() => apiDelete(`/api/qualification-types/${confirmType.id}`))
        }
      />
    </section>
  );
}

function QualificationTypeDialog({
  branches,
  branchId,
  mayGovern,
  onClose,
  onSaved,
}: {
  branches: Branch[];
  branchId: string | null;
  mayGovern: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { error, busy, run } = useSubmit(onSaved);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(form, async () => {
      await apiPost("/api/qualification-types", {
        code: String(data.get("code") || "")
          .trim()
          .toLowerCase()
          .replace(/\s+/g, "_"),
        name: data.get("name"),
        category: data.get("category"),
        validity_months: numberOrNull(data.get("validity_months")),
        reminder_days: numberOrNull(data.get("reminder_days")) ?? 60,
        evidence_required: data.get("evidence_required") !== "no",
        legal_basis: emptyToNull(data.get("legal_basis")),
        description: emptyToNull(data.get("description")),
        branch_id: emptyToNull(data.get("branch_id")),
      });
    });
  }

  return (
    <Modal
      open
      title="Qualifikationsart anlegen"
      subtitle="Gueltigkeitsdauer und Vorwarnzeit gelten anschliessend fuer jeden Eintrag dieser Art."
      onClose={onClose}
      footer={
        <>
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
            Abbrechen
          </button>
          <span className="ops-spacer" />
          <button
            type="submit"
            form="type-form"
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gespeichert..." : "Speichern"}
          </button>
        </>
      }
    >
      <form id="type-form" className="ops-dialog__body" onSubmit={submit}>
        <FormStatus error={error} busy={false} />
        <div className="ops-grid">
          <Field label="Bezeichnung">
            <TextInput name="name" required minLength={2} placeholder="z. B. Flurfoerderzeug-Schein" />
          </Field>
          <Field label="Kuerzel">
            <TextInput name="code" required minLength={2} placeholder="gabelstapler" />
          </Field>
          <Field label="Kategorie">
            <Select name="category" defaultValue="training">
              {options.qualificationCategory.map(([value, text]) => (
                <option key={value} value={value}>
                  {text}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Gueltigkeit in Monaten">
            <TextInput type="number" name="validity_months" min={1} placeholder="leer = unbefristet" />
          </Field>
          <Field label="Vorwarnung in Tagen">
            <TextInput type="number" name="reminder_days" min={1} defaultValue={60} />
          </Field>
          <Field label="Nachweis">
            <Select name="evidence_required" defaultValue="yes">
              <option value="yes">Dokument erforderlich</option>
              <option value="no">kein Dokument noetig</option>
            </Select>
          </Field>
          <Field label="Rechtsgrundlage" span>
            <TextInput name="legal_basis" placeholder="z. B. DGUV Vorschrift 68" />
          </Field>
          <Field label="Beschreibung" span>
            <TextArea name="description" />
          </Field>
          {branches.length > 1 && (
            <Field label="Gilt fuer" span>
              <Select name="branch_id" defaultValue={mayGovern ? "" : (branchId ?? branches[0]?.id ?? "")}>
                {mayGovern && <option value="">alle Niederlassungen</option>}
                {branches.map((branch) => (
                  <option key={branch.id} value={branch.id}>
                    nur {branch.name}
                  </option>
                ))}
              </Select>
            </Field>
          )}
        </div>
      </form>
    </Modal>
  );
}

function RequirementDialog({
  role,
  qualificationTypes,
  branchId,
  mayWrite,
  mayGovern,
  onClose,
  onChanged,
}: {
  role: JobRole;
  qualificationTypes: QualificationType[];
  branchId: string | null;
  mayWrite: boolean;
  mayGovern: boolean;
  onClose: () => void;
  onChanged: () => void;
}) {
  const action = useAction(onChanged);
  const byType = new Map(role.requirements.map((item) => [item.qualification_type_id, item]));
  // A requirement is group-wide only while both sides are: a branch's own
  // qualification required of a group function stays local.
  const groupWide = (kind: QualificationType) => !role.branch_id && !kind.branch_id;
  const [excepting, setExcepting] = React.useState<{ id: string; name: string } | null>(null);

  return (
    <Modal
      open
      size="lg"
      title={`Anforderungen: ${role.name}`}
      subtitle={role.description ?? undefined}
      onClose={onClose}
      footer={
        <>
          <span className="pds-meta">
            {role.employee_count} Mitarbeiter in dieser Funktion &ndash; Aenderungen wirken sofort
            auf deren Einsatzfaehigkeit.
          </span>
          <span className="ops-spacer" />
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
            Schliessen
          </button>
        </>
      }
    >
      <div className="ops-dialog__body">
        <FormStatus error={action.error} busy={action.busy} busyLabel="Wird gespeichert..." />
        <Table
          columns="minmax(0,1.6fr) 120px 190px"
          minWidth={560}
          head={["Qualifikation", "Gueltigkeit", "Anforderung"]}
        >
          {qualificationTypes.map((kind) => {
            const requirement = byType.get(kind.id);
            const state = requirement ? (requirement.mandatory ? "mandatory" : "optional") : "none";
            return (
              <Row key={kind.id} columns="minmax(0,1.6fr) 120px 190px">
                <TitleCell title={kind.name} meta={kind.legal_basis ?? kind.code} />
                <Cell>
                  <span className="ops-date">
                    {kind.validity_months ? `${kind.validity_months} Monate` : "unbefristet"}
                  </span>
                </Cell>
                <ActionCell>
                  {mayWrite && groupWide(kind) && !mayGovern ? (
                    // The branch may not change a group requirement, but it may
                    // record an exception - which the area manager sees and can
                    // revoke, unlike a silently deleted requirement.
                    requirement ? (
                      <button
                        type="button"
                        className="pds-btn pds-btn--outline pds-btn--sm"
                        disabled={!branchId}
                        title={
                          branchId
                            ? "Fuer diese Niederlassung aussetzen"
                            : "Zuerst eine Niederlassung waehlen"
                        }
                        onClick={() => setExcepting({ id: requirement.id, name: kind.name })}
                      >
                        Ausnahme
                      </button>
                    ) : (
                      <Pill tone="muted">nicht gefordert</Pill>
                    )
                  ) : mayWrite ? (
                    <Select
                      value={state}
                      className="pds-input--sm"
                      style={{ width: 180 }}
                      disabled={action.busy}
                      onChange={(event) => {
                        const next = event.target.value;
                        action.run(async () => {
                          if (next === "none") {
                            if (requirement)
                              await apiDelete(`/api/job-role-requirements/${requirement.id}`);
                            return;
                          }
                          const mandatory = next === "mandatory";
                          if (requirement) {
                            await apiPatch(`/api/job-role-requirements/${requirement.id}`, {
                              mandatory,
                            });
                          } else {
                            await apiPost("/api/job-role-requirements", {
                              job_role_id: role.id,
                              qualification_type_id: kind.id,
                              mandatory,
                            });
                          }
                        });
                      }}
                    >
                      <option value="none">nicht gefordert</option>
                      <option value="mandatory">Pflicht</option>
                      <option value="optional">optional</option>
                    </Select>
                  ) : (
                    <Pill tone={state === "mandatory" ? "info" : state === "optional" ? "muted" : "muted"}>
                      {state === "mandatory" ? (
                        <>
                          <Check size={12} /> Pflicht
                        </>
                      ) : state === "optional" ? (
                        "optional"
                      ) : (
                        "nicht gefordert"
                      )}
                    </Pill>
                  )}
                </ActionCell>
              </Row>
            );
          })}
        </Table>
        {!mayGovern && (
          <p className="pds-meta">
            Gruppenanforderungen legt die Bereichsleitung fest. Passt eine davon fuer diese
            Niederlassung nicht, wird das als begruendete Ausnahme erfasst - sichtbar fuer die
            Bereichsleitung und jederzeit widerrufbar.
          </p>
        )}
      </div>
      {excepting && branchId && (
        <ExceptionDialog
          requirementId={excepting.id}
          qualificationName={excepting.name}
          branchId={branchId}
          onClose={() => setExcepting(null)}
          onSaved={() => {
            setExcepting(null);
            onChanged();
          }}
        />
      )}
    </Modal>
  );
}

/** A branch setting itself an exception from a group requirement. */
function ExceptionDialog({
  requirementId,
  qualificationName,
  branchId,
  onClose,
  onSaved,
}: {
  requirementId: string;
  qualificationName: string;
  branchId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { error, busy, run } = useSubmit(onSaved);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(form, async () => {
      await apiPost("/api/requirement-overrides", {
        branch_id: branchId,
        requirement_id: requirementId,
        mode: data.get("mode"),
        reason: String(data.get("reason") || ""),
        valid_until: emptyToNull(data.get("valid_until")),
      });
    });
  }

  return (
    <Modal
      open
      size="sm"
      title="Ausnahme erfassen"
      subtitle={qualificationName}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
            Abbrechen
          </button>
          <span className="ops-spacer" />
          <button
            type="submit"
            form="exception-form"
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gespeichert..." : "Ausnahme setzen"}
          </button>
        </>
      }
    >
      <form id="exception-form" className="ops-dialog__body" onSubmit={submit}>
        <FormStatus error={error} busy={false} />
        <p className="pds-meta">
          Die Ausnahme gilt sofort und nur fuer diese Niederlassung. Sie erscheint bei der
          Bereichsleitung - eine Ausnahme, die niemand erklaeren kann, ist bei einer Pruefung
          schlimmer als eine offene Luecke.
        </p>
        <Field label="Art">
          <Select name="mode" defaultValue="excluded">
            <option value="excluded">entfaellt hier</option>
            <option value="optional">nur freiwillig</option>
            <option value="mandatory">hier verpflichtend</option>
          </Select>
        </Field>
        <Field label="Begruendung" span>
          <TextArea name="reason" required minLength={5} placeholder="Warum gilt das hier nicht?" />
        </Field>
        <Field label="Befristet bis (optional)">
          <TextInput type="date" name="valid_until" />
        </Field>
      </form>
    </Modal>
  );
}
