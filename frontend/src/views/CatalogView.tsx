import React from "react";
import { Check, Plus, Trash2 } from "lucide-react";
import { apiDelete, apiPatch, apiPost } from "../api";
import { label, options } from "../labels";
import { can, type JobRole, type QualificationType } from "../types";
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
  permissions,
  onReload,
  onToast,
}: {
  jobRoles: JobRole[];
  qualificationTypes: QualificationType[];
  permissions: string[];
  onReload: () => void;
  onToast: (message: string) => void;
}) {
  const mayWrite = can(permissions, "personnel:write");
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
                <span className="ops-cell__title">{role.name}</span>
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
              <TitleCell title={kind.name} meta={kind.code} />
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
          mayWrite={mayWrite}
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
  onClose,
  onSaved,
}: {
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
        </div>
      </form>
    </Modal>
  );
}

function RequirementDialog({
  role,
  qualificationTypes,
  mayWrite,
  onClose,
  onChanged,
}: {
  role: JobRole;
  qualificationTypes: QualificationType[];
  mayWrite: boolean;
  onClose: () => void;
  onChanged: () => void;
}) {
  const action = useAction(onChanged);
  const byType = new Map(role.requirements.map((item) => [item.qualification_type_id, item]));

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
                  {mayWrite ? (
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
      </div>
    </Modal>
  );
}
