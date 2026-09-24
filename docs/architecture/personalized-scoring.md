# Personalisiertes Scoring – verbindliche Grundlage

> Diese Datei wird in Phase A als `docs/architecture/personalized-scoring.md` ins Repo `dashboard` übernommen. Alle Phasen-Prompts verweisen darauf. Änderungen an Produktentscheidungen passieren hier, nicht in einzelnen Prompts.

## 1. Produktentscheidungen (fix)

| # | Entscheidung |
|---|---|
| E1 | **Der Score ist für Nutzer vollständig unsichtbar.** Keine Zahl, kein Prozent, keine Kategorie (gut/mäßig/nein), keine Begründung, keine Tags, kein „weil du …“, kein „Match“. Nutzer sehen nur kuratierte, sortierte Listen („Aktuelle Top-Spots für dich“, „Interessant nächste Woche“, „Deine Saison“, „Top in Region X“) und eine personalisierte Reihenfolge in Suche und Region. |
| E2 | **Kitesurfen zuerst (personalisierte Engine).** Nur `kitesurf` nutzt die volle personalisierte Rider-Band-Engine. Wing, Windsurf und Surf behalten das bestehende Scoring (`app/scoring/`, Gates + Magnitude bzw. Klimatologie). **Amendment 2026-09-25:** Auf Produktentscheidung werden die Empfehlungs-Ausspielflächen (`/recommendations`) für **alle** Sportarten freigeschaltet — Nicht-Kite über das bestehende Scoring (kein erfundenes Personal Band; einzige Rider-Eingabe ist das Level via `level_offsets`), Ranking-Utility = Anteil guter Tageslichtstunden im Surface-Fenster bzw. Klimatologie-Fit für `season`. Siehe `app/recommendations/multisport.py`. |
| E3 | **Nicht eingeloggte Nutzer** werden mit einem **Durchschnitts-Rider-Profil** bewertet (Abschnitt 4, Kite). Kein Session-Profil, keine Abfrage. **Amendment 2026-09-25:** Zusätzlich existiert ein **Sport-übergreifendes Aggregat** (`sport=all`) für die ausgeloggte Landing-Ansicht „Alle Sportarten": pro Spot wird über alle unterstützten Sportarten der **höchste** Nutzwert genommen („bestes Sport gewinnt"). Immer anonym, edge-cachebar. |
| E4 | **Nur Repo `dashboard`.** `surfwinddata` wird nicht angefasst. |
| E5 | **Benachrichtigungen kommen später.** Nichts davon wird gebaut. Alles Neue muss aber so geschnitten sein, dass ein späterer Dispatcher die Engine im Batch pro Nutzer aufrufen kann (Abschnitt 8). |
| E6 | Admins dürfen alles sehen. Der Scoring-Inspektor im Dashboard zeigt Zahlen und Komponenten. Unsichtbarkeit gilt ausschließlich für öffentliche Oberflächen und öffentliche API-Responses. |

## 2. Vokabular

- **Level (kanonisch, einzig gültig):** `beginner`, `advanced`, `expert`, `competition` (Quelle: `app/admin/constants.py::LEVELS`). Rider-Profile verwenden exakt dieselben Keys. Altwerte `intermediate` → `advanced` und `pro` → `expert` werden nur beim Import gemappt.
- **Personal Band (Kite):** `[min_kt, ideal_lo_kt, ideal_hi_kt, max_kt]` plus `gust_tolerance_kt`. Dies ist das persönliche Windfenster, abgeleitet aus Gewicht × Quiver × Board × Level.
- **Recommendable:** Ein Spot darf nur dann in einer Empfehlungsliste auftauchen, wenn er für die Sportart reviewte Richtungssektoren (`SpotWeatherSector`, aktives Profil mit `reviewed_at != null`) und ein gesetztes `facing` hat. Nicht empfehlbare Spots bleiben in Suche und Karte, erscheinen dort aber hinter allen empfehlbaren Treffern.
- **Session:** mindestens 3 aufeinanderfolgende Tageslichtstunden am selben lokalen Kalendertag, in denen jede Stunde die Machbarkeit erfüllt (analog zur V3-Definition in `docs/wind-climatology-v3.md`).
- **Surface:** eine Ausspielfläche mit eigenem Zeitfenster und Kandidatenmenge (Abschnitt 6).

## 3. Rider-Modell

Pro `app_users`-Eintrag:

- **Grundprofil:** `weight_kg` (Pflicht für Personalisierung), `home_location` (Punkt, optional), `max_travel_km` (optional), `travel_mode` ∈ `day_trip | weekend | trip | camper` (Default `day_trip`), `availability` (Wochentage, optional; leer = jeder Tag), `min_water_temp_c` (optional), `excluded_bottoms` (Teilmenge von `BOTTOM_TYPES`).
- **Sport-Profil (Kite):** `level`, `style_weights` (Gewichte 0–3 je Key aus `STYLES`), `preferred_water_character` (Teilmenge von `WATER_CHARACTERS`).
- **Quiver:** `gear_items` mit `kind` (`kite | board | foil`), `size` (m² für Kites, cm oder Liter für Boards), `board_type` (`twintip | surfboard | foil | bigair_twintip`), `active`.

Körpergröße wird **nicht** erfasst.

## 4. Durchschnitts-Rider (anonym)

Wird in `scoring_params` unter `default_rider.kitesurf` versioniert gespeichert und im Admin editierbar. Startwerte (Annahme, in Phase E aus dem Median echter Profile neu kalibrieren):

```json
{ "weight_kg": 78, "level": "advanced",
  "quiver": [{"kind":"kite","size":9},{"kind":"kite","size":12},{"kind":"board","board_type":"twintip"}],
  "style_weights": {"freeride": 2, "freestyle": 1, "big_air": 1, "wave_riding": 0, "wavekite": 0},
  "travel_mode": "day_trip" }
```

Ohne Standort ist die Erreichbarkeit für Anonyme neutral (Faktor 1).

## 5. Bewertung (Kite)

### 5.1 Personal Band

Für jeden aktiven Kite der Größe `s` gilt der Kernwind `w* = k_board × weight_kg / s`, und der Schirm deckt `[w* × f_lo, w* × f_hi]` ab. Die Vereinigung über den Quiver ergibt `[min_kt, max_kt]`, die Kernwinde der Schirme ergeben `[ideal_lo, ideal_hi]`. Das Level kappt `max_kt` und setzt `gust_tolerance_kt`. Alle Faktoren (`k_board` je Board-Typ, `f_lo`, `f_hi`, Level-Caps) sind **Startwerte in `scoring_params`**, nicht im Code hart verdrahtet, und werden im Admin kalibriert. Beispiel-Startwerte: `k_twintip = 2.2`, `k_foil ≈ 1.4`, `f_lo = 0.8`, `f_hi = 1.35`.

Phase B startet mit der versionierten Parameterversion 3: `k_board` ist 2,2
(Twintip), 2,0 (Surfboard), 1,4 (Foil) und 2,35 (Big-Air-Twintip).
Die Level-Caps/Böentoleranzen in Knoten sind 24/5 (Einsteiger), 34/8
(Fortgeschritten), 42/12 (Experte) und 50/15 (Competition). Der dokumentierte
Code-Fallback ist identisch mit diesem Seed; aktive Datenbankparameter haben
Vorrang. Das Durchschnittsprofil wiegt 78 kg, fährt Advanced und nutzt 9/12 m²
mit Twintip.

Phase E ergänzt Version 4. Das Sozialsignal ist darin mit einem kleinen
Startgewicht von 0,02 und einer Mindestgruppe von 20 konfiguriert, bleibt aber
bis zum Nachweis einer Verbesserung wirkungslos (`validated=false`). Weitere
Änderungen entstehen ausschließlich als freigegebene, neue Versionen. Das
fortlaufende Änderungsprotokoll steht in
`docs/architecture/scoring-parameter-log.md`.

### 5.2 Nutzwert

`U = Machbarkeit × ConditionFit × CharacterFit × Confidence × Reachability (+ Anomalie nur für Surface „next_week“) (+ Social, Gewicht 0 bis Phase E)`, danach Diversitäts-Reranking.

- **Machbarkeit (hart, 0/1):** Tageslicht; Richtung liegt in einem reviewten Sektor (fehlende Richtung oder fehlende Sektoren = nicht machbar); kein Offshore-Verstoß (Abschnitt 5.3); Wind in `[min_kt, max_kt]`; Böe ≤ Wind + `gust_tolerance_kt`; Tide im Fenster, falls der Spot tideabhängig ist.
- **ConditionFit:** Stundenfit als Trapez (0 bei `min`, 1 in `[ideal_lo, ideal_hi]`, 0 bei `max`), stilabhängig verschoben (hohe `big_air`-Gewichtung verschiebt die Präferenz zum oberen Idealrand). Nur Stunden in Sessions zählen. Aggregiert wird pro Tag und dann über das Surface-Fenster.
- **CharacterFit:** normiertes Skalarprodukt aus `style_weights` (Nutzer) und `style_affinity` (Spot, 0–3), multipliziert mit Wasser- und Untergrund-Passung. Ausgeschlossene Untergründe setzen den Wert auf 0.
- **Confidence:** Vorlaufzeit-Abfall, thermischer Abschlag (`editorial.wind_type == "thermal"`), Spot-Verifikationsfehler (`weather_verification`), Modellspreizung falls vorhanden.
- **Reachability:** `exp(-d / d0(travel_mode))`, bei `trip` fast flach. Ohne Standort gilt 1.
- **Anomalie:** Forecast-Sessionstunden im persönlichen Fenster relativ zum V3-Median derselben Woche und Variante, gedämpft mit Confidence. Niemals absolute Forecast-Werte direkt mit ERA5 vergleichen.
- **Saison:** V3-Variante, auf das Personal Band quantisiert (`min = floor(ideal_lo)`, `max = ceil(ideal_hi)`, `direction_mode = usable`), gemessen über `reliability_percent` und `median_session_hours` der Wochen im Zeitraum.

#### Tide-Normalisierung (Phase A)

FES-Ereignisse enthalten relative Höhen zu einem Modell-Bezugsniveau. Das bisherige redaktionelle Feld `editorial.tide.window` hatte dagegen keine festgelegte Einheit und wurde überwiegend als Freitext gepflegt; beide Werte sind deshalb nicht direkt vergleichbar. Für Scoring gilt zentral ein dimensionsloser Tidewert von `0` (Niedrigwasser) bis `1` (Hochwasser), abgeleitet aus der Position zwischen den um Korrekturen bereinigten Hoch- und Niedrigwasserereignissen. Ein strukturiertes `editorial.tide.window` muss denselben Wertebereich verwenden. Es findet keine Umrechnung der relativen FES-Höhe in Meter statt. Fehlende oder nicht reviewte Tide-Daten ergeben `tide_unknown` und keinen harten Ausschluss.

### 5.3 Offshore

Reviewte Sektoren sind maßgeblich: Liegt die Richtung in einem reviewten Sektor, hat die Kuratorin sie freigegeben. Zusätzlich gilt für `beginner`: Wind aus einer Richtung mit `angular_diff(wind_dir, facing) ≥ 110°` ist nicht machbar, außer `editorial.beginner_offshore_ok == true` (etwa eine flache, geschlossene Lagune).

## 6. Surfaces

| Surface-Key | Fenster | Quelle | Kandidaten |
|---|---|---|---|
| `now` | 0–48 h | Forecast | Radius um Standort bzw. Heimat |
| `next_week` | Tag 2–10 | Forecast + Anomalie | Reisemodus-Radius |
| `season` | gewählter Monat oder Wochenbereich | V3 | global |
| `region` | frei (Default `now`, sonst gewählt) | kombiniert | Spots der Region |
| `search` | wie `region` | kombiniert | Suchtreffer (Filter bleiben Filter, U sortiert nur) |

## 7. Unsichtbarkeits-Vertrag

- Öffentliche Endpunkte liefern keine Felder, aus denen die Bewertung ablesbar ist: `score`, `rank_score`, `rating` (Score-Kategorie), `reasons`, `pct_usable`, `gut_anteil`, `good_weeks`, `confidence` als Stufe und Ähnliches. Die Reihenfolge ist die einzige Information.
- **Community-Sternebewertungen sind davon ausgenommen**, denn sie sind ein separates, nutzergeneriertes System.
- Deskriptive Wetter- und Klimadaten (Wind, Böen, V3-Zuverlässigkeit auf der Spot-Seite) bleiben öffentlich, weil sie Messwerte sind, keine Bewertung.
- UI-Texte dürfen nicht erklären, warum etwas empfohlen wird.
- Jeder berechnete Score wird serverseitig in `recommendation_log` gespeichert (Komponenten, Parameterversion, Profil-Fingerprint).

## 8. Bereitschaft für spätere Benachrichtigungen

- Die Engine ist eine reine Funktion `evaluate(profile, spot_ids, surface, window) -> ranked components`, ohne Request-Kontext aufrufbar.
- `recommendation_log` hat einen stabilen Schlüssel `(user_ref, spot_id, surface, window_start)`, der sich später zur Deduplizierung eignet.
- `user_events` reserviert die Typen `notification_sent`, `notification_opened` und `notification_dismissed`, verwendet sie aber noch nicht.
- Die Tabellen `watches` und `notifications` werden **nicht** verändert.

### Offline-Auswertung

`scripts/scoring_backtest.py` prüft `now`, `next_week`, `region` und `search`
gegen archivierte Forecast-Samples und akzeptierte Stationsbeobachtungen. Für
`season` liest der Backtest die aktive V3-Variante je Profil-Archetyp
(`floor(ideal_lo)`, `ceil(ideal_hi)`, bevorzugt `usable`) und vergleicht deren
Wochenwahrscheinlichkeit für mindestens einen Session-Tag mit späteren
Beobachtungswochen. Beobachtungen aus dem Trainingszeitraum eines V3-Artefakts
werden ausgeschlossen, damit kein Rückblickwissen in die Auswertung gelangt.
Der tägliche Workflow `weather-verification.yml` berechnet die
Verifikationswerte neu und setzt die konfigurierbare Aufbewahrung der
Forecast-Samples durch.

## 9. Phasen

A Fundament & Unsichtbarkeit → B Rider-Modell & Events → C Nutzwert-Engine & Inspektor → D Ausspielflächen → E Evaluation & Kalibrierung. (Benachrichtigungen folgen als eigene, spätere Phase.)
