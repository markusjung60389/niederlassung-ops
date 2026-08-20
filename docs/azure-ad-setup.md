# Microsoft Entra ID (Azure AD) - Vorbereitung und Aktivierung

Der Code ist vollstaendig vorhanden und getestet, aber **nicht aktiv**:
`AUTH_MODE` steht auf `dev`. Es fehlt nichts mehr an der Anwendung - nur die
App-Registrierungen im Mandanten und die Werte dazu. Dieses Dokument beschreibt
beides, in der Reihenfolge, in der es getan wird.

## Was bereits implementiert ist

| Baustein | Ort | Status |
| --- | --- | --- |
| Token-Validierung (Signatur, Issuer, Audience, Ablauf) | `backend/app/auth.py` | fertig, getestet |
| JWKS-Abruf inkl. Cache und Key-Rollover | `backend/app/auth.py` (`JwksCache`) | fertig |
| Rollen-Mapping App-Rolle/Gruppe -> lokale Rolle | `backend/app/auth.py` (`_claim_role_names`) | fertig |
| Just-in-time-Anlage und Verknuepfung per E-Mail | `backend/app/auth.py` (`_resolve_azure_user`) | fertig |
| Berechtigungspruefung je Endpunkt | `backend/app/permissions.py`, `main.py` | fertig, aktiv |
| Frontend-Tokenbeschaffung (MSAL) | `frontend/src/auth.ts` | fertig, wartet auf die App-Registrierung |
| Notfall-Anmeldung mit Passwort | `backend/app/security.py`, `app/routers/auth_routes.py` | fertig, aktiv |

`backend/tests/test_azure_ad.py` signiert Token mit einem lokalen Testschluessel
und laesst sie durch den echten Validierungspfad laufen: gueltige Token, abgelaufene
Token, falsche Audience, falscher Issuer, fremder Signaturschluessel, `alg: none`,
Rollen-Mapping, Provisionierung und Verknuepfung bestehender Konten.

## Zwei Wege, und der einfachere zuerst

Die Rolle kann aus dem Verzeichnis kommen oder aus dieser Anwendung. Das ist
der einzige Unterschied, und er entscheidet ueber die Haelfte der Portalarbeit.

| | **A: Konten hier pflegen** (empfohlen fuer den Anfang) | **B: Rollen aus Entra ID** |
| --- | --- | --- |
| Im Portal noetig | zwei App-Registrierungen | zwei Registrierungen **plus** App-Rollen und Zuweisungen je Person |
| Rolle kommt aus | der Benutzerverwaltung dieser Anwendung | dem `roles`-Claim des Tokens |
| Neue Person | Konto anlegen (Name, E-Mail, Rolle, Niederlassung) | Person einer App-Rolle zuweisen **und** Niederlassung hier setzen |
| Person geht | Konto deaktivieren | Zuweisung entziehen; das Konto bleibt hier stehen |
| Wer pflegt | die Bereichsleitung, ohne Portalzugang | die IT im Portal |
| Einstellung | `AZURE_AUTO_PROVISION_USERS=false`, `AZURE_ROLE_MAP` leer | `AZURE_AUTO_PROVISION_USERS=true` mit `AZURE_ROLE_MAP` |

**Weg A** heisst: Sie legen die Person unter *Benutzer* mit ihrer dienstlichen
E-Mail-Adresse, ihrer Rolle und ihren Niederlassungen an. Sie meldet sich mit
*Mit Microsoft anmelden* an, das Backend erkennt sie an der Adresse aus dem
Token, merkt sich dauerhaft ihre Entra-Objekt-ID und laesst sie mit der hier
gesetzten Rolle herein. App-Rollen, Rollenzuweisungen und `AZURE_ROLE_MAP`
entfallen vollstaendig - Schritt 1a Punkt 4, Punkt 5 und Schritt 2 koennen Sie
ueberspringen.

Der Preis: Ein Konto, das es hier nicht gibt, kommt nicht herein - auch wenn
die Person im Verzeichnis existiert. Genau das ist bei vier Niederlassungen
und einer ueberschaubaren Zahl von Konten aber eher Vorteil als Aufwand: die
Liste, wer Zugriff hat, steht dort, wo auch steht, was er darf.

**Zwei Faelle, in denen sich Weg B lohnt:** viele Konten, die ueber
Gruppenmitgliedschaften kommen und gehen sollen, oder die Vorgabe, dass Zugriff
ausschliesslich ueber das Verzeichnis vergeben wird. Beides laesst sich
jederzeit nachtraeglich umstellen - `AZURE_ROLE_MAP` setzen, Provisionierung
einschalten, fertig; die bestehenden Konten bleiben ueber ihre Objekt-ID
verknuepft.

## Schritt 1: App-Registrierungen anlegen

Zwei Registrierungen, weil SPA und API unterschiedliche Token-Typen brauchen.

### 1a. API (`Remscheid Ops API`)

1. Entra ID -> App-Registrierungen -> Neue Registrierung, Name `Remscheid Ops API`,
   Konten nur im eigenen Verzeichnis.
2. **Eine API verfuegbar machen** -> Anwendungs-ID-URI setzen: `api://<API-CLIENT-ID>`.
3. Bereich hinzufuegen: `access_as_user`, Zustimmung durch Administrator und Benutzer.
4. **App-Rollen** anlegen (Typ jeweils `Benutzer/Gruppen`) - **nur fuer Weg B**,
   bei Weg A entfaellt dieser Punkt:

   | Wert | Anzeigename | Gedacht fuer |
   | --- | --- | --- |
   | `OpsAreaManager` | Bereichsleitung | Vollzugriff ueber alle Niederlassungen |
   | `OpsManager` | Niederlassungsleitung | Volle Fachrechte in der eigenen Niederlassung |
   | `OpsHSE` | HSE / Compliance | Compliance und Incidents schreiben, Personal lesen |
   | `OpsViewer` | Betrachter | nur Lesen |

5. Unter **Unternehmensanwendungen** die Benutzer bzw. Gruppen diesen Rollen
   zuweisen - ebenfalls nur fuer Weg B.

### 1b. SPA (`Remscheid Ops Frontend`)

1. Neue Registrierung, Name `Remscheid Ops Frontend`.
2. Plattform **Einzelseitenanwendung (SPA)**, Redirect-URI = Frontend-Origin,
   z. B. `https://ops.example.com` (lokal `http://localhost:3000`).
3. **API-Berechtigungen** -> Meine APIs -> `Remscheid Ops API` -> `access_as_user`,
   danach Administratorzustimmung erteilen.

## Schritt 2: Rollen zuordnen (nur Weg B)

Bei **Weg A** bleibt `AZURE_ROLE_MAP` leer und
`AZURE_AUTO_PROVISION_USERS=false`. Die Rolle steht am Konto und ueberlebt jede
Anmeldung unveraendert; ohne Treffer im Mapping ruehrt das Backend sie nicht an.
Ein Token ohne bekannte Rolle fuehrt dann nicht zu einem Konto ohne Rechte,
sondern zu dem Konto, das Sie vorbereitet haben.



Die Werte der App-Rollen werden auf die Rollennamen der `roles`-Tabelle abgebildet
(angelegt durch `backend/app/seed.py`):

```env
AZURE_ROLE_MAP=OpsAreaManager=Bereichsleiter,OpsManager=Niederlassungsleiter,OpsHSE=HSE / Compliance,OpsViewer=Betrachter
```

Gruppen-Objekt-IDs funktionieren genauso, falls statt App-Rollen mit Gruppen
gearbeitet wird (`groups`-Claim muss dann im Tokenkonfigurations-Blatt aktiviert sein):

```env
AZURE_ROLE_MAP=8f3c...-uuid=Niederlassungsleiter
```

Ohne Treffer bekommt der Benutzer **keine** Berechtigungen und laeuft in 403 —
gewollt. `AZURE_DEFAULT_ROLE_NAME` kann eine Auffangrolle setzen.

## Schritt 3: Backend umschalten

Weg A - die Konten stehen in der Anwendung:

```env
AUTH_MODE=azure_ad
AZURE_TENANT_ID=<Verzeichnis-(Mandanten)-ID>
AZURE_CLIENT_ID=<API-CLIENT-ID>
AZURE_API_AUDIENCE=api://<API-CLIENT-ID>     # optional, wird sonst abgeleitet
AZURE_AUTO_PROVISION_USERS=false
APP_ENV=production
```

Weg B - die Rollen kommen aus dem Verzeichnis:

```env
AUTH_MODE=azure_ad
AZURE_TENANT_ID=<Verzeichnis-(Mandanten)-ID>
AZURE_CLIENT_ID=<API-CLIENT-ID>
AZURE_ROLE_MAP=OpsAreaManager=Bereichsleiter,OpsManager=Niederlassungsleiter,OpsHSE=HSE / Compliance,OpsViewer=Betrachter
AZURE_AUTO_PROVISION_USERS=true
APP_ENV=production
```

Beim Start wird geprueft: `AUTH_MODE=azure_ad` ohne Tenant/Client bricht ab,
`APP_ENV=production` zusammen mit `AUTH_MODE=dev` ebenfalls.

Bestehende lokale Konten werden beim ersten Login ueber die E-Mail-Adresse
(`preferred_username`) verknuepft, **ohne Ruecksicht auf Gross- und
Kleinschreibung**, danach ueber die Entra-Objekt-ID (`oid`). Damit bleiben
`owner_user_id` und Audit-Log-Eintraege stabil, auch wenn die Person spaeter
heiratet und ihre Adresse wechselt.

Wichtig ist nur, dass die Adresse am Konto dieselbe Person meint wie die im
Verzeichnis. Passt sie nicht, sagt die Anmeldung das bei abgeschalteter
Provisionierung im Klartext und nennt die erwartete Adresse.

## Schritt 4: Frontend umschalten

MSAL ist eingebaut (`@azure/msal-browser`, dynamisch geladen), es ist also nur
noch eine Frage der Konfiguration. Der Anmeldebildschirm zeigt dann
*Mit Microsoft anmelden*; Token werden still erneuert und nur bei abgelaufener
Sitzung mit einem Popup.

**Mit dem veroeffentlichten Image (`docker-compose.release.yml`) reicht die
`.env` und ein Neustart** - kein Neubau. Der Container-Entrypoint schreibt bei
jedem Start `config.js`, und die Anwendung liest ihre Werte von dort:

```env
AUTH_MODE=azure_ad
AZURE_TENANT_ID=<Verzeichnis-(Mandanten)-ID>
AZURE_FRONTEND_CLIENT_ID=<SPA-CLIENT-ID>
AZURE_API_SCOPE=api://<API-CLIENT-ID>/access_as_user
```

```bash
docker compose -f docker-compose.release.yml up -d
```

Nur wer das Image **selbst baut** (`docker-compose.yml`), kann die Werte
stattdessen als Build-Args einbacken (`VITE_AUTH_MODE`, `VITE_AZURE_TENANT_ID`,
`VITE_AZURE_CLIENT_ID`, `VITE_AZURE_API_SCOPE`); `config.js` sticht sie zur
Laufzeit ohnehin. Es sind ausschliesslich oeffentliche Bezeichner, keine
Secrets - sie stehen im ausgelieferten JavaScript und sollen das auch.

### Reihenfolge beim Umschalten

Backend und Frontend gehoeren in denselben Neustart. Steht das Backend schon auf
`azure_ad` und das Frontend noch auf `dev`, schickt die Oberflaeche weiter
`X-User-Id`, bekommt 401 und landet auf dem Anmeldebildschirm - unschoen, aber
nicht gefaehrlich: die Passwort-Anmeldung funktioniert in beiden Faellen.

Nach dem Umschalten:

- `/api/auth/dev-users` antwortet mit 404, die Identitaetsauswahl oben rechts
  verschwindet.
- Bei **Weg B** hat ein neu angelegtes Konto **noch keine Niederlassung** und
  sieht deshalb nichts; die Zuordnung passiert nach der ersten Anmeldung unter
  *Benutzer*. Bei **Weg A** stellt sich die Frage nicht: dort ist die
  Niederlassung schon gesetzt, bevor sich jemand zum ersten Mal anmeldet.

## Schritt 5: Pruefen

```http
GET /api/auth/me
Authorization: Bearer <token>
```

Erwartet: `source: "azure-ad"`, der gemappte `role_name` und die Berechtigungsliste.
`/api/auth/dev-users` liefert unter `azure_ad` bewusst 404.

## Schritt 6: Authentifizierungskontext fuer Entgeltdaten

Nur noetig, wenn Gehaelter gepflegt werden - und nur mit Entra ID P1:

1. *Sicherheit -> Bedingter Zugriff -> Authentifizierungskontext*: Kontext `c1`
   anlegen, Name z. B. „Entgeltdaten", *Fuer Apps veroeffentlichen* aktivieren.
2. Eine Richtlinie fuer bedingten Zugriff auf diesen Kontext anwenden, die
   Multi-Faktor-Authentifizierung verlangt.
3. `AZURE_SALARY_AUTH_CONTEXT=c1` im Backend setzen (Vorgabe).

Ohne P1 greift der Rueckfall ueber `amr`/`auth_time`; dafuer muessen die beiden
in der API-App-Registrierung unter *Tokenkonfiguration* als optionale Claims
aktiviert sein. Einzelheiten in
[`benutzerverwaltung.md`](benutzerverwaltung.md#entgeltdaten-berechtigung-zweiter-faktor-leseprotokoll).

## Zuruecknehmen

`AUTH_MODE=dev` ist zusammen mit `APP_ENV=production` gesperrt, ein
Zurueckschalten waere also ein Rueckschritt in beidem. Der vorgesehene Weg
zurueck ist deshalb nicht der Modus, sondern die Tuer daneben:

## Der Weg zurueck, wenn Entra ID nicht funktioniert

Genau dafuer gibt es die Passwort-Anmeldung. Sie laeuft unabhaengig von
`AUTH_MODE` und ist der Grund, warum eine kaputte App-Registrierung kein
Totalausfall ist:

```http
POST /api/auth/login
{ "email": "admin@ops.local", "password": "<Startpasswort>" }
```

Das Startpasswort steht in `ADMIN_INITIAL_PASSWORD` und muss bei der ersten
Anmeldung geaendert werden - bis dahin beantwortet die API nichts anderes.
Einzelheiten in [`benutzerverwaltung.md`](benutzerverwaltung.md).

## Rollenmodell

| Rolle | Berechtigungen |
| --- | --- |
| Bereichsleiter | `*` |
| Niederlassungsleiter | alle Bereichsrechte, aber **kein** `rule:write` und `branch:write` |
| HSE / Compliance | `compliance:*`, `incident:*`, `personnel:read`, `fleet:read`, `assessment:read`, `sales:read`, `rule:read`, `branch:read`, `agent:run`, `audit:read` |
| Betrachter | alle `:read` |

Definiert in `backend/app/permissions.py`. Die Presets sind fuehrend: bei einer
Aenderung werden die Rollen beim naechsten Start abgeglichen.

Die Rolle sagt nur, **was** jemand darf. **Wo** er es darf, haengt am Konto:
`users.all_branches` fuer die Bereichsleitung, sonst je Zeile in
`user_branches`. Ein frisch ueber Azure AD angelegtes Konto hat noch keine
Zuordnung und sieht damit nichts - die Niederlassung wird nach der ersten
Anmeldung gesetzt. Siehe [`niederlassungen.md`](niederlassungen.md).

## Offene Punkte vor dem Produktivgang

- App-Registrierungen anlegen und die IDs setzen (Schritt 1 bis 4). Der Code
  wartet nur noch darauf.
- Redirect-URI der SPA-Registrierung auf den echten Frontend-Origin setzen -
  die Anwendung meldet sich per Popup gegen `window.location.origin` an.
- `AUTH_SESSION_SECRET` setzen - sonst verweigert das Backend in Produktion den
  Start, solange die Passwort-Anmeldung aktiv ist.
- Startpasswort des Notfallzugangs aendern (passiert bei der ersten Anmeldung
  von selbst) und `ADMIN_INITIAL_PASSWORD` aus der `.env` entfernen.
- TLS vor das Backend setzen; Bearer-Token duerfen nicht ueber HTTP laufen.
- `CORS_ALLOW_ORIGINS` auf die echte Frontend-Domain setzen.
- Entscheiden, ob `AZURE_AUTO_PROVISION_USERS=false` gelten soll, damit nur
  vorab angelegte Konten Zugriff bekommen.
