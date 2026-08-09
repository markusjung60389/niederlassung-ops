# Mehrere Niederlassungen

Bis Version 1.1 war die Anwendung eine Remscheid-Anwendung: eine
Niederlassung, ein Regelwerk, eine Sicht. Ab 1.2 verwaltet dasselbe Werkzeug
mehrere Standorte - aus zwei Perspektiven, die verschiedene Fragen stellen.

| Rolle | Frage |
| --- | --- |
| Niederlassungsleitung | Wer ist heute einsetzbar, was ist bei **mir** faellig? |
| Bereichsleitung | Welche Niederlassung driftet ab, und welche Ausnahmen wurden vor Ort gesetzt? |

Beide Fragen aus einer Datenbasis zu beantworten geht nur, wenn die Kennzahlen
vergleichbar sind. Deshalb ist der Katalog gruppenweit und die Abweichung davon
ein sichtbarer Eintrag, keine stille Luecke.

## Die drei Ebenen

```
Gruppe          Qualifikationskatalog, Funktionen, Compliance-Vorgaben  (branch_id = NULL)
  |
Niederlassung   eigene Qualifikationen, eigene Funktionen, eigene Vorgaben,
  |             Ausnahmen von Gruppenanforderungen
Person/Objekt   Mitarbeiter, Fahrzeuge, Compliance-Eintraege mit Nachweisen
```

`branch_id = NULL` heisst "gilt fuer alle". Das gilt fuer
`qualification_types`, `job_roles` und `compliance_rules` gleichermassen.

## Sichtbarkeit

Wer welche Niederlassung sieht, steht am Konto, nicht an der Rolle:

- `user_branches` - je Zeile eine Niederlassung, die das Konto sehen darf
- `users.all_branches` - fuer die Bereichsleitung, erspart die Pflege je Standort

Die Rolle entscheidet **was** jemand darf, das Konto **wo**. Jede Listen-API
filtert ueber `deps.branch_filter`; eine Niederlassung ausserhalb des eigenen
Bereichs liefert eine leere Liste, kein 403 und erst recht nicht alles. Bei
Einzelabfragen antwortet die API mit 404 statt 403, damit die blosse Existenz
eines Datensatzes nichts verraet.

Das ist keine Bequemlichkeit, sondern Datenschutz: Aufenthaltstitel,
Vorsorgetermine und Fuehrerscheindaten sind personenbezogen und gehen eine
fremde Niederlassung nichts an.

## Regeln: gruppenweit oder oertlich, in beide Richtungen

Eine **Vorgabe** (`compliance_rules`) beschreibt die Pflicht. Je Niederlassung
entsteht daraus ein **Compliance-Eintrag** (`compliance_records`) mit eigenem
Termin, eigenem Verantwortlichen und eigenen Nachweisen.

Diese Trennung ist der Grund, warum eine Vorgabe wandern kann:

| Richtung | Was passiert |
| --- | --- |
| oertlich -> gruppenweit | In jeder Niederlassung ohne Eintrag entsteht einer. Bestehende Eintraege bleiben unberuehrt - ihr Termin und ihre Nachweise gehoeren der Niederlassung. |
| gruppenweit -> oertlich | Die Eintraege der uebrigen Niederlassungen **verschwinden nicht**. Sie werden mit ihrer gesamten Historie zu eigenen Vorgaben dieser Standorte. |

Der zweite Fall ist der wichtige. Eine Regel zurueckzunehmen darf nicht
bedeuten, dass drei Niederlassungen ihre Unterweisungsnachweise verlieren -
gearbeitet wurde dort schliesslich. `POST /api/compliance-rules/{id}/scope`
mit `detach_dropped: true` (Standard) loest sie ab; die Oberflaeche zeigt
vorher unter `scope-preview`, was der Wechsel anrichten wird.

Anlegen und Aendern einer gruppenweiten Vorgabe verlangt `rule:write` und liegt
damit bei der Bereichsleitung. Eine gruppenweite Regel reicht in
Niederlassungen, fuer die der Aufrufer nicht verantwortlich ist.

## Ausnahmen statt stiller Abweichung

Die Niederlassung darf eine Gruppenanforderung fuer sich aussetzen - ohne
Freigabe, sofort wirksam. Der Preis dafuer steht in
`requirement_overrides`:

- eine **Begruendung** ist Pflicht (mindestens fuenf Zeichen)
- der Eintrag erscheint beim Vorgesetzten sofort und ist bis zur Kenntnisnahme
  als *neu* markiert
- die Bereichsleitung kann ihn **widerrufen**, standardmaessig mit 30 Tagen
  Vorlauf, damit ein Standort nicht ueber Nacht rot wird

Eine Ausnahme, die niemand erklaeren kann, ist bei einer Pruefung schlimmer als
eine offene Luecke. Genau deshalb ist sie eine Zeile mit Grund, Urheber und
Datum und nicht das Fehlen einer Zeile.

Ausnahmen gelten **je Niederlassung**. Wer in zwei Standorten arbeitet, muss
beide Regelwerke erfuellen; sonst waere eine Ausnahme in A eine Hintertuer fuer
den Einsatz in B.

## Menschen und Fahrzeuge wandern

**Mitarbeiter** haben eine Heimat-Niederlassung (`employees.branch_id`) und
beliebig viele Einsatzorte (`employee_branches`). Die Kopfzahl und die
Ersthelferquote zaehlen nur die Heimat - wer in drei Niederlassungen arbeitet,
darf nicht dreimal zaehlen. Die Einsatzfaehigkeit wird dagegen je Standort
beurteilt und in `readiness_by_branch` mitgeliefert.

**Fahrzeuge** haben eine Heimat (`vehicles.branch_id`) und einen aktuellen
Standort (`vehicles.current_branch_id`). Faellig ist ein Fahrzeug dort, wo es
steht: HU, UVV und der Fahrer sind das Problem der Niederlassung, in der es
gerade eingesetzt wird. Die Fuhrparkliste folgt deshalb
`coalesce(current_branch_id, branch_id)`.

`POST /api/vehicles/{id}/relocate` kennt beide Faelle:

| `permanent` | Wirkung |
| --- | --- |
| `false` (Standard) | Leihweise. Die Heimat behaelt das Fahrzeug im Bestand. |
| `true` | Uebergabe. Die Heimat wechselt, inklusive Kosten und Halterpflichten. |

## Oberflaeche

Die gewaehlte Niederlassung steht in der URL: `#/mitarbeiter/rs`. Ein Link an
eine Kollegin oeffnet damit die Niederlassung, die gemeint war, und nicht die,
auf der ihr eigener Umschalter zuletzt stand. Ohne Segment gilt "alle
Niederlassungen, die ich sehen darf".

Wer nur eine Niederlassung sieht, bekommt weder den Umschalter noch die
Portfolio-Ansicht - fuer ihn ist die Anwendung unveraendert.

## Neue Niederlassung anlegen

Geseedet wird ausschliesslich Remscheid. Namen, Kuerzel und Leitung der
uebrigen Standorte gehoeren der Organisation und nicht einer Seed-Datei; die
Bereichsleitung legt sie unter *Niederlassungen* an (`branch:write`).

Ab diesem Moment gilt jede gruppenweite Regel auch dort. Compliance-Eintraege
fuer eine bereits bestehende Vorgabe entstehen nicht rueckwirkend von selbst -
`POST /api/compliance-rules/{id}/materialise` holt sie nach.

## Migration 0005

Additiv, wie alle Migrationen hier:

- jedes bestehende Konto wird mit **jeder** bestehenden Niederlassung
  verknuepft. Vorher sah jeder alles; ohne diesen Schritt waere die Anwendung
  nach dem Upgrade fuer alle leer. Das Einschraenken ist danach eine bewusste
  Handlung.
- Katalog und Funktionen werden auf `branch_id = NULL` gesetzt, also
  gruppenweit - das waren sie faktisch bereits
- jeder bestehende Compliance-Eintrag bekommt eine oertliche Vorgabe, die ihn
  beschreibt. Gleiche Pflicht innerhalb einer Niederlassung teilt sich eine
  Vorgabe statt jede Zeile eine eigene zu bekommen.
- `employee_branches` wird bewusst **nicht** aus `employees.branch_id`
  vorbefuellt: die Heimat zaehlt bereits als Zuordnung, eine Kopie davon waere
  beim naechsten Wechsel eine Karteileiche
