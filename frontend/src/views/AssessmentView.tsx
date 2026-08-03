import React from "react";
import { NotebookPen } from "lucide-react";
import { apiDelete, apiPost } from "../api";
import { can, type Assessment, type Bootstrap } from "../types";
import {
  Badge,
  DeleteButton,
  FormStatus,
  Panel,
  emptyToNull,
  formatDate,
  useAction,
  useSubmit,
} from "../components/ui";

export function AssessmentView({
  assessments,
  bootstrap,
  permissions,
  onSaved,
}: {
  assessments: Assessment[];
  bootstrap: Bootstrap;
  permissions: string[];
  onSaved: () => void;
}) {
  const latest = assessments[0];
  return (
    <div className="grid detailLayout">
      <section className="stack">
        {can(permissions, "assessment:write") && <AssessmentForm bootstrap={bootstrap} onSaved={onSaved} />}
        {assessments.length > 0 && (
          <Panel title="Erfasste Bestandsaufnahmen" icon={<NotebookPen size={18} />}>
            <AssessmentTable
              assessments={assessments}
              mayWrite={can(permissions, "assessment:write")}
              onReload={onSaved}
            />
          </Panel>
        )}
      </section>
      <aside className="detail">
        <div className="detailHeader">
          <Badge state={latest ? "green" : "yellow"}>{latest ? "erfasst" : "offen"}</Badge>
          <h2>{latest?.title || "Noch keine Bestandsaufnahme"}</h2>
          <p>{latest ? formatDate(latest.assessment_date) : ""}</p>
        </div>
        {latest ? (
          <AssessmentSummary assessment={latest} />
        ) : (
          <div className="empty">Bitte die erste Bestandsaufnahme erfassen.</div>
        )}
      </aside>
    </div>
  );
}

function AssessmentForm({ bootstrap, onSaved }: { bootstrap: Bootstrap; onSaved: () => void }) {
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
        management_ratings: {
          compliance: data.get("rating_compliance"),
          personal: data.get("rating_personal"),
          service: data.get("rating_service"),
          sales: data.get("rating_sales"),
          operations: data.get("rating_operations"),
        },
      });
    });
  }

  return (
    <form className="form" onSubmit={submit}>
      <h2>Bestandsaufnahme erfassen</h2>
      <div className="formGrid">
        <input name="title" placeholder="Titel" defaultValue="Bestandsaufnahme Remscheid" required minLength={3} />
        <label>
          Datum
          <input name="assessment_date" type="date" defaultValue={new Date().toISOString().slice(0, 10)} required />
        </label>
      </div>
      <textarea name="team_structure" placeholder="Teamstruktur, Rollen, Verantwortliche" />
      <textarea name="customer_clusters" placeholder="Kundencluster und wichtige Accounts" />
      <textarea name="service_portfolio" placeholder="Leistungsportfolio" />
      <textarea name="project_types" placeholder="Projektarten und typische Baustellen" />
      <input name="service_share" placeholder="Service-/Wartungsanteil" />
      <textarea name="main_problems" placeholder="Aktuelle Hauptprobleme" />
      <div className="formGrid">
        {["compliance", "personal", "service", "sales", "operations"].map((key) => (
          <label key={key}>
            {key}
            <select name={`rating_${key}`} defaultValue="yellow">
              <option value="green">gruen</option>
              <option value="yellow">gelb</option>
              <option value="red">rot</option>
            </select>
          </label>
        ))}
      </div>
      <textarea name="next_actions_text" placeholder="Massnahmen, eine pro Zeile" />
      <textarea name="notes" placeholder="Bestandsaufnahme-Text / erzeugte Notizen" />
      <FormStatus error={error} busy={busy} />
      <button disabled={busy}>Bestandsaufnahme speichern</button>
    </form>
  );
}

function AssessmentTable({
  assessments,
  mayWrite,
  onReload,
}: {
  assessments: Assessment[];
  mayWrite: boolean;
  onReload: () => void;
}) {
  const remove = useAction(onReload);
  return (
    <>
      <FormStatus error={remove.error} busy={remove.busy} busyLabel="Wird geloescht..." />
      <table>
        <thead>
          <tr>
            <th>Datum</th>
            <th>Titel</th>
            <th>Personal</th>
            {mayWrite && <th />}
          </tr>
        </thead>
        <tbody>
          {assessments.map((item) => (
            <tr key={item.id}>
              <td>{formatDate(item.assessment_date)}</td>
              <td>
                <strong>{item.title}</strong>
                <span>{item.main_problems || "-"}</span>
              </td>
              <td>
                <Badge state={item.management_ratings?.personal || "yellow"}>
                  {item.management_ratings?.personal || "offen"}
                </Badge>
              </td>
              {mayWrite && (
                <td>
                  <DeleteButton
                    label="Loeschen"
                    confirmText={`Bestandsaufnahme "${item.title}" loeschen?`}
                    onConfirm={() => remove.run(() => apiDelete(`/api/branch-assessments/${item.id}`))}
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

export function AssessmentSummary({ assessment }: { assessment: Assessment }) {
  return (
    <div className="stack">
      <dl>
        <dt>Team</dt>
        <dd>{assessment.team_structure || "-"}</dd>
        <dt>Kunden</dt>
        <dd>{assessment.customer_clusters || "-"}</dd>
        <dt>Portfolio</dt>
        <dd>{assessment.service_portfolio || "-"}</dd>
        <dt>Probleme</dt>
        <dd>{assessment.main_problems || "-"}</dd>
      </dl>
      <h3>Ampeln</h3>
      <div className="chips">
        {Object.entries(assessment.management_ratings || {}).map(([key, value]) => (
          <span key={key}>
            {key}: {value}
          </span>
        ))}
      </div>
    </div>
  );
}
