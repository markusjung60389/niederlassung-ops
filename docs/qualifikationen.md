# Funktionen, Qualifikationen und Einsatzfaehigkeit

Die fachliche Grundlage ab Version 1.1.0.

## Warum

Vor 1.1.0 hingen die Pflichten an einzelnen Personen: `employee_profiles` hatte
feste Spalten fuer IPAF, Erste Hilfe und Fuehrerscheinkontrolle, waehrend
`employee_qualifications` dasselbe generisch konnte. Zwei Orte fuer dieselbe
Tatsache, und nur der generische konnte ein Dokument tragen - ausgerechnet die
fuenf wichtigsten Fristen waren also die, zu denen kein Nachweis hinterlegbar
war.

`employees.role` war Freitext. Aus einer Berufsbezeichnung folgte nichts; die
Niederlassungsleitung musste sich fuer jede Person einzeln merken, was
erforderlich ist.

## Modell

```
   Qualifikationsart ──────┐
   (Katalog)               │  Anforderung
   IPAF                    ├──────────────►  Funktion
   Fuehrerscheinkontrolle  │  Pflicht/opt.   Projektleiter
   Erste Hilfe             │                 Service-Techniker
   Unterweisung            │                 Monteur
        │                  │                      │
        │ Ist              │                      │ hat
        ▼                  │                      ▼
   Qualifikation  ◄─────────────────────────  Mitarbeiter
   gueltig bis + Nachweis
```

| Tabelle | Inhalt |
| --- | --- |
| `qualification_types` | Katalog: Bezeichnung, Gueltigkeitsdauer, Vorwarnzeit, Nachweispflicht, Rechtsgrundlage |
| `job_roles` | Funktionen der Niederlassung |
| `job_role_requirements` | Funktion x Qualifikationsart, `mandatory` ja/nein |
| `employee_qualifications` | Was tatsaechlich vorliegt, mit `issued_on`, `valid_until` und Dokument |

**Funktion, nicht Rolle.** `roles` ist im Code die *Berechtigungsrolle* am
Benutzerkonto. Die fachliche Zuordnung heisst deshalb ueberall `job_role`
beziehungsweise in der Oberflaeche "Funktion". Die eine entscheidet, was jemand
anklicken darf, die andere, was er vor Ort tun darf.

## Zustaende je Anforderung

Berechnet in `app/readiness.py`, nie gespeichert.

| Zustand | Bedeutung |
| --- | --- |
| `ok` | gueltig, und der geforderte Nachweis liegt vor |
| `evidence_missing` | Datum gueltig, aber kein Dokument hinterlegt |
| `expiring` | laeuft innerhalb der Vorwarnzeit des Katalogs ab |
| `expired` | Gueltigkeit ueberschritten |
| `undated` | erfasst, aber ohne Gueltigkeitsdatum, obwohl die Art eine Frist hat |
| `missing` | nicht erfasst |

Mehrere Eintraege derselben Art sind vorgesehen: eine Auffrischung wird als
neue Zeile erfasst, gezaehlt wird die am laengsten gueltige.

## Einsatzfaehigkeit

| Stufe | Regel |
| --- | --- |
| **nicht einsatzfaehig** | eine Pflichtanforderung ist `missing`, `expired` oder `undated` |
| **eingeschraenkt** | eine Pflichtanforderung ist `expiring` oder `evidence_missing` |
| **einsatzfaehig** | sonst |

Optionale Anforderungen wirken nie auf die Stufe. Eine optionale Qualifikation,
die niemand hat, ist keine Luecke, sondern schlicht nicht einschlaegig - sonst
stuende jeder Mitarbeiter dauerhaft auf Gelb und die Ampel waere wertlos.

Ausgeschiedene Mitarbeiter (`status = inactive`) loesen keine Erinnerungen mehr
aus und stehen auf Gruen, bleiben aber vollstaendig erhalten. Loeschen ist
weiterhin moeglich, aber der falsche Weg: Nachweise unterliegen
Aufbewahrungsfristen.

## Ablaufdatum

Traegt die Qualifikationsart eine Gueltigkeitsdauer, wird `valid_until` aus
`issued_on` berechnet (`domain.add_months`, am Monatsende korrekt gekappt: ein
Kurs am 31.08. mit sechs Monaten laeuft am 28.02. ab). Ein ausdruecklich
gesetztes `valid_until` hat Vorrang.

## Katalog aendern

Der Katalog ist Referenzdaten, keine fest verdrahtete Regel. Unter
*Stammdaten* lassen sich Qualifikationsarten anlegen und die Anforderungen je
Funktion auf Pflicht, optional oder nicht gefordert stellen. Aenderungen wirken
sofort auf die Einsatzfaehigkeit aller Mitarbeiter dieser Funktion.

Die Erstbefuellung steht in `app/catalog.py` und wird beim Start ergaenzt -
vorhandene Zeilen werden nie ueberschrieben, damit eine angepasste
Gueltigkeitsdauer erhalten bleibt.

## Querpruefungen

- **Fahrer und Fahrzeug**: ist einem Fahrzeug ein Mitarbeiter zugeordnet,
  dessen Fuehrerscheinkontrolle fehlt oder ueberfaellig ist, weist die
  Fahrzeugliste darauf hin. Das ist der Fall, der zur Halterhaftung fuehrt.
- **Ersthelferquote**: `readiness.first_aider_target` rechnet die Mindestzahl
  nach DGUV Vorschrift 1 Paragraf 26 (ab drei Beschaeftigten zehn Prozent,
  aufgerundet, mindestens einer) und vergleicht sie mit den benannten
  Ersthelfern.

## Migration der Bestandsdaten

`0004_qualifications` **kopiert** die fuenf Datumspaare aus
`employee_profiles` nach `employee_qualifications`:

| Profilspalte | Qualifikationsart |
| --- | --- |
| `driver_license_next_check` / `_last_check` | Fuehrerscheinkontrolle |
| `first_aid_valid_until` / `first_aid_last_course` | Erste-Hilfe-Ausbildung |
| `ipaf_valid_until` / `ipaf_last_training` | IPAF-Bedienerschulung |
| `general_instruction_next` / `_last` | Jaehrliche Unterweisung |
| `occupational_health_next` / `_last` | Arbeitsmedizinische Vorsorge |

Die Quellspalten bleiben unveraendert stehen und werden nur nicht mehr gelesen.
Stellt sich die Zuordnung fuer eine Niederlassung als falsch heraus, sind die
Originalwerte noch da - ohne Ruecksicherung. Entfernt werden sie erst in einer
spaeteren Version, wenn sich die Migration im Betrieb bewaehrt hat.

Freitextrollen werden ueber eine Aliasliste mit den Funktionen verknuepft
(`Servicetechniker`, `Service-Techniker`, `Techniker` → Service-Techniker und
so weiter). Was nicht passt, bleibt ohne Funktion und wird in der Oberflaeche
zugeordnet; weiter zu raten wuerde Menschen an die falschen Anforderungen
haengen.
