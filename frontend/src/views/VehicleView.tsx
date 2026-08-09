import React from "react";
import { MapPin, Pencil, Plus, Trash2, TriangleAlert } from "lucide-react";
import { apiDelete, apiPatch, apiPost } from "../api";
import { can, type Branch, type Employee, type Vehicle } from "../types";
import { ActionCell, Cell, Row, Table, TitleCell } from "../components/Table";
import { ConfirmDialog, Modal } from "../components/Modal";
import {
  DueDate,
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
  numberOrNull,
  splitCsv,
  toneOf,
  useAction,
  useSubmit,
} from "../components/ui";

const COLUMNS = "112px minmax(0,1.4fr) minmax(0,1.1fr) 104px 104px 104px 92px";
type Filter = "all" | "due" | "unassigned" | "away";

export function VehicleView({
  vehicles,
  employees,
  branches,
  branchId,
  permissions,
  onReload,
  onToast,
}: {
  vehicles: Vehicle[];
  employees: Employee[];
  branches: Branch[];
  /** The selected branch, or null while every branch is shown at once. */
  branchId: string | null;
  permissions: string[];
  onReload: () => void;
  onToast: (message: string) => void;
}) {
  const mayWrite = can(permissions, "fleet:write");
  const [filter, setFilter] = React.useState<Filter>("all");
  const [search, setSearch] = React.useState("");
  const [editing, setEditing] = React.useState<Vehicle | null | "new">(null);
  const [relocating, setRelocating] = React.useState<Vehicle | null>(null);
  const [detail, setDetail] = React.useState<string | null>(null);
  const [confirm, setConfirm] = React.useState<Vehicle | null>(null);
  const remove = useAction(() => {
    setConfirm(null);
    onToast("Fahrzeug geloescht");
    onReload();
  });

  const counts = {
    all: vehicles.length,
    due: vehicles.filter((item) => item.due_state !== "green" || item.driver_alert).length,
    unassigned: vehicles.filter((item) => !item.assigned_employee_id).length,
    away: vehicles.filter((item) => Boolean(item.current_branch_id)).length,
  };

  const visible = vehicles
    .filter((item) => {
      if (filter === "due") return item.due_state !== "green" || Boolean(item.driver_alert);
      if (filter === "unassigned") return !item.assigned_employee_id;
      if (filter === "away") return Boolean(item.current_branch_id);
      return true;
    })
    .filter((item) => {
      const needle = search.trim().toLowerCase();
      if (!needle) return true;
      return [item.license_plate, item.brand ?? "", item.model ?? "", item.assigned_employee_name ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(needle);
    });

  const selected = vehicles.find((item) => item.id === detail) ?? null;
  const alerts = vehicles.filter((item) => item.driver_alert);

  return (
    <section className="ops-stack">
      <div className="ops-row ops-row--between">
        <Segments<Filter>
          value={filter}
          onChange={setFilter}
          options={[
            { key: "all", label: "Alle", count: counts.all },
            { key: "due", label: "Handlungsbedarf", count: counts.due },
            { key: "unassigned", label: "Ohne Fahrer", count: counts.unassigned },
            ...(branches.length > 1
              ? [{ key: "away" as Filter, label: "Verliehen", count: counts.away }]
              : []),
          ]}
        />
        <div className="ops-row ops-spacer">
          <SearchField value={search} onChange={setSearch} placeholder="Kennzeichen, Marke, Fahrer" />
          {mayWrite && (
            <button
              type="button"
              className="pds-btn pds-btn--primary pds-btn--sm"
              onClick={() => setEditing("new")}
            >
              <Plus size={15} /> Fahrzeug
            </button>
          )}
        </div>
      </div>

      {alerts.length > 0 && (
        <div className="pds-banner pds-banner--warn">
          <TriangleAlert size={15} />
          {alerts.length === 1
            ? alerts[0].driver_alert
            : `${alerts.length} Fahrzeuge sind Fahrern mit ueberfaelliger Fuehrerscheinkontrolle zugeordnet.`}
        </div>
      )}

      <FormStatus error={remove.error} busy={remove.busy} busyLabel="Wird geloescht..." />

      <Table
        columns={COLUMNS}
        empty={search ? "Kein Treffer fuer die Suche." : "Noch keine Fahrzeuge erfasst."}
        head={["Status", "Fahrzeug", "Zugeordnet", "HU", "UVV", "Service", ""]}
      >
        {visible.map((vehicle) => (
          <Row
            key={vehicle.id}
            columns={COLUMNS}
            onOpen={() => setDetail(vehicle.id)}
            title="Details oeffnen"
          >
            <Cell>
              <Pill tone={toneOf(vehicle.due_state)}>
                {vehicle.next_due_title ? "faellig" : "in Ordnung"}
              </Pill>
            </Cell>
            <TitleCell
              title={vehicle.license_plate}
              meta={
                <>
                  {[vehicle.brand, vehicle.model, vehicle.vehicle_type].filter(Boolean).join(" ") || "-"}
                  {vehicle.current_branch_name && ` · steht in ${vehicle.current_branch_name}`}
                </>
              }
            />
            <Cell title={vehicle.driver_alert ?? undefined}>
              {vehicle.assigned_employee_name ? (
                <>
                  <span className="ops-cell__title">{vehicle.assigned_employee_name}</span>
                  {vehicle.driver_alert && (
                    <span className="ops-cell__meta" style={{ color: "var(--pds-amber-text)" }}>
                      Fuehrerscheinkontrolle pruefen
                    </span>
                  )}
                </>
              ) : (
                <span className="ops-cell__meta">frei</span>
              )}
            </Cell>
            <Cell>
              <DueDate value={vehicle.hu_due_date} />
            </Cell>
            <Cell>
              <DueDate value={vehicle.uvv_next_check} />
            </Cell>
            <Cell>
              <DueDate value={vehicle.service_due_date} />
            </Cell>
            <ActionCell>
              {mayWrite && (
                <>
                  {branches.length > 1 && (
                    <button
                      type="button"
                      className="pds-icon-btn"
                      aria-label={`${vehicle.license_plate} verlegen`}
                      title="In eine andere Niederlassung verlegen"
                      onClick={() => setRelocating(vehicle)}
                    >
                      <MapPin size={14} />
                    </button>
                  )}
                  <button
                    type="button"
                    className="pds-icon-btn"
                    aria-label={`${vehicle.license_plate} bearbeiten`}
                    onClick={() => setEditing(vehicle)}
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    type="button"
                    className="pds-icon-btn pds-icon-btn--danger"
                    aria-label={`${vehicle.license_plate} loeschen`}
                    onClick={() => setConfirm(vehicle)}
                  >
                    <Trash2 size={14} />
                  </button>
                </>
              )}
            </ActionCell>
          </Row>
        ))}
      </Table>

      {editing && (
        <VehicleDialog
          vehicle={editing === "new" ? null : editing}
          employees={employees}
          branches={branches}
          branchId={branchId}
          onClose={() => setEditing(null)}
          onSaved={(message) => {
            setEditing(null);
            onToast(message);
            onReload();
          }}
        />
      )}

      {relocating && (
        <RelocateDialog
          vehicle={relocating}
          branches={branches}
          onClose={() => setRelocating(null)}
          onSaved={(message) => {
            setRelocating(null);
            onToast(message);
            onReload();
          }}
        />
      )}

      {selected && (
        <VehicleDetail
          vehicle={selected}
          mayWrite={mayWrite}
          onEdit={() => {
            setDetail(null);
            setEditing(selected);
          }}
          onClose={() => setDetail(null)}
        />
      )}

      <ConfirmDialog
        open={confirm !== null}
        title="Fahrzeug loeschen"
        busy={remove.busy}
        body={
          <p>
            <strong>{confirm?.license_plate}</strong> wird mit allen Prueffristen entfernt. Bereits
            erfasste Nachweise zu diesem Fahrzeug bleiben nicht erhalten.
          </p>
        }
        onCancel={() => setConfirm(null)}
        onConfirm={() => confirm && remove.run(() => apiDelete(`/api/vehicles/${confirm.id}`))}
      />
    </section>
  );
}

/* --------------------------------------------------------------------------
 * Create and edit
 * ----------------------------------------------------------------------- */

function VehicleDialog({
  vehicle,
  employees,
  branches,
  branchId,
  onClose,
  onSaved,
}: {
  vehicle: Vehicle | null;
  employees: Employee[];
  branches: Branch[];
  branchId: string | null;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const [dirty, setDirty] = React.useState(false);
  const { error, busy, run } = useSubmit(() =>
    onSaved(vehicle ? "Aenderungen gespeichert" : "Fahrzeug angelegt")
  );
  const [homeBranch, setHomeBranch] = React.useState(
    vehicle?.branch_id ?? branchId ?? branches[0]?.id ?? ""
  );

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    run(form, async () => {
      if (!homeBranch) throw new Error("Keine Niederlassung verfuegbar.");
      const payload = {
        license_plate: data.get("license_plate"),
        brand: emptyToNull(data.get("brand")),
        model: emptyToNull(data.get("model")),
        vehicle_type: emptyToNull(data.get("vehicle_type")),
        vin: emptyToNull(data.get("vin")),
        first_registration: emptyToNull(data.get("first_registration")),
        ownership_type: emptyToNull(data.get("ownership_type")),
        assigned_employee_id: emptyToNull(data.get("assigned_employee_id")),
        mileage: numberOrNull(data.get("mileage")),
        hu_due_date: emptyToNull(data.get("hu_due_date")),
        uvv_last_check: emptyToNull(data.get("uvv_last_check")),
        uvv_next_check: emptyToNull(data.get("uvv_next_check")),
        service_due_date: emptyToNull(data.get("service_due_date")),
        tire_type: emptyToNull(data.get("tire_type")),
        tire_change_due_date: emptyToNull(data.get("tire_change_due_date")),
        insurance_valid_until: emptyToNull(data.get("insurance_valid_until")),
        fuel_card_number: emptyToNull(data.get("fuel_card_number")),
        equipment: splitCsv(data.get("equipment")),
        notes: emptyToNull(data.get("notes")),
      };
      if (vehicle) await apiPatch(`/api/vehicles/${vehicle.id}`, payload);
      else await apiPost("/api/vehicles", { branch_id: homeBranch, ...payload });
    });
  }

  return (
    <Modal
      open
      title={vehicle ? `${vehicle.license_plate} bearbeiten` : "Fahrzeug anlegen"}
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
            form="vehicle-form"
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gespeichert..." : "Speichern"}
          </button>
        </>
      }
    >
      <form id="vehicle-form" className="ops-dialog__body" onSubmit={submit} onChange={() => setDirty(true)}>
        <FormStatus error={error} busy={false} />

        <Fieldset legend="Fahrzeug">
          <div className="ops-grid">
            {!vehicle && branches.length > 1 && (
              <Field label="Heimat-Niederlassung">
                <Select value={homeBranch} onChange={(event) => setHomeBranch(event.target.value)}>
                  {branches.map((branch) => (
                    <option key={branch.id} value={branch.id}>
                      {branch.name}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            <Field label="Kennzeichen">
              <TextInput
                name="license_plate"
                required
                minLength={2}
                defaultValue={vehicle?.license_plate}
              />
            </Field>
            <Field label="Marke">
              <TextInput name="brand" defaultValue={vehicle?.brand ?? ""} />
            </Field>
            <Field label="Modell / Typ">
              <TextInput name="model" defaultValue={vehicle?.model ?? ""} />
            </Field>
            <Field label="Art">
              <TextInput
                name="vehicle_type"
                placeholder="z. B. Transporter"
                defaultValue={vehicle?.vehicle_type ?? ""}
              />
            </Field>
            <Field label="FIN / VIN">
              <TextInput name="vin" defaultValue={vehicle?.vin ?? ""} />
            </Field>
            <Field label="Erstzulassung">
              <TextInput
                type="date"
                name="first_registration"
                defaultValue={vehicle?.first_registration ?? ""}
              />
            </Field>
          </div>
        </Fieldset>

        <Fieldset legend="Zuordnung und Nutzung">
          <div className="ops-grid">
            <Field label="Zugeordnet an">
              <Select name="assigned_employee_id" defaultValue={vehicle?.assigned_employee_id ?? ""}>
                <option value="">niemandem</option>
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.full_name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Eigentum / Leasing">
              <Select name="ownership_type" defaultValue={vehicle?.ownership_type ?? ""}>
                <option value="">nicht gesetzt</option>
                <option value="Eigentum">Eigentum</option>
                <option value="Leasing">Leasing</option>
                <option value="Miete">Miete</option>
              </Select>
            </Field>
            <Field label="Kilometerstand">
              <TextInput type="number" name="mileage" min={0} defaultValue={vehicle?.mileage ?? ""} />
            </Field>
            <Field label="Tankkarte">
              <TextInput name="fuel_card_number" defaultValue={vehicle?.fuel_card_number ?? ""} />
            </Field>
          </div>
        </Fieldset>

        <Fieldset legend="Pruefungen und Fristen">
          <div className="ops-grid ops-grid--three">
            <Field label="HU faellig">
              <TextInput type="date" name="hu_due_date" defaultValue={vehicle?.hu_due_date ?? ""} />
            </Field>
            <Field label="Letzte UVV">
              <TextInput type="date" name="uvv_last_check" defaultValue={vehicle?.uvv_last_check ?? ""} />
            </Field>
            <Field label="Naechste UVV">
              <TextInput type="date" name="uvv_next_check" defaultValue={vehicle?.uvv_next_check ?? ""} />
            </Field>
            <Field label="Service faellig">
              <TextInput
                type="date"
                name="service_due_date"
                defaultValue={vehicle?.service_due_date ?? ""}
              />
            </Field>
            <Field label="Versicherung bis">
              <TextInput
                type="date"
                name="insurance_valid_until"
                defaultValue={vehicle?.insurance_valid_until ?? ""}
              />
            </Field>
          </div>
        </Fieldset>

        <Fieldset legend="Reifen und Ausstattung">
          <div className="ops-grid">
            <Field label="Reifen">
              <Select name="tire_type" defaultValue={vehicle?.tire_type ?? ""}>
                <option value="">nicht gesetzt</option>
                <option value="Sommer">Sommer</option>
                <option value="Winter">Winter</option>
                <option value="Ganzjahr">Ganzjahr</option>
              </Select>
            </Field>
            <Field label="Reifenwechsel">
              <TextInput
                type="date"
                name="tire_change_due_date"
                defaultValue={vehicle?.tire_change_due_date ?? ""}
              />
            </Field>
          </div>
          <Field label="Ausstattung (kommagetrennt)" span>
            <TextInput
              name="equipment"
              placeholder="Leiter, Feuerloescher, Verbandkasten"
              defaultValue={vehicle?.equipment.join(", ") ?? ""}
            />
          </Field>
          <Field label="Notizen" span>
            <TextArea name="notes" defaultValue={vehicle?.notes ?? ""} />
          </Field>
        </Fieldset>
      </form>
    </Modal>
  );
}

/* --------------------------------------------------------------------------
 * Relocation
 * ----------------------------------------------------------------------- */

/**
 * Moving a vehicle to another branch.
 *
 * Two different things, deliberately one dialog with one switch: on loan, the
 * home branch keeps it on its books while the receiving branch is responsible
 * for HU, UVV and the driver; for good, the vehicle changes hands entirely.
 * Either way it appears in the fleet list where it actually stands, because
 * that is where somebody has to act on a due date.
 */
function RelocateDialog({
  vehicle,
  branches,
  onClose,
  onSaved,
}: {
  vehicle: Vehicle;
  branches: Branch[];
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const [target, setTarget] = React.useState(vehicle.location_branch_id ?? vehicle.branch_id);
  const [permanent, setPermanent] = React.useState(false);
  const home = branches.find((item) => item.id === vehicle.branch_id);
  const { error, busy, run } = useAction(() =>
    onSaved(permanent ? "Fahrzeug uebergeben" : "Fahrzeug verlegt")
  );

  return (
    <Modal
      open
      size="sm"
      title="Fahrzeug verlegen"
      subtitle={`${vehicle.license_plate}${home ? ` · Heimat ${home.name}` : ""}`}
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
            disabled={busy}
            onClick={() =>
              run(() =>
                apiPost(`/api/vehicles/${vehicle.id}/relocate`, {
                  branch_id: target === vehicle.branch_id && !permanent ? null : target,
                  permanent,
                })
              )
            }
          >
            {busy ? "Wird uebernommen..." : "Verlegen"}
          </button>
        </>
      }
    >
      <div className="ops-dialog__body">
        <FormStatus error={error} busy={false} />
        <Field label="Steht kuenftig in">
          <Select value={target} onChange={(event) => setTarget(event.target.value)}>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
                {branch.id === vehicle.branch_id ? " (Heimat)" : ""}
              </option>
            ))}
          </Select>
        </Field>
        <label className="ops-check">
          <input
            type="checkbox"
            checked={permanent}
            onChange={(event) => setPermanent(event.target.checked)}
          />
          Dauerhaft uebergeben (Heimat-Niederlassung wechselt)
        </label>
        <p className="pds-meta">
          {permanent
            ? "Das Fahrzeug gehoert danach zur neuen Niederlassung - inklusive Kosten und Halterpflichten."
            : "Leihweise: die Heimat-Niederlassung behaelt das Fahrzeug in ihrem Bestand, faellig ist es dort, wo es steht."}
        </p>
      </div>
    </Modal>
  );
}

/* --------------------------------------------------------------------------
 * Detail
 * ----------------------------------------------------------------------- */

function VehicleDetail({
  vehicle,
  mayWrite,
  onEdit,
  onClose,
}: {
  vehicle: Vehicle;
  mayWrite: boolean;
  onEdit: () => void;
  onClose: () => void;
}) {
  return (
    <Modal
      open
      title={vehicle.license_plate}
      subtitle={[vehicle.brand, vehicle.model, vehicle.vehicle_type].filter(Boolean).join(" ") || undefined}
      onClose={onClose}
      footer={
        <>
          <Pill tone={toneOf(vehicle.due_state)}>
            {vehicle.next_due_title ? `${vehicle.next_due_title} faellig` : "keine offenen Fristen"}
          </Pill>
          <span className="ops-spacer" />
          {mayWrite && (
            <button type="button" className="pds-btn pds-btn--primary pds-btn--sm" onClick={onEdit}>
              <Pencil size={14} /> Bearbeiten
            </button>
          )}
        </>
      }
    >
      <div className="ops-dialog__body">
        {vehicle.driver_alert && (
          <div className="pds-banner pds-banner--warn">
            <TriangleAlert size={15} />
            {vehicle.driver_alert}. Ohne gueltige Kontrolle traegt die Niederlassungsleitung das
            Halterrisiko.
          </div>
        )}
        <dl className="ops-facts">
          <dt>Steht in</dt>
          <dd>{vehicle.current_branch_name ?? "der Heimat-Niederlassung"}</dd>
          <dt>Zugeordnet an</dt>
          <dd>{vehicle.assigned_employee_name ?? "niemandem"}</dd>
          <dt>Eigentum</dt>
          <dd>{vehicle.ownership_type ?? "-"}</dd>
          <dt>FIN / VIN</dt>
          <dd className="ops-date">{vehicle.vin ?? "-"}</dd>
          <dt>Erstzulassung</dt>
          <dd>{formatDate(vehicle.first_registration)}</dd>
          <dt>Kilometerstand</dt>
          <dd className="ops-date">
            {vehicle.mileage !== null && vehicle.mileage !== undefined
              ? `${vehicle.mileage.toLocaleString("de-DE")} km`
              : "-"}
          </dd>
          <dt>Tankkarte</dt>
          <dd className="ops-date">{vehicle.fuel_card_number ?? "-"}</dd>
          <dt>HU faellig</dt>
          <dd>
            <DueDate value={vehicle.hu_due_date} />
          </dd>
          <dt>UVV</dt>
          <dd>
            <DueDate value={vehicle.uvv_next_check} /> (zuletzt {formatDate(vehicle.uvv_last_check)})
          </dd>
          <dt>Service</dt>
          <dd>
            <DueDate value={vehicle.service_due_date} />
          </dd>
          <dt>Reifen</dt>
          <dd>
            {vehicle.tire_type ?? "-"} / Wechsel <DueDate value={vehicle.tire_change_due_date} />
          </dd>
          <dt>Versicherung</dt>
          <dd>
            <DueDate value={vehicle.insurance_valid_until} />
          </dd>
          <dt>Ausstattung</dt>
          <dd>
            {vehicle.equipment.length ? (
              <span className="ops-chips">
                {vehicle.equipment.map((item) => (
                  <span key={item} className="pds-tag">
                    {item}
                  </span>
                ))}
              </span>
            ) : (
              "-"
            )}
          </dd>
          {vehicle.notes && (
            <>
              <dt>Notizen</dt>
              <dd>{vehicle.notes}</dd>
            </>
          )}
        </dl>
      </div>
    </Modal>
  );
}
