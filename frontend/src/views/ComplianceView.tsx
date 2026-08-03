import React from "react";
import { AlertTriangle, ClipboardCheck, Download, FileUp, Sparkles } from "lucide-react";
import { apiDelete, apiGet, apiPatch, apiPost, apiUpload, downloadFile } from "../api";
import {
  can,
  type Action,
  type AgentRun,
  type Bootstrap,
  type Evidence,
  type RecordItem,
} from "../types";
import {
  Badge,
  DeleteButton,
  FormStatus,
  Panel,
  emptyToNull,
  formatBytes,
  formatDate,
  useAction,
  useSubmit,
} from "../components/ui";

export function ComplianceView({
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
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const selected = records.find((record) => record.id === selectedId) ?? records[0] ?? null;

  return (
    <section className="stack">
      {can(permissions, "compliance:write") && <CreateRecordForm bootstrap={bootstrap} onCreated={onReload} />}

      <Panel title="Compliance-Records" icon={<ClipboardCheck size={18} />}>
        <RecordTable records={records} selectedId={selected?.id ?? null} onSelect={setSelectedId} />
      </Panel>

      {selected && (
        <RecordDetail record={selected} permissions={permissions} onReload={onReload} />
      )}

      <Panel title="Massnahmen" icon={<AlertTriangle size={18} />}>
        <ActionTable actions={actions} records={records} permissions={permissions} onReload={onReload} />
      </Panel>
    </section>
  );
}

function RecordTable({
  records,
  selectedId,
  onSelect,
}: {
  records: RecordItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (!records.length) return <div className="empty">Keine Eintraege erfasst.</div>;
  return (
    <table>
      <thead>
        <tr>
          <th>Status</th>
          <th>Titel</th>
          <th>Nachweise</th>
          <th>Faellig</th>
        </tr>
      </thead>
      <tbody>
        {records.map((record) => (
          <tr
            key={record.id}
            className={record.id === selectedId ? "selectable active" : "selectable"}
            onClick={() => onSelect(record.id)}
          >
            <td>
              <Badge state={record.due_state}>{record.priority}</Badge>
            </td>
            <td>
              <strong>{record.title}</strong>
              <span>
                {record.category} / {record.status}
              </span>
            </td>
            <td>{record.evidence.length}</td>
            <td>{formatDate(record.due_date)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RecordDetail({
  record,
  permissions,
  onReload,
}: {
  record: RecordItem;
  permissions: string[];
  onReload: () => void;
}) {
  const mayWrite = can(permissions, "compliance:write");
  const mayRunAgent = can(permissions, "agent:run");
  const remove = useAction(onReload);

  return (
    <Panel
      title={record.title}
      icon={<ClipboardCheck size={18} />}
      actions={
        mayWrite ? (
          <DeleteButton
            label="Record loeschen"
            confirmText={`"${record.title}" mit allen Nachweisen und Massnahmen loeschen?`}
            onConfirm={() => remove.run(() => apiDelete(`/api/compliance-records/${record.id}`))}
          />
        ) : undefined
      }
    >
      <FormStatus error={remove.error} busy={remove.busy} busyLabel="Wird geloescht..." />
      <dl>
        <dt>Rechtsgrundlage</dt>
        <dd>{record.legal_basis}</dd>
        <dt>Wiederholung</dt>
        <dd>{(record as RecordItem & { recurrence?: string }).recurrence || "-"}</dd>
        <dt>Risiko</dt>
        <dd>{record.risk_if_missing || "-"}</dd>
      </dl>

      <h3>Nachweise</h3>
      <EvidenceList evidence={record.evidence} mayWrite={mayWrite} onReload={onReload} />
      {mayWrite && <EvidenceUploadForm recordId={record.id} onUploaded={onReload} />}

      {mayRunAgent && <AgentReview recordId={record.id} />}
    </Panel>
  );
}

function EvidenceList({
  evidence,
  mayWrite,
  onReload,
}: {
  evidence: Evidence[];
  mayWrite: boolean;
  onReload: () => void;
}) {
  const remove = useAction(onReload);
  const [downloadError, setDownloadError] = React.useState<string | null>(null);

  if (!evidence.length) return <div className="empty">Noch keine Nachweise hochgeladen.</div>;
  return (
    <>
      <FormStatus error={remove.error || downloadError} busy={remove.busy} busyLabel="Wird geloescht..." />
      <table>
        <thead>
          <tr>
            <th>Datei</th>
            <th>Art</th>
            <th>Groesse</th>
            <th>Gueltig bis</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {evidence.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.file_name}</strong>
                <span>{item.description || formatDate(item.uploaded_at)}</span>
              </td>
              <td>{item.evidence_type}</td>
              <td>{formatBytes(item.file_size_bytes)}</td>
              <td>{formatDate((item as Evidence & { valid_until?: string | null }).valid_until)}</td>
              <td className="rowActions">
                <button
                  type="button"
                  onClick={() =>
                    downloadFile(`/api/evidence/${item.id}/download`, item.file_name).catch((caught) =>
                      setDownloadError(caught instanceof Error ? caught.message : "Download fehlgeschlagen")
                    )
                  }
                >
                  <Download size={14} /> Laden
                </button>
                {mayWrite && (
                  <DeleteButton
                    label="Loeschen"
                    confirmText={`Nachweis "${item.file_name}" loeschen?`}
                    onConfirm={() => remove.run(() => apiDelete(`/api/evidence/${item.id}`))}
                  />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
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
    <form className="form inline" onSubmit={submit}>
      <h3>
        <FileUp size={16} /> Nachweis hochladen
      </h3>
      <div className="formGrid">
        <input name="file" type="file" required />
        <select name="evidence_type" defaultValue="certificate">
          <option value="certificate">Zertifikat</option>
          <option value="protocol">Protokoll</option>
          <option value="photo">Foto</option>
          <option value="other">Sonstiges</option>
        </select>
        <label>
          Gueltig bis
          <input name="valid_until" type="date" />
        </label>
      </div>
      <input name="description" placeholder="Beschreibung" />
      <FormStatus error={error} busy={busy} busyLabel="Wird hochgeladen..." />
      <button disabled={busy}>Hochladen</button>
    </form>
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
    <div className="stack">
      <h3>
        <Sparkles size={16} /> Hermes-Review
      </h3>
      <FormStatus error={error} busy={busy} busyLabel="Review laeuft..." />
      <button
        type="button"
        disabled={busy}
        onClick={() => run(() => apiPost("/api/agent/compliance-review", { compliance_record_id: recordId }))}
      >
        Review starten
      </button>
      {latest ? (
        <div className="agentRun">
          <Badge state={latest.status === "completed" ? "green" : "red"}>{latest.status}</Badge>
          <span>{formatDate(latest.created_at)}</span>
          <pre>{JSON.stringify(latest.response_payload, null, 2)}</pre>
        </div>
      ) : (
        <div className="empty">Noch kein Review durchgefuehrt.</div>
      )}
    </div>
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
        recurrence: data.get("recurrence"),
        legal_basis: data.get("legal_basis"),
        due_date: data.get("due_date"),
        review_date: data.get("review_date"),
        risk_if_missing: emptyToNull(data.get("risk_if_missing")),
        branch_id: branchId,
        owner_user_id: ownerId,
        tags: [],
        scope_type: "branch",
      });
    });
  }

  return (
    <form className="form" onSubmit={submit}>
      <h2>Compliance-Thema erfassen</h2>
      <input name="title" placeholder="Titel" required minLength={3} />
      <div className="formGrid">
        <select name="category" defaultValue="training_instruction">
          <option value="training_instruction">Unterweisung</option>
          <option value="risk_assessment">Gefaehrdungsbeurteilung</option>
          <option value="tools_and_equipment_inspection">DGUV / Arbeitsmittel</option>
          <option value="first_aid">Erste Hilfe</option>
          <option value="occupational_health">Arbeitsmedizin</option>
          <option value="electrical_safety">Elektrosicherheit</option>
          <option value="documentation">Dokumentation</option>
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
        <label>
          Wiederholung
          <select name="recurrence" defaultValue="yearly">
            <option value="one_time">einmalig</option>
            <option value="monthly">monatlich</option>
            <option value="quarterly">quartalsweise</option>
            <option value="yearly">jaehrlich</option>
            <option value="event_based">anlassbezogen</option>
          </select>
        </label>
      </div>
      <input name="legal_basis" placeholder="Rechtsgrundlage" required minLength={2} />
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

function ActionTable({
  actions,
  records,
  permissions,
  onReload,
}: {
  actions: Action[];
  records: RecordItem[];
  permissions: string[];
  onReload: () => void;
}) {
  const update = useAction(onReload);
  const mayWrite = can(permissions, "compliance:write");

  if (!actions.length) return <div className="empty">Keine offenen Massnahmen erfasst.</div>;
  return (
    <>
      <FormStatus error={update.error} busy={update.busy} busyLabel="Wird aktualisiert..." />
      <table>
        <thead>
          <tr>
            <th>Status</th>
            <th>Massnahme</th>
            <th>Record</th>
            <th>Eskalation</th>
            <th>Faellig</th>
            {mayWrite && <th />}
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
              <td>{(action as Action & { escalation_level?: number }).escalation_level ?? 0}</td>
              <td>{formatDate(action.due_date)}</td>
              {mayWrite && (
                <td className="rowActions">
                  {action.status !== "done" && (
                    <button
                      type="button"
                      disabled={update.busy}
                      onClick={() =>
                        update.run(async () => {
                          await apiPatch(`/api/actions/${action.id}`, { status: "done" });
                        })
                      }
                    >
                      Erledigt
                    </button>
                  )}
                  <DeleteButton
                    label="Loeschen"
                    confirmText={`Massnahme "${action.title}" loeschen?`}
                    onConfirm={() => update.run(() => apiDelete(`/api/actions/${action.id}`))}
                  />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
