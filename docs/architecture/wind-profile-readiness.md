# Windprofil-Bereitschaft

Stand: 24. September 2026. Dieser Bericht trennt drei unabhängige Dinge:

1. redaktionelle Windrichtungen für Empfehlungen,
2. lokale Forecast-Physik und deren WP1-Freigabe,
3. Exact-Point-Evidenz für LiveWind.

Keiner dieser Pfade darf Werte aus `spots.facing` in eine Küstennormale oder
einen physikalischen Korrekturfaktor umdeuten.

## Produktionsbefund

Der öffentliche Katalog enthält 32 veröffentlichte Kite-Spots. Bei 25 fehlt
`facing`; sieben besitzen den Wert. Die Recommendation-Surfaces `now`,
`next_week`, `season` und `region` liefern zum Prüfzeitpunkt jeweils eine leere
Liste. Die APIs, das Schema und der Cache sind gesund; die leeren Listen sind
eine Datenbereitschaftsfrage.

Aktivierungs- und Reviewdaten der Wetterprofile sind absichtlich nicht Teil des
öffentlichen Spot-Vertrags. Den verbindlichen Detailstand liefert daher nur der
geschützte Adminpfad `/admin/weather` beziehungsweise
`GET /admin/weather/profiles` und pro Spot
`GET /admin/weather/spots/{spot_id}/profile`.

## Mindestanforderungen für Empfehlungen

Ein veröffentlichter Kite-Spot ist nach dem aktuellen Scoring-Vertrag erst
empfehlbar, wenn alle folgenden Bedingungen erfüllt sind:

- `kitesurf` ist in `spot.sports` enthalten.
- `spot.facing` ist gesetzt. Der Wert wird im allgemeinen Spot-Editor unter
  „Ausrichtung“ gepflegt und ist keine Küstennormale.
- Ein `SpotWeatherProfile` existiert und ist `active=true`.
- Das Profil ist fachlich geprüft (`reviewed_at` ist gesetzt).
- Mindestens ein Richtungssektor ist aktiviert.
- Für `now` und `next_week` existiert im Forecast eine machbare dreistündige
  Tageslicht-Session innerhalb des Personal Bands.
- Für `season` existiert eine passende aktive V3-Variante für das quantisierte
  Personal Band.

Die Qualitätsstufen `coastal` und `extended` benötigen zusätzlich IANA-Zeitzone,
Höhe und eine fachlich belegte wasserwärtige Küstennormale. Ein
`coordinates`-Profil erfindet diese Angaben nicht. `advanced` bleibt gesperrt.

## Redaktioneller Ablauf pro Spot

1. Im Spot-Editor `facing` prüfen und mit einer redaktionellen Quelle setzen.
2. Unter `/admin/weather/{spot_id}` das Profil anlegen, aktivieren und den
   Reviewstatus erst nach fachlicher Prüfung setzen.
3. Nutzbare Windrichtungen im V3-Richtungseditor als meteorologische
   *Von-Richtungen* auswählen und reviewen. Dadurch wird auch ein V3-Lauf
   eingeplant.
4. Forecast-Korrektursektoren getrennt behandeln. Neue Kandidaten bleiben
   inaktiv und dürfen erst mit einem aktuellen, kontextgebundenen WP1-Gate-Run
   aktiviert werden.
5. Forecast neu berechnen, Diagnostik prüfen und danach die Recommendation-
   Surfaces kontrollieren.

Die Pilotmatrix in `config/weather-pilot-spots.json` enthält noch keine
kanonischen Spot-IDs. Vor einer Serienpflege müssen Product Owner,
Profilersteller, Zweitprüfer und akzeptierte Quellen festgelegt werden. Reale
Profilwerte dürfen nicht aus `facing`, Beschreibungen oder vermuteter Geografie
abgeleitet werden.

## Bekannte Sektor-Semantik

`SpotWeatherSector` speichert derzeit zwei fachlich verschiedene Arten von
Sektoren: die mit `note="Windklimatologie V3"` gekennzeichneten nutzbaren
Windrichtungen und versionierte Forecast-Korrektursektoren. Forecast-Serving und
Aktivierung trennen beide Arten bereits explizit. Die Recommendation-Funktion
`_direction_windows()` sowie `reviewed_direction_windows()` der V3-Aufbereitung
übernehmen dagegen noch alle aktivierten Zeilen.

Das ist vor der breiten Profilpflege zu entscheiden und zu bereinigen. Eine
aktivierte Forecast-Korrekturversion kann sonst die kuratierten Nutzrichtungen
erweitern und damit die Machbarkeitsprüfung beeinflussen. Die sichere Zielregel
ist, Empfehlungen und `direction_mode=usable` ausschließlich aus den im
V3-Richtungseditor reviewten Nutzrichtungen zu bilden. Die Umstellung benötigt
eine Bestandsprüfung bestehender Profile und einen eigenen Contract-Test, damit
Profile ohne migrierte V3-Auswahl nicht versehentlich unempfehlbar werden.

## Exact-Point-Workflow

Der Exact-Point-Pfad befüllt keine Windprofile. Er erfasst rohe GFS/ICON-Werte
an Stations- und Spotkoordinaten, persistiert kompakte u/v-Punktbundles und
liefert später reproduzierbare Station-minus-Modell-Evidenz für LiveWind.

Der gehostete Capture-Job verwendet bewusst einen joblokalen GRIB-Cache unter
`$RUNNER_TEMP`. Die dauerhafte Übergabe erfolgt über die Tabellen für
Exact-Point-Bundles; der Residual-Job liest diese mit `persisted-residuals`.
Ein gemeinsames persistentes Dateisystem ist für diesen gehosteten Pfad nicht
erforderlich.

Für eine kontrollierte Aktivierung werden benötigt:

- Repository Secret `LIVE_WIND_POINT_DATABASE_URL` mit dem vorgesehenen,
  migrierten Datenbankziel und minimal nötigen Rechten,
- Variable `LIVE_WIND_POINT_CAPTURE_ENABLED=true`,
- nach erfolgreicher Punktabdeckung Variable
  `LIVE_WIND_RESIDUALS_ENABLED=true`,
- optional begrenzte Werte für `LIVE_WIND_EXACT_CAPTURE_TILE_LIMIT`,
  `LIVE_WIND_EXACT_POINT_BATCH_SIZE` und `LIVE_WIND_RESIDUAL_BATCH_SIZE`.

Capture wird zuerst aktiviert. Erst wenn die Runs ohne Providerfehler kompakte
Bundles schreiben und deren Abdeckung geprüft ist, folgt der Residual-Job.
Beide Schalter bleiben bis dahin explizit `false`. Exact-Point-Evidenz schaltet
weder LiveWind noch Forecast-Korrekturen automatisch öffentlich.

## Offene Betriebsarbeit

- Die 25 Kite-Spots ohne `facing` redaktionell abarbeiten.
- Im geschützten Wetterprofil-Dashboard die exakten Zahlen für fehlende,
  inaktive, ungeprüfte und sektorlose Profile erfassen.
- Zunächst eine benannte Pilotgruppe mit Quellen und Vier-Augen-Review
  vervollständigen; danach die Recommendation-Surfaces erneut prüfen.
- Einen dedizierten Datenbankzugang für Exact Points bereitstellen, bevor die
  beiden derzeit deaktivierten Jobs eingeschaltet werden.
