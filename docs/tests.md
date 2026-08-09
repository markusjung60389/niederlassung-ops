# Tests

Drei Ebenen, jede mit einer eigenen Aufgabe.

| Ebene | Was sie prueft | Wo |
| --- | --- | --- |
| Backend | Fachlogik, Berechtigungen, Migrationen, Datenerhalt | `backend/tests/`, `pytest` |
| Typecheck | Vertrag zwischen API-Typen und Oberflaeche | `npm run typecheck` |
| End-to-end | Ob die Bildschirme im Browser tatsaechlich tun, was sie versprechen | `frontend/e2e/`, Playwright |

## Backend

```bash
cd backend
python -m pytest -q
```

Migrationen laufen in der CI zusaetzlich gegen PostgreSQL, inklusive Downgrade
und erneutem Upgrade. SQLite akzeptiert Dinge, die PostgreSQL ablehnt - zuletzt
einen Fremdschluesselnamen mit 66 Zeichen.

## End-to-end

```bash
cd frontend
npm run e2e            # kompletter Durchlauf
npm run e2e:ui         # interaktiv, zum Nachvollziehen
npm run e2e:report     # Bericht des letzten Laufs
```

### Was der Aufbau leistet

**Das gebaute Artefakt, nicht der Dev-Server.** Das Frontend wird gebaut und
aus `dist` ausgeliefert; die Backend-URL kommt aus `/config.js`, genau dem
Weg, den der Container-Entrypoint schreibt. Dieser Pfad hat die erste
Live-Inbetriebnahme lahmgelegt und gehoert deshalb in den Test.

**Eine frische Datenbank je Lauf.** Der Playwright-`webServer` startet
`uvicorn` gegen eine SQLite-Datei unter `frontend/.e2e/state`, die vorher
geloescht wird. Jeder Lauf beginnt mit angewendeten Migrationen, geseedetem
Katalog und sonst nichts.

**Vorbedingungen ueber die API, Verhalten ueber die Oberflaeche.** Einen
Mitarbeiter fuer einen Bearbeiten-Test durch ein 30-Feld-Formular zu klicken,
wuerde jeden Test vom Anlegen-Dialog abhaengig machen; ein Fehler dort wuerde
die ganze Suite rot faerben. Die Helfer in `e2e/support/api.ts` legen die
Ausgangslage an, geklickt wird nur, was gerade geprueft wird.

**Ein Worker.** Die Suite teilt sich eine Datenbank; serieller Lauf haelt den
Zustand vorhersagbar. Der komplette Durchlauf dauert etwa zwei Minuten.

**Zwei Niederlassungen ab dem ersten Spec.** `branches.spec.ts` laeuft zuerst
und legt einen zweiten Standort an. Alle folgenden Faelle arbeiten damit in der
Konfiguration, in der das Werkzeug tatsaechlich betrieben wird.

**Zwei Viewports.** `chromium` mit 1440px und `tablet` mit 1024px - der
Styleguide nennt iPad quer als gleichwertiges Ziel, nicht als reduziertes.

### Umgebungsvariablen

| Variable | Zweck |
| --- | --- |
| `E2E_PYTHON` | Interpreter fuer das Backend, z. B. `backend/.venv/bin/python` |
| `E2E_CHROMIUM` | Pfad zu einem vorhandenen Chromium statt eines Downloads |
| `E2E_BACKEND_PORT`, `E2E_FRONTEND_PORT` | Ports, falls belegt |

Lokal typischerweise:

```bash
cd frontend
E2E_PYTHON=../backend/.venv/bin/python npm run e2e
```

### Abdeckung

| Datei | Inhalt |
| --- | --- |
| `branches.spec.ts` | Umschalter und Niederlassung in der URL, Abschottung zwischen Standorten, Portfolio, Ausnahme setzen und widerrufen, Fahrzeug verlegen, Einsatzort, Vorgabe von oertlich auf gruppenweit |
| `navigation.spec.ts` | Hash-Routing, Deep Link, Zurueck, Neuladen, unbekannte Route, Rollen, Dialogverhalten, kein horizontaler Scroll |
| `employees.spec.ts` | Tabelle, Anlegen, Bearbeiten, Qualifikation erfassen, Funktionswechsel, Ausscheiden, Loeschen samt Kindschutz |
| `qualifications.spec.ts` | Matrixzustaende und -zeichen, Filter, Katalogpflege, Anforderung umstellen |
| `vehicles.spec.ts` | Tabelle, Anlegen, Bearbeiten, Fahrer-Kreuzcheck, Filter, Loeschen |
| `compliance.spec.ts` | Vorlagenkatalog, freie Erfassung, Nachweis-Upload, Massnahmen, Filter |
| `cockpit.spec.ts` | Kennzahlen, Arbeitsliste nach Zeitraum, Banner, Ersthelferquote |

### Was die Suite bereits gefunden hat

Beim ersten Durchlauf gegen v1.1.0:

1. **Qualifikation aus einer Anforderung erfassen war unmoeglich.** Das
   vorbelegte Auswahlfeld ist `disabled`, und ein deaktiviertes Feld wird nicht
   mitgesendet - der Dialog meldete nur "Bitte eine Qualifikation waehlen".
   Der Hauptweg der neuen Funktion lief also ins Leere.
2. **Jedes Speichern riss den offenen Dialog weg.** Der Ladehinweis ersetzte
   den kompletten Inhaltsbereich, auch beim Nachladen nach einer Aenderung.
   Jetzt erscheint er nur beim ersten Laden.
3. **Die dokumentierten HSE-Rechte stimmten nicht** mit `ROLE_PRESETS`
   ueberein (`sales:read` fehlte in README und Azure-Anleitung).

Beim Ausbau auf mehrere Niederlassungen:

4. **Der Wechsel der Niederlassung konnte die alte Liste stehen lassen.** Die
   noch laufende, ungefilterte Anfrage ueberholte die gefilterte und
   ueberschrieb sie. Jede Ladung ist jetzt nummeriert; eine veraltete Antwort
   wird verworfen.

### Beim Erweitern

- Testdaten mit `unique()` benennen, damit Faelle sich nie gegenseitig sehen.
- Auf Zeilen ueber `firstTable`, `section` oder den Dialog eingrenzen: mehrere
  Tabellen auf einer Seite koennen denselben Titel zeigen.
- `dialog(page)` liefert den obersten Dialog - Detail und Erfassen sind
  gleichzeitig offen.
- Keine festen Wartezeiten. Alle Helfer warten auf Zustaende.
- `gotoAs` geht ueber `about:blank`, wenn schon eine Seite offen ist: sonst
  aendert sich nur der Hash, das Init-Skript mit der Identitaet laeuft nicht,
  und die laufende Anwendung leitet vorher noch von einer Ansicht weg, die die
  alte Identitaet gar nicht oeffnen darf.
