# Benutzer, Rollen und Anmeldung

Wer hereinkommt, was er darf und wo er es darf - drei Fragen, die bewusst
getrennt beantwortet werden.

| Frage | Antwort in |
| --- | --- |
| Wer ist das? | Entra ID oder die Passwort-Anmeldung |
| Was darf die Person? | die Rolle (`roles.permissions`) |
| Wo darf sie es? | `user_branches` bzw. `users.all_branches` |

Die Trennung der letzten beiden ist der Grund, warum die Rollenliste kurz
bleibt: waeren Rolle und Standort dasselbe, brauchte es bei vier
Niederlassungen sechzehn Rollen, die niemand mehr anfasst.

## Anmeldung

### Microsoft Entra ID (der Regelweg)

`AUTH_MODE=azure_ad`, MSAL im Frontend, Token-Pruefung im Backend gegen die
Tenant-JWKS. Einrichtung Schritt fuer Schritt in
[`azure-ad-setup.md`](azure-ad-setup.md).

### Passwort (der Notfallweg)

Unabhaengig von `AUTH_MODE` verfuegbar, abschaltbar ueber
`AUTH_PASSWORD_LOGIN_ENABLED=false`. Er existiert fuer den Tag, an dem die
App-Registrierung falsch ist oder der Tenant nicht erreichbar - dann muss
trotzdem jemand hereinkommen.

```http
POST /api/auth/login
{ "email": "admin@ops.local", "password": "..." }
-> { "token": "...", "expires_at": "...", "must_change_password": true }
```

Das Token wird wie jedes andere als `Authorization: Bearer` gesendet. Das
Backend erkennt am Aussteller, welchen Pruefpfad es nimmt.

Was diesen Weg tragbar macht:

- **Das Startpasswort kann nicht in Gebrauch bleiben.** Solange
  `must_change_password` gesetzt ist, beantwortet die API ausser der Aenderung
  selbst nichts - kein Lesen, kein Schreiben.
- **Passwoerter werden mit scrypt gehasht** (N = 32768, r = 8, p = 1, Salt je
  Konto), aus der Standardbibliothek, ohne zusaetzliche Abhaengigkeit.
- **Fuenf Fehlversuche sperren das Konto fuer 15 Minuten.** Gezaehlt wird pro
  Konto; die Antwort ist bei falschem Passwort und unbekannter Adresse
  wortgleich, sonst waere das Anmeldeformular ein Verzeichnis gueltiger
  E-Mail-Adressen.
- **Jede Anmeldung steht im Protokoll**, die gescheiterten ebenso.
- **Sitzungen lassen sich zurueckziehen.** Jedes Token traegt eine
  `token_version`; ein Passwortwechsel, ein Abmelden oder eine Deaktivierung
  erhoeht sie und macht damit alle aelteren Token wertlos - ohne
  Sitzungstabelle, die jemand aufraeumen muesste.

### Entwicklungsmodus

`AUTH_MODE=dev`: der Aufrufer schickt `X-User-Id`, die Oberflaeche waehlt die
Identitaet oben rechts. Das Backend verweigert den Start, wenn gleichzeitig
`APP_ENV=production` gesetzt ist. Der Notfall-Administrator taucht in dieser
Auswahl nicht auf - er ist keine Rolle zum Ausprobieren.

## Der Notfallzugang

Beim ersten Start legt der Seed genau ein Konto an, wenn keines existiert:

| Feld | Wert |
| --- | --- |
| E-Mail | `ADMIN_EMAIL`, Vorgabe `admin@ops.local` |
| Rolle | `Administrator` (alle Berechtigungen) |
| Niederlassungen | alle |
| Startpasswort | `ADMIN_INITIAL_PASSWORD`, Vorgabe `BSchmitt-Ops-2026!` |

**Das Startpasswort gehoert geaendert, und die Anwendung setzt das durch.** Es
steht in der Konfiguration, damit es nicht auf einem Zettel steht; nach der
ersten Anmeldung darf `ADMIN_INITIAL_PASSWORD` aus der `.env` verschwinden.

Der Seed laeuft bei jedem Start, legt das Konto aber nur an, wenn es weder die
Adresse noch ein anderes Konto mit der Administratorrolle gibt. Ein Konto, dem
die Passwort-Anmeldung entzogen wurde, bekommt sie also nicht heimlich zurueck.

In Produktion verweigert das Backend den Start, solange die Passwort-Anmeldung
aktiv ist und `AUTH_SESSION_SECRET` fehlt: ohne festen Schluessel wuerde jeder
Neustart alle Sitzungen beenden, und mehrere Instanzen wuerden verschieden
signieren.

## Rollen

Fuenf Rollen kommen aus dem Programm (`app/permissions.py`) und werden bei jedem
Start abgeglichen - eine neue Berechtigung erreicht so bestehende Installationen.
Genau deshalb sind sie in der Oberflaeche nicht editierbar: die naechste
Aenderung im Code wuerde jede Anpassung ueberschreiben.

| Rolle | Gedacht fuer |
| --- | --- |
| Administrator | Verwaltung des Werkzeugs, Notfallzugang |
| Bereichsleiter | verantwortet mehrere Niederlassungen, setzt Gruppenvorgaben |
| Niederlassungsleiter | fuehrt eine Niederlassung, volle Fachrechte vor Ort |
| HSE / Compliance | Arbeitssicherheit ueber die Standorte hinweg |
| Betrachter | liest mit |

Fuer alles andere legt die Verwaltung **eigene Rollen** an, mit frei
zusammengestellten Berechtigungen. Der Editor zeigt jede Berechtigung mit
deutschem Namen und einem Satz dazu - wer Rechte vergibt, soll nicht raten
muessen, was `rule:write` bedeutet.

`user:read` fehlt bewusst in der Betrachterrolle: die Kontoliste mit Rollen und
Standortzuordnungen ist Verwaltung, nicht Lesestoff fuer alle.

## Konten

- **Anlegen** mit Name, E-Mail (das ist die Anmeldung), Rolle und
  Niederlassungen. Ein Passwort ist optional und der Ausnahmefall - wer sich
  ueber Microsoft anmeldet, braucht keines, und ein Passwort, das es nicht
  gibt, kann nicht verloren gehen.
- **Ohne Zuordnung sieht ein Konto nichts.** Kein Fehler, sondern Absicht: der
  leere Bereich ist die sichere Vorgabe.
- **Deaktivieren statt loeschen.** Sobald ein Konto irgendwo als
  Verantwortlicher steht oder etwas im Protokoll hinterlassen hat, verweigert
  die API das Loeschen und sagt auch warum - sonst bricht die Spur, wer was
  getan hat.
- **Das letzte Konto mit `user:write` kann sich diese Berechtigung nicht selbst
  nehmen.** Sonst waere die einzige Reparatur eine Datenbankkonsole.
- **Passwort setzen** ist der Weg zurueck nach einer Aussperrung. Es ist immer
  ein Startpasswort und im Protokoll steht nur, *dass* es gesetzt wurde.

## Was wo liegt

| Zweck | Ort |
| --- | --- |
| Hashing, Passwortregeln, Sitzungstoken | `backend/app/security.py` |
| Anmeldung, Abmeldung, Passwortwechsel | `backend/app/routers/auth_routes.py` |
| Konten, Rollen, Berechtigungskatalog | `backend/app/routers/users.py` |
| Aufloesung des Aufrufers je Modus | `backend/app/auth.py` |
| Berechtigungen und Rollenvorlagen | `backend/app/permissions.py` |
| Anmeldebildschirm und Passwortdialog | `frontend/src/components/Login.tsx` |
| Benutzeroberflaeche der Verwaltung | `frontend/src/views/UsersView.tsx` |
