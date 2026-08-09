import React from "react";
import { Plus, Trash2 } from "lucide-react";
import { apiDelete, apiPost } from "../api";
import { can, type Assessment, type Bootstrap } from "../types";
import { ActionCell, Cell, Row, Table, TitleCell } from "../components/Table";
import { ConfirmDialog, Modal } from "../components/Modal";
import {
  EmptyState,
  Field,
  Fieldset,
  FormStatus,
  Pill,
  Section,
  Select,
  TextArea,
  TextInput,
  emptyToNull,
  formatDate,
  toneOf,
  useAction,
  useSubmit,
} from "../components/ui";

const COLUMNS = "120px minmax(0,2fr) 120px 72px";
const RATINGS: [string, string][] = [
  ["compliance", "Compliance"],
  ["personal", "Personal"],
  ["service", "Service"],
  ["sales", "Vertrieb"],
  ["operations", "Betrieb"],
];

export function AssessmentView({
  assessments,
  bootstrap,
  permissions,
  onSaved,
  onToast,
}: {
  assessments: Assessment[];
  bootstrap: Bootstrap;
  permissions: string[];
  onSaved: () => void;
  onToast: (message: string) => void;
}) {
  const mayWrite = can(permissions, "assessment:write");
  const [creating, setCreating] = React.useState(false);
  const [confirm, setConfirm] = React.useState<Assessment | null>(null);
  const remove = useAction(() => {
    setConfirm(null);
    onToast("Bestandsaufnahme geloescht");
    onSaved();
  });
  const latest = assessments[0];

  return (
    <section className="ops-stack">
      <div className="ops-row ops-row--between">
        <span className="pds-meta">
          {assessments.length} Bestandsaufnahme(n)
          {latest ? ` · zuletzt ${formatDate(latest.assessment_date)}` : ""}
        </span>
        {mayWrite && (
          <button
            type="button"
            className="pds-btn pds-btn--primary pds-btn--sm ops-spacer"
            onClick={() => setCreating(true)}
          >
            <Plus size={15} /> Bestandsaufnahme
          </button>
        )}
      </div>

      {latest && (
        <Section title={latest.title}>
          <AssessmentSummary assessment={latest} />
        </Section>
      )}

      <FormStatus error={remove.error} busy={remove.busy} busyLabel="Wird geloescht..." />

      <Table
        columns={COLUMNS}
        minWidth={640}
        head={["Datum", "Titel", "Personal", ""]}
        empty="Noch keine Bestandsaufnahme erfasst."
      >
        {assessments.map((item) => (
          <Row key={item.id} columns={COLUMNS}>
            <Cell>
              <span className="ops-date">{formatDate(item.assessment_date)}</span>
            </Cell>
            <TitleCell title={item.title} meta={item.main_problems || "-"} />
            <Cell>
              <Pill tone={toneOf(item.management_ratings?.personal)}>
                {item.management_ratings?.personal || "offen"}
              </Pill>
            </Cell>
            <ActionCell>
              {mayWrite && (
                <button
                  type="button"
                  className="pds-icon-btn pds-icon-btn--danger"
                  aria-label={`${item.title} loeschen`}
                  onClick={() => setConfirm(item)}
                >
                  <Trash2 size={14} />
                </button>
              )}
            </ActionCell>
          </Row>
        ))}
      </Table>

      {creating && (
        <AssessmentDialog
          bootstrap={bootstrap}
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            onToast("Bestandsaufnahme gespeichert");
            onSaved();
          }}
        />
      )}

      <ConfirmDialog
        open={confirm !== null}
        title="Bestandsaufnahme loeschen"
        busy={remove.busy}
        body={
          <p>
            <strong>{confirm?.title}</strong> vom {formatDate(confirm?.assessment_date)} wird
            entfernt.
          </p>
        }
        onCancel={() => setConfirm(null)}
        onConfirm={() =>
          confirm && remove.run(() => apiDelete(`/api/branch-assessments/${confirm.id}`))
        }
      />
    </section>
  );
}

function AssessmentDialog({
  bootstrap,
  onClose,
  onSaved,
}: {
  bootstrap: Bootstrap;
  onClose: () => void;
  onSaved: () => void;
}) {
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
        management_ratings: Object.fromEntries(
          RATINGS.map(([key]) => [key, data.get(`rating_${key}`)])
        ),
      });
    });
  }

  return (
    <Modal
      open
      size="lg"
      title="Bestandsaufnahme erfassen"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
            Abbrechen
          </button>
          <span className="ops-spacer" />
          <button
            type="submit"
            form="assessment-form"
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gespeichert..." : "Speichern"}
          </button>
        </>
      }
    >
      <form id="assessment-form" className="ops-dialog__body" onSubmit={submit}>
        <FormStatus error={error} busy={false} />

        <Fieldset legend="Rahmen">
          <div className="ops-grid">
            <Field label="Titel">
              <TextInput name="title" required minLength={3} defaultValue="Bestandsaufnahme Remscheid" />
            </Field>
            <Field label="Datum">
              <TextInput
                type="date"
                name="assessment_date"
                required
                defaultValue={new Date().toISOString().slice(0, 10)}
              />
            </Field>
          </div>
        </Fieldset>

        <Fieldset legend="Aufnahme">
          <Field label="Teamstruktur, Rollen, Verantwortliche" span>
            <TextArea name="team_structure" />
          </Field>
          <Field label="Kundencluster und wichtige Accounts" span>
            <TextArea name="customer_clusters" />
          </Field>
          <Field label="Leistungsportfolio" span>
            <TextArea name="service_portfolio" />
          </Field>
          <Field label="Projektarten und typische Baustellen" span>
            <TextArea name="project_types" />
          </Field>
          <Field label="Service-/Wartungsanteil" span>
            <TextInput name="service_share" />
          </Field>
          <Field label="Aktuelle Hauptprobleme" span>
            <TextArea name="main_problems" />
          </Field>
        </Fieldset>

        <Fieldset legend="Ampeln">
          <div className="ops-grid ops-grid--three">
            {RATINGS.map(([key, text]) => (
              <Field key={key} label={text}>
                <Select name={`rating_${key}`} defaultValue="yellow">
                  <option value="green">gruen</option>
                  <option value="yellow">gelb</option>
                  <option value="red">rot</option>
                </Select>
              </Field>
            ))}
          </div>
        </Fieldset>

        <Fieldset legend="Massnahmen und Notizen">
          <Field label="Massnahmen, eine pro Zeile" span>
            <TextArea name="next_actions_text" />
          </Field>
          <Field label="Notizen" span>
            <TextArea name="notes" />
          </Field>
        </Fieldset>
      </form>
    </Modal>
  );
}

export function AssessmentSummary({ assessment }: { assessment: Assessment }) {
  const ratings = Object.entries(assessment.management_ratings || {});
  return (
    <div className="ops-stack">
      <dl className="ops-facts">
        <dt>Team</dt>
        <dd>{assessment.team_structure || "-"}</dd>
        <dt>Kunden</dt>
        <dd>{assessment.customer_clusters || "-"}</dd>
        <dt>Portfolio</dt>
        <dd>{assessment.service_portfolio || "-"}</dd>
        <dt>Probleme</dt>
        <dd>{assessment.main_problems || "-"}</dd>
      </dl>
      {ratings.length ? (
        <div className="ops-chips">
          {ratings.map(([key, value]) => (
            <Pill key={key} tone={toneOf(value)}>
              {RATINGS.find(([id]) => id === key)?.[1] ?? key}
            </Pill>
          ))}
        </div>
      ) : (
        <EmptyState>Keine Ampeln gesetzt.</EmptyState>
      )}
    </div>
  );
}
