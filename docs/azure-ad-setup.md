# Microsoft Entra ID (Azure AD) - Vorbereitung und Aktivierung

Der Code ist vollstaendig vorhanden und getestet, aber **nicht aktiv**.
`AUTH_MODE` steht auf `dev`. Dieses Dokument beschreibt, was im Azure-Portal
angelegt werden muss und welche Schalter danach umgelegt werden.

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

## Schritt 1: App-Registrierungen anlegen

Zwei Registrierungen, weil SPA und API unterschiedliche Token-Typen brauchen.

### 1a. API (`Remscheid Ops API`)

1. Entra ID -> App-Registrierungen -> Neue Registrierung, Name `Remscheid Ops API`,
   Konten nur im eigenen Verzeichnis.
2. **Eine API verfuegbar machen** -> Anwendungs-ID-URI setzen: `api://<API-CLIENT-ID>`.
3. Bereich hinzufuegen: `access_as_user`, Zustimmung durch Administrator und Benutzer.
4. **App-Rollen** anlegen (Typ jeweils `Benutzer/Gruppen`):

   | Wert | Anzeigename | Gedacht fuer |
   | --- | --- | --- |
   | `OpsAreaManager` | Bereichsleitung | Vollzugriff ueber alle Niederlassungen |
   | `OpsManager` | Niederlassungsleitung | Volle Fachrechte in der eigenen Niederlassung |
   | `OpsHSE` | HSE / Compliance | Compliance und Incidents schreiben, Personal lesen |
   | `OpsViewer` | Betrachter | nur Lesen |

5. Unter **Unternehmensanwendungen** die Benutzer bzw. Gruppen diesen Rollen zuweisen.

### 1b. SPA (`Remscheid Ops Frontend`)

1. Neue Registrierung, Name `Remscheid Ops Frontend`.
2. Plattform **Einzelseitenanwendung (SPA)**, Redirect-URI = Frontend-Origin,
   z. B. `https://ops.example.com` (lokal `http://localhost:3000`).
3. **API-Berechtigungen** -> Meine APIs -> `Remscheid Ops API` -> `access_as_user`,
   danach Administratorzustimmung erteilen.

## Schritt 2: Rollen zuordnen

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

```env
AUTH_MODE=azure_ad
AZURE_TENANT_ID=<Verzeichnis-(Mandanten)-ID>
AZURE_CLIENT_ID=<API-CLIENT-ID>
AZURE_API_AUDIENCE=api://<API-CLIENT-ID>     # optional, wird sonst abgeleitet
AZURE_ROLE_MAP=OpsAreaManager=Bereichsleiter,OpsManager=Niederlassungsleiter,OpsHSE=HSE / Compliance,OpsViewer=Betrachter
AZURE_AUTO_PROVISION_USERS=true
APP_ENV=production
```

Beim Start wird geprueft: `AUTH_MODE=azure_ad` ohne Tenant/Client bricht ab,
`APP_ENV=production` zusammen mit `AUTH_MODE=dev` ebenfalls.

Bestehende lokale Konten werden beim ersten Login ueber die E-Mail-Adresse
(`preferred_username`) verknuepft, danach ueber die Entra-Objekt-ID (`oid`).
Damit bleiben `owner_user_id` und Audit-Log-Eintraege stabil.

## Schritt 4: Frontend umschalten

MSAL ist eingebaut (`@azure/msal-browser`, dynamisch geladen), es ist also nur
noch eine Frage der Konfiguration. Der Anmeldebildschirm zeigt dann
*Mit Microsoft anmelden*; Token werden still erneuert und nur bei abgelaufener
Sitzung mit einem Popup. Build-Variablen:

```env
VITE_AUTH_MODE=azure_ad
VITE_AZURE_TENANT_ID=<Verzeichnis-(Mandanten)-ID>
VITE_AZURE_CLIENT_ID=<SPA-CLIENT-ID>
VITE_AZURE_API_SCOPE=api://<API-CLIENT-ID>/access_as_user
```

Ueber Compose sind das `AUTH_MODE`, `AZURE_TENANT_ID`, `AZURE_FRONTEND_CLIENT_ID`
und `AZURE_API_SCOPE` in der `.env`; sie werden als Build-Args durchgereicht.
Vite backt sie zur Buildzeit ein — nach einer Aenderung muss das Frontend-Image
neu gebaut werden. Es sind ausschliesslich oeffentliche Bezeichner, keine Secrets.

## Schritt 5: Pruefen

```http
GET /api/auth/me
Authorization: Bearer <token>
```

Erwartet: `source: "azure-ad"`, der gemappte `role_name` und die Berechtigungsliste.
`/api/auth/dev-users` liefert unter `azure_ad` bewusst 404.

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
- `AUTH_SESSION_SECRET` setzen - sonst verweigert das Backend in Produktion den
  Start, solange die Passwort-Anmeldung aktiv ist.
- Startpasswort des Notfallzugangs aendern (passiert bei der ersten Anmeldung
  von selbst) und `ADMIN_INITIAL_PASSWORD` aus der `.env` entfernen.
- TLS vor das Backend setzen; Bearer-Token duerfen nicht ueber HTTP laufen.
- `CORS_ALLOW_ORIGINS` auf die echte Frontend-Domain setzen.
- Entscheiden, ob `AZURE_AUTO_PROVISION_USERS=false` gelten soll, damit nur
  vorab angelegte Konten Zugriff bekommen.
