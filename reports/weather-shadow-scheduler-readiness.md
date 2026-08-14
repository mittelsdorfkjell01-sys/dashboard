# Weather-Shadow-Scheduler – Readiness

Endstatus: `awaiting_deployment_confirmation`

## Deployment und Scheduler

- Gepushter Branch: `main`
- Gepushter Commit: `72fc729a0dc97f8ebc9874d2c4d70796660b7e46`
- Hosting: zwei Vercel-Projekte aus demselben Repository; der Shadow-Router ist nur
  im Admin-Projekt `dashboard` mit dem Alias `dashboardsurfwind.vercel.app` und
  `ENABLE_ADMIN_API=true` aktiv.
- Letzter Production-Deploy dieses Commits: fehlgeschlagen. Vercel meldete einen
  Frontend-TypeScript-Typfehler in `frontend/src/lib/__tests__/adapt.test.ts`.
- Schedulerklassifikation: `repo_managed_scheduler` über den bereits betrieblich
  genutzten GitHub-Actions-Fallback. Vercel Cron scheidet aus, weil er nur `GET`
  aufruft und der Endpunkt bewusst nur `POST` akzeptiert.
- Risiko: Geplante GitHub-Actions-Ausführungen können verzögert werden oder
  ausfallen. Idempotenz und begrenztes Wiederaufnehmen verhindern Duplikate, sind
  aber keine garantierte lückenlose Ausführung.

## Endpoint-Audit

- Effektiver Pfad: `POST https://dashboardsurfwind.vercel.app/api/cron/weather-shadow`
- Authentifizierung: Header `Authorization: Bearer <secret>`; Backendvariable
  `CRON_SECRET`; zeitkonstanter Vergleich.
- Kein Request-Body erforderlich; `Content-Type: application/json` wird vom
  Scheduler gesetzt.
- Fehlendes/falsches Secret: `401`; fehlende Backendkonfiguration: `503`;
  falsche Methode: `405`; korrekter neuer oder deduplizierter Request: `202`.
- Antwort enthält nur Jobstatus, Job-ID, Study-Version, Modelllauf und
  `public_effect: none`; keine Provider-Rohdaten oder Secrets.
- Der Request führt keine Providerabfrage aus. Er legt nur atomar einen Job an und
  antwortet innerhalb des normalen Datenbank-Roundtrips.

## Laufidentität, Worker und Beobachtbarkeit

Die eindeutige Identität kombiniert `swd-phase4-shadow-v1` und die kanonische
sechsstündige GFS-Modellgeneration. PostgreSQL `ON CONFLICT DO NOTHING` schützt
auch parallele Scheduler-Retries. Der bestehende `ForecastProcessingJob`-Stack
claimt mit Row-Lock/`SKIP LOCKED`; maximal drei Versuche sind erlaubt. Nach einem
harten Prozessabbruch kann ein älter als 30 Minuten stehender Job erneut geclaimt
werden. Der Worker verarbeitet ausdrücklich den im Job gespeicherten Modelllauf.

Der Adminstatus zeigt ohne Rohpayloads: Jobzustand, Versuch/Retry, Modelllauf,
Study-Version, fünf Referenzspots, Forecastpunkte, Providerrequests und Bytes,
Beobachtungspunkte/Stationsblocker, Start/Ende/Laufzeit, nächsten Modelllauf und
`public_effect: none`. Authentifizierungsannahme und -ablehnung werden ohne Header
oder Tokenwert protokolliert.

## Lokale Änderungen und Verifikation

- HTTP-Endpunkt auf schnelle Jobanlage mit `202` umgestellt.
- Job-Enqueue, Claiming, begrenzter Retry und Workerübergabe ergänzt.
- GitHub-Actions-Workflow mit UTC-Schedule `41 */6 * * *`, manuellem Dispatch,
  Secretreferenzen, Timeout, Retry und Overlap-Schutz ergänzt.
- Admin-Diagnostik und Setup-Dokumentation erweitert.
- Relevante Backend-/Forecast-/Shadow-/Jobtests: 47 bestanden.
- Frontendtests: 181 bestanden; ESLint bestanden.
- Ruff und `git diff --check`: bestanden.
- TypeScript/Vite-Build: lokal bestanden; Chunkgrößenwarnung ohne Buildabbruch.
- Public-Baseline: Tests bestätigen unveränderte aktive Snapshots;
  `public_effect` bleibt `none`.

Live-Smoke-Test und Scheduleraktivierung wurden nicht ausgeführt, weil kein
erfolgreicher Deploy der neuen Konfiguration bestätigt ist. Es erfolgte kein
Commit, Push, Deployment oder PR.

## Stationsstatus

| Spot | Kandidat | Distanz | Höhe / Exposition | Daten und Historie | Lizenz / Vollständigkeit | Klasse und Entscheidung |
|---|---|---:|---|---|---|---|
| Baleal | IPMA Cabo Carvoeiro 531 | ca. 6.0 km | Station 32 m; exponierte Kapsituation, Höhenunterschied zum Strand ca. 32 m; Messhöhe nicht bestätigt | Offizielle aktuelle Beobachtungen; 10-m-Windrichtungsklassen dokumentiert; Böe/Historienvollständigkeit noch zu prüfen | Offizielle IPMA-API; Wiederverwendung/Attribution vor Adapteraktivierung festhalten; Live-Daten teils nicht verfügbar | `B-review_required`; bester Kandidat, nicht als Ground Truth aktivieren |
| Brouwersdam | KNMI Oosterschelde WP | ca. 15.5 km | Offshore-/Küstenmesspunkt; Sensorhöhe ca. 16.5 m, daher Normalisierung auf 10 m nötig | Wind, Richtung und Böen plausibel; aktuelle Stations-ID und durchgehender API-/Historienzugang noch zu bestätigen | Offizielle KNMI-Daten; Lizenz/Attribution und Vollständigkeit im konkreten Datensatz bestätigen | `B-review_required`; Wilhelminadorp 323 (ca. 25.6 km, Sensor 10 m) als belastbarer Fallback |
| Mundaka | AEMET Matxitxako 1057B | ca. 6.8 km | 93 m hohe, exponierte Klippe; großer Höhen-/Expositionsunterschied zur Bucht | Stundenwerte für Windgeschwindigkeit, Richtung und Böe; Echtzeit-Automatendaten nur vorläufig qualitätsgeprüft; Historie über OpenData zu prüfen | AEMET OpenData erlaubt Wiederverwendung mit Attribution; API-Schlüssel/Adapter fehlen | `C-review_required`; nicht repräsentativ genug für automatische Ground Truth |
| Lo Stagnone | Trapani Birgi | ca. 4.0 km | Flughafen/Küstenebene; Stations- und Sensorhöhe nicht aus offizieller Quelle bestätigt | Oberflächen-Wind/Böe/Richtung, Aktualität und Historienzugang nicht offiziell bestätigt | Offizielle API und kommerzielle Wiederverwendung/Attribution ungeklärt | `blocked_observation_source`; keine Aktivierung |
| Pozo Izquierdo | AEMET Gran Canaria Aeropuerto C649I | ca. 12.2 km | Station 24 m; gleiche Inselseite, aber Flughafenexposition bildet lokale Küstenbeschleunigung/Orographie nicht sicher ab; Messhöhe zu bestätigen | Stundenwerte für Wind, Richtung und Böe; Historie über OpenData zu prüfen | AEMET OpenData mit Attribution; API-Schlüssel/Adapter fehlen | `C-review_required`; nur Vergleichsstation, keine automatische Ground Truth |

Aktivierte Stationsbindungen: **0 von 5**. Bias-Korrektur bleibt deaktiviert.
