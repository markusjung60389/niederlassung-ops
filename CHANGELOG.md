# Changelog

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

## [1.2.2] - 2026-08-20

Ergebnis eines Security-Reviews: die Mandantentrennung griff auf den
Listen-Endpunkten, aber nicht auf den Einzelobjekt-Routen (`GET`/`PATCH`/
`DELETE .../{id}`). Wer eine ID aus einer anderen Niederlassung kannte oder
erriet, kam an ihre Daten - lesend, schreibend und loeschend.

### Behoben

- **Mandantentrennung fehlte auf 40+ Einzelobjekt-Routen.** Compliance-Datensaetze,
  Nachweise, Massnahmen, Vorfaelle, Niederlassungsbewertungen, Mitarbeiter,
  Qualifikationen, Personalakten-Eintraege, Kunden (`/api/accounts`) und
  Mitarbeitergespraeche liessen sich per ID ueber Niederlassungsgrenzen hinweg
  lesen, aendern und loeschen, sobald die aufrufende Person irgendeine
  Schreib- oder Leseberechtigung fuer den jeweiligen Bereich hatte - unabhaengig
  davon, ob die betroffene Niederlassung zu ihrem Zustaendigkeitsbereich
  gehoerte. Ein neuer `ensure_visible`-Baustein (404 statt 403, damit die
  Existenz einer fremden ID nicht bestaetigt wird) schliesst die Luecke; die
  generische CRUD-Fabrik (`app/crud.py`) unterstuetzt Mandantentrennung jetzt
  ebenfalls und verweigert, ein Objekt per Aenderung in eine fremde
  Niederlassung zu verschieben.
- **Dokumente waren vollstaendig ungescoped.** `/api/documents` listete jedes
  hochgeladene Dokument aller Niederlassungen, der Download-Endpunkt lieferte
  den Inhalt - unabhaengig davon, mit welcher Mitarbeiterqualifikation es
  verknuepft war. Sichtbar ist ein Dokument jetzt nur noch fuer die
  hochladende Person und fuer alle mit Zugriff auf den Mitarbeiter, dessen
  Qualifikation es belegt.
- **Das Audit-Log war nicht nach Niederlassung gefiltert**, und `audit:read`
  stand im Berechtigungspaket der reinen Lesevers­ion (Betrachter). Eine
  Leseberechtigung fuer die eigene Niederlassung reichte, um die
  Loeschprotokolle - vollstaendige Datenschnappschuesse inklusive
  Aufenthaltstitel und arbeitsmedizinischer Termine - jeder anderen
  Niederlassung einzusehen. Das Log traegt jetzt eine `branch_id` (neue
  Spalte, per Migration ergaenzt, bestehende Eintraege bleiben `NULL` und
  damit wie bisher sichtbar); niederlassungsuebergreifende Ereignisse (Rollen,
  Katalogeintraege, Benutzerkonten) bleiben fuer alle mit `audit:read`
  einsehbar, niederlassungsgebundene nur fuer die jeweils Zustaendigen.
  `audit:read` ist aus dem Betrachter-Paket entfernt.
- **Der gruppenweite Katalog liess sich von jeder Niederlassungsleitung
  aendern.** `guard_rule_scope` war auf `job-role-requirements` angewendet,
  fehlte aber bei `qualification-types` und `job-roles` (Aendern/Loeschen) -
  eine Niederlassungsleitung konnte damit eine Qualifikationsvorgabe oder
  Funktion fuer alle Niederlassungen aendern oder loeschen. Betrifft nur
  `rule:write`, das bei der Bereichsleitung liegt.
- **`/api/hermes/context/branches/{id}` hatte keine Zugriffspruefung** und war
  durch einen zweiten Fehler zufaellig verdeckt: der Aufruf von
  `build_reminders` uebergab die Niederlassungs-ID als einzelnen String statt
  als Liste, was die Abfrage bei jedem Aufruf mit HTTP 500 abbrechen liess.
  Beides behoben; der Endpunkt liefert jetzt nur die eigene Niederlassung und
  antwortet wieder mit 200.
- **Anmeldeversuche mit unbekannter Adresse liefen messbar schneller
  durch** als solche mit existierendem Konto (der Passwort-Hash-Vergleich lief
  nur, wenn ein Konto gefunden wurde), sodass sich Konten trotz identischer
  Fehlermeldung per Antwortzeit auflisten liessen. Ein fixer Vergleichshash
  fuellt jetzt den fehlenden Fall auf.
- **Beide Container liefen als root.** Backend und Frontend-Image laufen jetzt
  unter einem eigenen, unprivilegierten Benutzer.
- Fehlende Sicherheits-Header (`X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`, `Content-Security-Policy`) im
  Frontend-Image ergaenzt; die CSP wird beim Containerstart passend zur
  konfigurierten API- und Azure-AD-Adresse geschrieben.
- `/docs`, `/redoc` und `/openapi.json` sind unter `APP_ENV=production`
  deaktiviert; `/api/meta` verlangt jetzt eine Anmeldung (`/health` bleibt wie
  vorgesehen offen fuer den Container-Healthcheck).

### Bekannt, nicht behoben

- Die Vertriebs-Endpunkte (`/api/opportunities`, `/api/projects`,
  `/api/project-sites`, `/api/service-contracts`, `/api/service-events`,
  `/api/tasks`) sind weiterhin nicht nach Niederlassung gescoped - anders als
  `/api/accounts`, das jetzt gescoped ist. Vertrieb ist seit v1.2.0 aus der
  Oberflaeche entfernt, die API bleibt aber ueber Werkzeuge wie `curl`
  erreichbar. Empfehlung: entweder vor einer Reaktivierung nachziehen oder die
  Routen bis dahin ganz entfernen.

## [1.2.1] - 2026-08-09

### Behoben

- **Ein vorbereitetes Konto wurde bei der Entra-ID-Anmeldung uebersehen, wenn
  die E-Mail-Adresse anders geschrieben war.** Die Adresse wird beim Anlegen
  klein gespeichert, das Verzeichnis liefert `preferred_username` aber in der
  Schreibweise des UPN. Der Abgleich ignoriert Gross- und Kleinschreibung
  jetzt. Ohne das wurde die Anmeldung entweder abgewiesen
  (`AZURE_AUTO_PROVISION_USERS=false`) oder es entstand still ein **zweites**
  Konto neben dem vorbereiteten.
- Die Abweisung ohne hinterlegtes Konto nennt jetzt auf Deutsch die erwartete
  E-Mail-Adresse - die einzige Information, die zum Beheben fehlt.

### Geaendert

- **Zwei Wege zur Entra-ID-Anmeldung dokumentiert**, mit einer Gegenueberstellung
  in [`docs/azure-ad-setup.md`](docs/azure-ad-setup.md): Konten in der Anwendung
  vorbereiten (ohne App-Rollen, ohne Rollen-Mapping) oder die Rolle aus dem
  Verzeichnis beziehen. Der erste Weg spart App-Rollen, Rollenzuweisungen und
  `AZURE_ROLE_MAP`.
- Die Anleitung behauptete, das Frontend muesse fuer eine Aenderung der
  Azure-Werte neu gebaut werden. Das gilt nur fuer selbst gebaute Images; das
  veroeffentlichte liest sie beim Start aus `config.js`, also genuegen ein
  Eintrag in der `.env` und ein Neustart.

## [1.2.0] - 2026-08-09

Mehrere Niederlassungen, Benutzerverwaltung mit Anmeldung ueber Entra ID und
Entgeltdaten hinter einer zweiten Bestaetigung.

### Hinzugefuegt

- **Entgeltdaten je Mitarbeiter**, in einer eigenen Tabelle und hinter drei
  Schranken: der Berechtigung `salary:read` / `salary:write` (in keiner
  Standardrolle ausser den beiden Wildcard-Rollen), einer **zweiten
  Bestaetigung ueber Entra ID** (Authentifizierungskontext per bedingtem
  Zugriff, mit `amr`/`auth_time` als Rueckfall ohne P1-Lizenz) und einem
  Protokoll, das auch jeden **Lese**zugriff festhaelt. Der Betrag selbst steht
  nie im Protokoll. Ueber den Notfallzugang mit Passwort sind Entgeltdaten gar
  nicht erreichbar. Beschrieben in
  [`docs/benutzerverwaltung.md`](docs/benutzerverwaltung.md).
- **Benutzerverwaltung und Berechtigungssystem.** Konten, Rollen und
  Niederlassungszuordnung sind jetzt in der Oberflaeche pflegbar; beschrieben in
  [`docs/benutzerverwaltung.md`](docs/benutzerverwaltung.md).
  - **Anmeldung ueber Microsoft Entra ID** ist im Frontend fertig verdrahtet
    (`@azure/msal-browser`, dynamisch nachgeladen). Es fehlen nur noch die
    App-Registrierungen.
  - **Passwort-Anmeldung als Notfallweg**, unabhaengig vom `AUTH_MODE`. Beim
    ersten Start entsteht ein Administratorkonto (`ADMIN_EMAIL`, Startpasswort
    aus `ADMIN_INITIAL_PASSWORD`). **Das Startpasswort muss bei der ersten
    Anmeldung geaendert werden** - bis dahin beantwortet die API nichts anderes.
  - scrypt-Hashing aus der Standardbibliothek, Sperre nach fuenf Fehlversuchen,
    Sitzungen ueber eine `token_version` widerrufbar, jede Anmeldung im
    Protokoll.
  - **Eigene Rollen** mit frei zusammengestellten Berechtigungen; die fuenf
    Standardrollen bleiben programmseitig gepflegt und damit unveraenderbar.
  - Neue Berechtigungen `user:read` und `user:write`, neue Rolle *Administrator*.
- **Mehrere Niederlassungen.** Dieselbe Anwendung verwaltet jetzt mehrere
  Standorte, aus zwei Perspektiven: der Niederlassungsleitung und der
  Bereichsleitung darueber. Beschrieben in
  [`docs/niederlassungen.md`](docs/niederlassungen.md).
  - Umschalter in der Kopfzeile, die gewaehlte Niederlassung steht in der URL
    (`#/mitarbeiter/rs`); ohne Auswahl gilt "alle, die ich sehen darf"
  - Sichtbarkeit haengt am Konto (`user_branches`, `users.all_branches`), nicht
    an der Rolle. Jede Liste ist gefiltert, Einzelabfragen antworten mit 404
    statt 403 - Aufenthaltstitel und Vorsorgetermine gehen eine fremde
    Niederlassung nichts an
  - **Portfolio** ueber alle Standorte mit denselben Kennzahlen je Zeile
  - Neue Rolle **Bereichsleiter**; der Niederlassungsleiter behaelt jedes
    fachliche Recht, aber nicht `rule:write` und `branch:write`
- **Compliance-Vorgaben getrennt von den Eintraegen.** Eine Vorgabe beschreibt
  die Pflicht, je Niederlassung entsteht daraus ein Eintrag mit eigenem Termin
  und eigenen Nachweisen. Eine Vorgabe laesst sich in beide Richtungen
  umstellen; beim Verkleinern des Geltungsbereichs werden die Eintraege der
  uebrigen Standorte zu eigenstaendigen Vorgaben abgeloest statt geloescht.
  Eine Vorschau zeigt vorher, was der Wechsel anrichtet.
- **Ausnahmeregister.** Die Niederlassung darf eine Gruppenanforderung fuer
  sich aussetzen - mit Pflichtbegruendung, sofort sichtbar fuer die
  Bereichsleitung und mit 30 Tagen Vorlauf widerrufbar.
- **Fahrzeuge wandern zwischen Niederlassungen**, leihweise oder dauerhaft.
  Faellig ist ein Fahrzeug dort, wo es steht.
- **Mitarbeiter mit mehreren Einsatzorten**: die Anforderungen beider
  Standorte addieren sich, gezaehlt wird die Person nur in ihrer Heimat.
- **End-to-end-Tests** mit Playwright: 70 Faelle in zwei Viewports gegen das
  gebaute Frontend und ein echtes Backend, inklusive der Laufzeitkonfiguration
  ueber `/config.js`. Ablauf und Erweiterung in [`docs/tests.md`](docs/tests.md).
  Als eigener CI-Job.

### Entfernt

- **Vertrieb** ist aus der Oberflaeche verschwunden, ebenso die
  Vertriebskennzahlen im Cockpit. Tabellen und Endpunkte (`/api/accounts`,
  `/api/opportunities`, `/api/service-contracts`) bestehen unveraendert weiter -
  erfasste Daten gehen nicht verloren.

### Behoben

- **`/api/actions` und `/api/bootstrap` waren nicht nach Zustaendigkeit
  gefiltert** (siehe unten) - beides faellt jetzt unter dieselbe Pruefung wie die
  uebrigen Listen.
- **Ein Wechsel der Niederlassung konnte die alte Liste zeigen.** Die noch
  laufende, ungefilterte Antwort ueberholte die gefilterte; die Tabelle zeigte
  dann Standorte, die der Umschalter nicht ausgewaehlt hatte.
- **Massnahmen waren nicht nach Niederlassung gefiltert** und `/api/bootstrap`
  lieferte alle Niederlassungen unabhaengig von der Zustaendigkeit.
- **Qualifikation aus einer Anforderung erfassen war wirkungslos.** Das
  vorbelegte Auswahlfeld ist `disabled` und wurde deshalb nicht mitgesendet;
  der Dialog verlangte stattdessen eine Auswahl, die er selbst gesperrt hatte.
  Damit war der Hauptweg der neuen Qualifikationsverwaltung unbenutzbar.
- **Jedes Speichern schloss den offenen Dialog.** Der Ladehinweis ersetzte den
  gesamten Inhaltsbereich auch beim Nachladen nach einer Aenderung und hat den
  Dialog dabei ausgehaengt. Er erscheint jetzt nur noch beim ersten Laden.
- Die dokumentierten Rechte der Rolle *HSE / Compliance* stimmten nicht mit
  `ROLE_PRESETS` ueberein - `sales:read` fehlte in README und
  Azure-AD-Anleitung.
- Der Bestaetigungsdialog fuer Qualifikationsarten beschriftete die Aktion mit
  "Loeschen" statt "Entfernen".

## [1.1.0] - 2026-08-09

Qualifikationsmodell und neue Oberflaeche im PDS-Fokus-Design.

### Hinzugefuegt

- **Funktionen und Qualifikationskatalog.** Projektleiter, Service-Techniker
  und Monteur tragen die Qualifikationen, die sie erfordern. Katalog und
  Anforderungsmatrix sind unter *Stammdaten* bearbeitbar. Fachliche Grundlage:
  [`docs/qualifikationen.md`](docs/qualifikationen.md).
- **Einsatzfaehigkeit** je Mitarbeiter, aus Anforderung und erfasstem Stand
  berechnet: einsatzfaehig, eingeschraenkt, nicht einsatzfaehig. Ein gueltiges
  Datum ohne hinterlegtes Dokument ist ein eigener Zustand - bei einer
  Besichtigung ist es sonst nicht belegbar.
- **Qualifikationsmatrix**: Mitarbeiter gegen Qualifikationsarten, mit Filter
  auf Luecken. Jede Zelle traegt zusaetzlich zur Farbe ein Zeichen.
- **Fuehrerscheinkontrolle als Qualifikation mit Turnus** (sechs Monate,
  nachweispflichtig). Ist einem Fahrzeug ein Fahrer mit ueberfaelliger
  Kontrolle zugeordnet, weist die Fahrzeugliste darauf hin.
- **Ersthelferquote** nach DGUV Vorschrift 1 Paragraf 26 im Cockpit. Das Feld
  `first_aider` wurde bisher erfasst und nie angezeigt.
- **Mitarbeiterstatus aktiv/ausgeschieden** mit Austrittsdatum. Ausgeschiedene
  loesen keine Erinnerungen aus, bleiben aber vollstaendig erhalten -
  Nachweise unterliegen Aufbewahrungsfristen.
- **Vorlagenkatalog** fuer die Standardpflichten einer Niederlassung
  (Gefaehrdungsbeurteilung, Unterweisung, DGUV V3, Hubarbeitsbuehnenpruefung,
  Erste Hilfe, Brandschutz, Vorsorge, Regalpruefung). Themen werden ausgewaehlt
  statt aus dem Kopf erfasst.
- **Bearbeiten** fuer Mitarbeiter und Fahrzeuge. Die PATCH-Endpunkte gab es
  seit 1.0.0, die Oberflaeche rief sie nie auf - ein Tippfehler war nur ueber
  Loeschen und Neuanlegen korrigierbar, und Loeschen war bei zugeordnetem
  Fahrzeug gesperrt.
- **Hash-Routing**: Ansichten sind verlinkbar, Browser-Zurueck und F5
  funktionieren.
- Ablaufdaten werden aus der Gueltigkeitsdauer des Katalogs berechnet.

### Geaendert

- **Oberflaeche auf den PDS-Fokus-Styleguide umgestellt** (`docs/design/`):
  Topbar-Shell, Werkbank-Tabellen, Status-Pills, Dialoge in vier festen
  Breiten, Archivo fuer die Oberflaeche und IBM Plex Mono fuer Zahlen und
  Daten. Schriften liegen im Image, es gehen keine Requests nach aussen.
- Mitarbeiter und Fahrzeuge stehen in Tabellen statt in Karten; Anlegen,
  Bearbeiten und Details laufen ueber Dialoge. Die Liste beginnt damit wieder
  oben statt unter einem dauerhaft geoeffneten Formular.
- Fahrzeuge zeigen den zugeordneten Mitarbeiter, Kilometerstand, FIN,
  Eigentumsart und Tankkarte - alles bisher erfasst und nie dargestellt.
- Compliance-Detail zeigt Nachweise und Massnahmen beim Thema, zu dem sie
  gehoeren.
- Das Cockpit ist eine Arbeitsliste nach Faelligkeit statt einer Namensliste
  aller Mitarbeiter und Fahrzeuge ohne Status.
- Statuswerte erscheinen auf Deutsch. Bisher stand `training_instruction` und
  `non_compliant` woertlich auf dem Bildschirm.
- Erinnerungen zu Schulungen und Fahrerlaubnis kommen aus den Qualifikationen
  statt aus den Profilspalten; doppelte Eintraege entfallen.
- `GET /api/auth/dev-users` liefert die Rolle mit den weitesten Rechten zuerst.
  Alphabetisch stand der Betrachter vorn, sodass die Anwendung ohne gespeicherte
  Identitaet ohne jede Aktion startete.

### Migration

`0004_qualifications`, rein additiv. Die Schulungs- und Fahrerlaubnisdaten
werden aus `employee_profiles` nach `employee_qualifications` **kopiert**; die
Quellspalten bleiben unveraendert stehen, auch nach einem Downgrade. Freitexte
in `employees.role` werden ueber eine Aliasliste mit den Funktionen verknuepft,
der Freitext selbst bleibt als Bezeichnung erhalten. Keine Spalte wird
entfernt, keine bestehende auf NOT NULL gezogen.

### Bekannte Einschraenkungen

- Der Vertriebsbereich wurde nur auf die neuen Bausteine gehoben, fachlich
  nicht ueberarbeitet - eine Entscheidung ueber seinen Verbleib steht aus.
- Azure AD bleibt vorbereitet, aber nicht aktiv (MSAL fehlt im Frontend).
- Ein Export der Nachweise fuer eine Besichtigung fehlt weiterhin.

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

[1.2.1]: https://github.com/markusjung60389/niederlassung-ops/releases/tag/v1.2.1
[1.2.0]: https://github.com/markusjung60389/niederlassung-ops/releases/tag/v1.2.0
[1.1.0]: https://github.com/markusjung60389/niederlassung-ops/releases/tag/v1.1.0
[1.0.0]: https://github.com/markusjung60389/niederlassung-ops/releases/tag/v1.0.0
