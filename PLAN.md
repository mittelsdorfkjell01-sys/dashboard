# Media-Picker für Spots & Regionen — Sprint 0: Repo-Audit & Umsetzungsplan

Stand: 2026-08-06 · Branch `main` (clean) · erstellt vor der ersten Code-Zeile.

---

## 1. Ist-Zustand

### 1.1 Stack

| Bereich | Befund |
|---|---|
| Backend | FastAPI, Python 3.11, SQLAlchemy 2 (ORM `Mapped[...]`), Pydantic v2 + `pydantic-settings` |
| DB | Postgres + PostGIS (GeoAlchemy2 `Geography`), Alembic-Migrationen `0001`–`0026` |
| Frontend | React 18 + TypeScript, Vite 8, React Router 7, Tailwind 3, framer-motion. Kein Redux/Zustand — State lokal + eigene `swr.ts`-Hooks |
| Auth | Cookie-Session (JWT, httpOnly) + CSRF-Double-Submit. `require_role("admin","curator")` als Router-Dependency |
| Hosting | Vercel Serverless (`api/index.py` ASGI-Wrapper, `maxDuration 60`, Region `fra1`) **und** Docker/VPS (`docker-compose.prod.yml`, Caddy) |
| Tests | Backend: pytest gegen echtes Postgres (`TEST_DATABASE_URL`), 40 Test-Module. Frontend: vitest **nur für reine Logik** (`src/lib/__tests__`) — kein jsdom, kein testing-library. UI-Abdeckung via Playwright (`frontend/e2e/*.spec.ts`) |
| Deployment-Trennung | `ENABLE_ADMIN_API=false` auf der Public-Domain → `/admin*`-Router wird gar nicht gemountet. Frontend: Admin-Code liegt hinter `adminRoutes.tsx` und wird nur im Admin-Build gebündelt (`scripts/check-bundle.mjs` bricht den Build ab, wenn ein Admin-Chunk im Public-Bundle landet) |

### 1.2 Wo `image` definiert ist

| Ort | Inhalt |
|---|---|
| [app/models/spot.py:82](app/models/spot.py#L82) | `image: Mapped[dict \| None]` — **JSONB, schemalos**, keine Migration nötig um Felder zu ergänzen |
| [app/models/region.py:41](app/models/region.py#L41) | dito |
| [app/schemas/spot.py:35](app/schemas/spot.py#L35), [:82](app/schemas/spot.py#L82) | `image: dict[str, Any] \| None` — wird **roh** durchgereicht (Summary + Read) |
| [app/schemas/region.py:20](app/schemas/region.py#L20) | dito |
| [frontend/src/lib/api.ts:65-72](frontend/src/lib/api.ts#L65-L72) | `interface ImageRecord { url, source?, license?, credit?, focal?: {x,y} }` |

Faktisch gespeicherte Form heute: **genau vier Rechte-Felder + optional `focal`**.

Schreibpfade, die das Objekt aktiv **auf vier Schlüssel zurückschneiden** — beide müssen in Sprint 1 angefasst werden:

- [app/admin/spots.py:339](app/admin/spots.py#L339) — `spot.image = {k: image[k] for k in ("url","source","license","credit")}` → verwirft alles andere, inkl. eines zuvor gesetzten `focal`
- [app/admin/regions.py:342-347](app/admin/regions.py#L342-L347) — baut das Dict ebenfalls neu auf

Erhaltende Pfade: `update_image_attribution` ([spots.py:359](app/admin/spots.py#L359)) und `set_image_focal` ([spots.py:407](app/admin/spots.py#L407)) mergen korrekt via `{**spot.image, ...}`.

### 1.3 Galerie — was es schon gibt

`spot_images` ([app/models/ugc.py:158](app/models/ugc.py#L158)) ist eine **fertige Galerie-Tabelle für Spots** mit genau den Provenienz-Feldern, die der Auftrag verlangt: `source`, `credit`, `license_name`, `license_url`, `source_url`, `width`, `height`, `status`, `kind (gallery|hero_candidate)`.

Sie wird bereits von zwei Quellen befüllt:
- Community-Uploads (mit Consent-Versionierung `license_version`/`license_accepted_at`)
- **Wikimedia Commons** — [app/admin/commons.py](app/admin/commons.py) (Geosearch + imageinfo, HTML-Stripping serverseitig) → [app/community/service.py:268](app/community/service.py#L268), `source="wikimedia_commons"`, `status="approved"`, Dubletten-Schutz über `source_url`

**Für Regionen existiert keinerlei Galerie** — weder Tabelle noch UI noch öffentliches Rendering.

Es gibt keine Sortier-/Reihenfolgespalte (`list_images` sortiert nach `created_at DESC`).

### 1.4 Wo Bilder gerendert werden

| Komponente | Rolle |
|---|---|
| [frontend/src/components/editorial/EditorialHero.tsx](frontend/src/components/editorial/EditorialHero.tsx) | Voll-Bleed-Hero mit Parallax, Scrim, Typografie-Block **und Credit-Zeile unten rechts** (`credit · license · Quelle`) |
| [frontend/src/components/HeroImage.tsx:39](frontend/src/components/HeroImage.tsx#L39) | `style={{ objectPosition: \`${focal.x}% ${focal.y}%\` }}` + `<picture>` mit AVIF/WebP-srcset, aber **nur für lokale Assets aus `heroManifest`**; externe URLs laufen als schlichtes `<img>` |
| [frontend/src/lib/adapt.ts:48-53](frontend/src/lib/adapt.ts#L48-L53) | mappt `image.{url,focal,credit,license,source}` → `hero*`-Props |
| [pages/SpotDetail.tsx:143-150](frontend/src/pages/SpotDetail.tsx#L143-L150) | übergibt Credit/License/Source ✅ |
| [pages/RegionDetail.tsx:159-165](frontend/src/pages/RegionDetail.tsx#L159-L165) | übergibt **kein** Credit, keine Lizenz ❌ (siehe Kollision K7) |
| [components/PhotoGalleryOverlay.tsx](frontend/src/components/PhotoGalleryOverlay.tsx) | Community-Fotogalerie (justified layout + Lightbox), nur Spots |
| `resolveMediaUrl` / `usableMediaUrl` ([api.ts:39-54](frontend/src/lib/api.ts#L39-L54)) | absolute URLs unverändert, root-relative gegen `API_BASE`; `*.local`-Hosts gelten als „kein Bild" |

Bemerkenswert: `adapt.ts` schiebt `image.source` (den Provider**namen**) in die Prop `sourceUrl`. `EditorialHero` prüft `^https?://`, deshalb fällt es nicht auf — die „Quelle"-Verlinkung ist heute faktisch tot.

### 1.5 Admin-Auth (wird wiederverwendet, nichts Neues)

```
app/api/admin.py:72   router = APIRouter(prefix="/admin", dependencies=[Depends(require_role("admin","curator"))])
app/auth/deps.py:66   current_user  → Cookie-Session, Break-Glass X-Admin-Key (IP+Ablauf-beschränkt)
app/csrf.py:51        CSRFMiddleware → alle unsicheren Methoden brauchen x-csrf-token
```
Ein neuer Router unter `/admin/media/*` erbt beides automatisch. 403 bei falscher Rolle ist bereits die Norm.

### 1.6 Der Seed-Bug — exakter Befund

Der Bug ist **zweiteilig**, nicht einteilig:

1. **Seed-Writer:** [app/seed/seed.py:63-73](app/seed/seed.py#L63-L73) übergibt beim `Region(...)` ein `image=r["image"]`. Der `Spot(...)`-Konstruktor darunter ([:87-107](app/seed/seed.py#L87-L107)) hat **keinen `image=`-Parameter** — auch nicht als `s.get("image")`.
2. **Seed-Daten:** Die Spot-Fixtures führen den Schlüssel gar nicht. `grep '"image"'` → `data.py`: 3 Treffer, alle in `REGIONS`. `data_europe.py`: 25 Treffer, alle in `REGIONS` (via Helper `_img()`, [data_europe.py:38](app/seed/data_europe.py#L38)); im gesamten `SPOTS`-Block ab Zeile 232 **null Treffer**.

Selbst wenn (1) gefixt wird, bleibt das Feld leer, solange (2) offen ist. Bestätigt durch [tests/test_seed.py](tests/test_seed.py) — dort wird `image` nie geprüft.

Nebenbefund mit Folgen: Seed-URLs sind Sentinels. `data_europe` nutzt `https://placeholder.local/…` (vom Frontend korrekt als „kein Bild" behandelt), das Kern-`data.py` dagegen `https://example.com/img/tarifa.jpg` — **kein** Sentinel, rendert als kaputtes `<img>`.

### 1.7 Sonstige relevante Infrastruktur

- **Cache:** [app/live/cache.py](app/live/cache.py) — Redis, *fail-open* (Ausfall = Miss). `InMemoryCache` nur für Tests.
- **Rate-Limit:** [app/community/ratelimit.py](app/community/ratelimit.py) — Redis-Zähler für UGC.
- **CSP** ([vercel.json](vercel.json)): `img-src 'self' data: blob: https:` → **Hotlinking auf Unsplash-CDN ist bereits erlaubt**, keine CSP-Änderung nötig. `connect-src` erlaubt nur `self` + MapTiler → der Client könnte Provider-APIs ohnehin nicht direkt rufen. Proxy ist damit nicht nur Policy, sondern Zwang.
- **Storage:** [app/media/storage.py](app/media/storage.py) — `local` (Disk) oder `blob` (Vercel Blob), umschaltbar über `MEDIA_BACKEND`. Re-Encoding zu AVIF/WebP existiert ([app/media/hero.py:62](app/media/hero.py#L62)), aber **nur einbreitig** — kein srcset-Derivat-Satz für externe Bilder.
- **`EXPECTED_DB_REVISION = "0026_remove_admin_totp"`** ([app/main.py:26](app/main.py#L26)) — muss bei jeder neuen Migration mitgezogen werden, sonst meldet `/health` „schema mismatch".
- `UNSPLASH_ACCESS_KEY` wird heute **an `Settings` vorbei** direkt aus `os.environ` gelesen ([app/admin/stock.py:23](app/admin/stock.py#L23)).

---

## 2. Kollisionen mit den Vorgaben — jeweils mit Empfehlung

> Grundlinie laut Auftrag: „Bestehende Konventionen des Repos schlagen jede Konvention aus diesem Dokument."

### K1 — `focal` ist im Repo `{x, y}` in **Prozent (0..100)**, nicht `[0.5, 0.42]`

Betroffen: DB-Werte, `set_image_focal` + `set_region_image_focal`, `POST …/image/focal` (beide Entitäten), `ImageFocalEditor`, `HeroImage` (`objectPosition: ${x}%`), `adapt.ts`, `api.ts`-Typ.

**Empfehlung: Repo-Format `{x, y}` 0..100 behalten.** Das Array-Format brächte eine Datenmigration, eine API-Änderung und zwei Frontend-Umbauten für null Funktionsgewinn — `objectPosition` will ohnehin Prozent. Ich dokumentiere das Mapping im Schema-Kommentar. Bitte kurz bestätigen, da es eine explizite Vorgabe berührt.

### K2 — Zwei unterschiedliche Hero-Mindestmaße

Auftrag: `hero_eligible = w≥3840 && h≥1920`. Repo-Upload: `HERO_MIN_WIDTH=3840`, `HERO_MIN_HEIGHT=2000` ([app/media/hero.py:22-23](app/media/hero.py#L22-L23)), Admin darf per `allow_below_min=True` sogar darunter.

**Empfehlung: beide nebeneinander, getrennt benannt.** Neue Konstante `MEDIA_HERO_MIN = (3840, 1920)` nur für den Picker (mit dem 2:1-Crop-Argument als Kommentar); der Upload-Pfad bleibt bei 3840×2000. Die Upload-Regel still auf 1920 abzusenken wäre eine unbeauftragte Lockerung, sie anzuheben würde bestehende Admin-Uploads brechen.

### K3 — Galerie: Spots haben eine Tabelle, Regionen keine

Der Auftrag will „dieselbe Struktur, eine geordnete Liste pro Spot/Region". Drei Wege:

| Option | Kosten | Risiko |
|---|---|---|
| **A** `spot_images` generalisieren: `spot_id` nullable + `region_id` nullable + `CHECK` genau eines gesetzt, plus `position`-Spalte | 1 Migration, Anpassung der Community-Queries auf `spot_id IS NOT NULL` | mittel — die Tabelle heißt danach falsch |
| **B** neue Tabelle `media_gallery_item` für admin-kuratierte Stockbilder, `spot_images` bleibt Community-only | keine Migration an Bestandsdaten | die öffentliche Spot-Galerie muss zwei Quellen mergen und sortieren |
| **C** `region_images` als Zwillingstabelle | einfach | zwei fast identische Code-Pfade — genau das, was der Auftrag verbietet |

**Empfehlung: A.** Es gibt Präzedenz — externe Provider-Bilder (Commons) landen bereits in `spot_images` mit `source`/`license_name`/`license_url`/`source_url`. Ein zweiter Galerie-Speicher für Spots wäre die eigentliche Duplizierung. Den Tabellennamen würde ich **nicht** umbenennen (Rename = Kaskade durch Moderation, Reports, Community-API); stattdessen ein Doc-Kommentar. Optionaler späterer Rename als eigener Sprint.

**Das ist die einzige Entscheidung, bei der ich vor Sprint 1 ein Ja brauche** — sie bestimmt Migration, Adopt-Logik und die Galerie-UI in Sprint 6.

### K4 — Cache & Budget-Zähler brauchen einen Store, den es auf Vercel nicht gibt

Der Auftrag verlangt einen **serverseitig persistierten** Stundenzähler und 24-h-Cache. Redis ist konfiguriert, aber der Vercel-Deploy hat keine Redis-Instanz (es gibt keinen Upstash-/Redis-Eintrag in `vercel.json` oder `env.prod.example`), und der bestehende Redis-Cache ist bewusst *fail-open*. Ein fail-open-Budgetzähler ist wertlos (er würde Unsplash-Overrun nicht verhindern), ein fail-closed-Zähler auf einem nicht existierenden Redis sperrt das Overlay dauerhaft.

**Empfehlung: Postgres.** Zwei kleine Tabellen — `media_search_cache` (Key, JSONB-Payload, `expires_at`) und `media_provider_budget` (Provider, Stunden-Bucket, Count, `UNIQUE(provider, hour)`, Increment via `INSERT … ON CONFLICT DO UPDATE`). Postgres ist der einzige Store, der in *allen* drei Betriebsarten (dev, Docker/VPS, Vercel) garantiert existiert, und ein atomares Upsert ist hier korrekter als ein Redis-`INCR` ohne Redis. Aufräumen abgelaufener Zeilen im bestehenden Cron (`/api/cron/climatology`) mitziehen — kein neuer Cron.

### K5 — „Alle Tabs beim Öffnen befüllt" × 50 Unsplash-Requests/Stunde

Der Auftrag will Trefferzahlen pro Tab **vor** dem Durchklicken. Das heißt: ein Request pro Provider und Query. Jeder Chip-Wechsel ist eine neue Query → bei kaltem Cache 1 Unsplash-Request pro Chip. Der Adopt-Ping auf `download_location` kostet **zusätzlich** einen Request. Realistisch: ~40 frische Chip-Wechsel pro Stunde, danach ist das Kontingent leer.

**Empfehlung:** So bauen wie spezifiziert (der 24-h-Cache macht Wiederholungen frei), aber drei Dämpfer: (a) Chip-Wechsel um 250 ms entprellen, (b) Query-Normalisierung aggressiv (lowercase, Whitespace/Umlaute), damit „Tarifa kitesurf" und „tarifa  Kitesurf" denselben Cache-Key treffen, (c) das Budget-Meter aus Sprint 6 gleich in Sprint 2 mitliefern, statt erst später. Kein Prefetch beim bloßen Hovern.

Hinweis zur Kalkulation: Unsplash Demo = 50/h, Production (nach Review) = 5000/h. Der Antrag lohnt sich, ist aber nicht Voraussetzung.

### K6 — `manage_spot_image` schneidet das Bildobjekt auf vier Felder zurück

Nicht nur der Picker ist betroffen: [app/admin/moderation.py:339](app/admin/moderation.py#L339) promotet Community-Hero-Kandidaten über dieselbe Funktion. Wenn wir sie erweitern, muss dieser Pfad `provider:"upload"`, `delivery:"hosted"` mitliefern, sonst entstehen ab sofort Bildobjekte mit halbem Schema.

**Empfehlung:** In Sprint 1 eine zentrale Normalisierungsfunktion `app/media/image_object.py::build_image(...)` einführen, durch die **jeder** Schreibpfad geht (Picker, Upload, Community-Promotion, Seed-Migration, manuelle URL). Keine Ad-hoc-Dicts mehr.

### K7 — Regionen-Heroes laufen heute ohne Attribution

`RegionDetail` übergibt weder `credit` noch `license` an `EditorialHero`, obwohl `POST /admin/regions/{id}/stock-image` seit jeher **Unsplash**-Bilder setzt ([app/admin/regions.py:374](app/admin/regions.py#L374)). Wo Regionen bebildert sind, verletzt die Seite die Unsplash-Attributionsbedingung aktuell.

**Empfehlung:** Das in Sprint 5 mitfixen und im Bericht als Bestandsfehler ausweisen — es ist kein Nebenprodukt des Pickers, sondern ein bestehender Compliance-Mangel, der durch mehr Stockbilder nur größer wird.

### K8 — Seed-Bugfix kippt die Readiness von ~25 Spots

`image_ready` verlangt `url+source+license+credit` ([app/admin/readiness.py:68](app/admin/readiness.py#L68)). Sobald der Seed Spot-Bilder schreibt, gelten alle geseedeten Europa-Spots als „Bild vorhanden" — mit Platzhalter-URLs. Die Sprint-6-Liste „Spots ohne Hero" wäre ab Tag 1 falsch, und die Fertigstellen-Ampel würde grüner als die Realität.

**Empfehlung:** `image_ready` zusätzlich gegen Platzhalter prüfen — `provider == "seed"` oder Sentinel-Host `*.local` zählt **nicht** als fertiges Bild. Dazu die drei `example.com`-URLs im Kern-Seed auf die `.local`-Sentinelform ziehen, damit dev keine kaputten `<img>` zeigt. Der Seed schreibt dann echt in die DB (Akzeptanzkriterium erfüllt), ohne die Roadmap zu verfälschen.

### K9 — `license_type=commercial,modification` bei Openverse ohne Keys

Openverse funktioniert anonym (nur niedrigeres Limit); Client-Credentials heben es an. Der Auftrag sagt „fehlender Key = Tab deaktiviert".

**Empfehlung:** Für Openverse abweichen — ohne Keys **anonym weiterlaufen** und nur einen dezenten Hinweis zeigen. Ein grundlos deaktivierter Tab kostet Funktion ohne Gegenwert. Für Unsplash und Pexels gilt die Vorgabe unverändert (dort geht ohne Key gar nichts).

### K10 — Frontend-Tests: kein jsdom im Repo

`vitest` läuft ohne DOM-Umgebung; es gibt weder `@testing-library/react` noch `jsdom` in den devDependencies. Komponententests für das Overlay wären eine neue schwere Abhängigkeit.

**Empfehlung:** Testbare Logik aus der Komponente ziehen (Chip-Generierung, Gate-Auswertung, Tab-Reihenfolge, Fokuspunkt-Mathematik → reine Funktionen in `src/lib/`, mit vitest getestet), die Interaktion über einen Playwright-Fall in `frontend/e2e/admin-workflow.spec.ts` abdecken. Keine neue Test-Runtime.

### K11 — Kleinkram, ohne Rückfrage erledigt

- Neue Keys kommen in `Settings` (pydantic), nicht `os.environ` — inkl. Nachziehen von `UNSPLASH_ACCESS_KEY`.
- `EXPECTED_DB_REVISION` in `app/main.py` bei jeder Migration mitziehen.
- Picker-Komponenten unter `frontend/src/components/admin/` ablegen, damit `check-bundle.mjs` grün bleibt.
- `unsplash_download_location` bleibt **Suchergebnis-Feld**, wird nie ins gespeicherte `image`-Objekt geschrieben.
- Der alte Endpunkt `POST /admin/regions/{id}/stock-image` (Button wurde bereits aus der UI entfernt) wird in Sprint 6 samt `app/admin/stock.py` zurückgebaut, sobald der Picker steht.

---

## 3. Umsetzungsplan pro Sprint

### Sprint 1 — Datenmodell & Seed-Fix

1. `app/media/image_object.py` — kanonischer Builder + Validator für das erweiterte Bildobjekt (K6). Ein Ort, an dem `provider`/`delivery`/`role`/`focal`-Defaults gesetzt werden.
2. `app/admin/spots.py::manage_spot_image` und `app/admin/regions.py::set_region_image` auf den Builder umstellen (nicht mehr auf vier Felder zurückschneiden). `approve_hero_image` mitziehen.
3. Migration `0027_media_provenance`:
   - `media_usage` (`provider`, `external_id`, `entity_type`, `entity_id`, `role`, `created_at`) mit **partiellem** Unique-Index `WHERE external_id IS NOT NULL` — in Postgres kollidieren NULLs sonst nie, der Constraint wäre wirkungslos.
   - Galerie-Generalisierung gemäß Entscheidung zu K3, plus `position`-Spalte.
   - Datenmigration: bestehende `image`-Objekte (Spots + Regionen) auf das neue Schema heben — `provider:"unknown"`, `delivery:"hosted"`, `focal` beibehalten falls vorhanden sonst `{x:50,y:50}`, Rest `null`. Reversibel: `downgrade()` schneidet auf die vier Ursprungsfelder zurück.
   - `media_search_cache` + `media_provider_budget` (K4) — hier schon anlegen, benutzt ab Sprint 2.
4. Seed-Fix beidseitig: `image=` im `Spot(...)`-Konstruktor **und** Bilddaten in `data.py`/`data_europe.py` (Sentinel-Form, K8). `image_ready` um die Platzhalter-Regel erweitern.
5. Frontend-Typ `ImageRecord` erweitern (additiv, keine Breaking Changes).

**Akzeptanz:** `alembic upgrade head` + `downgrade -1` grün · frisch geseedeter Spot hat `image` in der DB · bestehende Bilder rendern unverändert · `pytest` grün.

### Sprint 2 — Media-Proxy

- Neuer Router `app/api/admin_media.py` (`/admin/media/*`), Auth per Router-Dependency wie überall.
- `app/media/providers/` — je Provider ein Modul mit `search(...) -> list[NormalizedResult]`, alle hinter einem Protocol wie `CommonsClient`/`StockImageClient` (Netzwerk in Tests mockbar). Commons-Client aus `app/admin/commons.py` wiederverwenden, nicht neu schreiben.
- Normalisierung + Gates zentral in `app/media/normalize.py`, `used_by` aus `media_usage` angereichert.
- Cache/Budget über Postgres (K4); Per-Provider-Degradation: jeder Provider in eigenem try/except, Teilergebnisse werden geliefert.

**Akzeptanz:** zweimal dieselbe Suche = ein Upstream-Request · simulierter Unsplash-Ausfall lässt die anderen Tabs unberührt · ohne Key liefert der Tab `{status:"disabled"}` statt 500.

### Sprint 3 — Adopt

- `POST /admin/media/adopt` — serverseitiges Neu-Auflösen, Gate-Recheck, dann getrennte Pfade: Unsplash → `download_location`-Ping + `delivery:"hotlinked"`; alle anderen → Download in `app/media/storage.py` + Derivate.
- **Offener Punkt:** „Derivate erzeugen (AVIF/WebP, responsive Breiten, Blur-Placeholder)" existiert heute nicht — `reencode_image` erzeugt *eine* Breite, und `HeroImage`s srcset-Pfad greift ausschließlich für lokale Build-Assets aus `heroManifest`. Das ist eigenständige Arbeit (Multi-Breiten-Encode + Manifest-Ersatz für DB-Bilder). Ich schlage vor, Sprint 3 mit einer Breite + korrektem `delivery` zu liefern und den Derivat-Satz als Sprint 3b zu führen, statt ihn nebenbei halb zu bauen.
- Dubletten: Hero hart gesperrt, Galerie mit Warnung. Hero-Wechsel schiebt das alte Bild in die Galerie.
- Wartungs-Job: `POST /admin/media/verify-sources`, admin-ausgelöst, markiert tote Quellen.

### Sprint 4 — Overlay-UI

- Eine Komponente `frontend/src/components/admin/MediaPicker/`, Props `entityType`/`entityId`/`role`; Tab-Reihenfolge und Chips aus einer reinen Funktion je Entitätstyp (testbar, K10).
- Vorschau rendert die **echte** `EditorialHero`-Komposition in Desktop- und Mobil-Crop. Damit das kein zweiter Renderpfad wird, extrahiere ich die Hero-Innerei so, dass Admin-Vorschau und Public-Seite dieselbe Komponente nutzen — das ist die einzige Stelle, an der Sprint 4 öffentlichen Code anfasst.
- Tastatur, Lazy-Loading mit reservierten Aspect-Boxen (kein Layout-Shift), Ladezustände pro Tab.

### Sprint 5 — Credit-Rendering

- `<ImageCredit image={…} />` aus dem Bildobjekt, ein Renderpfad für Stock **und** Community (identische Position/Stil, wie gefordert).
- Region-Hero endlich mit Attribution versorgen (K7). `adapt.ts`-Fehlmapping `source → sourceUrl` korrigieren.
- Serverseitige Validierung: Credit darf korrigiert, nicht geleert werden — im Builder aus Sprint 1 verankert, nicht nur im Formular.
- Bildkomponente verzweigt nach `delivery` (Unsplash-CDN-Parameter vs. eigene Derivate), beide respektieren `focal`.

### Sprint 6 — Admin-Integration

- „Bild suchen"-Button in Spot- und Regionsformular; Galerie-Verwaltung (Drag-Reihenfolge über `position`, Entfernen, Hero tauschen).
- „Spots ohne Hero": der bestehende `completeness`-Filter der Admin-Spotliste liefert die Daten fast schon — er wird um gap-genaue Filter (`image`, „Ortsbezug ungeprüft", „mehrfach genutzt", „Quelle tot") erweitert, statt eine Parallelliste zu bauen.
- Budget-Anzeige im Admin-Header.
- Rückbau von `app/admin/stock.py` + `stock-image`-Endpunkt.

### Sprint 7 — Tests, Doku, Konfiguration

- pytest: Normalisierung je Provider gegen eingefrorene Fixtures (`tests/fixtures/media/*.json`), Gate-Grenzwerte (3839×1920 fällt, 3840×1920 besteht), Adopt hotlinked/hosted, Dubletten-Sperre, Budget-Erschöpfung isoliert einen Tab, Seed-Regression.
- vitest: Chips, Gate-Auswertung, Tab-Reihenfolge, Fokus-Mathematik.
- Playwright: ein Durchstich Overlay → Adopt → Hero sichtbar.
- `.env.example` + README-Abschnitt; fehlender Key = Tab deaktiviert mit Hinweis.

---

## 4. Was ich vor Sprint 1 von dir brauche

| # | Frage | Meine Empfehlung |
|---|---|---|
| 1 | **K3** — Galerie-Speicher: `spot_images` generalisieren (A), neue Tabelle (B) oder Zwillingstabelle (C)? | **A** |
| 2 | **K1** — `focal` im Repo-Format `{x,y}` 0..100 statt `[0.5,0.42]`? | ja, Repo-Format |
| 3 | **K8** — Platzhalter-Seed-Bilder zählen *nicht* als „Bild vorhanden"? | ja |
| 4 | **Sprint 3b** — Derivate/Blur-Placeholder als eigener Sprint statt Beiwerk von Adopt? | ja |

Alles andere setze ich wie oben beschrieben um, ohne weitere Rückfrage.
