import React from "react";
import { ArrowLeftRight, Pencil, Plus, Trash2 } from "lucide-react";
import { apiDelete, apiPatch, apiPost } from "../api";
import { label, options } from "../labels";
import {
  can,
  type Branch,
  type ComplianceRule,
  type ScopeChangePreview,
} from "../types";
import { ActionCell, Cell, Row, Table, TitleCell } from "../components/Table";
import { ConfirmDialog, Modal } from "../components/Modal";
import {
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
  useAction,
  useSubmit,
} from "../components/ui";

/**
 * Rules: the obligation, separate from the branch's work on it.
 *
 * The distinction the whole screen turns on: a rule says what has to happen,
 * a compliance record is one branch doing it. Only that separation makes a
 * rule movable - a local rule can be raised to the group, and a group rule can
 * be restricted to one branch without the other branches losing their evidence.
 */

const COLUMNS = "124px minmax(0,1.7fr) minmax(0,1fr) 120px 148px 116px";
type Scope = "all" | "group" | "local";

export function RulesView({
  rules,
  branches,
  branchId,
  permissions,
  onReload,
  onToast,
}: {
  rules: ComplianceRule[];
  branches: Branch[];
  branchId: string | null;
  permissions: string[];
  onReload: () => void;
  onToast: (message: string) => void;
}) {
  const mayWrite = can(permissions, "compliance:write");
  const mayGovern = can(permissions, "rule:write");
  const [scope, setScope] = React.useState<Scope>("all");
  const [search, setSearch] = React.useState("");
  const [editing, setEditing] = React.useState<ComplianceRule | null | "new">(null);
  const [moving, setMoving] = React.useState<ComplianceRule | null>(null);
  const [confirm, setConfirm] = React.useState<ComplianceRule | null>(null);
  const remove = useAction(() => {
    setConfirm(null);
    onToast("Vorgabe entfernt, Nachweise bleiben erhalten");
    onReload();
  });

  const counts = {
    all: rules.length,
    group: rules.filter((item) => !item.branch_id).length,
    local: rules.filter((item) => Boolean(item.branch_id)).length,
  };
  const visible = rules
    .filter((item) => {
      if (scope === "group") return !item.branch_id;
      if (scope === "local") return Boolean(item.branch_id);
      return true;
    })
    .filter((item) => {
      const needle = search.trim().toLowerCase();
      if (!needle) return true;
      return [item.title, item.legal_basis, item.category].join(" ").toLowerCase().includes(needle);
    });

  return (
    <section className="ops-stack">
      <div className="ops-row ops-row--between">
        <Segments<Scope>
          value={scope}
          onChange={setScope}
          options={[
            { key: "all", label: "Alle", count: counts.all },
            { key: "group", label: "Gruppenvorgabe", count: counts.group },
            { key: "local", label: "Niederlassung", count: counts.local },
          ]}
        />
        <div className="ops-row ops-spacer">
          <SearchField value={search} onChange={setSearch} placeholder="Titel, Rechtsgrundlage" />
          {mayWrite && (
            <button
              type="button"
              className="pds-btn pds-btn--primary pds-btn--sm"
              onClick={() => setEditing("new")}
            >
              <Plus size={15} /> Vorgabe
            </button>
          )}
        </div>
      </div>

      <div className="pds-banner">
        Eine Vorgabe beschreibt die Pflicht. Je Niederlassung entsteht daraus ein Compliance-Eintrag
        mit eigenem Termin und eigenen Nachweisen. Gruppenvorgaben aendert die Bereichsleitung,
        eigene Vorgaben die Niederlassung selbst.
      </div>

      <FormStatus error={remove.error} busy={remove.busy} busyLabel="Wird entfernt..." />

      <Table
        columns={COLUMNS}
        minWidth={940}
        empty={search ? "Kein Treffer fuer die Suche." : "Noch keine Vorgaben erfasst."}
        head={["Geltung", "Vorgabe", "Rechtsgrundlage", "Turnus", "Eintraege", ""]}
      >
        {visible.map((rule) => {
          const editable = rule.branch_id ? mayWrite : mayGovern;
          return (
            <Row key={rule.id} columns={COLUMNS}>
              <Cell>
                <Pill tone={rule.branch_id ? "info" : "ok"}>
                  {rule.branch_id ? "Niederlassung" : "Gruppe"}
                </Pill>
              </Cell>
              <TitleCell
                title={rule.title}
                meta={`${label.category(rule.category)} · ${label.controlType(rule.control_type)}${
                  rule.branch_name ? ` · ${rule.branch_name}` : ""
                }`}
              />
              <Cell title={rule.legal_basis}>{rule.legal_basis}</Cell>
              <Cell>{label.recurrence(rule.recurrence)}</Cell>
              <Cell className="ops-date" title={`Erster Termin: ${formatDate(rule.first_due_date)}`}>
                {rule.record_count}
                <span className="ops-cell__meta">
                  {rule.branch_ids.length === 1 ? "1 Niederlassung" : `${rule.branch_ids.length} Niederlassungen`}
                </span>
              </Cell>
              <ActionCell>
                {mayGovern && (
                  <button
                    type="button"
                    className="pds-icon-btn"
                    aria-label={`Geltung von ${rule.title} aendern`}
                    title="Geltungsbereich aendern"
                    onClick={() => setMoving(rule)}
                  >
                    <ArrowLeftRight size={14} />
                  </button>
                )}
                {editable && (
                  <>
                    <button
                      type="button"
                      className="pds-icon-btn"
                      aria-label={`${rule.title} bearbeiten`}
                      onClick={() => setEditing(rule)}
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      type="button"
                      className="pds-icon-btn pds-icon-btn--danger"
                      aria-label={`${rule.title} loeschen`}
                      onClick={() => setConfirm(rule)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </>
                )}
              </ActionCell>
            </Row>
          );
        })}
      </Table>

      {editing && (
        <RuleDialog
          rule={editing === "new" ? null : editing}
          branches={branches}
          branchId={branchId}
          mayGovern={mayGovern}
          onClose={() => setEditing(null)}
          onSaved={(message) => {
            setEditing(null);
            onToast(message);
            onReload();
          }}
        />
      )}

      {moving && (
        <ScopeDialog
          rule={moving}
          branches={branches}
          onClose={() => setMoving(null)}
          onSaved={() => {
            setMoving(null);
            onToast("Geltungsbereich geaendert");
            onReload();
          }}
        />
      )}

      <ConfirmDialog
        open={confirm !== null}
        title="Vorgabe entfernen"
        confirmLabel="Entfernen"
        busy={remove.busy}
        body={
          <p>
            <strong>{confirm?.title}</strong> wird als Vorgabe entfernt. Die {confirm?.record_count ?? 0}{" "}
            Compliance-Eintraege der Niederlassungen bleiben mit allen Nachweisen bestehen - sie
            stehen danach fuer sich.
          </p>
        }
        onCancel={() => setConfirm(null)}
        onConfirm={() => confirm && remove.run(() => apiDelete(`/api/compliance-rules/${confirm.id}`))}
      />
    </section>
  );
}

/* --------------------------------------------------------------------------
 * Create and edit
 * ----------------------------------------------------------------------- */

function RuleDialog({
  rule,
  branches,
  branchId,
  mayGovern,
  onClose,
  onSaved,
}: {
  rule: ComplianceRule | null;
  branches: Branch[];
  branchId: string | null;
  mayGovern: boolean;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const [dirty, setDirty] = React.useState(false);
  const { error, busy, run } = useSubmit(() =>
    onSaved(rule ? "Vorgabe gespeichert" : "Vorgabe angelegt")
  );
  const defaultScope = rule ? (rule.branch_id ?? "") : (branchId ?? branches[0]?.id ?? "");

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(form, async () => {
      const payload = {
        title: data.get("title"),
        category: data.get("category"),
        control_type: data.get("control_type"),
        recurrence: data.get("recurrence"),
        legal_basis: data.get("legal_basis"),
        priority: data.get("priority"),
        risk_if_missing: emptyToNull(data.get("risk_if_missing")),
        valid_from: emptyToNull(data.get("valid_from")),
      };
      if (rule) {
        await apiPatch(`/api/compliance-rules/${rule.id}`, payload);
      } else {
        await apiPost("/api/compliance-rules", {
          ...payload,
          branch_id: emptyToNull(data.get("branch_id")),
          first_due_date: data.get("first_due_date"),
        });
      }
    });
  }

  return (
    <Modal
      open
      title={rule ? `${rule.title} bearbeiten` : "Vorgabe anlegen"}
      subtitle={
        rule
          ? rule.branch_id
            ? "Gilt nur fuer diese Niederlassung"
            : "Gilt fuer alle Niederlassungen"
          : "Aus der Vorgabe entsteht je Niederlassung ein Compliance-Eintrag"
      }
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
            form="rule-form"
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gespeichert..." : "Speichern"}
          </button>
        </>
      }
    >
      <form id="rule-form" className="ops-dialog__body" onSubmit={submit} onChange={() => setDirty(true)}>
        <FormStatus error={error} busy={false} />

        <Fieldset legend="Pflicht">
          <div className="ops-grid">
            <Field label="Titel" span>
              <TextInput name="title" required minLength={3} defaultValue={rule?.title} />
            </Field>
            <Field label="Bereich">
              <Select name="category" defaultValue={rule?.category ?? "training_instruction"}>
                {options.category.map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Art der Kontrolle">
              <Select name="control_type" defaultValue={rule?.control_type ?? "training"}>
                {options.controlType.map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Turnus">
              <Select name="recurrence" defaultValue={rule?.recurrence ?? "yearly"}>
                {options.recurrence.map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Prioritaet">
              <Select name="priority" defaultValue={rule?.priority ?? "medium"}>
                {options.priority.map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Rechtsgrundlage" span>
              <TextInput
                name="legal_basis"
                required
                minLength={2}
                placeholder="z. B. DGUV Vorschrift 1 Paragraf 4"
                defaultValue={rule?.legal_basis}
              />
            </Field>
            <Field label="Risiko bei Nichterfuellung" span>
              <TextArea name="risk_if_missing" defaultValue={rule?.risk_if_missing ?? ""} />
            </Field>
          </div>
        </Fieldset>

        <Fieldset legend="Geltung">
          <div className="ops-grid">
            {!rule && (
              <Field label="Gilt fuer">
                <Select name="branch_id" defaultValue={defaultScope}>
                  {mayGovern && <option value="">alle Niederlassungen</option>}
                  {branches.map((branch) => (
                    <option key={branch.id} value={branch.id}>
                      nur {branch.name}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            {!rule && (
              <Field label="Erster Termin">
                <TextInput type="date" name="first_due_date" required />
              </Field>
            )}
            <Field label="Gilt ab (optional)">
              <TextInput type="date" name="valid_from" defaultValue={rule?.valid_from ?? ""} />
            </Field>
          </div>
          {!rule && (
            <p className="pds-meta">
              Der erste Termin gilt fuer die Eintraege, die jetzt entstehen. Jede Niederlassung kann
              ihren Termin danach selbst verschieben.
            </p>
          )}
        </Fieldset>
      </form>
    </Modal>
  );
}

/* --------------------------------------------------------------------------
 * Scope change
 * ----------------------------------------------------------------------- */

function ScopeDialog({
  rule,
  branches,
  onClose,
  onSaved,
}: {
  rule: ComplianceRule;
  branches: Branch[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [target, setTarget] = React.useState<string>(rule.branch_id ? "" : (branches[0]?.id ?? ""));
  const [preview, setPreview] = React.useState<ScopeChangePreview | null>(null);
  const [firstDue, setFirstDue] = React.useState("");
  const { error, busy, run } = useSubmit(onSaved);
  const apply = useAction(onSaved);

  // The preview is fetched on every change of the target: what the change does
  // is the whole question, and finding out afterwards is too late.
  React.useEffect(() => {
    let cancelled = false;
    apiPost<ScopeChangePreview>(`/api/compliance-rules/${rule.id}/scope-preview`, {
      branch_id: target || null,
    })
      .then((result) => {
        if (!cancelled) setPreview(result);
      })
      .catch(() => {
        if (!cancelled) setPreview(null);
      });
    return () => {
      cancelled = true;
    };
  }, [rule.id, target]);

  return (
    <Modal
      open
      size="lg"
      title="Geltungsbereich aendern"
      subtitle={rule.title}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
            Abbrechen
          </button>
          <span className="ops-spacer" />
          <button
            type="button"
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={apply.busy || busy}
            onClick={() =>
              apply.run(() =>
                apiPost(`/api/compliance-rules/${rule.id}/scope`, {
                  branch_id: target || null,
                  first_due_date: firstDue || null,
                  detach_dropped: true,
                })
              )
            }
          >
            {apply.busy ? "Wird uebernommen..." : "Uebernehmen"}
          </button>
        </>
      }
    >
      <div className="ops-dialog__body">
        <FormStatus error={apply.error ?? error} busy={false} />
        <div className="ops-grid">
          <Field label="Neue Geltung">
            <Select value={target} onChange={(event) => setTarget(event.target.value)}>
              <option value="">alle Niederlassungen</option>
              {branches.map((branch) => (
                <option key={branch.id} value={branch.id}>
                  nur {branch.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Erster Termin fuer neue Eintraege">
            <TextInput type="date" value={firstDue} onChange={(event) => setFirstDue(event.target.value)} />
          </Field>
        </div>

        {preview && (
          <dl className="ops-facts">
            <dt>Neu angelegt in</dt>
            <dd>{preview.creates_in.length ? preview.creates_in.join(", ") : "keiner Niederlassung"}</dd>
            <dt>Bleibt unveraendert in</dt>
            <dd>{preview.unchanged_in.length ? preview.unchanged_in.join(", ") : "-"}</dd>
            <dt>Wird herausgeloest in</dt>
            <dd>
              {preview.detaches_in.length ? preview.detaches_in.join(", ") : "keiner Niederlassung"}
            </dd>
          </dl>
        )}

        {preview && preview.detaches_in.length > 0 && (
          <div className="pds-banner pds-banner--warn">
            Die Eintraege in {preview.detaches_in.join(", ")} verschwinden nicht. Sie werden mit ihrer
            gesamten Historie zu eigenen Vorgaben dieser Niederlassungen - dort wird also weiter
            gearbeitet, nur nicht mehr auf Ansage der Gruppe.
          </div>
        )}
      </div>
    </Modal>
  );
}
