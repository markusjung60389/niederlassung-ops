import React from "react";
import { Wrench } from "lucide-react";
import { apiDelete, apiPost } from "../api";
import { can, type Bootstrap, type Employee, type Vehicle } from "../types";
import {
  DeleteButton,
  FormStatus,
  Panel,
  emptyToNull,
  formatDate,
  splitCsv,
  useAction,
  useSubmit,
} from "../components/ui";

export function VehicleView({
  vehicles,
  employees,
  bootstrap,
  permissions,
  onReload,
}: {
  vehicles: Vehicle[];
  employees: Employee[];
  bootstrap: Bootstrap;
  permissions: string[];
  onReload: () => void;
}) {
  const mayWrite = can(permissions, "fleet:write");
  const remove = useAction(onReload);

  return (
    <section className="stack">
      {mayWrite && <VehicleForm employees={employees} bootstrap={bootstrap} onSaved={onReload} />}
      <FormStatus error={remove.error} busy={remove.busy} busyLabel="Wird geloescht..." />
      <div className="grid two">
        {vehicles.map((vehicle) => (
          <Panel
            key={vehicle.id}
            title={vehicle.license_plate}
            icon={<Wrench size={18} />}
            actions={
              mayWrite ? (
                <DeleteButton
                  label="Loeschen"
                  confirmText={`Fahrzeug "${vehicle.license_plate}" loeschen?`}
                  onConfirm={() => remove.run(() => apiDelete(`/api/vehicles/${vehicle.id}`))}
                />
              ) : undefined
            }
          >
            <dl>
              <dt>Fahrzeug</dt>
              <dd>
                {vehicle.brand || "-"} {vehicle.model || ""} / {vehicle.vehicle_type || "-"}
              </dd>
              <dt>HU</dt>
              <dd>{formatDate(vehicle.hu_due_date)}</dd>
              <dt>UVV</dt>
              <dd>{formatDate(vehicle.uvv_next_check)}</dd>
              <dt>Service</dt>
              <dd>{formatDate(vehicle.service_due_date)}</dd>
              <dt>Reifen</dt>
              <dd>
                {vehicle.tire_type || "-"} / Wechsel {formatDate(vehicle.tire_change_due_date)}
              </dd>
              <dt>Versicherung</dt>
              <dd>{formatDate(vehicle.insurance_valid_until)}</dd>
            </dl>
            <div className="chips">
              {vehicle.equipment.map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          </Panel>
        ))}
      </div>
    </section>
  );
}

function VehicleForm({
  employees,
  bootstrap,
  onSaved,
}: {
  employees: Employee[];
  bootstrap: Bootstrap;
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
      await apiPost("/api/vehicles", {
        branch_id: branchId,
        license_plate: data.get("license_plate"),
        brand: emptyToNull(data.get("brand")),
        model: emptyToNull(data.get("model")),
        vehicle_type: emptyToNull(data.get("vehicle_type")),
        vin: emptyToNull(data.get("vin")),
        first_registration: emptyToNull(data.get("first_registration")),
        ownership_type: emptyToNull(data.get("ownership_type")),
        assigned_employee_id: emptyToNull(data.get("assigned_employee_id")),
        mileage: data.get("mileage") ? Number(data.get("mileage")) : null,
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
      });
    });
  }

  return (
    <form className="form" onSubmit={submit}>
      <h2>Fahrzeug erfassen</h2>
      <div className="formGrid">
        <input name="license_plate" placeholder="Kennzeichen" required minLength={2} />
        <input name="brand" placeholder="Marke" />
        <input name="model" placeholder="Modell / Typ" />
        <input name="vehicle_type" placeholder="Art, z. B. Transporter" />
        <input name="vin" placeholder="FIN/VIN" />
        <label>
          Erstzulassung
          <input name="first_registration" type="date" />
        </label>
        <select name="ownership_type" defaultValue="">
          <option value="">Eigentum/Leasing</option>
          <option value="Eigentum">Eigentum</option>
          <option value="Leasing">Leasing</option>
          <option value="Miete">Miete</option>
        </select>
        <select name="assigned_employee_id" defaultValue="">
          <option value="">Zugeordnet an</option>
          {employees.map((employee) => (
            <option key={employee.id} value={employee.id}>
              {employee.full_name}
            </option>
          ))}
        </select>
        <input name="mileage" type="number" placeholder="Kilometerstand" />
      </div>
      <div className="formGrid">
        <label>
          HU faellig
          <input name="hu_due_date" type="date" />
        </label>
        <label>
          Letzte UVV
          <input name="uvv_last_check" type="date" />
        </label>
        <label>
          Naechste UVV
          <input name="uvv_next_check" type="date" />
        </label>
        <label>
          Service faellig
          <input name="service_due_date" type="date" />
        </label>
        <select name="tire_type" defaultValue="">
          <option value="">Reifen</option>
          <option>Sommer</option>
          <option>Winter</option>
          <option>Ganzjahr</option>
        </select>
        <label>
          Reifenwechsel
          <input name="tire_change_due_date" type="date" />
        </label>
        <label>
          Versicherung bis
          <input name="insurance_valid_until" type="date" />
        </label>
        <input name="fuel_card_number" placeholder="Tankkarte" />
      </div>
      <input name="equipment" placeholder="Ausstattung, z. B. Leiter, Feuerloescher, Verbandkasten" />
      <textarea name="notes" placeholder="Notizen / Besonderheiten" />
      <FormStatus error={error} busy={busy} />
      <button disabled={busy}>Fahrzeug speichern</button>
    </form>
  );
}
