# Release und Container-Veroeffentlichung

Images liegen auf der GitHub Container Registry:

- `ghcr.io/markusjung60389/niederlassung-ops-backend`
- `ghcr.io/markusjung60389/niederlassung-ops-frontend`

## Einmalige Einrichtung

Nur beim allerersten Release noetig.

1. **Branch nach `main` bringen.** Der Release-Workflow existiert erst dort,
   wo er auch liegt - ein Tag auf einem Branch ohne die Workflow-Datei loest
   nichts aus.
2. **Workflow-Rechte pruefen.** *Settings → Actions → General → Workflow
   permissions*: "Read and write permissions". Der Workflow fordert
   `packages: write` zwar explizit an, eine organisationsweit auf read-only
   gesetzte Voreinstellung sticht das aber aus.
3. **Nach dem ersten erfolgreichen Lauf** liegen zwei Packages unter
   *Profil/Organisation → Packages*. Beide sind zunaechst **privat**:
   - `niederlassung-ops-backend`
   - `niederlassung-ops-frontend`

   Je Package unter *Package settings*:
   - *Manage Actions access* → das Repository mit Rolle **Write** eintragen,
     damit spaetere Laeufe dasselbe Package aktualisieren duerfen.
   - *Change visibility* → **Public**, falls ohne Login gezogen werden soll.
     Bleibt es privat, braucht jeder Zielserver ein Personal Access Token mit
     `read:packages` und ein `docker login ghcr.io`.

   Die Verknuepfung zum Repository setzt der Workflow selbst ueber das Label
   `org.opencontainers.image.source`; die Rechte muessen trotzdem einmal
   vergeben werden.

Kein zusaetzliches Secret erforderlich - `GITHUB_TOKEN` genuegt.

## Release erstellen

Zwei gleichwertige Wege. Beide erzeugen dieselben Image-Tags und denselben
GitHub-Release-Eintrag.

### Weg A: Tag pushen (Standard)

```bash
# 1. CHANGELOG.md ergaenzen, Version in backend/app/main.py (VERSION)
#    und frontend/package.json angleichen
# 2. Tag setzen
git tag -a v1.0.0 -m "v1.0.0"
git push origin v1.0.0
```

### Weg B: Manuell ueber die Actions-Oberflaeche

Fuer Umgebungen, in denen kein Tag gepusht werden kann (eingeschraenkte
Git-Zugaenge, Arbeit ueber die API):

*Actions → Release → Run workflow*, Feld **version** auf `1.0.0` setzen
(ohne fuehrendes `v`), Branch `main`.

Der Workflow prueft das Format, baut die Images mit denselben Tags und legt
**Tag und Release selbst an** (`gh release create --target`). Der so erzeugte
Tag loest den Workflow nicht erneut aus, weil er mit `GITHUB_TOKEN` entsteht.

Bleibt das Feld leer, wird nur `:edge` neu gebaut.

### Was danach laeuft

Beide Wege starten `.github/workflows/release.yml`:

1. `verify` fuehrt die komplette CI aus (Tests, Migrationen gegen SQLite **und**
   PostgreSQL, Typecheck, Build, Compose-Validierung).
2. `build` baut beide Images und pusht sie nach ghcr.io.
3. `release` legt Tag und GitHub-Release-Eintrag an.

Images werden nur aus einem gruenen Baum gebaut. Pushes auf `main` erzeugen
zusaetzlich `:edge` zum Testen vor dem Release.

Erzeugte Image-Tags fuer Version `1.0.0`:

| Image-Tag | Woher |
| --- | --- |
| `1.0.0` | Semver ohne fuehrendes `v` |
| `1.0` | Minor-Serie, folgt Patch-Releases |
| `v1.0.0` | Git-Tag unveraendert, damit `OPS_IMAGE_TAG=v1.0.0` funktioniert |
| `latest` | nur bei Releases, nicht bei einem reinen `main`-Push |
| `sha-<kurz>` | exakter Commit |

Fuer ein Deployment gehoert ein fester Tag in die `.env`, nicht `latest`.

## Betrieb aus den Images

```bash
cp .env.example .env          # POSTGRES_PASSWORD, DATABASE_URL, CORS_ALLOW_ORIGINS setzen
export OPS_IMAGE_TAG=v1.0.0
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d
```

Erforderliche Variablen ohne Default, damit nichts unbemerkt falsch startet:
`POSTGRES_PASSWORD`, `DATABASE_URL`, `CORS_ALLOW_ORIGINS`, `PUBLIC_API_BASE_URL`.

### Frontend-Konfiguration zur Laufzeit

Vite backt Variablen normalerweise beim Build ein, was ein veroeffentlichtes
Image an eine URL binden wuerde. Stattdessen schreibt der Container-Entrypoint
bei jedem Start `/config.js`:

| Variable | Wirkung |
| --- | --- |
| `API_BASE_URL` | Basis-URL des Backends |
| `AUTH_MODE` | `dev` oder `azure_ad` |
| `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_API_SCOPE` | nur fuer `azure_ad` |

Dasselbe Image laeuft damit in Test und Produktion, ohne neu gebaut zu werden.

## Upgrade

```bash
export OPS_IMAGE_TAG=v1.1.0
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d
```

Das Backend fuehrt beim Start `alembic upgrade head` aus. Bestandsdaten werden
migriert, nicht neu angelegt - auch aus einer Datenbank von vor Einfuehrung der
Migrationen. Details in [`migrations.md`](migrations.md).

Ein Backup vor dem Upgrade bleibt trotzdem richtig:

```bash
docker compose -f docker-compose.release.yml exec -T db \
  pg_dump -U remscheid_ops remscheid_ops > backup-$(date +%F).sql
```

Das Upload-Verzeichnis liegt im Volume `uploads_data` und gehoert mit ins Backup.

## Rollback

```bash
export OPS_IMAGE_TAG=v1.0.0
docker compose -f docker-compose.release.yml up -d
```

Achtung: ein aelteres Backend kennt neuere Migrationen nicht. Wenn die neue
Version Migrationen mitbrachte, vorher gezielt zurueckmigrieren:

```bash
docker compose -f docker-compose.release.yml run --rm ops-backend \
  alembic downgrade <revision>
```

Alle Migrationen dieses Projekts haben ein getestetes Downgrade.

## Healthchecks

| Dienst | Endpunkt |
| --- | --- |
| Backend | `GET /health` (unauthentifiziert, fuer den Healthcheck) |
| Backend | `GET /api/meta` - Version, Auth-Modus, Schemarevision |
| Frontend | `GET /healthz` |

## Checkliste vor dem Produktivgang

- [ ] `POSTGRES_PASSWORD` gesetzt, nicht der Beispielwert
- [ ] `CORS_ALLOW_ORIGINS` auf die echte Frontend-Domain
- [ ] TLS vor Frontend und Backend
- [ ] `APP_ENV=production` (verweigert den Start mit `AUTH_MODE=dev`)
- [ ] Azure AD aktiviert, siehe [`azure-ad-setup.md`](azure-ad-setup.md)
- [ ] Backup fuer `postgres_data` und `uploads_data` eingerichtet
