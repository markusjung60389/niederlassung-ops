import React from "react";
import { Download, FileUp, Plus, Sparkles, Trash2, TriangleAlert } from "lucide-react";
import { apiDelete, apiGet, apiPatch, apiPost, apiUpload, downloadFile } from "../api";
import { label, options } from "../labels";
import {
  can,
  type Action,
  type AgentRun,
  type Bootstrap,
  type ComplianceTemplate,
  type Evidence,
  type RecordItem,
} from "../types";
import { ActionCell, Cell, Row, Table, TitleCell } from "../components/Table";
import { ConfirmDialog, Modal } from "../components/Modal";
import {
  DueDate,
  EmptyState,
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
  formatBytes,
  formatDate,
  toneOf,
  useAction,
  useSubmit,
} from "../components/ui";

const RECORD_COLUMNS = "104px minmax(0,2fr) minmax(0,1fr) 96px 110px 92px";
const ACTION_COLUMNS = "104px minmax(0,2fr) minmax(0,1.2fr) 110px 130px";
type Filter = "open" | "overdue" | "all";

export function ComplianceView({
  records,
  actions,
  bootstrap,
  permissions,
  onReload,
  onToast,
}: {
  records: RecordItem[];
  actions: Action[];
  bootstrap: Bootstrap;
  permissions: string[];
  onReload: () => void;
  onToast: (message: string) => void;
}) {
  const mayWrite = can(permissions, "compliance:write");
  const [filter, setFilter] = React.useState<Filter>("open");
  const [search, setSearch] = React.useState("");
  const [category, setCategory] = React.useState("");
  const [creating, setCreating] = React.useState(false);
  const [detail, setDetail] = React.useState<string | null>(null);
  const [confirm, setConfirm] = React.useState<RecordItem | null>(null);
  const remove = useAction(() => {
    setConfirm(null);
    onToast("Thema geloescht");
    onReload();
  });

  const isOpen = (record: RecordItem) => record.status !== "compliant" && record.status !== "waived";
  const counts = {
    open: records.filter(isOpen).length,
    overdue: records.filter((record) => record.due_state === "red").length,
    all: records.length,
  };

  const visible = records
    .filter((record) => {
      if (filter === "open") return isOpen(record);
      if (filter === "overdue") return record.due_state === "red";
      return true;
    })
    .filter((record) => !category || record.category === category)
    .filter((record) => {
      const needle = search.trim().toLowerCase();
      if (!needle) return true;
      return `${record.title} ${record.legal_basis}`.toLowerCase().includes(needle);
    });

  const selected = records.find((record) => record.id === detail) ?? null;
  const openActions = actions.filter((action) => action.status !== "done" && action.status !== "cancelled");

  return (
    <section className="ops-stack">
      <div className="ops-row ops-row--between">
        <Segments<Filter>
          value={filter}
          onChange={setFilter}
          options={[
            { key: "open", label: "Offen", count: counts.open },
            { key: "overdue", label: "Ueberfaellig", count: counts.overdue },
            { key: "all", label: "Alle", count: counts.all },
          ]}
        />
        <div className="ops-row ops-spacer">
          <SearchField value={search} onChange={setSearch} placeholder="Titel oder Rechtsgrundlage" />
          {mayWrite && (
            <button
              type="button"
              className="pds-btn pds-btn--primary pds-btn--sm"
              onClick={() => setCreating(true)}
            >
              <Plus size={15} /> Thema
            </button>
          )}
        </div>
      </div>

      <div className="ops-row">
        <button
          type="button"
          className={`pds-chip${category === "" ? " is-active" : ""}`}
          onClick={() => setCategory("")}
        >
          Alle Kategorien
        </button>
        {options.category.map(([value, text]) => {
          const count = records.filter((record) => record.category === value).length;
          if (!count) return null;
          return (
            <button
              key={value}
              type="button"
              className={`pds-chip${category === value ? " is-active" : ""}`}
              onClick={() => setCategory(category === value ? "" : value)}
            >
              {text} &middot; {count}
            </button>
          );
        })}
      </div>

      <FormStatus error={remove.error} busy={remove.busy} busyLabel="Wird geloescht..." />

      <Table
        columns={RECORD_COLUMNS}
        head={["Status", "Thema", "Kategorie", "Nachweise", "Faellig", ""]}
        empty={search || category ? "Kein Treffer." : "Noch keine Compliance-Themen erfasst."}
      >
        {visible.map((record) => (
          <Row
            key={record.id}
            columns={RECORD_COLUMNS}
            onOpen={() => setDetail(record.id)}
            title="Details oeffnen"
          >
            <Cell>
              <Pill tone={toneOf(record.due_state)}>{label.status(record.status)}</Pill>
            </Cell>
            <TitleCell title={record.title} meta={record.legal_basis} />
            <Cell>
              <span className="pds-meta">{label.category(record.category)}</span>
            </Cell>
            <Cell>
              <span className={`ops-date${record.evidence.length ? "" : " is-yellow"}`}>
                {record.evidence.length}
              </span>
            </Cell>
            <Cell>
              <DueDate value={record.due_date} />
            </Cell>
            <ActionCell>
              {mayWrite && (
                <button
                  type="button"
                  className="pds-icon-btn pds-icon-btn--danger"
                  aria-label={`${record.title} loeschen`}
                  onClick={() => setConfirm(record)}
                >
                  <Trash2 size={14} />
                </button>
              )}
            </ActionCell>
          </Row>
        ))}
      </Table>

      <Section title="Offene Massnahmen" flush>
        <ActionTable actions={openActions} records={records} mayWrite={mayWrite} onReload={onReload} />
      </Section>

      {creating && (
        <CreateRecordDialog
          bootstrap={bootstrap}
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            onToast("Thema angelegt");
            onReload();
          }}
        />
      )}

      {selected && (
        <RecordDetail
          record={selected}
          permissions={permissions}
          onClose={() => setDetail(null)}
          onChanged={(message) => {
            onToast(message);
            onReload();
          }}
        />
      )}

      <ConfirmDialog
        open={confirm !== null}
        title="Compliance-Thema loeschen"
        busy={remove.busy}
        body={
          <p>
            <strong>{confirm?.title}</strong> wird mit {confirm?.evidence.length ?? 0} Nachweis(en)
            und {confirm?.actions.length ?? 0} Massnahme(n) entfernt.
          </p>
        }
        onCancel={() => setConfirm(null)}
        onConfirm={() =>
          confirm && remove.run(() => apiDelete(`/api/compliance-records/${confirm.id}`))
        }
      />
    </section>
  );
}

/* --------------------------------------------------------------------------
 * Create, from a template or from scratch
 * ----------------------------------------------------------------------- */

function CreateRecordDialog({
  bootstrap,
  onClose,
  onSaved,
}: {
  bootstrap: Bootstrap;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [templates, setTemplates] = React.useState<ComplianceTemplate[]>([]);
  const [picked, setPicked] = React.useState<ComplianceTemplate | null>(null);
  const [step, setStep] = React.useState<"pick" | "form">("pick");
  const { error, busy, run } = useSubmit(onSaved);
  const branchId = bootstrap.branches[0]?.id;
  const ownerId = bootstrap.users[0]?.id;

  React.useEffect(() => {
    apiGet<ComplianceTemplate[]>("/api/compliance-templates")
      .then(setTemplates)
      .catch(() => setTemplates([]));
  }, []);

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
        recurrence: data.get("recurrence"),
        legal_basis: data.get("legal_basis"),
        due_date: data.get("due_date"),
        review_date: data.get("review_date") || data.get("due_date"),
        risk_if_missing: emptyToNull(data.get("risk_if_missing")),
        branch_id: branchId,
        owner_user_id: ownerId,
        tags: [],
        scope_type: "branch",
      });
    });
  }

  if (step === "pick") {
    return (
      <Modal
        open
        size="lg"
        title="Compliance-Thema anlegen"
        subtitle="Aus dem Katalog der Standardpflichten waehlen - oder frei erfassen."
        onClose={onClose}
        footer={
          <>
            <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
              Abbrechen
            </button>
            <span className="ops-spacer" />
            <button
              type="button"
              className="pds-btn pds-btn--outline pds-btn--sm"
              onClick={() => {
                setPicked(null);
                setStep("form");
              }}
            >
              Frei erfassen
            </button>
          </>
        }
      >
        <div className="ops-dialog__body">
          {templates.length === 0 && <EmptyState>Katalog wird geladen...</EmptyState>}
          {templates.map((template) => (
            <button
              key={template.key}
              type="button"
              className="pds-selection-card"
              style={{ textAlign: "left", cursor: "pointer", width: "100%" }}
              onClick={() => {
                setPicked(template);
                setStep("form");
              }}
            >
              <span style={{ minWidth: 0, display: "block" }}>
                <span className="ops-cell__title">{template.title}</span>
                <span className="ops-cell__meta">
                  {template.legal_basis} &middot; {label.recurrence(template.recurrence)} &middot;{" "}
                  {label.category(template.category)}
                </span>
              </span>
            </button>
          ))}
        </div>
      </Modal>
    );
  }

  const today = new Date();
  const defaultDue = new Date(today.getFullYear(), today.getMonth() + 1, today.getDate())
    .toISOString()
    .slice(0, 10);

  return (
    <Modal
      open
      title={picked ? picked.title : "Thema frei erfassen"}
      subtitle={picked ? "Aus Vorlage - alle Felder bleiben aenderbar." : undefined}
      onClose={onClose}
      footer={
        <>
          <button
            type="button"
            className="pds-btn pds-btn--outline pds-btn--sm"
            onClick={() => setStep("pick")}
          >
            Zurueck
          </button>
          <span className="ops-spacer" />
          <button
            type="submit"
            form="record-form"
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gespeichert..." : "Anlegen"}
          </button>
        </>
      }
    >
      <form id="record-form" className="ops-dialog__body" onSubmit={submit}>
        <FormStatus error={error} busy={false} />

        <Fieldset legend="Thema">
          <Field label="Titel" span>
            <TextInput name="title" required minLength={3} defaultValue={picked?.title ?? ""} />
          </Field>
          <Field label="Rechtsgrundlage" span>
            <TextInput
              name="legal_basis"
              required
              minLength={2}
              defaultValue={picked?.legal_basis ?? ""}
            />
          </Field>
          <div className="ops-grid">
            <Field label="Kategorie">
              <Select name="category" defaultValue={picked?.category ?? "training_instruction"}>
                {options.category.map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Art der Kontrolle">
              <Select name="control_type" defaultValue={picked?.control_type ?? "training"}>
                {options.controlType.map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Prioritaet">
              <Select name="priority" defaultValue={picked?.priority ?? "high"}>
                {options.priority.map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Status">
              <Select name="status" defaultValue="open">
                {options.status.map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Wiederholung">
              <Select name="recurrence" defaultValue={picked?.recurrence ?? "yearly"}>
                {options.recurrence.map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Faellig">
              <TextInput type="date" name="due_date" required defaultValue={defaultDue} />
            </Field>
          </div>
        </Fieldset>

        <Fieldset legend="Risiko">
          <Field label="Was passiert, wenn der Nachweis fehlt" span>
            <TextArea name="risk_if_missing" defaultValue={picked?.risk_if_missing ?? ""} />
          </Field>
        </Fieldset>
      </form>
    </Modal>
  );
}

/* --------------------------------------------------------------------------
 * Detail: evidence, actions and review together
 * ----------------------------------------------------------------------- */

function RecordDetail({
  record,
  permissions,
  onClose,
  onChanged,
}: {
  record: RecordItem;
  permissions: string[];
  onClose: () => void;
  onChanged: (message: string) => void;
}) {
  const mayWrite = can(permissions, "compliance:write");
  const mayRunAgent = can(permissions, "agent:run");

  return (
    <Modal
      open
      size="lg"
      title={record.title}
      subtitle={`${label.category(record.category)} · ${record.legal_basis}`}
      onClose={onClose}
      footer={
        <>
          <Pill tone={toneOf(record.due_state)}>{label.status(record.status)}</Pill>
          <span className="pds-meta">faellig {formatDate(record.due_date)}</span>
          <span className="ops-spacer" />
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
            Schliessen
          </button>
        </>
      }
    >
      <div className="ops-dialog__body">
        {record.evidence.length === 0 && (
          <div className="pds-banner pds-banner--warn">
            <TriangleAlert size={15} />
            Kein Nachweis hinterlegt &ndash; bei einer Besichtigung ist der Punkt damit nicht
            belegbar.
          </div>
        )}

        <dl className="ops-facts">
          <dt>Prioritaet</dt>
          <dd>{label.priority(record.priority)}</dd>
          <dt>Art der Kontrolle</dt>
          <dd>{label.controlType(record.control_type)}</dd>
          <dt>Wiederholung</dt>
          <dd>{label.recurrence(record.recurrence)}</dd>
          <dt>Review</dt>
          <dd>{formatDate(record.review_date)}</dd>
          <dt>Risiko</dt>
          <dd>{record.risk_if_missing || "-"}</dd>
        </dl>

        <EvidenceList evidence={record.evidence} mayWrite={mayWrite} onChanged={onChanged} />
        {mayWrite && <EvidenceUploadForm recordId={record.id} onUploaded={() => onChanged("Nachweis hochgeladen")} />}

        <RecordActions record={record} mayWrite={mayWrite} onChanged={onChanged} />

        {mayRunAgent && <AgentReview recordId={record.id} />}
      </div>
    </Modal>
  );
}

const EVIDENCE_COLUMNS = "minmax(0,1.8fr) 110px 90px 140px";

function EvidenceList({
  evidence,
  mayWrite,
  onChanged,
}: {
  evidence: Evidence[];
  mayWrite: boolean;
  onChanged: (message: string) => void;
}) {
  const remove = useAction(() => onChanged("Nachweis geloescht"));
  const [downloadError, setDownloadError] = React.useState<string | null>(null);

  return (
    <div>
      <h3 className="pds-label pds-label--micro" style={{ marginBottom: 8 }}>
        Nachweise
      </h3>
      <FormStatus
        error={remove.error || downloadError}
        busy={remove.busy}
        busyLabel="Wird geloescht..."
      />
      <Table
        columns={EVIDENCE_COLUMNS}
        minWidth={560}
        head={["Datei", "Art", "Groesse", ""]}
        empty="Noch keine Nachweise hochgeladen."
      >
        {evidence.map((item) => (
          <Row key={item.id} columns={EVIDENCE_COLUMNS}>
            <TitleCell title={item.file_name} meta={item.description || formatDate(item.uploaded_at)} />
            <Cell>
              <span className="pds-meta">{item.evidence_type}</span>
            </Cell>
            <Cell>
              <span className="ops-date">{formatBytes(item.file_size_bytes)}</span>
            </Cell>
            <ActionCell>
              <button
                type="button"
                className="pds-btn pds-btn--outline pds-btn--sm"
                onClick={() =>
                  downloadFile(`/api/evidence/${item.id}/download`, item.file_name).catch((caught) =>
                    setDownloadError(caught instanceof Error ? caught.message : "Download fehlgeschlagen")
                  )
                }
              >
                <Download size={14} /> Laden
              </button>
              {mayWrite && (
                <button
                  type="button"
                  className="pds-icon-btn pds-icon-btn--danger"
                  aria-label={`${item.file_name} loeschen`}
                  onClick={() => remove.run(() => apiDelete(`/api/evidence/${item.id}`))}
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

function EvidenceUploadForm({ recordId, onUploaded }: { recordId: string; onUploaded: () => void }) {
  const { error, busy, run } = useSubmit(onUploaded);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(form, async () => {
      const file = data.get("file");
      if (!(file instanceof File) || file.size === 0) throw new Error("Bitte eine Datei auswaehlen.");
      const upload = new FormData();
      upload.append("file", file);
      upload.append("evidence_type", String(data.get("evidence_type") || "other"));
      const description = emptyToNull(data.get("description"));
      if (description) upload.append("description", description);
      const validUntil = emptyToNull(data.get("valid_until"));
      if (validUntil) upload.append("valid_until", validUntil);
      await apiUpload(`/api/compliance-records/${recordId}/evidence`, upload);
    });
  }

  return (
    <form onSubmit={submit} style={{ display: "grid", gap: 10 }}>
      <div className="ops-grid ops-grid--three">
        <Field label="Datei">
          <TextInput type="file" name="file" required />
        </Field>
        <Field label="Art">
          <Select name="evidence_type" defaultValue="certificate">
            <option value="certificate">Zertifikat</option>
            <option value="protocol">Protokoll</option>
            <option value="photo">Foto</option>
            <option value="other">Sonstiges</option>
          </Select>
        </Field>
        <Field label="Gueltig bis">
          <TextInput type="date" name="valid_until" />
        </Field>
      </div>
      <Field label="Beschreibung">
        <TextInput name="description" />
      </Field>
      <FormStatus error={error} busy={busy} busyLabel="Wird hochgeladen..." />
      <div>
        <button type="submit" className="pds-btn pds-btn--outline pds-btn--sm" disabled={busy}>
          <FileUp size={14} /> Nachweis hochladen
        </button>
      </div>
    </form>
  );
}

/** Actions belonging to this record - shown where they arose. */
function RecordActions({
  record,
  mayWrite,
  onChanged,
}: {
  record: RecordItem;
  mayWrite: boolean;
  onChanged: (message: string) => void;
}) {
  const update = useAction(() => onChanged("Massnahme aktualisiert"));
  const columns = "104px minmax(0,2fr) 110px 120px";

  return (
    <div>
      <h3 className="pds-label pds-label--micro" style={{ marginBottom: 8 }}>
        Massnahmen zu diesem Thema
      </h3>
      <FormStatus error={update.error} busy={update.busy} busyLabel="Wird aktualisiert..." />
      <Table
        columns={columns}
        minWidth={520}
        head={["Status", "Massnahme", "Faellig", ""]}
        empty="Keine Massnahmen erfasst."
      >
        {record.actions.map((action) => (
          <Row key={action.id} columns={columns}>
            <Cell>
              <Pill tone={toneOf(action.due_state)}>{label.status(action.status)}</Pill>
            </Cell>
            <TitleCell title={action.title} meta={label.priority(action.priority)} />
            <Cell>
              <DueDate value={action.due_date} />
            </Cell>
            <ActionCell>
              {mayWrite && action.status !== "done" && (
                <button
                  type="button"
                  className="pds-btn pds-btn--outline pds-btn--sm"
                  disabled={update.busy}
                  onClick={() => update.run(() => apiPatch(`/api/actions/${action.id}`, { status: "done" }))}
                >
                  Erledigt
                </button>
              )}
            </ActionCell>
          </Row>
        ))}
      </Table>
    </div>
  );
}

function AgentReview({ recordId }: { recordId: string }) {
  const [runs, setRuns] = React.useState<AgentRun[]>([]);
  const load = React.useCallback(async () => {
    setRuns(await apiGet<AgentRun[]>(`/api/agent/runs?source_entity_id=${recordId}`));
  }, [recordId]);
  const { error, busy, run } = useAction(load);

  React.useEffect(() => {
    load().catch(() => setRuns([]));
  }, [load]);

  const latest = runs[0];

  return (
    <div>
      <h3 className="pds-label pds-label--micro" style={{ marginBottom: 8 }}>
        Hermes-Review
      </h3>
      <FormStatus error={error} busy={busy} busyLabel="Review laeuft..." />
      <button
        type="button"
        className="pds-btn pds-btn--outline pds-btn--sm"
        disabled={busy}
        onClick={() => run(() => apiPost("/api/agent/compliance-review", { compliance_record_id: recordId }))}
      >
        <Sparkles size={14} /> Review starten
      </button>
      {latest && (
        <div style={{ marginTop: 10 }}>
          <div className="ops-row">
            <Pill tone={latest.status === "completed" ? "ok" : "danger"}>{latest.status}</Pill>
            <span className="pds-meta">{formatDate(latest.created_at)}</span>
          </div>
          <pre className="ops-code" style={{ marginTop: 8 }}>
            {JSON.stringify(latest.response_payload, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

/** All open actions across records, as a follow-up list. */
function ActionTable({
  actions,
  records,
  mayWrite,
  onReload,
}: {
  actions: Action[];
  records: RecordItem[];
  mayWrite: boolean;
  onReload: () => void;
}) {
  const update = useAction(onReload);

  return (
    <>
      <FormStatus error={update.error} busy={update.busy} busyLabel="Wird aktualisiert..." />
      <Table
        columns={ACTION_COLUMNS}
        head={["Status", "Massnahme", "Thema", "Faellig", ""]}
        empty="Keine offenen Massnahmen."
      >
        {actions.map((action) => (
          <Row key={action.id} columns={ACTION_COLUMNS}>
            <Cell>
              <Pill tone={toneOf(action.due_state)}>{label.status(action.status)}</Pill>
            </Cell>
            <TitleCell title={action.title} meta={label.priority(action.priority)} />
            <Cell>
              <span className="pds-meta">
                {records.find((record) => record.id === action.compliance_record_id)?.title ?? "-"}
              </span>
            </Cell>
            <Cell>
              <DueDate value={action.due_date} />
            </Cell>
            <ActionCell>
              {mayWrite && (
                <>
                  <button
                    type="button"
                    className="pds-btn pds-btn--outline pds-btn--sm"
                    disabled={update.busy}
                    onClick={() => update.run(() => apiPatch(`/api/actions/${action.id}`, { status: "done" }))}
                  >
                    Erledigt
                  </button>
                  <button
                    type="button"
                    className="pds-icon-btn pds-icon-btn--danger"
                    aria-label={`${action.title} loeschen`}
                    onClick={() => update.run(() => apiDelete(`/api/actions/${action.id}`))}
                  >
                    <Trash2 size={14} />
                  </button>
                </>
              )}
            </ActionCell>
          </Row>
        ))}
      </Table>
    </>
  );
}
