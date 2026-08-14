# Wetterdaten W1 – Neon-Abnahme

Stand: 13. August 2026
Endstatus: **`ready_for_user_review`**
Reviewempfehlung: **mit Auflagen freigeben** – Canary akzeptieren, vor einem Bestandsbackfill die unten genannten offenen Browser-/Race-Prüfungen reviewen.

## Neon- und Testdatenbank-Preflight

- Neon-Verbindung erfolgreich, Psycopg-Client-TLS aktiv.
- Alembic unverändert auf `0034_geodata_shadow_phase2`; keine Migration ausgeführt.
- 52 Spots, davon 49 veröffentlicht; benötigte Forecast-/Job-/Spotstrukturen vorhanden.
- Die getrennte lokale `surfwind_test`-PostGIS-Datenbank wurde über den dokumentierten Compose-Service eingerichtet. Sie ist nachweislich von Neon getrennt und darf durch `tests/conftest.py` neu aufgebaut werden.
- Die relevante Backendgruppe bestand mit **52/52 Tests**, ohne Skip.

## Fehlerkorrekturen aus der Abnahme

1. Ein veralteter API-Test erwartete öffentliche Rohmodellnamen. Er prüft nun die verbindliche Schutzgrenze `models == []`, während die Zahl der Konsensbeiträge weiterhin über das aggregierte Spread-Feld geprüft wird.
2. `wind_ms` und `gust_ms` wurden vom Publicschema versehentlich verworfen. Beide bestehenden optionalen SI-Felder sind wieder im Schema enthalten; Windberechnung und Gewichte blieben unverändert.
3. Fehlende Geoprofile hätten im Forecastpublisher einen WorldCover-Remoteabruf ausgelöst. Forecastgeneration erzeugt jetzt ein ehrliches neutrales Koordinatenprofil ohne Remote-Rasterzugriff; dedizierte Geoprofilworkflows behalten ihre bisherige Remote-Fähigkeit. Dadurch bleibt W1 unabhängig von Phase 3/4 und der Canary lud keine Copernicus-/CDSE-Daten.
4. Der vorhandene Open-Meteo-Client erfasst sanitisiert Requestversuche und Responsebytes für begrenzte Betriebsabnahmen.

## Auswahl und Dry-Run

| Spot | Klassifikation | Koordinatenhash | Geplante Requests |
|---|---|---|---:|
| Baleal | `ocean` | `b54d772a12768739` | 1 Atmosphäre + 1 Marine |
| Fischbach Ost | `lake` | `d8135ed7f425a5b3` | 1 Atmosphäre + 0 Marine |
| Lo Stagnone | `lagoon` | `74981600ec0a6698` | 1 Atmosphäre + 1 Marine |

Dry-Run: exakt drei Spots und fünf Providerrequests; keine Writes oder Bytes.

## Live-Canary

Der Canary lief sequenziell über `enqueue` und `run_job` des vorhandenen Publishers, mit einem Versuch pro Endpoint und globalem Acht-Request-Wächter.

Für Fischbach Ost existierte bereits ein deduplizierter, noch aktiver `spot_created`-Lifecyclejob. `enqueue` erzeugte deshalb korrekt keinen parallelen Canaryjob, sondern der Lauf verarbeitete diesen vorhandenen Job. Baleal und Lo Stagnone erhielten zwei dedizierte `weather_w1_canary`-Jobs. Alle drei Generationen wurden genau einmal verarbeitet.

| Spot | Job | Dauer | Snapshot | Größe | Atmosphäre | Solar | Marine | Horizont Atm./Marine | Rasterdistanz |
|---|---|---:|---|---:|---|---|---|---:|---:|
| Baleal | succeeded | 2,406 s | `566de942-c4eb-4211-8fe2-ea0b1c9b4987` | 42.843 B | available | available | available | 218 / 240 h | 3,146 km |
| Fischbach Ost | succeeded | 1,204 s | `133716bf-1eb6-410d-a4b4-477e9159b9f9` | 41.937 B | available | available | not_applicable_inland | 217 / 0 h | – |
| Lo Stagnone | succeeded | 2,093 s | `37825ac5-d137-4244-b150-26176a5535c2` | 41.863 B | available | available | available | 217 / 240 h | 8,356 km |

Providertelemetrie:

| Gruppe | Requests | Retries | Bytes |
|---|---:|---:|---:|
| Atmosphäre | 3 | 0 | 517.818 |
| Marine | 2 | 0 | 27.841 |
| Gesamt | 5 | 0 | 545.659 |

Fischbach Ost erhielt keinen Marinerequest und enthält keine Wellen-/SST-Werte. Beide Meeresrasterpunkte liegen deutlich innerhalb der konfigurierten 25-km-Grenze.

## Snapshot- und Public-Vertrag

- Alle drei Snapshots: `weather-v2`, zehn lokale Tageszusammenfassungen, strikt sortierte und eindeutige UTC-Stunden.
- Zeitzonen: Baleal `Europe/Lisbon`, Lo Stagnone `Europe/Rome`, Fischbach Ost `Europe/Berlin`.
- Stunden- und Tagesfelder vollständig vorhanden; Nullwerte bleiben nullable.
- Publicmodell `surfwinddata`, öffentliche Rohmodellliste leer, Attribution vorhanden, kein `internal`-Block im Payload.
- Produktname wird durch den unveränderten Publisher weiterhin als **Surfwinddata Forecast** ergänzt.
- Je Spot existiert genau ein aktiver Snapshot. Baleals alter Snapshot blieb historisch erhalten; er wurde erst durch die erfolgreiche neue Aktivierung inaktiv.
- Baleal-Baseline: `d89379fd-ffbd-4369-a856-401fa51f5f2e`, 10 Tage, 26.323 B. Neuer Snapshot: 42.843 B. Lo Stagnone und Fischbach Ost hatten vorher keinen aktiven Snapshot.
- Ein numerischer Vorher-/Nachher-Vergleich einzelner Windstunden ist wegen eines neuen Providerlaufs zu einem anderen Abrufzeitpunkt nicht als Gleichheit interpretierbar. Die unveränderte Windlogik und die wiederhergestellten SI-Felder sind durch die vollständige relevante Testgruppe abgesichert.

## Tests und UI

- Backend relevant: **52 bestanden, 0 übersprungen**.
- Frontend: **181 bestanden** in 22 Dateien.
- TypeScript/Vite-Build, Ruff, ESLint und Python-Compilecheck bestanden.
- UI-Detektor: 0 Befunde.
- Komponentenvertrag zeigt zehn Tageszeilen, nächste 24 Stunden, zugängliche Tag-/Nachticons, alle W1-Werte, Polarstatus und „Nicht verfügbar“. Marine wird nur bei `availability.marine == available` angezeigt.
- Ein realer Browser-Screenshotlauf gegen Neon wurde nicht automatisiert; Mobile/Desktop sowie Browserkonsole bleiben ein manueller Reviewpunkt.

## Grenzen und Empfehlung

Kein 5-Spot-Validationlauf, kein weiterer Backfill, keine direkte Modellaktivierung, keine Gewichtsänderung, kein Deployment, Commit, Push oder PR wurde ausgeführt.

Empfehlung: Den Drei-Spot-Canary **mit Auflagen freigeben**. Vor Freigabe eines breiteren Backfills sollten die reale Mobile-/Desktop-Darstellung und ein expliziter DB-Racetest für ältere/jüngere Snapshotgenerationen reviewt werden.
