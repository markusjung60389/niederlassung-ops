# Datenbankaenderungen - verbindliche Regeln

Grundsatz: **Bestandsdaten gehen nie verloren.** Jede Schemaaenderung laeuft
ueber eine Alembic-Migration, die gegen eine gefuellte Datenbank getestet ist.
`create_all()` wird nicht mehr verwendet.

## Ablauf

```powershell
cd backend
# 1. Modell in app/models.py aendern
# 2. Migration erzeugen
alembic revision --autogenerate -m "kurze beschreibung"
# 3. Erzeugte Datei PRUEFEN und nacharbeiten (siehe Checkliste)
# 4. Anwenden
alembic upgrade head
# 5. Rueckwaerts pruefen
alembic downgrade -1
alembic upgrade head
# 6. Tests
pytest
```

`alembic check` schlaegt fehl, wenn ein Modell ohne passende Migration geaendert
wurde. Das laeuft in der CI und blockiert den Merge.

## Checkliste fuer jede erzeugte Migration

Autogenerate erzeugt Code, der auf einer leeren Datenbank funktioniert und auf
einer gefuellten scheitert. Diese Punkte sind bereits zweimal aufgetreten:

| Punkt | Warum |
| --- | --- |
| **NOT NULL nur mit `server_default`** | Ohne Default schlaegt das ALTER auf vorhandenen Zeilen fehl ("column contains null values"). |
| **Constraints immer benennen** | `create_unique_constraint(None, ...)` laesst sich im Downgrade auf PostgreSQL nicht ansprechen. Gilt auch fuer Fremdschluessel. |
| **Neue Unique-Constraints: Duplikate vorher behandeln** | Sonst bricht die Migration ab. Nicht einfach loeschen - betroffene Zeilen nach `audit_log` schreiben, wie in `0002_auth`. |
| **Spalten fuer Bestandszeilen nullable** | Neue Pflichtfelder werden im Schema nullable und in der API verpflichtend, siehe `accounts.branch_id` in `0003_sales`. |
| **Kein `DROP COLUMN` ohne Backup** | Der Inhalt ist danach weg. Erst in einer spaeteren Version entfernen, nachdem die Spalte nachweislich ungenutzt ist. |
| **Downgrade wirklich schreiben** | Wird in der CI ausgefuehrt (`downgrade base` und wieder hoch). |

## SQLite

SQLite kann die meisten ALTER-Operationen nicht und baut die Tabelle neu
(anlegen, kopieren, loeschen, umbenennen). Deshalb:

- `render_as_batch` ist in `alembic/env.py` fuer SQLite aktiv.
- Migrationen laufen auf einer eigenen Engine **ohne** das
  `PRAGMA foreign_keys=ON` der Anwendung. Mit aktiver Fremdschluesselpruefung
  scheitert das Zwischenschritt-`DROP TABLE` an Verweisen anderer Tabellen.

Beides steckt in `app/database.py::init_db` und muss so bleiben.

## Bestehende Datenbanken

`init_db()` laeuft bei jedem Backend-Start:

1. Keine Tabellen vorhanden → alle Migrationen laufen durch.
2. Tabellen vorhanden, `alembic_version` fehlt (Datenbank aus der Zeit vor den
   Migrationen) → sie wird auf `0001_initial` gestempelt und danach normal
   hochmigriert. Es wird nichts geloescht und nichts neu angelegt.
3. `alembic_version` vorhanden → nur die fehlenden Migrationen laufen.

Ein Zuruecksetzen der Datenbank ist damit nie erforderlich.

## Tests

`backend/tests/test_migrations.py` baut eine Datenbank im alten Zustand, fuellt
sie mit Zeilen und prueft nach der Migration, dass alles noch da ist:

- Alt-Datenbank wird uebernommen, Mitarbeiter, Profile, Records und Benutzer
  bleiben erhalten, neue Spalten sind befuellt statt NULL
- Doppelte Profile landen in `audit_log`, statt verworfen zu werden
- Zweimaliges Migrieren aendert nichts
- Downgrade und erneutes Upgrade lassen die Daten unangetastet
- Modelle und Migrationen sind deckungsgleich

Wer eine Migration hinzufuegt, ergaenzt hier den passenden Fall.
