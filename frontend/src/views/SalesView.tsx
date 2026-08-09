import React from "react";
import { Plus, Trash2 } from "lucide-react";
import { apiDelete, apiGet, apiPost } from "../api";
import { can, type Account, type Bootstrap, type Opportunity, type ServiceContract } from "../types";
import { ActionCell, Cell, Row, Table, TitleCell } from "../components/Table";
import { Modal } from "../components/Modal";
import {
  DueDate,
  Field,
  FormStatus,
  Pill,
  Section,
  Select,
  TextArea,
  TextInput,
  emptyToNull,
  formatEuro,
  numberOrNull,
  useAction,
  useSubmit,
} from "../components/ui";

/**
 * Sales.
 *
 * Deliberately left at its previous scope - only carried over to the shared
 * components so the application looks like one product. The area is pending a
 * decision on whether it stays at all.
 */

const OFFER_LABELS: Record<string, string> = {
  lead: "Lead",
  qualified: "qualifiziert",
  offer_sent: "Angebot raus",
  negotiation: "Verhandlung",
  won: "gewonnen",
  lost: "verloren",
};

const OFFER_TONES: Record<string, "ok" | "warn" | "danger"> = {
  won: "ok",
  lost: "danger",
};

const ACCOUNT_COLUMNS = "minmax(0,2fr) 140px 140px 72px";
const OPPORTUNITY_COLUMNS = "120px minmax(0,1.8fr) minmax(0,1fr) 120px 110px 72px";
const CONTRACT_COLUMNS = "minmax(0,1.8fr) minmax(0,1fr) 90px 120px 72px";

type Dialog = "account" | "opportunity" | "contract" | null;

export function SalesView({
  bootstrap,
  permissions,
  onToast,
}: {
  bootstrap: Bootstrap;
  permissions: string[];
  onToast: (message: string) => void;
}) {
  const [accounts, setAccounts] = React.useState<Account[]>([]);
  const [opportunities, setOpportunities] = React.useState<Opportunity[]>([]);
  const [contracts, setContracts] = React.useState<ServiceContract[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [dialog, setDialog] = React.useState<Dialog>(null);

  const load = React.useCallback(async () => {
    try {
      const [accountData, opportunityData, contractData] = await Promise.all([
        apiGet<Account[]>("/api/accounts"),
        apiGet<Opportunity[]>("/api/opportunities"),
        apiGet<ServiceContract[]>("/api/service-contracts"),
      ]);
      setAccounts(accountData);
      setOpportunities(opportunityData);
      setContracts(contractData);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unbekannter Fehler");
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const remove = useAction(() => {
    onToast("Eintrag geloescht");
    load();
  });
  const mayWrite = can(permissions, "sales:write");
  const accountName = (id: string) => accounts.find((item) => item.id === id)?.name || id;
  const openPipeline = opportunities
    .filter((item) => !["won", "lost"].includes(item.offer_status))
    .reduce((total, item) => total + item.expected_volume, 0);

  const closed = () => {
    setDialog(null);
    onToast("Gespeichert");
    load();
  };

  return (
    <section className="ops-stack">
      {error && <div className="pds-banner pds-banner--danger">{error}</div>}
      <FormStatus error={remove.error} busy={remove.busy} busyLabel="Wird geloescht..." />

      <div className="ops-metrics">
        <div className="ops-metric">
          <span className="ops-metric__label">Offene Pipeline</span>
          <strong className="ops-metric__value">{formatEuro(openPipeline)}</strong>
        </div>
        <div className="ops-metric">
          <span className="ops-metric__label">Kunden</span>
          <strong className="ops-metric__value">{accounts.length}</strong>
        </div>
        <div className="ops-metric">
          <span className="ops-metric__label">Servicevertraege</span>
          <strong className="ops-metric__value">{contracts.length}</strong>
        </div>
      </div>

      <Section
        title="Kunden"
        actions={
          mayWrite ? (
            <button
              type="button"
              className="pds-btn pds-btn--outline pds-btn--sm"
              onClick={() => setDialog("account")}
            >
              <Plus size={15} /> Kunde
            </button>
          ) : undefined
        }
        flush
      >
        <Table
          columns={ACCOUNT_COLUMNS}
          minWidth={620}
          head={["Kunde", "Art", "Branche", ""]}
          empty="Noch keine Kunden erfasst."
        >
          {accounts.map((account) => (
            <Row key={account.id} columns={ACCOUNT_COLUMNS}>
              <TitleCell title={account.name} meta={account.notes || "-"} />
              <Cell>
                <span className="pds-meta">{account.account_type}</span>
              </Cell>
              <Cell>
                <span className="pds-meta">{account.industry || "-"}</span>
              </Cell>
              <ActionCell>
                {mayWrite && (
                  <button
                    type="button"
                    className="pds-icon-btn pds-icon-btn--danger"
                    aria-label={`${account.name} loeschen`}
                    onClick={() => remove.run(() => apiDelete(`/api/accounts/${account.id}`))}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </ActionCell>
            </Row>
          ))}
        </Table>
      </Section>

      <Section
        title="Chancen und Angebote"
        actions={
          mayWrite && accounts.length > 0 ? (
            <button
              type="button"
              className="pds-btn pds-btn--outline pds-btn--sm"
              onClick={() => setDialog("opportunity")}
            >
              <Plus size={15} /> Chance
            </button>
          ) : undefined
        }
        flush
      >
        <Table
          columns={OPPORTUNITY_COLUMNS}
          head={["Status", "Titel", "Kunde", "Volumen", "Wiedervorlage", ""]}
          empty="Noch keine Chancen erfasst."
        >
          {opportunities.map((item) => (
            <Row key={item.id} columns={OPPORTUNITY_COLUMNS}>
              <Cell>
                <Pill tone={OFFER_TONES[item.offer_status] ?? "warn"}>
                  {OFFER_LABELS[item.offer_status] ?? item.offer_status}
                </Pill>
              </Cell>
              <TitleCell title={item.title} meta={item.next_step || "-"} />
              <Cell>
                <span className="pds-meta">{accountName(item.account_id)}</span>
              </Cell>
              <Cell>
                <span className="pds-table__amount">{formatEuro(item.expected_volume)}</span>
              </Cell>
              <Cell>
                <DueDate value={item.follow_up_date} />
              </Cell>
              <ActionCell>
                {mayWrite && (
                  <button
                    type="button"
                    className="pds-icon-btn pds-icon-btn--danger"
                    aria-label={`${item.title} loeschen`}
                    onClick={() => remove.run(() => apiDelete(`/api/opportunities/${item.id}`))}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </ActionCell>
            </Row>
          ))}
        </Table>
      </Section>

      <Section
        title="Servicevertraege"
        actions={
          mayWrite && accounts.length > 0 ? (
            <button
              type="button"
              className="pds-btn pds-btn--outline pds-btn--sm"
              onClick={() => setDialog("contract")}
            >
              <Plus size={15} /> Vertrag
            </button>
          ) : undefined
        }
        flush
      >
        <Table
          columns={CONTRACT_COLUMNS}
          minWidth={680}
          head={["Vertrag", "Kunde", "SLA", "Naechste Wartung", ""]}
          empty="Noch keine Servicevertraege erfasst."
        >
          {contracts.map((contract) => (
            <Row key={contract.id} columns={CONTRACT_COLUMNS}>
              <TitleCell title={contract.title} meta={contract.upsell_hint || "-"} />
              <Cell>
                <span className="pds-meta">{accountName(contract.account_id)}</span>
              </Cell>
              <Cell>
                <span className="ops-date">
                  {contract.sla_response_hours ? `${contract.sla_response_hours} h` : "-"}
                </span>
              </Cell>
              <Cell>
                <DueDate value={contract.next_maintenance_at} />
              </Cell>
              <ActionCell>
                {mayWrite && (
                  <button
                    type="button"
                    className="pds-icon-btn pds-icon-btn--danger"
                    aria-label={`${contract.title} loeschen`}
                    onClick={() => remove.run(() => apiDelete(`/api/service-contracts/${contract.id}`))}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </ActionCell>
            </Row>
          ))}
        </Table>
      </Section>

      {dialog === "account" && (
        <AccountDialog bootstrap={bootstrap} onClose={() => setDialog(null)} onSaved={closed} />
      )}
      {dialog === "opportunity" && (
        <OpportunityDialog accounts={accounts} onClose={() => setDialog(null)} onSaved={closed} />
      )}
      {dialog === "contract" && (
        <ContractDialog accounts={accounts} onClose={() => setDialog(null)} onSaved={closed} />
      )}
    </section>
  );
}

function DialogShell({
  title,
  formId,
  busy,
  onClose,
  children,
}: {
  title: string;
  formId: string;
  busy: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <Modal
      open
      title={title}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
            Abbrechen
          </button>
          <span className="ops-spacer" />
          <button
            type="submit"
            form={formId}
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gespeichert..." : "Speichern"}
          </button>
        </>
      }
    >
      {children}
    </Modal>
  );
}

function AccountDialog({
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

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(form, async () => {
      if (!branchId) throw new Error("Keine Niederlassung verfuegbar.");
      await apiPost("/api/accounts", {
        branch_id: branchId,
        name: data.get("name"),
        account_type: data.get("account_type"),
        industry: emptyToNull(data.get("industry")),
        notes: emptyToNull(data.get("notes")),
      });
    });
  }

  return (
    <DialogShell title="Kunde erfassen" formId="account-form" busy={busy} onClose={onClose}>
      <form id="account-form" className="ops-dialog__body" onSubmit={submit}>
        <FormStatus error={error} busy={false} />
        <div className="ops-grid">
          <Field label="Kundenname">
            <TextInput name="name" required minLength={2} />
          </Field>
          <Field label="Art">
            <Select name="account_type" defaultValue="existing">
              <option value="existing">Bestandskunde</option>
              <option value="prospect">Interessent</option>
              <option value="target">Zielkunde</option>
              <option value="inactive">Inaktiv</option>
            </Select>
          </Field>
          <Field label="Branche" span>
            <TextInput name="industry" />
          </Field>
          <Field label="Notizen" span>
            <TextArea name="notes" />
          </Field>
        </div>
      </form>
    </DialogShell>
  );
}

function OpportunityDialog({
  accounts,
  onClose,
  onSaved,
}: {
  accounts: Account[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const { error, busy, run } = useSubmit(onSaved);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(form, async () => {
      await apiPost("/api/opportunities", {
        account_id: data.get("account_id"),
        title: data.get("title"),
        offer_status: data.get("offer_status"),
        probability: numberOrNull(data.get("probability")) ?? 25,
        expected_volume: numberOrNull(data.get("expected_volume")) ?? 0,
        strategic_relevance: data.get("strategic_relevance"),
        next_step: emptyToNull(data.get("next_step")),
        follow_up_date: emptyToNull(data.get("follow_up_date")),
      });
    });
  }

  return (
    <DialogShell title="Chance erfassen" formId="opportunity-form" busy={busy} onClose={onClose}>
      <form id="opportunity-form" className="ops-dialog__body" onSubmit={submit}>
        <FormStatus error={error} busy={false} />
        <div className="ops-grid">
          <Field label="Kunde">
            <Select name="account_id" required>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Titel">
            <TextInput name="title" required minLength={2} />
          </Field>
          <Field label="Status">
            <Select name="offer_status" defaultValue="lead">
              {Object.entries(OFFER_LABELS).map(([value, text]) => (
                <option key={value} value={value}>
                  {text}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Volumen in EUR">
            <TextInput type="number" name="expected_volume" min={0} step={100} />
          </Field>
          <Field label="Wahrscheinlichkeit in %">
            <TextInput type="number" name="probability" min={0} max={100} defaultValue={25} />
          </Field>
          <Field label="Strategische Relevanz">
            <Select name="strategic_relevance" defaultValue="medium">
              <option value="low">gering</option>
              <option value="medium">mittel</option>
              <option value="high">hoch</option>
            </Select>
          </Field>
          <Field label="Wiedervorlage">
            <TextInput type="date" name="follow_up_date" />
          </Field>
          <Field label="Naechster Schritt" span>
            <TextArea name="next_step" />
          </Field>
        </div>
      </form>
    </DialogShell>
  );
}

function ContractDialog({
  accounts,
  onClose,
  onSaved,
}: {
  accounts: Account[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const { error, busy, run } = useSubmit(onSaved);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(form, async () => {
      await apiPost("/api/service-contracts", {
        account_id: data.get("account_id"),
        title: data.get("title"),
        sla_response_hours: numberOrNull(data.get("sla_response_hours")),
        next_maintenance_at: emptyToNull(data.get("next_maintenance_at")),
        upsell_hint: emptyToNull(data.get("upsell_hint")),
      });
    });
  }

  return (
    <DialogShell title="Servicevertrag erfassen" formId="contract-form" busy={busy} onClose={onClose}>
      <form id="contract-form" className="ops-dialog__body" onSubmit={submit}>
        <FormStatus error={error} busy={false} />
        <div className="ops-grid">
          <Field label="Kunde">
            <Select name="account_id" required>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Vertragstitel">
            <TextInput name="title" required minLength={2} />
          </Field>
          <Field label="SLA Reaktionszeit in Stunden">
            <TextInput type="number" name="sla_response_hours" min={1} />
          </Field>
          <Field label="Naechste Wartung">
            <TextInput type="date" name="next_maintenance_at" />
          </Field>
          <Field label="Upselling-Hinweis" span>
            <TextArea name="upsell_hint" />
          </Field>
        </div>
      </form>
    </DialogShell>
  );
}
