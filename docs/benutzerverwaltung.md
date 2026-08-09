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

## Entgeltdaten: Berechtigung, zweiter Faktor, Leseprotokoll

Gehaelter liegen in einer eigenen Tabelle (`employee_salaries`) und hinter einem
eigenen Endpunkt - **nicht** als Spalte im Mitarbeiterprofil. Das Profil reist
in jeder Mitarbeiterantwort mit; ein Feld, das niemals versehentlich
mitgeschickt werden darf, gehoert nicht in eine Nutzlast, die fuer etwas
anderes gebaut wurde.

Drei Schranken, die verschiedene Aufgaben haben:

| Schranke | Beantwortet |
| --- | --- |
| `salary:read` / `salary:write` | Wer darf ueberhaupt hinsehen |
| Step-up (zweiter Faktor) | Wie sicher ist es, dass er es *jetzt gerade* ist |
| Protokoll **jedes Lesezugriffs** | Wer hat hineingesehen |

Die dritte ist die, die bei Entgeltdaten am haeufigsten gebraucht wird. Das
uebrige Protokoll haelt nur Aenderungen fest; hier wird auch das blosse Ansehen
vermerkt. **Der Betrag steht nie im Protokoll** - das Protokoll liest jeder mit
`audit:read`, und dorthin die Zahl zu schreiben hiesse, sie genau den Leuten zu
geben, vor denen der Endpunkt sie schuetzt.

Keine der fuenf Standardrollen bringt `salary:read` mit, ausser den beiden
Wildcard-Rollen (Administrator, Bereichsleiter). Wer sonst Entgelt sehen soll,
bekommt eine eigene Rolle.

### Der zweite Faktor

Der Regelweg ist der **Authentifizierungskontext von Entra ID**:

1. Im Portal unter *Sicherheit -> Bedingter Zugriff -> Authentifizierungskontext*
   einen Kontext anlegen, z. B. `c1` mit dem Namen „Entgeltdaten".
2. Eine Richtlinie fuer bedingten Zugriff auf diesen Kontext anwenden, die
   Multi-Faktor-Authentifizierung verlangt.
3. `AZURE_SALARY_AUTH_CONTEXT=c1` setzen (Vorgabe).

Beim Zugriff auf ein Entgeltfeld antwortet die API mit `401` und einem
Claims-Challenge (`WWW-Authenticate: Bearer error="insufficient_claims"`, und
derselbe Wert im Antwortkoerper, weil CORS eigene Header sonst verbirgt). MSAL
fordert damit ein neues Token an, Entra ID verlangt die Bestaetigung, und das
neue Token traegt `acrs: ["c1"]`. Das staerkere Token bleibt nur im
Arbeitsspeicher der Seite und wird ausschliesslich fuer Entgeltanfragen
verwendet.

**Der Authentifizierungskontext braucht Entra ID P1.** Ohne diese Lizenz greift
ein Rueckfall: das Backend akzeptiert ein Token, dessen `amr`-Claim `mfa`
enthaelt und dessen `auth_time` hoechstens
`SALARY_STEP_UP_MAX_AGE_SECONDS` (Vorgabe 15 Minuten) alt ist. Schwaecher, weil
es keine Bestaetigung *fuer diese eine Handlung* erzwingen kann. Je nach Tenant
muessen `amr` und `auth_time` in der App-Registrierung als optionale Claims
aktiviert werden.

**Ueber den Notfallzugang mit Passwort gibt es keinen Zugriff auf
Entgeltdaten** - unabhaengig von der Rolle. Ein Notfallweg, der auch die
sensibelsten Daten oeffnet, ist kein Notfallweg mehr.

Im Entwicklungsmodus (`AUTH_MODE=dev`) gilt der Step-up als erfuellt: dort gibt
es keinen zweiten Faktor zu verlangen, und der Modus ist in Produktion ohnehin
gesperrt.

## Was wo liegt

| Zweck | Ort |
| --- | --- |
| Hashing, Passwortregeln, Sitzungstoken | `backend/app/security.py` |
| Anmeldung, Abmeldung, Passwortwechsel | `backend/app/routers/auth_routes.py` |
| Konten, Rollen, Berechtigungskatalog | `backend/app/routers/users.py` |
| Aufloesung des Aufrufers je Modus | `backend/app/auth.py` |
| Berechtigungen und Rollenvorlagen | `backend/app/permissions.py` |
| Step-up und Claims-Challenge | `backend/app/auth.py` (`requires_step_up`) |
| Entgelt-Endpunkte | `backend/app/routers/salary.py` |
| Anmeldebildschirm und Passwortdialog | `frontend/src/components/Login.tsx` |
| Benutzeroberflaeche der Verwaltung | `frontend/src/views/UsersView.tsx` |
