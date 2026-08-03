# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

## [1.0.0] - 2026-08-03

Erstes Release mit Container-Images auf ghcr.io.

### Hinzugefuegt

- **Zugriffskontrolle** auf allen `/api`-Endpunkten, Lesezugriffe eingeschlossen.
  Rollen- und Berechtigungsmodell auf Basis der `roles`-Tabelle
  (Niederlassungsleiter, HSE / Compliance, Betrachter).
- **Microsoft Entra ID (Azure AD)** vollstaendig implementiert und getestet,
  ueber `AUTH_MODE=azure_ad` aktivierbar. Standard bleibt `dev`.
  Siehe `docs/azure-ad-setup.md`.
- **Alembic-Migrationen**. Bestehende Datenbanken werden uebernommen und
  hochmigriert, nie neu angelegt. Regeln in `docs/migrations.md`.
- **Vertrieb und Service**: API und Oberflaeche fuer Kunden, Chancen, Projekte,
  Baustellen, Servicevertraege und Serviceereignisse. Die Cockpit-Kacheln
  "Pipeline EUR" und "Service due" zeigen damit echte Werte.
- **Datei-Upload** fuer Nachweise und Dokumente mit serverseitig vergebenem
  Speicherpfad, Groessen- und Typpruefung sowie geschuetztem Download.
- **Wiederholungslogik**: abgeschlossene wiederkehrende Records planen den
  naechsten Zyklus; der Worker oeffnet sie zum Termin wieder und haelt die
  Eskalationsstufe offener Massnahmen aktuell.
- **PATCH und DELETE** fuer Mitarbeiter, Qualifikationen, Pflichtenprofile,
  Fahrzeuge, Incidents, Bestandsaufnahmen, Records, Massnahmen und Nachweise.
  Loeschvorgaenge schreiben den vollstaendigen Datensatz ins Audit-Log und
  werden blockiert, solange abhaengige Eintraege bestehen.
- **Audit-Log** ueber `GET /api/audit-log` lesbar, mit Filtern.
- **Agent-Runs** ueber `GET /api/agent/runs` abfragbar; der Hermes-Review ist
  aus der Compliance-Ansicht heraus startbar.
- Aufgaben, Dokumente und Mitarbeitergespraeche als eigene Ressourcen.
- `GET /api/meta` mit Version, Auth-Modus und Schemarevision.
- CI fuer Tests, Migrationen gegen SQLite und PostgreSQL, Typecheck, Build und
  Compose-Validierung. Release-Workflow fuer ghcr.io.

### Geaendert

- Frontend-Konfiguration wird zur Laufzeit injiziert (`/config.js`), damit ein
  Image in jeder Umgebung laeuft.
- Frontend in Module aufgeteilt (`api`, `auth`, `types`, `views/`), Formulare
  behalten ihre Eingaben bei Fehlern.
- Backend in Router aufgeteilt; wiederkehrende CRUD-Faelle laufen ueber einen
  gemeinsamen Baukasten mit einheitlicher Pruefung und Auditierung.
- Faelligkeiten rechnen in der konfigurierten Zeitzone (`APP_TIMEZONE`) statt
  in UTC.
- Der `worker`-Container fuehrt echte Jobs aus statt zu schlafen.
- Listen-Endpunkte sind paginiert und indiziert.
- Abhaengigkeiten des Frontends sind gepinnt, Images bauen mit `npm ci`.
- Postgres veroeffentlicht keinen Host-Port mehr; `POSTGRES_PASSWORD` und
  `DATABASE_URL` haben keine Defaults.
- CORS-Origins sind konfigurierbar, ein Wildcard wird abgelehnt.

### Behoben

- Alle Lesezugriffe waren ohne Anmeldung erreichbar. `GET /api/employees` und
  `GET /api/hermes/context/...` gaben Aufenthaltstitel, Vertragsdaten und
  arbeitsmedizinische Vorsorgetermine an jeden Aufrufer heraus.
- Die Schreibpruefung akzeptierte jeden beliebigen `X-User-Role`-Header.
- `POST /api/agent/compliance-review` hatte keinerlei Berechtigungspruefung.
- Abgelaufene Qualifikationen fehlten im Cockpit, weil der Filter nur in die
  Zukunft blickte - genau die dringendsten Faelle waren unsichtbar.
- Qualifikationen erzeugten keine Erinnerungen; `reminder_days` war wirkungslos.
- Fehlende Fremdschluesselpruefung erzeugte unter SQLite verwaiste Verweise und
  unter PostgreSQL einen HTTP 500.
- Formulare im Frontend meldeten Fehler nicht und setzten sich trotzdem zurueck;
  bei fehlgeschlagener Mitarbeiteranlage ging das gesamte Pflichtenprofil
  stillschweigend verloren.
- Nur-Datum-Werte wurden als UTC interpretiert und westlich von UTC einen Tag
  zu frueh angezeigt.
- Mitarbeiter- und Qualifikationsaenderungen wurden nicht auditiert.
- Pro Mitarbeiter war mehr als ein Pflichtenprofil moeglich.
- Der veraltete `on_event`-Startup-Hook wurde durch `lifespan` ersetzt.

### Entfernt

- `schemas/compliance-record.schema.json` - ein zweiter, abweichender Vertrag in
  camelCase, den kein Code verwendete. Massgeblich ist `/openapi.json`.

### Bekannte Einschraenkungen

- Azure AD ist vorbereitet, aber nicht aktiv: im Frontend fehlt noch MSAL.
- Mehrere Niederlassungen sind modelliert, die Oberflaeche arbeitet weiterhin
  mit der ersten.
- Der Worker laeuft als Einzelinstanz ohne Sperren; mehrere Instanzen
  parallel sind nicht vorgesehen.

[1.0.0]: https://github.com/markusjung60389/niederlassung-ops/releases/tag/v1.0.0
