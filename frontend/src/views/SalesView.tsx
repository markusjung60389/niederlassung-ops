import React from "react";
import { BriefcaseBusiness, Handshake, Wrench } from "lucide-react";
import { apiDelete, apiGet, apiPost } from "../api";
import { can, type Account, type Bootstrap, type Opportunity, type ServiceContract } from "../types";
import {
  Badge,
  DeleteButton,
  FormStatus,
  Panel,
  emptyToNull,
  formatDate,
  formatEuro,
  useAction,
  useSubmit,
} from "../components/ui";

const OFFER_STATES: Record<string, string> = {
  lead: "yellow",
  qualified: "yellow",
  offer_sent: "yellow",
  negotiation: "yellow",
  won: "green",
  lost: "red",
};

export function SalesView({ bootstrap, permissions }: { bootstrap: Bootstrap; permissions: string[] }) {
  const [accounts, setAccounts] = React.useState<Account[]>([]);
  const [opportunities, setOpportunities] = React.useState<Opportunity[]>([]);
  const [contracts, setContracts] = React.useState<ServiceContract[]>([]);
  const [error, setError] = React.useState<string | null>(null);

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

  const mayWrite = can(permissions, "sales:write");
  const accountName = (id: string) => accounts.find((item) => item.id === id)?.name || id;
  const openPipeline = opportunities
    .filter((item) => !["won", "lost"].includes(item.offer_status))
    .reduce((total, item) => total + item.expected_volume, 0);

  return (
    <section className="stack">
      {error && <div className="notice danger">{error}</div>}

      <div className="metrics">
        <div className="metric">
          <span>Offene Pipeline</span>
          <strong>{formatEuro(openPipeline)}</strong>
          <Badge state="green">{opportunities.length} Chancen</Badge>
        </div>
        <div className="metric">
          <span>Kunden</span>
          <strong>{accounts.length}</strong>
          <Badge state="green">erfasst</Badge>
        </div>
        <div className="metric">
          <span>Servicevertraege</span>
          <strong>{contracts.length}</strong>
          <Badge state="green">erfasst</Badge>
        </div>
      </div>

      {mayWrite && <AccountForm bootstrap={bootstrap} onSaved={load} />}

      <Panel title="Kunden" icon={<BriefcaseBusiness size={18} />}>
        {accounts.length === 0 ? (
          <div className="empty">Noch keine Kunden erfasst.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Kunde</th>
                <th>Art</th>
                <th>Branche</th>
                {mayWrite && <th />}
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={account.id}>
                  <td>
                    <strong>{account.name}</strong>
                    <span>{account.notes || "-"}</span>
                  </td>
                  <td>{account.account_type}</td>
                  <td>{account.industry || "-"}</td>
                  {mayWrite && (
                    <td>
                      <RowDelete path={`/api/accounts/${account.id}`} name={account.name} onDone={load} />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {mayWrite && accounts.length > 0 && <OpportunityForm accounts={accounts} onSaved={load} />}

      <Panel title="Chancen / Angebote" icon={<Handshake size={18} />}>
        {opportunities.length === 0 ? (
          <div className="empty">Noch keine Chancen erfasst.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Titel</th>
                <th>Kunde</th>
                <th>Volumen</th>
                <th>Wiedervorlage</th>
                {mayWrite && <th />}
              </tr>
            </thead>
            <tbody>
              {opportunities.map((item) => (
                <tr key={item.id}>
                  <td>
                    <Badge state={OFFER_STATES[item.offer_status] || "yellow"}>{item.offer_status}</Badge>
                  </td>
                  <td>
                    <strong>{item.title}</strong>
                    <span>{item.next_step || "-"}</span>
                  </td>
                  <td>{accountName(item.account_id)}</td>
                  <td>{formatEuro(item.expected_volume)}</td>
                  <td>{formatDate(item.follow_up_date)}</td>
                  {mayWrite && (
                    <td>
                      <RowDelete path={`/api/opportunities/${item.id}`} name={item.title} onDone={load} />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {mayWrite && accounts.length > 0 && <ServiceContractForm accounts={accounts} onSaved={load} />}

      <Panel title="Servicevertraege" icon={<Wrench size={18} />}>
        {contracts.length === 0 ? (
          <div className="empty">Noch keine Servicevertraege erfasst.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Vertrag</th>
                <th>Kunde</th>
                <th>SLA</th>
                <th>Naechste Wartung</th>
                {mayWrite && <th />}
              </tr>
            </thead>
            <tbody>
              {contracts.map((contract) => (
                <tr key={contract.id}>
                  <td>
                    <strong>{contract.title}</strong>
                    <span>{contract.upsell_hint || "-"}</span>
                  </td>
                  <td>{accountName(contract.account_id)}</td>
                  <td>{contract.sla_response_hours ? `${contract.sla_response_hours} h` : "-"}</td>
                  <td>{formatDate(contract.next_maintenance_at)}</td>
                  {mayWrite && (
                    <td>
                      <RowDelete path={`/api/service-contracts/${contract.id}`} name={contract.title} onDone={load} />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </section>
  );
}

function RowDelete({ path, name, onDone }: { path: string; name: string; onDone: () => void }) {
  const { error, busy, run } = useAction(onDone);
  return (
    <>
      <DeleteButton
        label={busy ? "..." : "Loeschen"}
        confirmText={`"${name}" wirklich loeschen?`}
        onConfirm={() => run(() => apiDelete(path))}
      />
      {error && <span className="inlineError">{error}</span>}
    </>
  );
}

function AccountForm({ bootstrap, onSaved }: { bootstrap: Bootstrap; onSaved: () => void }) {
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
    <form className="form" onSubmit={submit}>
      <h2>Kunde erfassen</h2>
      <div className="formGrid">
        <input name="name" placeholder="Kundenname" required minLength={2} />
        <select name="account_type" defaultValue="existing">
          <option value="existing">Bestandskunde</option>
          <option value="prospect">Interessent</option>
          <option value="target">Zielkunde</option>
          <option value="inactive">Inaktiv</option>
        </select>
        <input name="industry" placeholder="Branche" />
      </div>
      <textarea name="notes" placeholder="Notizen" />
      <FormStatus error={error} busy={busy} />
      <button disabled={busy}>Kunde speichern</button>
    </form>
  );
}

function OpportunityForm({ accounts, onSaved }: { accounts: Account[]; onSaved: () => void }) {
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
        probability: Number(data.get("probability") || 25),
        expected_volume: Number(data.get("expected_volume") || 0),
        strategic_relevance: data.get("strategic_relevance"),
        next_step: emptyToNull(data.get("next_step")),
        follow_up_date: emptyToNull(data.get("follow_up_date")),
      });
    });
  }

  return (
    <form className="form" onSubmit={submit}>
      <h2>Chance erfassen</h2>
      <div className="formGrid">
        <select name="account_id" required>
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name}
            </option>
          ))}
        </select>
        <input name="title" placeholder="Titel" required minLength={2} />
        <select name="offer_status" defaultValue="lead">
          <option value="lead">Lead</option>
          <option value="qualified">Qualifiziert</option>
          <option value="offer_sent">Angebot raus</option>
          <option value="negotiation">Verhandlung</option>
          <option value="won">Gewonnen</option>
          <option value="lost">Verloren</option>
        </select>
        <input name="expected_volume" type="number" min={0} step={100} placeholder="Volumen EUR" />
        <input name="probability" type="number" min={0} max={100} placeholder="Wahrscheinlichkeit %" />
        <select name="strategic_relevance" defaultValue="medium">
          <option value="low">geringe Relevanz</option>
          <option value="medium">mittlere Relevanz</option>
          <option value="high">hohe Relevanz</option>
        </select>
        <label>
          Wiedervorlage
          <input name="follow_up_date" type="date" />
        </label>
      </div>
      <textarea name="next_step" placeholder="Naechster Schritt" />
      <FormStatus error={error} busy={busy} />
      <button disabled={busy}>Chance speichern</button>
    </form>
  );
}

function ServiceContractForm({ accounts, onSaved }: { accounts: Account[]; onSaved: () => void }) {
  const { error, busy, run } = useSubmit(onSaved);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(form, async () => {
      await apiPost("/api/service-contracts", {
        account_id: data.get("account_id"),
        title: data.get("title"),
        sla_response_hours: data.get("sla_response_hours") ? Number(data.get("sla_response_hours")) : null,
        next_maintenance_at: emptyToNull(data.get("next_maintenance_at")),
        upsell_hint: emptyToNull(data.get("upsell_hint")),
      });
    });
  }

  return (
    <form className="form" onSubmit={submit}>
      <h2>Servicevertrag erfassen</h2>
      <div className="formGrid">
        <select name="account_id" required>
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name}
            </option>
          ))}
        </select>
        <input name="title" placeholder="Vertragstitel" required minLength={2} />
        <input name="sla_response_hours" type="number" min={1} placeholder="SLA Reaktionszeit (h)" />
        <label>
          Naechste Wartung
          <input name="next_maintenance_at" type="date" />
        </label>
      </div>
      <textarea name="upsell_hint" placeholder="Upselling-Hinweis" />
      <FormStatus error={error} busy={busy} />
      <button disabled={busy}>Vertrag speichern</button>
    </form>
  );
}
