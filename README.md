# Surfwinddata

Surfwinddata ist eine Full-Stack-Anwendung für Wassersport-Spots,
Wettervorhersagen und Reiseplanung. Das Repository enthält die öffentliche
Website, das getrennt gebaute Admin-Dashboard, die FastAPI sowie Offline- und
Worker-Prozesse für Wetter-, Geodaten- und Gezeitenprodukte.

Dieses Repository ist die einzige kanonische Entwicklungsquelle. Das frühere
Repository `surfwinddata` wird nicht mehr gespiegelt. Beide Vercel-Projekte
werden aus diesem Repository gebaut.

## Funktionsumfang

- öffentlicher Spot- und Regionenkatalog mit Karte und Suche
- Live-Wetter und stündliche Vorhersage für alle zehn Forecast-Tage
- saisonale Windklimatologie, Spot-Vergleiche und Alternativen
- öffentliche Konten, Favoriten und Community-Beiträge
- rollen- und sitzungsbasiertes Admin-Dashboard für Katalog, Medien,
  Moderation, Nutzer und Betriebsaufgaben
- versionierte PostgreSQL/PostGIS-Migrationen sowie Redis-Caches
- getrennte Public- und Admin-Builds mit fail-closed API-Routing

Die laufende API-Dokumentation ist lokal unter `/docs` verfügbar. Eine statische
Aufzählung aller Routen im README wird bewusst vermieden, damit OpenAPI die
maßgebliche Schnittstellenbeschreibung bleibt.

## Architektur

```text
React/Vite browser
  -> FastAPI (app/main.py)
     -> PostgreSQL/PostGIS
     -> Redis
     -> weather, tide, geodata and media providers
```

Wichtige Einstiegspunkte:

- [Repository- und Architekturkarte](docs/architecture/repository-map.md)
- Backend: `app/main.py`
- Frontend: `frontend/src/main.tsx`
- Migrationen: `alembic/versions/`
- [Vercel-Deployment](DEPLOY-VERCEL.md)
- [Production-Recovery-Runbook](docs/production-recovery-runbook.md)

## Voraussetzungen

- Python 3.11 oder neuer
- Node.js 22
- Docker mit Compose für PostgreSQL/PostGIS und Redis

## Lokale Einrichtung

1. Infrastruktur starten:

   ```powershell
   docker compose up -d db redis
   ```

2. Python-Umgebung erstellen und Abhängigkeiten installieren:

   ```powershell
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Lokale Konfiguration anlegen:

   ```powershell
   Copy-Item .env.example .env
   ```

   Die Vorlagen enthalten ausschließlich lokale oder beispielhafte Werte.
   Echte Secrets gehören in lokale Umgebungsvariablen beziehungsweise in die
   Secret Stores von GitHub und Vercel und dürfen nie committed werden.

4. Schema migrieren und optionale Beispieldaten laden:

   ```powershell
   $env:DATABASE_URL='postgresql+psycopg://surf:surf@localhost:5432/surfwind'
   alembic upgrade head
   python -m app.seed.seed
   ```

5. Backend und Frontend in getrennten Terminals starten:

   ```powershell
   python -m uvicorn app.main:app --reload
   npm --prefix frontend ci
   npm --prefix frontend run dev
   ```

Lokale Standardports sind `8000` für die API, `5173` für Vite, `5432` für
PostgreSQL und `6379` für Redis.

## Prüfungen

Für normale Änderungen zuerst den passenden fokussierten Check ausführen:

```powershell
./scripts/check.ps1 frontend
./scripts/check.ps1 backend
./scripts/check.ps1 changed
```

Einzelne Prüfungen:

```powershell
pytest -q
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run test:e2e
python -m pip_audit -r requirements.txt
npm --prefix frontend audit --audit-level=high
```

Die GitHub-CI prüft Backend, Frontend, Browser-Flows, Migrationen,
Abhängigkeiten und das Git-History-Secret-Scanning. CodeQL und Dependabot decken
statische Analyse und laufende Dependency-Aktualisierungen ab.

## Deployment

Aus einem Commit entstehen zwei getrennte Vercel-Projekte:

| Projekt | Build | API |
|---|---|---|
| Public | öffentliche SPA ohne Admin-Code | Public- und Community-Routen |
| Admin | Dashboard-Bundle | zusätzlich Auth- und Admin-Routen |

Die Build- und Runtime-Schalter sowie die notwendigen Umgebungsvariablen sind in
[DEPLOY-VERCEL.md](DEPLOY-VERCEL.md) beschrieben. Produktionsmigrationen laufen
nur über den geschützten Recovery-Workflow und die `production`-Umgebung.

## Dokumentation

- [Forecast-System](docs/forecast-system-v1.md)
- [Wettervertrag](docs/weather-v1.md)
- [Windklimatologie V3](docs/wind-climatology-v3.md)
- [Geodaten Phase 1–4](docs/geodata-phase1.md)
- [Gezeiten](docs/tides.md)
- [Spot-Bulk-Import](docs/spot-bulk-import.md)
- [Admin-Audit](docs/admin-audit.md)
- [Security-Ausnahmen](docs/security-exceptions.md)
- [Asset-Provenienz](frontend/ASSETS.md)

Historische Spezifikationen und Audits dokumentieren Entscheidungen, sind aber
keine aktuelle API- oder Betriebsreferenz.

## Sicherheit und Lizenz

Sicherheitslücken bitte nach [SECURITY.md](SECURITY.md) vertraulich melden.
Produktionsdaten, Zugangsdaten und Laufzeitberichte gehören nicht in Git.

Der eigene Projektcode ist proprietär; siehe [LICENSE](LICENSE). Hinweise und
Lizenztexte für Drittanbieter befinden sich in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
