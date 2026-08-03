# Architekturuebersicht - Remscheid Ops Platform

## Annahmen aus der Uebergabe

- Im Workspace war keine bestehende Ziel-App vorhanden. Deshalb wurde eine neue separate Ops-Anwendung aufgebaut.
- Fachliche Daten kommen nicht aus einer externen API. Sie werden zunaechst manuell in der Bestandsaufnahme und den Modulen erfasst.
- Das bestehende Projekt-Dashboard bleibt ausserhalb dieses Stacks.
- V1 implementiert keinen Dashboard-Import, keine Sync-Logik und keine Shared-DB-Kopplung.
- Hermes wird ausschliesslich serverseitig ueber das Backend vorbereitet.

## Stack

- Frontend: React/Vite, ausgeliefert ueber Nginx im Container `ops-frontend`
- Backend: FastAPI, SQLAlchemy, Pydantic, Container `ops-backend`
- Datenbank: PostgreSQL 16, Container `db`
- Worker: Platzhalter-Service fuer spaetere Reminder- oder Agent-Jobs

## Datenfluss V1

- Eigene Backend-API: Persistenzschicht fuer Eingaben aus der Web-App.
- Keine externe Datenquelle fuer die Fachinhalte.
- Hermes-Zugriff spaeter ueber eigene Backend-Endpunkte wie `/api/hermes/context/branches/{branch_id}`.

## Datenmodell V1

Das Backend definiert Tabellen fuer:

- branches, users, roles
- employees, employee_qualifications, employee_reviews
- accounts, opportunities
- projects, project_sites
- service_contracts, service_events
- compliance_records, compliance_evidence, compliance_actions
- incidents, documents, tasks, audit_log
- branch_assessments
- agent_runs

Compliance-relevante Aenderungen erzeugen Audit-Log-Eintraege fuer Create/Update,
Evidence, Actions sowie fuer Mitarbeiter, Qualifikationen und Pflichtenprofile.
Der Akteur stammt aus der authentifizierten Identitaet, nicht aus dem Payload.

Das Schema wird ueber Alembic versioniert (`backend/alembic/`). `init_db()` fuehrt
beim Start `alembic upgrade head` aus.

## Authentifizierung und Autorisierung

- `AUTH_MODE=dev`: Identitaet ueber den `X-User-Id`-Header, verweigert unter `APP_ENV=production`.
- `AUTH_MODE=azure_ad`: Microsoft Entra ID Bearer-Token, Validierung gegen die Tenant-JWKS.
  Implementiert und getestet, aber noch nicht aktiv (siehe `azure-ad-setup.md`).

Die Berechtigungen stehen in `app/permissions.py` und haengen als
`Depends(requires(...))` an den Endpunkten. Rollen werden in der `roles`-Tabelle
gehalten; die Presets im Seed sind fuehrend und werden beim Start abgeglichen.

Personenbezogene Daten werden zusaetzlich mengenmaessig begrenzt: `build_reminders`
liefert Personal- und Fuhrpark-Erinnerungen nur, wenn der Aufrufer
`personnel:read` bzw. `fleet:read` besitzt. Das Cockpit nutzt dieselbe Pruefung.

## Compliance-Workflow

1. Compliance-Record anlegen oder aus Seed-Daten nutzen.
2. Faelligkeitslogik berechnet Ampelstatus serverseitig.
3. Nachweise und Massnahmen koennen an Records gehaengt werden.
4. Nicht-konforme oder ueberfaellige Records erscheinen im Cockpit.
5. Hermes-Review kann ueber `POST /api/agent/compliance-review` gestartet werden.

## Hermes-Kommunikation

Das Frontend spricht nie direkt Hermes. Der Backend-Service `HermesClient` kapselt:

- `HERMES_API_BASE_URL`
- `HERMES_API_KEY`
- `HERMES_AGENT_MODEL`

Ohne konfigurierte Hermes-ENV liefert der Endpunkt eine nachvollziehbare lokale Stub-Antwort und speichert den Agent Run trotzdem.


