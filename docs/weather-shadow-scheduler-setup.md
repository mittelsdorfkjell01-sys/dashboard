# Weather-Shadow-Scheduler: Produktionskonfiguration

## Architektur

Der produktive Scheduler ist GitHub Actions (`.github/workflows/weather-shadow.yml`).
Vercel Cron wird für diesen Ablauf nicht verwendet: Vercel ruft Cron-Ziele per `GET`
auf, während der sicherheitskritische Weather-Shadow-Endpunkt ausschließlich `POST`
akzeptiert. Außerdem bleibt die lang laufende Provider-Abfrage im GitHub-Worker und
nicht in der Vercel-Funktion.

- Ziel: `https://kjellmittelsdorf.de/api/cron/weather-shadow`
- Methode: `POST`
- Header: `Authorization: Bearer <WEATHER_SHADOW_CRON_SECRET>`
- Header: `Content-Type: application/json`
- Body: keiner
- Takt: `41 */6 * * *` (00:41, 06:41, 12:41 und 18:41 UTC)
- HTTP-Timeout: 30 Sekunden; zwei Wiederholungen mit zehn Sekunden Abstand
- Workflow-Timeout: 15 Minuten
- Überlappung: durch eine feste Concurrency-Gruppe verhindert

Der HTTP-Aufruf legt atomar höchstens einen Job pro Study-Version und GFS-Modelllauf
an und antwortet sofort. Der nachfolgende Worker verarbeitet den gespeicherten
Modelllauf. Wiederholte Scheduler-Aufrufe sind dadurch idempotent.

## Einmalige Einrichtung

1. Im Vercel-Projekt für `kjellmittelsdorf.de` unter **Settings → Environment
   Variables** `CRON_SECRET` für Production setzen.
2. In GitHub unter **Settings → Secrets and variables → Actions → Secrets**
   `WEATHER_SHADOW_CRON_SECRET` mit demselben Wert setzen.
3. Dort zusätzlich `DIRECT_DATABASE_URL` und
   `WEATHER_SHADOW_WORKER_JWT_SECRET` als Repository-Secrets setzen.
4. Unter **Variables** `WEATHER_SHADOW_ENDPOINT` exakt auf
   `https://kjellmittelsdorf.de/api/cron/weather-shadow` setzen.
5. Erst nach erfolgreichem Production-Deploy unter **Actions → Weather Shadow
   Collector → Run workflow** einen manuellen Probelauf auf `main` starten.

Secrets dürfen weder in Workflow-Dateien noch in Logs oder Screenshots eingefügt
werden.

## Erwartete Antworten und Kontrolle

- `202` mit `status: accepted`: neuer Modelllauf wurde eingereiht.
- `202` mit `status: deduplicated`: derselbe Modelllauf war bereits vorhanden.
- `401`: Authorization-Header fehlt oder stimmt nicht überein.
- `405`: falsche HTTP-Methode, insbesondere `GET`.
- `503`: `CRON_SECRET` fehlt im Admin-Backend.

Die Ausführungshistorie steht unter **Actions → Weather Shadow Collector**. Der
interne Status ist außerdem über den Admin-Endpunkt
`/api/admin/weather/shadow-study/status` sichtbar. Zum kontrollierten Stoppen im
Workflow-Menü **… → Disable workflow** wählen; bereits gespeicherte Shadow-Daten
bleiben erhalten und der öffentliche Forecast wird nicht verändert.

## Noch offene Produktionsabnahme

Der zuletzt geprüfte Vercel-Production-Deploy für Commit `72fc729` ist
fehlgeschlagen. Der Build meldete einen TypeScript-Typfehler in
`frontend/src/lib/__tests__/adapt.test.ts` (`region_name` optional gegenüber
`string | null`). Deshalb dürfen Live-Smoke-Test und Scheduler-Aktivierung erst
nach erfolgreichem Deploy erfolgen.

Quellen: [Vercel Cron Jobs](https://vercel.com/docs/cron-jobs),
[Vercel Cron verwalten](https://vercel.com/docs/cron-jobs/manage-cron-jobs),
[Vercel Function Duration](https://vercel.com/docs/functions/configuring-functions/duration),
[GitHub Workflow manuell starten](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow?tool=cli).
