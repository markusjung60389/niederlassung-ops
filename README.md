# Remscheid Ops Platform

Separate Ops-, Compliance- und Bestandsaufnahme-Anwendung fuer die Niederlassung Remscheid von B.Schmitt mobile.

## Umfang V1

- Bestandsaufnahme als primaerer Einstieg fuer manuell erfasste Niederlassungsdaten
- Cockpit mit ueberfaelligen Compliance-Themen, 30-Tage-Faelligkeiten, offenen Massnahmen, Incidents, Qualifikationen, Service- und Pipeline-Snapshot
- Compliance-Records CRUD mit serverseitiger Validierung
- Evidence- und Massnahmenmodell pro Compliance-Record
- Mitarbeiter und Qualifikationen mit Ablauf-/Reminderlogik
- Incident-Erfassung
- Audit Log fuer Compliance-relevante Aenderungen
- Serverseitig gekapselter Hermes-Client mit Agent-Run-Logging
- Docker Compose mit `ops-frontend`, `ops-backend`, `db` und `worker`

Nicht enthalten in V1: Dashboard-Import, Shared DB, Synchronisation mit dem vorhandenen Projekt-Dashboard.

## Start per Docker

```powershell
Copy-Item .env.example .env
# bei Bedarf HERMES_API_KEY in .env setzen
docker compose up --build
```

Danach:

- Frontend: http://localhost:3000
- Backend Health: http://localhost:8000/health
- API Docs: http://localhost:8000/docs

Die erste Version erzeugt das initiale Schema beim Backend-Start ueber SQLAlchemy-Metadaten und seeded nur Remscheid sowie minimale Rollen/User. Fachliche Daten werden in der App erfasst. Fuer spaetere produktive Increments sollte daraus eine versionierte Alembic-Migration gemacht werden.

## Lokale Backend-Pruefung

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
uvicorn app.main:app --reload
```

Ohne `DATABASE_URL` nutzt das Backend lokal SQLite (`backend/remscheid_ops.db`). Im Compose-Stack wird PostgreSQL verwendet.

## Lokale Frontend-Entwicklung

```powershell
cd frontend
npm install
npm run dev
```

Bei lokaler Entwicklung erwartet das Frontend standardmaessig `http://localhost:8000` als API.

## Hermes-Konfiguration

Secrets bleiben im Backend/Server-Environment:

```env
HERMES_API_BASE_URL=http://host.docker.internal:8642/v1
HERMES_API_KEY=<secret>
HERMES_AGENT_MODEL=hermes-agent
```

Hermes kann spaeter serverseitig auf die erfassten Daten zugreifen, z. B. ueber `GET /api/hermes/context/branches/branch-remscheid`.

Use Cases V1:

```http
GET /api/hermes/context/branches/branch-remscheid
POST /api/agent/compliance-review
```

Der Kontext-Endpunkt liefert Hermes spaeter die erfassten Bestandsaufnahme-, Compliance-, Mitarbeiter- und Massnahmendaten. Der Review-Endpunkt kann fuer einen zuvor erfassten Compliance-Record genutzt werden und speichert Request/Response in `agent_runs`.

## Weitere Dokumentation

- `docs/architecture.md`
- `schemas/compliance-record.schema.json`
- Originale Uebergabe: `handover/remscheid-ops-platform`



