# PDS Fokus-Design — übertragbarer Style-Guide

> **Zweck:** Das Erscheinungsbild der ProDoc Suite (Fokus-Design) in einem
> anderen Projekt so nachbauen, dass die Oberfläche ähnlich bis nahezu gleich
> aussieht — unabhängig davon, ob dort Next.js, Tailwind oder shadcn/ui
> eingesetzt wird.
>
> **Abgrenzung:** `docs/fokus-design-guide.md` ist die interne Arbeitsregel
> *dieses* Repos (mit Verweisen auf `components/fokus/*`). Dieses Dokument hier
> ist die **exportierbare** Fassung: alle Werte ausgeschrieben, alle Bausteine
> als kopierbarer Code, ohne Abhängigkeit zur PDS-Codebasis.

Dateien in diesem Ordner:

| Datei | Inhalt |
|---|---|
| `README.md` | Dieser Guide: Prinzipien, Tokens, Bausteine, Seitenrezepte |
| `pds-theme.css` | Drop-in: alle Design-Tokens + Basis + optionales shadcn-Mapping |
| `pds-components.css` | Alle Bausteine als reine CSS-Klassen (Projekte ohne Tailwind) |
| `preview.html` | Referenzseite: zeigt alle Bausteine, im Browser öffnen |

---

## 1 · Übernahme in ein neues Projekt

### Schritt 1 — Dateien kopieren

`pds-theme.css` (und optional `pds-components.css`) in das Zielprojekt legen,
z. B. nach `styles/`.

### Schritt 2 — Schriften laden

Zwei Schriften tragen das Design: **Archivo** für UI, **IBM Plex Mono** für
alles Zahlenhafte.

Mit Next.js (`next/font`, bevorzugt — kein FOUT, keine externen Requests):

```ts
// lib/fonts.ts
import { Archivo, IBM_Plex_Mono } from "next/font/google";

export const archivo = Archivo({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-archivo",
  display: "swap",
  fallback: ["Arial", "Helvetica", "sans-serif"]
});

export const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-ibm-plex-mono",
  display: "swap",
  fallback: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"]
});
```

```tsx
// app/layout.tsx — Variablen ans <html> hängen
<html lang="de" className={`${archivo.variable} ${ibmPlexMono.variable}`}>
```

Ohne Next.js reicht ein Link im `<head>`; `pds-theme.css` fällt automatisch auf
die Literalnamen zurück:

```html
<link rel="stylesheet"
  href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
```

### Schritt 3 — Theme einbinden

**Tailwind v4:**

```css
@import "tailwindcss";
@import "./pds-theme.css";
```

Anschließend den `@theme inline`-Block aus dem Kommentar am Ende von
`pds-theme.css` in die eigene Entry-CSS kopieren, damit `bg-primary`,
`text-muted-foreground`, `border-border` usw. auf die Azur-Palette zeigen.

**Ohne Tailwind:**

```css
@import "./pds-theme.css";
@import "./pds-components.css";
```

**Mit shadcn/ui:** Das Mapping der Semantiktokens (`--primary`, `--border`,
`--ring` …) steckt bereits in `pds-theme.css`. Der komplette bestehende
Komponentenbestand färbt sich damit um, ohne dass eine Komponente angefasst
werden muss. Das ist der Schritt mit dem größten Effekt pro Aufwand.

### Schritt 4 — Shell bauen

Die Topbar und der zentrierte Inhaltsbereich (§ 8.1) prägen den ersten
Eindruck stärker als jede Einzelkomponente. Zuerst bauen.

### Schritt 5 — Bausteine übernehmen

Aus § 7 kopieren statt neu erfinden. `preview.html` im Browser öffnen und
gegenhalten.

---

## 2 · Design-DNA (was das Design ausmacht)

Wenn nur fünf Sätze übrig bleiben dürften:

1. **Werkbank statt Kartenflut.** Dichte Zeilen mit Aufklapp-Detail, sticky
   Kopf- und Fußzeilen. Nicht jede Information bekommt eine eigene Karte.
2. **Azur ist Signal, nicht Dekoration.** Die Marke erscheint dort, wo etwas
   aktiv, ausgewählt oder die Primäraktion ist — sonst bleibt die Fläche
   grau-weiß.
3. **Status ist sichtbar, nicht versteckt.** Fortschritt und fehlende
   Pflichtangaben stehen als Chip/Pill am Ort der Entscheidung, nicht in einer
   Fehlermeldung nach dem Absenden.
4. **Zahlen sind Mono.** Nummern, Preise, Artikelnummern, Dateinamen,
   Zeitstempel laufen in IBM Plex Mono. Das ist das auffälligste Merkmal des
   Designs und in jedem Screenshot sofort erkennbar.
5. **Ruhige Dichte.** 4er-Raster, wenig Schatten, 150ms-Übergänge, keine
   Verläufe, keine Emojis, Icons nur als 13–16px-Strichzeichnung (lucide).

Was es **nicht** ist: Startup-Dashboard, Landingpage, Showcase. Keine
Farbverläufe, keine großen Hero-Bereiche, keine dekorativen Illustrationen.

---

## 3 · Farben

Alle Werte kommen über CSS-Variablen. **Keine Hex-Werte im Komponentencode.**

### Marke (B.Schmitt-Azur)

| Token | Wert | Verwendung |
|---|---|---|
| `--pds-brand` | `#009DE0` | Signalton: CTA in dunklen Leisten, Fokusring, Zähler-Badges |
| `--pds-brand-strong` | `#0080B8` | Primärbuttons auf weißem Grund, aktive Textlinks |
| `--pds-brand-strong-hover` | `#006A99` | Hover dazu, Text auf Tint-Flächen |
| `--pds-brand-light` | `#33B1E6` | Hover für `--pds-brand` (auf dunklem Grund) |

Zwei Azur-Töne sind kein Versehen: `#009DE0` leuchtet auf Navy, hat auf Weiß
aber zu wenig Kontrast für Buttontext — dort steht `#0080B8`.

### Azur-Tints (aktiv, ausgewählt, ruhige Flächen)

| Token | Wert | Verwendung |
|---|---|---|
| `--pds-tint` | `#E0F2FC` | aktiver Nav-Eintrag, aktiver Chip, Dokumenttyp-Pill |
| `--pds-tint-border` | `#BDE3F5` | Rahmen von Systemblöcken |
| `--pds-tint-border-strong` | `#7FCBED` | Fokus-Rahmen an Inputs, geöffnete Zeile |
| `--pds-tint-bg` | `#F0F9FE` | aktive Zeile in Listen, Hinweisbanner |
| `--pds-tint-bg-2` | `#F6FBFE` | Detailbereich einer geöffneten Zeile, Header-Hover |
| `--pds-tint-bg-3` | `#F0F7FB` | Abschnittsüberschrift in Positionslisten |

### Text und dunkle Flächen

| Token | Wert | Verwendung |
|---|---|---|
| `--pds-navy` | `#071F30` | Summenleiste, Tabellen-Header im Dokument, Avatar |
| `--pds-text` | `#0F1B26` | Primärtext |
| `--pds-text-2` | `#33424F` | Labels, Sekundärwerte |
| `--pds-text-3` | `#46586A` | Tertiärtext, inaktive Navigation |
| `--pds-muted` | `#71808F` | Metazeilen, Tabellen-Header, Chevrons |
| `--pds-placeholder` | `#9AAAB8` | Platzhalter, Versionsanzeige |

### Flächen und Rahmen

| Token | Wert | Verwendung |
|---|---|---|
| `--pds-app-bg` | `#F6F8FA` | Seitenhintergrund, Tabellenkopf |
| `--pds-surface` | `#FFFFFF` | Karten, Tabellen, Dialoge |
| `--pds-row-hover` | `#F6FBFE` | Zeilen-Hover |
| `--pds-segment-bg` | `#E2E8EE` | Spur des Segment-Controls |
| `--pds-field-muted` | `#F0F4F7` | Readonly-Felder, Hover ohne Farbe, Kürzel-Tags |
| `--pds-border` | `#E2E8EE` | Karten- und Container-Rahmen |
| `--pds-border-input` | `#D5DDE4` | Input- und Outline-Button-Rahmen |
| `--pds-border-row` | `#EDF1F5` | Zeilentrenner |
| `--pds-border-dashed` | `#B9C5CF` | gestrichelte CTAs, offene Stepper-Kreise |

### Status

| Bedeutung | Token | Werte |
|---|---|---|
| **Grün — fertig / läuft** | `--pds-success` · `-bg` · `-text` | `#1F8A5B` · `#E5F3ED` · `#14603F` |
| **Amber — unvollständig / Handlungsbedarf** | `--pds-amber` · `-bg` · `-text` | `#D9822B` · `#FEF3E2` · `#92580B` |
| Amber-Rahmen / Warnfläche | `--pds-warn-border` · `--pds-warn-bg` · `--pds-warn-bg-2` | `#E0A857` · `#FFFDF8` · `#F2D9B8` |
| **Rot — Fehler / destruktiv** | `--pds-danger` · `-bg` | `#B3261E` · `rgba(220,38,38,0.08)` |
| **Azur — aktiv / ausgewählt / CTA** | siehe Marke | |

Die Trennung Amber/Rot ist zentral: **fehlende Pflichtangaben sind amber, nicht
rot.** Rot bleibt echten Fehlern und dem Löschen vorbehalten. Wer das
vertauscht, bekommt eine Oberfläche, die permanent alarmiert.

Sonstiges: `--pds-toggle-on: #0080B8`, `--pds-toggle-off: #C6D0D9`,
`--pds-overlay: rgba(7,31,48,0.45)`.

---

## 4 · Typografie

**UI: Archivo** (400/500/600/700/800). **Zahlen: IBM Plex Mono** (400–600).

### Skala

| px | Gewicht | Verwendung |
|---|---|---|
| 10.5 | 600, uppercase, ls 0.1em | Mikro-Labels in Detailbereichen |
| 11 | 600, uppercase, ls 0.1em | Tabellen-Header, Gruppentitel in Navigationen |
| 11.5 | 600 | Kürzel-Tags, kleine Chips |
| 12 | 400/600 | Metazeilen, Status-Pills |
| 12.5 | 500/600 | Labels, Nummern in Tabellen, Filter-Selects |
| 13 | 400/500 | kompakte Buttons, Zusammenfassungen, Toasts |
| 13.5 | 400/500 | **Body und Tabellenzeilen** — der Standardwert |
| 14 | 400 | Formularwerte in Inputs, Navigation |
| 15.5–16 | 700 | Abschnittstitel |
| 22–24 | 700, ls −0.01em | Seitentitel |

Textgrößen skalieren **nicht** mit der Viewport-Breite.

### Mono-Regel

Immer `font-family: var(--pds-font-mono)` (bzw. `.pds-mono`) für:
Angebots-/Belegnummern, Preise und Summen, Artikelnummern, Dateinamen,
Zeitstempel, Kunden-/Systemschlüssel, Versionsangaben.

Beträge zusätzlich `font-variant-numeric: tabular-nums`, damit Spalten
untereinander stehen.

### Labels

```
Standard-Label:  12.5px / 600 / var(--pds-text-2)
Mikro-Label:     10.5px / 600 / uppercase / ls 0.1em / var(--pds-muted)
Tabellen-Header: 11px  / 600 / uppercase / ls 0.1em / var(--pds-muted)
```

---

## 5 · Radien, Abstände, Schatten

### Radien — genau vier Werte

| Wert | Kontext |
|---|---|
| **6px** | kleine Controls (Segment-Buttons, Icon-Buttons, Kürzel-Tags) |
| **8px** | Buttons, Inputs, Zeilenkarten, Segment-Spur, Nav-Einträge |
| **12px** | Tabellen-Container, Dropdown-Panels, Hinweisbanner |
| **14px** | Abschnittskarten, Modals |
| voll | Pills, Chips, Avatare, Toggles, Toasts |

Keine Zwischenwerte. `rounded-md`/`rounded-2xl` erzeugen sichtbare Unruhe.

### Abstände — 4er-Raster

```
Karten-Padding (Abschnitt):   20–24px   (px-6 py-5)
Karten-Padding (kompakt):     14–18px
Tabellenzeile:                13px vertikal / 18px horizontal
Abstand zwischen Abschnitten: 16px      (gap-4)
Grid-Gaps in Formularen:      10–16px
Zwischen Label und Feld:      6px       (gap-1.5)
Seiten-Padding:               28px (Listen) / 24px (Editor)
```

Inhaltsbreiten: **1360px** für Listen- und Hub-Seiten, **1180px** für den
Editor mit Stepper.

### Schatten — sparsam

```
aktives Segment:      0 1px 2px  rgba(7,31,48,0.10)
geöffnete Zeile:      0 4px 16px rgba(0,157,224,0.12)   ← azur getönt
Dropdown/Popover:     0 12px 32px rgba(7,31,48,0.14)
Modal / Toast:        0 32px 80px rgba(7,31,48,0.35)
schwebendes Blatt:    0 8px 30px rgba(7,31,48,0.14)
```

Karten und Tabellen bekommen **keinen** Schatten — nur einen 1px-Rahmen.

### Bewegung

Alle Übergänge **150 ms**, ausschließlich für Farbe, Hintergrund und
Chevron-Rotation (180°). Keine Bounce-Effekte, keine Skalierungen, keine
Einblend-Animationen bei Listen. Maximal eine Transition pro Aktion.

---

## 6 · Icons

`lucide-react`, Größe **13–16px**, `stroke-width: 2`, Farbe erbt vom Text bzw.
`--pds-muted`. Keine Emojis, keine Custom-SVGs für Standardaktionen.

Feste Zuordnungen im Design: `ChevronDown` (auf-/zuklappen, rotiert 180°),
`Search`, `X` (leeren/schließen), `SlidersHorizontal` (Filter), `Check`
(erledigt/versandbereit), `TriangleAlert` (Blocker/Warnung), `Plus`
(hinzufügen), `Trash2` (löschen), `ArrowLeft` (zurück).

---

## 7 · Bausteine

Jeder Baustein hier ist 1:1 aus der laufenden Anwendung übernommen. Die
Tailwind-Ketten sind kopierfertig; die CSS-Klasse in Klammern kommt aus
`pds-components.css`.

### 7.1 Buttons

Vier Typen, mehr nicht. **Maximal drei Button-Stile pro Seite.**

```html
<!-- Primär im Content (.pds-btn .pds-btn--primary) -->
<button class="inline-flex h-8 items-center gap-1.5 rounded-lg
  bg-[var(--pds-brand-strong)] px-3 text-[13px] font-medium text-white
  transition-colors hover:bg-[var(--pds-brand-strong-hover)]">
  Position hinzufügen
</button>

<!-- Outline (.pds-btn .pds-btn--outline) -->
<button class="inline-flex h-8 items-center gap-1.5 rounded-lg border
  border-[var(--pds-border-input)] bg-white px-3 text-[13px] font-medium
  text-[var(--pds-text-2)] transition-colors hover:bg-[var(--pds-field-muted)]">
  Importieren
</button>

<!-- Primär in dunkler Leiste (.pds-btn .pds-btn--brand) -->
<button class="inline-flex h-9 items-center gap-1.5 rounded-lg
  bg-[var(--pds-brand)] px-4 text-[14px] font-semibold text-white
  transition-colors hover:bg-[var(--pds-brand-light)] disabled:opacity-60">
  Speichern und versenden
</button>

<!-- Destruktiv (.pds-btn .pds-btn--danger) -->
<button class="inline-flex h-8 items-center gap-1.5 rounded-lg
  bg-[var(--pds-danger-bg)] px-3 text-[13px] font-medium
  text-[var(--pds-danger)]">
  Entfernen
</button>
```

Höhen: **32px** in Karten und Toolbars · **36px** in Filterzeilen · **38px**
für Seiten-CTAs · **34px** für Icon-/Zurück-Buttons in der Topbar. Innerhalb
eines Kontexts nie mischen.

### 7.2 Formularfelder

```html
<label class="grid gap-1.5">
  <span class="text-[12.5px] font-semibold text-[var(--pds-text-2)]">Titel</span>
  <input class="h-[38px] w-full rounded-lg border border-[var(--pds-border-input)]
    bg-white px-3 text-[14px] outline-none
    placeholder:text-[var(--pds-placeholder)]
    focus:border-[var(--pds-tint-border-strong)]
    focus:ring-2 focus:ring-[var(--pds-brand)]/20
    disabled:bg-[var(--pds-field-muted)]" />
</label>
```

- **Readonly-Werte** (Einzelpreis, Gesamt): `bg-[var(--pds-field-muted)]`,
  Mono 12px, `whitespace-nowrap`, kein Fokusring. Der Unterschied zu
  editierbaren Feldern muss auf einen Blick erkennbar sein.
- **Fehlende Pflichtangabe:** `border-[1.5px] border-[var(--pds-warn-border)]
  text-[var(--pds-amber-text)]` — und das Label ebenfalls amber.
- **Rich-Text niemals in `<textarea>`** — sonst steht rohes HTML im Feld.

### 7.3 Segment-Control

Der zentrale Ausschnitt-Umschalter (Statusgruppen, Ansichten). Nicht mit Tabs
oder Filtern verwechseln: Segmente bestimmen, *was* die Liste überhaupt zeigt.

```html
<div class="inline-flex h-9 items-center rounded-lg
  bg-[var(--pds-segment-bg)] p-[3px]">
  <button class="inline-flex h-[30px] items-center rounded-md px-3 text-[13px]
    font-medium bg-white text-[var(--pds-text)]
    shadow-[0_1px_2px_rgba(7,31,48,0.1)]">Entwurf · 12</button>
  <button class="inline-flex h-[30px] items-center rounded-md px-3 text-[13px]
    font-medium text-[var(--pds-text-3)]
    hover:text-[var(--pds-text)]">Versendet · 34</button>
</div>
```

Segmente tragen **immer Zähler** (`Label · n`).

### 7.4 Status-Pill

```html
<span class="inline-flex h-[22px] items-center gap-1.5 rounded-full px-2.5
  text-[12px] font-semibold bg-[var(--pds-amber-bg)]
  text-[var(--pds-amber-text)]">
  <span class="size-1.5 rounded-full bg-[var(--pds-amber)]"></span>
  Entwurf
</span>
```

Zuordnung: Entwurf/offen → amber · erledigt/gewonnen → grün · verloren →
rot · archiviert/obsolet → `--pds-field-muted` + `--pds-muted` · Typ-/Info-Pill
→ `--pds-tint` + `--pds-brand-strong-hover`.

### 7.5 Werkbank-Tabelle

Kein `<table>`, sondern ein CSS-Grid — nur so lassen sich Spaltenbreiten in
`fr` und Pixel mischen und Zellen sauber kürzen.

```html
<div class="overflow-hidden rounded-xl border border-[var(--pds-border)] bg-white">

  <div class="grid grid-cols-[128px_minmax(0,1.7fr)_minmax(0,1fr)_118px_128px_40px]
    items-center gap-x-4 border-b border-[var(--pds-border)]
    bg-[var(--pds-app-bg)] px-[18px] py-2.5 text-[11px] font-semibold
    uppercase tracking-[0.1em] text-[var(--pds-muted)]">
    <span class="truncate">Nummer</span>
    <span class="truncate">Titel</span>
    <span class="truncate">Kunde</span>
    <span class="truncate">Status</span>
    <span class="truncate text-right">Summe</span>
    <span aria-hidden="true"></span>
  </div>

  <div role="link" tabindex="0" class="grid grid-cols-[...] cursor-pointer
    items-center gap-x-4 border-b border-[var(--pds-border-row)] px-[18px]
    py-[13px] text-[13.5px] transition-colors last:border-b-0
    hover:bg-[var(--pds-row-hover)] focus-visible:bg-[var(--pds-row-hover)]
    focus-visible:outline-none">
    <span class="truncate text-[12.5px] text-[var(--pds-text-2)]"
      style="font-family: var(--pds-font-mono)">ANG-26-0148</span>
    <span class="truncate font-semibold">Titel der Zeile</span>
    <span class="truncate">Kundenname</span>
    <span><!-- Status-Pill --></span>
    <span class="truncate text-right text-[12.5px] font-semibold"
      style="font-family: var(--pds-font-mono)">12.480,00 €</span>
    <span class="flex justify-end"><!-- Kebab --></span>
  </div>
</div>
```

Regeln: ganze Zeile klickbar (`role="link"` + `tabIndex={0}` + Enter/Space) ·
jede Zelle `truncate` mit `title` · Zeilenaktionen im Kebab am Zeilenende, mit
`stopPropagation` · leere Liste als zentrierter Satz mit
`--pds-muted`, nie eine leere Fläche.

Wichtig bei `sr-only`-Spaltenköpfen: `sr-only` setzt `position: absolute` und
fällt damit aus dem Grid-Fluss — alle folgenden Spalten verrutschen. Stattdessen
`<span aria-hidden="true" />` als Platzhalter und die Beschriftung am
Bedienelement selbst (`aria-label`).

### 7.6 Abschnittskarte (auf-/zuklappbar)

```html
<div class="overflow-hidden rounded-[14px] border border-[var(--pds-border)]
  bg-white" style="scroll-margin-top: 76px">
  <div role="button" tabindex="0" class="flex w-full cursor-pointer
    items-center justify-between gap-3 px-6 py-4 text-left
    hover:bg-[var(--pds-tint-bg-2)]">
    <div class="flex min-w-0 items-center gap-3">
      <h3 class="shrink-0 text-[16px] font-bold">2 · Positionen</h3>
      <!-- nur wenn eingeklappt: -->
      <span class="truncate text-[13px] text-[var(--pds-muted)]">
        7 Positionen · 12.480,00 €
      </span>
    </div>
    <div class="flex shrink-0 items-center gap-2.5">
      <span class="inline-flex h-[22px] items-center rounded-full px-2.5
        text-[11.5px] font-semibold bg-[var(--pds-success-bg)]
        text-[var(--pds-success-text)]">vollständig</span>
      <svg class="size-4 text-[var(--pds-muted)] transition-transform rotate-180">…</svg>
    </div>
  </div>
  <div class="px-6 pb-6 pt-1"><!-- Inhalt --></div>
</div>
```

- Eingeklappt zeigt der Kopf eine **einzeilige Zusammenfassung** — nie nur den
  Titel.
- Fehlen Pflichtangaben: `border-[var(--pds-warn-bg-2)]
  bg-[var(--pds-warn-bg)]` + amber Chip.
- Der Hauptarbeitsbereich (z. B. Positionen) ist **nie** einklappbar.
- Kopf als `div role="button"`, nicht `<button>`: in einem `fieldset disabled`
  (Readonly-Modus) wäre ein `<button>` deaktiviert und die Karte nicht mehr
  aufklappbar.

### 7.7 Stepper

```html
<nav class="sticky top-[68px] hidden h-fit w-[232px] flex-col gap-0.5 lg:flex">
  <button class="flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-left
    text-[13.5px] hover:bg-[var(--pds-field-muted)]">
    <span class="inline-flex size-[22px] shrink-0 items-center justify-center
      rounded-full text-[11px] font-semibold bg-[var(--pds-success-bg)]
      text-[var(--pds-success-text)]"><!-- Check --></span>
    <span class="truncate">Kunde &amp; Anlass</span>
  </button>
</nav>
```

Kreis-Zustände: offen = `border-[1.5px] border-[var(--pds-border-dashed)]
text-[var(--pds-muted)]` mit Nummer · erledigt = grün mit Haken · Warnung =
amber mit Warndreieck. Klick scrollt zum Abschnitt (`scroll-margin-top: 76px`)
und klappt ihn auf.

### 7.8 Sticky-Aktionsleiste

Die dunkle Leiste am unteren Rand ist das zweite Erkennungsmerkmal des Designs.
Links Summen, rechts Blocker und Primäraktion.

```html
<div class="fixed inset-x-0 bottom-0 z-40 border-t border-black/20
  bg-[var(--pds-navy)] pb-[env(safe-area-inset-bottom)] text-white">
  <div class="mx-auto flex max-w-[1180px] flex-wrap items-center
    justify-between gap-3 px-6 py-3">
    <div class="flex items-center gap-5 text-[13px]">
      <span class="text-white/65">Zwischensumme
        <span class="text-white tabular-nums">10.487,39 €</span></span>
      <span class="text-white/65">MwSt. 19 %
        <span class="text-white tabular-nums">1.992,61 €</span></span>
      <span class="font-semibold">Gesamt
        <span class="text-[15px] font-bold tabular-nums">12.480,00 €</span></span>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <button class="inline-flex h-7 items-center gap-1.5 rounded-full
        bg-[var(--pds-amber-bg)] px-3 text-[12px] font-semibold
        text-[var(--pds-amber-text)]"><!-- Warn --> Kunde fehlt</button>
      <button class="inline-flex h-9 items-center gap-1.5 rounded-lg
        bg-[var(--pds-brand)] px-4 text-[14px] font-semibold text-white
        hover:bg-[var(--pds-brand-light)]">Speichern und versenden</button>
    </div>
  </div>
</div>
```

**Blocker statt Fehlermeldung:** Jede fehlende Pflichtangabe wird zu einem
klickbaren amber Chip, der zum betroffenen Abschnitt scrollt und ihn aufklappt.
Sind alle erfüllt, steht dort ein grüner Chip („Versandbereit"). Serverfehler
gehören dagegen als Banner nach oben.

`pb-[env(safe-area-inset-bottom)]` nicht weglassen (iPad-Home-Indicator). Bei
geöffneter Bildschirmtastatur die Leiste per `translate-y-full` ausblenden.

### 7.9 Toast

```html
<div class="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex justify-center">
  <span class="rounded-full bg-[#0f1b26] px-4 py-2 text-[13px] font-medium
    text-white shadow-[0_12px_32px_rgba(7,31,48,0.35)]">Position eingefügt</span>
</div>
```

Dunkel, zentriert **über** der Aktionsleiste, ca. 2,6 s, nicht klickbar.

### 7.10 Dialoge

Vier Breiten, keine frei gewählten Werte:

| Klasse | Breite | Verwendung |
|---|---|---|
| `sm:max-w-[440px]` | 440 px | Bestätigungen (Löschen, Wiedereröffnen) |
| `sm:max-w-[640px]` | 640 px | Formulare (anlegen, speichern unter) |
| `sm:max-w-[900px]` | 900 px | Auswahl- und Suchdialoge |
| `sm:max-w-[min(1100px,92vw)] h-[85vh]` | groß, feste Höhe | Viewer (Mail, Dokument) |

Overlay `rgba(7,31,48,0.45)`, Modal `rounded-[14px]`, Schatten
`0 32px 80px rgba(7,31,48,0.35)`.

**Verhalten von Suchdialogen:** Suchfeld mit `autoFocus` und ~180 ms Debounce ·
Filter-Chips über der Trefferliste · pro Trefferzeile eine Direktaktion
(„Einfügen") · der Dialog **bleibt beim Mehrfach-Einfügen offen**, die Fußzeile
zählt mit („3 Positionen eingefügt") · Enter übernimmt den ersten Treffer ·
kein Treffer → Angebot, den Suchbegriff als freien Eintrag anzulegen.

### 7.11 Auswahlkarte und gestrichelte CTA

Für „ein Objekt ist gewählt / noch nicht gewählt":

```html
<!-- gesetzt -->
<div class="flex items-center justify-between gap-3 rounded-lg border
  border-[var(--pds-border)] bg-white px-3.5 py-3">
  <div class="min-w-0">
    <p class="truncate text-[13.5px] font-semibold">Muster GmbH</p>
    <p class="truncate text-[12px] text-[var(--pds-muted)]">10115 Berlin · SHC 4711</p>
  </div>
  <button class="text-[13px] font-semibold text-[var(--pds-brand-strong)]">Ändern</button>
</div>

<!-- leer -->
<button class="flex w-full items-center justify-center gap-2 rounded-lg border
  border-dashed border-[var(--pds-border-dashed)] px-3.5 py-3.5 text-[13.5px]
  font-medium text-[var(--pds-text-3)]
  hover:border-[var(--pds-tint-border-strong)] hover:bg-[var(--pds-tint-bg)]
  hover:text-[var(--pds-brand-strong)]">
  Kunde wählen oder anlegen
</button>
```

### 7.12 Aufklapp-Zeile

Kompakte Zeile, die sich zum Detail öffnet — das Kernmuster für Listen mit
bearbeitbaren Einträgen. Geschlossen: Grid aus Nummer (Mono), zweizeiliger
Bezeichnung (Zeile 1 fett 13.5px/600, Zeile 2 normal 12.5px
`--pds-text-2`, Metazeile 12px `--pds-muted`), Kurzkalkulation, Summe (Mono
600), Chevron. Geöffnet: `border-[var(--pds-tint-border-strong)]` +
`shadow-[0_4px_16px_rgba(0,157,224,0.12)]`, Detailbereich mit
`bg-[var(--pds-tint-bg-2)]`, eingerückt auf Höhe der Bezeichnung.

---

## 8 · Seitenrezepte

### 8.1 Shell (jede Seite)

```html
<div class="min-h-screen bg-[var(--pds-app-bg)] text-[var(--pds-text)]">
  <header class="sticky top-0 z-40 flex items-center justify-between gap-4
    border-b border-[var(--pds-border)] bg-white/94 px-7 py-2.5
    backdrop-blur-[8px]">
    <div class="flex min-w-0 items-center gap-3.5">
      <a href="/" class="inline-flex size-8 shrink-0 items-center justify-center
        rounded-lg bg-[var(--pds-brand)] text-[13px] font-extrabold text-white">BS</a>
      <span class="text-[11px] text-[var(--pds-placeholder)]"
        style="font-family: var(--pds-font-mono)">v1.17.0</span>
      <nav class="flex items-center gap-0.5"><!-- Nav-Einträge --></nav>
    </div>
    <div class="flex shrink-0 items-center gap-2.5"><!-- Status-Pill, Avatar --></div>
  </header>

  <main class="mx-auto w-full max-w-[1360px] px-7 py-7">
    <div class="mb-5 flex flex-wrap items-center justify-between gap-4">
      <div class="min-w-0">
        <h1 class="text-2xl font-bold tracking-[-0.01em]">Angebote</h1>
      </div>
      <div class="flex flex-wrap justify-end gap-2"><!-- Seiten-CTAs --></div>
    </div>
    <!-- Inhalt -->
  </main>
</div>
```

Nav-Eintrag: `h-[34px] rounded-lg px-3.5 text-sm`, aktiv
`bg-[var(--pds-tint)] font-semibold text-[var(--pds-brand-strong-hover)]`,
inaktiv `font-medium text-[var(--pds-text-3)]
hover:bg-[var(--pds-field-muted)]`. Zähler als amber Kreis-Badge rechts am
Label. Die Versionsanzeige in Mono neben dem Logo ist ein bewusstes Detail —
sie signalisiert „internes Werkzeug".

### 8.2 Übersicht (Liste)

Von oben nach unten, bewusst als getrennte Ebenen statt einer umbrechenden
Zeile:

1. **Ausschnitt** — Segment-Control mit Zählern (was zeigt die Liste
   überhaupt), rechts optional ein zweites Segment („Meine / Alle").
2. **Arbeitszeile** — Suchfeld (max. 420px, Icon links, X zum Leeren),
   Filter-Button mit Popover (300px, `rounded-xl`, Dropdown-Schatten) und Zähler
   der aktiven Filter, Sortier-Select.
3. **Aktive Filter** als entfernbare Chips + „Alle zurücksetzen".
4. **Werkbank-Tabelle** (§ 7.5).

Filterzustand in `sessionStorage` halten, damit die Rückkehr aus dem Detail den
Ausschnitt nicht verliert.

### 8.3 Editor (komplexes Objekt)

```
Sticky-Topbar: Zurück · Breadcrumb (11.5px, Nummer Mono) + Titel (15.5px/700)
               · Status-Pill · Typ-Pill · rechts Autosave-Hinweis, Versionen,
                 Export, Avatar
Raster:        grid max-w-[1180px] gap-6 px-6 py-6 lg:grid-cols-[232px_minmax(0,1fr)]
Links:         Stepper (§ 7.7), sticky top-[68px], unter lg ausgeblendet
Rechts:        nummerierte Abschnittskarten (§ 7.6), gap-4
Unten:         Sticky-Aktionsleiste (§ 7.8)
```

Aufklapp-Default: bestehendes Objekt → vollständige Abschnitte eingeklappt,
unvollständige offen; neues Objekt → alles offen.

### 8.4 Einstellungen / Hub

Linke Abschnitts-Navigation (gruppiert, Gruppentitel 11px/700 uppercase
ls 0.11em `--pds-muted`, aktiver Eintrag `bg-[var(--pds-tint)]
font-semibold text-[var(--pds-brand-strong-hover)]`), rechts der gewählte
Bereich. Detailseiten führen eine „Zur Übersicht"-Aktion.

### 8.5 Status-Center / Monitoring

Gesamtstatus-Pill oben, darunter eine Karte je System mit letzter Aktivität
(Zeitstempel Mono), gestörte Karten amber hervorgehoben, darunter ein
filterbares Ereignisprotokoll mit Chips.

---

## 9 · Zustände

Jeder interaktive Zustand muss existieren:

| Zustand | Umsetzung |
|---|---|
| hover | `bg-[var(--pds-field-muted)]` (neutral) oder `bg-[var(--pds-row-hover)]` (Zeilen) |
| focus | `focus:border-[var(--pds-tint-border-strong)] focus:ring-2 focus:ring-[var(--pds-brand)]/20` |
| aktiv/ausgewählt | `bg-[var(--pds-tint)]` + `text-[var(--pds-brand-strong-hover)]`, bei Karten zusätzlich `border-[var(--pds-tint-border-strong)]` |
| disabled | `opacity-50 cursor-not-allowed`, Felder zusätzlich `bg-[var(--pds-field-muted)]` |
| readonly | `bg-[var(--pds-field-muted)]`, kein Fokusring |
| unvollständig | amber: Rahmen `1.5px var(--pds-warn-border)`, Text `--pds-amber-text` |
| Fehler | rot: `--pds-danger` + `aria-invalid` |

Pflichtangaben und Warnungen müssen **auch ohne Farbe** erkennbar sein — Icon
plus Text, nicht nur ein farbiger Rahmen.

---

## 10 · Responsiveness

- Zielgerät neben dem Desktop ist **iPad quer (≥ 1024px)** — dort muss die
  Ansicht gleichwertig sein, nicht reduziert.
- Unter `lg` entfällt der Stepper; die Abschnitte bleiben vollständig bedienbar.
- Tabellenzellen kürzen (`overflow: hidden; text-overflow: ellipsis`) statt
  umzubrechen; breite Inhalte scrollen in einem **eigenen** Container — die
  Seite selbst scrollt nie horizontal.
- Filterzeilen brechen um (`flex-wrap`), Segmente bleiben zusammen.
- Sticky-Leisten brauchen `env(safe-area-inset-bottom)`.

---

## 11 · Don'ts

```
✗ Hex-Farben direkt im Komponentencode        → immer über --pds-*-Tokens
✗ Radien außerhalb von 6 / 8 / 12 / 14 / voll → sichtbare Unruhe
✗ Schatten auf Karten und Tabellen            → nur 1px-Rahmen
✗ Rot für fehlende Pflichtangaben             → Amber; Rot ist Fehler/Löschen
✗ Zahlen in der UI-Schrift                    → Mono, sonst springen die Spalten
✗ Emojis als Icons, Custom-SVGs für Standard  → lucide, 13–16px, stroke 2
✗ Farbverläufe, Purple/Lila, Hero-Flächen     → passt nicht zur Marke
✗ Mehr als 3 Button-Stile pro Seite           → visuelle Konkurrenz
✗ Karte in Karte                              → Tiefenstapelung ohne Bedeutung
✗ Icon-Buttons unterschiedlicher Größe nebeneinander
✗ <textarea> für Rich-Text-Inhalte            → zeigt rohes HTML
✗ Animationen über 150 ms, Bounce, Skalierung
✗ Fehlermeldungen erst nach dem Absenden      → Blocker vorher sichtbar machen
```

---

## 12 · Prüfliste vor dem Merge

- [ ] Keine neuen Hex-Werte, keine Radien außerhalb des Systems
- [ ] Alle Zahlen, Nummern und Dateinamen in Mono
- [ ] Hover-, Fokus-, Disabled-, Readonly- und Warnzustände vorhanden
- [ ] Pflichtangaben amber (nicht rot) und ohne Farbe erkennbar
- [ ] Status-Pills `h-[22px] rounded-full`, Segment-Zähler gesetzt
- [ ] Tabellenzellen kürzen und tragen `title`
- [ ] Seite scrollt bei 1024px nicht horizontal
- [ ] Höchstens drei Button-Stile, Icon-Buttons einheitlich groß
- [ ] Sticky-Leisten mit Safe-Area-Abstand

---

## 13 · Herkunft der Werte

Alles in diesem Guide ist aus der laufenden ProDoc Suite abgeleitet:

| Thema | Quelle im Repo |
|---|---|
| Tokens | `app/globals.css` (`--pds-*` und das `html[data-design="fokus"]`-Mapping) |
| Schriften | `lib/fonts.ts`, `app/layout.tsx` |
| Shell/Topbar | `components/fokus/fokus-shell.tsx`, `components/fokus/fokus-nav.tsx` |
| Werkbank-Tabelle, Segmente, Pills, Filter | `components/fokus/offer-overview-fokus.tsx` |
| Abschnittskarte, Stepper, Aktionsleiste, Toast, Felder | `components/fokus/offer-editor-fokus.tsx` |
| Dialog-Raster | `components/ui/dialog-sizes.ts` |
| Abschnitts-Navigation | `components/fokus/settings-hub-fokus.tsx` |
| Ursprüngliche Design-Spezifikation | `docs/design_handoff_fookus_flow/README.md` |
| Interne Arbeitsregel | `docs/fokus-design-guide.md` |

Ändert sich einer dieser Werte im Produkt, gehört er hier nachgezogen —
sonst driften Guide und Anwendung auseinander.
