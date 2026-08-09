import React from "react";
import { Check, ExternalLink, Undo2 } from "lucide-react";
import { apiPost } from "../api";
import {
  can,
  type Branch,
  type PortfolioRow,
  type RequirementOverride,
} from "../types";
import { ActionCell, Cell, Row, Table, TitleCell } from "../components/Table";
import { Modal } from "../components/Modal";
import {
  Field,
  FormStatus,
  Pill,
  Section,
  Segments,
  TextArea,
  TextInput,
  emptyToNull,
  formatDate,
  toneOf,
  useAction,
  useSubmit,
} from "../components/ui";

/**
 * The area manager's two screens.
 *
 * The branch manager never opens this: it answers the one question the branch
 * views cannot, namely how the branches compare, and it shows the exceptions
 * that were taken locally. Those exceptions are the price of letting a branch
 * decide for itself - they only work while somebody above sees them.
 */

const BRANCH_COLUMNS = "104px minmax(0,1.3fr) 88px 152px 108px 104px 104px 44px";
const EXCEPTION_COLUMNS = "minmax(0,1fr) minmax(0,1.2fr) 116px minmax(0,1.5fr) 108px 88px";

type Tab = "open" | "new" | "revoked";

export function PortfolioView({
  rows,
  overrides,
  branches,
  permissions,
  onOpenBranch,
  onReload,
  onToast,
}: {
  rows: PortfolioRow[];
  overrides: RequirementOverride[];
  branches: Branch[];
  permissions: string[];
  onOpenBranch: (branch: Branch) => void;
  onReload: () => void;
  onToast: (message: string) => void;
}) {
  const mayGovern = can(permissions, "rule:write");
  const [tab, setTab] = React.useState<Tab>("open");
  const [revoking, setRevoking] = React.useState<RequirementOverride | null>(null);
  const acknowledge = useAction(() => {
    onToast("Als gesehen markiert");
    onReload();
  });

  const isNew = (item: RequirementOverride) => item.active && !item.acknowledged_at;
  const counts = {
    open: overrides.filter((item) => item.active).length,
    new: overrides.filter(isNew).length,
    revoked: overrides.filter((item) => item.revoked_at).length,
  };
  const visible = overrides.filter((item) => {
    if (tab === "new") return isNew(item);
    if (tab === "revoked") return Boolean(item.revoked_at);
    return item.active;
  });

  const totals = rows.reduce(
    (sum, row) => ({
      headcount: sum.headcount + row.headcount,
      blocked: sum.blocked + row.blocked,
      overdue: sum.overdue + row.overdue_compliance,
    }),
    { headcount: 0, blocked: 0, overdue: 0 }
  );

  return (
    <section className="ops-stack">
      <div className="ops-metrics">
        <div className="ops-metric">
          <span className="ops-metric__label">Mitarbeiter gesamt</span>
          <strong className="ops-metric__value">{totals.headcount}</strong>
        </div>
        <div className={`ops-metric${totals.blocked ? " is-red" : ""}`}>
          <span className="ops-metric__label">Nicht einsatzfaehig</span>
          <strong className="ops-metric__value">{totals.blocked}</strong>
        </div>
        <div className={`ops-metric${totals.overdue ? " is-red" : ""}`}>
          <span className="ops-metric__label">Compliance ueberfaellig</span>
          <strong className="ops-metric__value">{totals.overdue}</strong>
        </div>
        <div className={`ops-metric${counts.new ? " is-yellow" : ""}`}>
          <span className="ops-metric__label">Offene Ausnahmen</span>
          <strong className="ops-metric__value">{counts.open}</strong>
        </div>
      </div>

      <Section title="Niederlassungen im Vergleich" flush>
        <Table
          columns={BRANCH_COLUMNS}
          minWidth={980}
          empty="Keine Niederlassungen sichtbar."
          head={[
            "Status",
            "Niederlassung",
            "Personal",
            "Nicht einsetzbar",
            "Ueberfaellig",
            "Fahrzeuge",
            "Ersthelfer",
            "",
          ]}
        >
          {rows.map((row) => {
            const branch = branches.find((item) => item.id === row.branch_id);
            const firstAidShort = row.first_aiders_trained < row.first_aiders_required;
            return (
              <Row
                key={row.branch_id}
                columns={BRANCH_COLUMNS}
                onOpen={branch ? () => onOpenBranch(branch) : undefined}
                title="Niederlassung oeffnen"
              >
                <Cell>
                  <Pill tone={toneOf(row.state)}>
                    {row.state === "red" ? "kritisch" : row.state === "yellow" ? "beobachten" : "in Ordnung"}
                  </Pill>
                </Cell>
                <TitleCell
                  title={row.branch_name}
                  meta={
                    row.open_exceptions
                      ? `${row.open_exceptions} Ausnahme(n)${row.new_exceptions ? `, ${row.new_exceptions} neu` : ""}`
                      : "keine Ausnahmen"
                  }
                />
                <Cell className="ops-date">{row.headcount}</Cell>
                <Cell className={`ops-date${row.blocked ? " is-red" : ""}`}>
                  {row.blocked}
                  {row.limited > 0 && (
                    <span className="ops-cell__meta">+{row.limited} eingeschraenkt</span>
                  )}
                </Cell>
                <Cell className={`ops-date${row.overdue_compliance ? " is-red" : ""}`}>
                  {row.overdue_compliance}
                </Cell>
                <Cell className={`ops-date${row.due_vehicles ? " is-yellow" : ""}`}>
                  {row.due_vehicles}
                </Cell>
                <Cell className={`ops-date${firstAidShort ? " is-yellow" : ""}`}>
                  {row.first_aiders_trained} / {row.first_aiders_required}
                </Cell>
                <ActionCell>
                  {branch && (
                    <button
                      type="button"
                      className="pds-icon-btn"
                      aria-label={`${row.branch_name} oeffnen`}
                      onClick={() => onOpenBranch(branch)}
                    >
                      <ExternalLink size={14} />
                    </button>
                  )}
                </ActionCell>
              </Row>
            );
          })}
        </Table>
      </Section>

      <Section
        title="Ausnahmen der Niederlassungen"
        actions={
          <Segments<Tab>
            value={tab}
            onChange={setTab}
            options={[
              { key: "open", label: "Gueltig", count: counts.open },
              { key: "new", label: "Neu", count: counts.new },
              { key: "revoked", label: "Widerrufen", count: counts.revoked },
            ]}
          />
        }
        flush
      >
        <FormStatus error={acknowledge.error} busy={acknowledge.busy} busyLabel="Wird gespeichert..." />
        <Table
          columns={EXCEPTION_COLUMNS}
          minWidth={980}
          empty={
            tab === "new"
              ? "Keine neuen Ausnahmen seit dem letzten Blick."
              : "Keine Ausnahmen erfasst."
          }
          head={["Niederlassung", "Anforderung", "Art", "Begruendung", "Gesetzt am", ""]}
        >
          {visible.map((item) => (
            <Row key={item.id} columns={EXCEPTION_COLUMNS}>
              <TitleCell
                title={item.branch_name}
                meta={isNew(item) ? "neu, noch nicht gesehen" : item.revoked_at ? "widerrufen" : "gesehen"}
              />
              <TitleCell title={item.qualification_name} meta={item.job_role_name} />
              <Cell>
                <Pill tone={item.mode === "excluded" ? "warn" : "info"}>
                  {item.mode === "excluded"
                    ? "entfaellt"
                    : item.mode === "optional"
                      ? "freiwillig"
                      : "verpflichtend"}
                </Pill>
              </Cell>
              <Cell title={item.reason}>
                <span className="ops-cell__title">{item.reason}</span>
                {item.revoked_effective_from && (
                  <span className="ops-cell__meta">
                    Widerruf gilt ab {formatDate(item.revoked_effective_from)}
                  </span>
                )}
              </Cell>
              <Cell className="ops-date">{formatDate(item.created_at)}</Cell>
              <ActionCell>
                {mayGovern && !item.acknowledged_at && (
                  <button
                    type="button"
                    className="pds-icon-btn"
                    aria-label="Als gesehen markieren"
                    title="Als gesehen markieren"
                    onClick={() =>
                      acknowledge.run(() =>
                        apiPost(`/api/requirement-overrides/${item.id}/acknowledge`, {})
                      )
                    }
                  >
                    <Check size={14} />
                  </button>
                )}
                {mayGovern && !item.revoked_at && (
                  <button
                    type="button"
                    className="pds-icon-btn pds-icon-btn--danger"
                    aria-label="Ausnahme widerrufen"
                    title="Ausnahme widerrufen"
                    onClick={() => setRevoking(item)}
                  >
                    <Undo2 size={14} />
                  </button>
                )}
              </ActionCell>
            </Row>
          ))}
        </Table>
      </Section>

      {revoking && (
        <RevokeDialog
          override={revoking}
          onClose={() => setRevoking(null)}
          onSaved={() => {
            setRevoking(null);
            onToast("Ausnahme widerrufen");
            onReload();
          }}
        />
      )}
    </section>
  );
}

function RevokeDialog({
  override,
  onClose,
  onSaved,
}: {
  override: RequirementOverride;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { error, busy, run } = useSubmit(onSaved);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(form, async () => {
      await apiPost(`/api/requirement-overrides/${override.id}/revoke`, {
        reason: String(data.get("reason") || ""),
        effective_from: emptyToNull(data.get("effective_from")),
      });
    });
  }

  return (
    <Modal
      open
      size="sm"
      title="Ausnahme widerrufen"
      subtitle={`${override.qualification_name} - ${override.branch_name}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
            Abbrechen
          </button>
          <span className="ops-spacer" />
          <button
            type="submit"
            form="revoke-form"
            className="pds-btn pds-btn--danger pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gespeichert..." : "Widerrufen"}
          </button>
        </>
      }
    >
      <form id="revoke-form" className="ops-dialog__body" onSubmit={submit}>
        <FormStatus error={error} busy={false} />
        <p className="pds-meta">
          Begruendung der Niederlassung: &bdquo;{override.reason}&ldquo;. Ohne Datum gilt der Widerruf
          in 30 Tagen - die Niederlassung bekommt Zeit, den Nachweis zu beschaffen, statt ueber Nacht
          rot zu werden.
        </p>
        <Field label="Begruendung des Widerrufs" span>
          <TextArea name="reason" required minLength={5} placeholder="Warum gilt die Regel wieder?" />
        </Field>
        <Field label="Gilt ab (optional)">
          <TextInput type="date" name="effective_from" />
        </Field>
      </form>
    </Modal>
  );
}
