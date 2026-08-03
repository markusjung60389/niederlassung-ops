# Remscheid Ops Platform

Separate Ops-, Compliance- und Bestandsaufnahme-Anwendung fuer die Niederlassung Remscheid von B.Schmitt mobile.

## Umfang

- Bestandsaufnahme als primaerer Einstieg fuer manuell erfasste Niederlassungsdaten
- Cockpit mit ueberfaelligen Compliance-Themen, 30-Tage-Faelligkeiten, offenen Massnahmen, Incidents, Qualifikationen, Service- und Pipeline-Snapshot
- Compliance-Records CRUD mit serverseitiger Validierung
- Evidence- und Massnahmenmodell pro Compliance-Record
- Mitarbeiter und Qualifikationen mit Ablauf-/Reminderlogik
- Incident-Erfassung
- Rollenbasierte Zugriffskontrolle auf allen API-Endpunkten
- Audit Log fuer Compliance-relevante Aenderungen, lesbar ueber `GET /api/audit-log`
- Serverseitig gekapselter Hermes-Client mit Agent-Run-Logging
- Versionierte Alembic-Migrationen
- Docker Compose mit `ops-frontend`, `ops-backend`, `db` und `worker`

Nicht enthalten: Dashboard-Import, Shared DB, Synchronisation mit dem vorhandenen Projekt-Dashboard.

## Authentifizierung

Zwei Modi, gesteuert ueber `AUTH_MODE`:

| Modus | Verhalten |
| --- | --- |
| `dev` (Standard) | Der Aufrufer weist sich mit `X-User-Id` aus. Nur fuer lokale Arbeit und Tests. Das Backend verweigert den Start, wenn gleichzeitig `APP_ENV=production` gesetzt ist. |
| `azure_ad` | Microsoft Entra ID Bearer-Token werden bei jedem Request geprueft (Signatur, Issuer, Audience, Ablauf) und auf lokale Rollen gemappt. |

**Der Azure-AD-Pfad ist implementiert und getestet, aber noch nicht scharf geschaltet.**
Die Aktivierung ist Schritt fuer Schritt in [`docs/azure-ad-setup.md`](docs/azure-ad-setup.md)
beschrieben; im Frontend fehlt dafuer noch die MSAL-Abhaengigkeit.

Rollen und Berechtigungen stehen in `backend/app/permissions.py`:

| Rolle | Berechtigungen |
| --- | --- |
| Niederlassungsleiter | `*` |
| HSE / Compliance | `compliance:*`, `incident:*`, `personnel:read`, `fleet:read`, `assessment:read`, `agent:run`, `audit:read` |
| Betrachter | alle `:read` |

Alle `/api/*`-Endpunkte erfordern eine Identitaet, Lesezugriffe eingeschlossen.
Ausgenommen ist nur `/health` fuer den Container-Healthcheck.
Personenbezogene Daten werden zusaetzlich gefiltert: wer `personnel:read` nicht
hat, bekaeme im Cockpit weder Namen noch Aufenthalts- oder Vorsorgetermine.

## Start per Docker

```powershell
Copy-Item .env.example .env
# POSTGRES_PASSWORD und DATABASE_URL setzen - beide haben bewusst keinen Default
docker compose up --build
```

Danach:

- Frontend: http://localhost:3000
- Backend Health: http://localhost:8000/health
- API Docs: http://localhost:8000/docs

Im Entwicklungsmodus waehlt das Frontend oben rechts die Identitaet aus
`GET /api/auth/dev-users`; damit laesst sich das Rollenmodell durchspielen.

Die Datenbank veroeffentlicht keinen Host-Port. Zugriff bei Bedarf ueber
`docker compose exec db psql -U remscheid_ops remscheid_ops`.

## Datenbankschema

Das Schema wird beim Backend-Start ueber `alembic upgrade head` angelegt und
aktualisiert. Geseedet werden nur Remscheid sowie die drei Rollen und je ein
Konto dazu; fachliche Daten werden in der App erfasst.

Eine Datenbank aus der Zeit vor den Migrationen (per `create_all` erzeugt) wird
beim Start erkannt und mit einer Meldung abgelehnt, statt still ein halbes
Schema zu benutzen. In dem Fall neu aufsetzen:

```powershell
docker compose down -v      # bzw. backend/remscheid_ops.db loeschen
docker compose up --build
```

Neue Migration nach einer Modelaenderung:

```powershell
cd backend
alembic revision --autogenerate -m "beschreibung"
alembic upgrade head
```

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

Beispielaufruf im Entwicklungsmodus:

```http
GET http://localhost:8000/api/cockpit
X-User-Id: user-branch-manager
```

## Lokale Frontend-Entwicklung

```powershell
cd frontend
npm ci
npm run dev
```

Bei lokaler Entwicklung erwartet das Frontend standardmaessig `http://localhost:8000` als API.
`CORS_ALLOW_ORIGINS` im Backend muss den Origin des Frontends enthalten.

## Hermes-Konfiguration

Secrets bleiben im Backend/Server-Environment:

```env
HERMES_API_BASE_URL=http://host.docker.internal:8642/v1
HERMES_API_KEY=<secret>
HERMES_AGENT_MODEL=hermes-agent
```

Use Cases:

```http
GET  /api/hermes/context/branches/branch-remscheid   # compliance:read + personnel:read
POST /api/agent/compliance-review                    # agent:run
```

Der Kontext-Endpunkt liefert Hermes die erfassten Bestandsaufnahme-, Compliance-,
Mitarbeiter- und Massnahmendaten. Der Review-Endpunkt speichert Request und
Response in `agent_runs`.

## Bekannte offene Punkte

- Kein DELETE, und PATCH nur fuer Compliance-Records und Massnahmen. Fahrzeuge, Mitarbeiter, Incidents und Bestandsaufnahmen lassen sich nach dem Anlegen nicht mehr korrigieren oder loeschen.
- `accounts`, `opportunities`, `projects`, `service_contracts` und weitere Tabellen haben keine API. Die Cockpit-Kacheln "Pipeline EUR" und "Service due" stehen deshalb dauerhaft auf 0.
- `recurrence`, `next_due_at` und `review_date` werden gespeichert, aber von keiner Logik ausgewertet; der `worker` ist ein Platzhalter ohne Funktion.
- Kein Datei-Upload: `ComplianceEvidence.storage_path` wird vom Client gesetzt und verweist auf nichts.
- `schemas/compliance-record.schema.json` ist ein zweiter, abweichender Vertrag (camelCase) und wird von keinem Code verwendet. Massgeblich ist `/openapi.json`.
- Der Hermes-Review ist aus der Oberflaeche nicht erreichbar, und `agent_runs` ist nicht abfragbar.

## Weitere Dokumentation

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/azure-ad-setup.md`](docs/azure-ad-setup.md)
- `schemas/compliance-record.schema.json`
- Originale Uebergabe: `handover/remscheid-ops-platform`
