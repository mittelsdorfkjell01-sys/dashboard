# Europaweite Tide ohne zusätzliche Providerkosten

Status: umgesetzt als konservativer Fallback; FES2022b bleibt das Zielprodukt.

## Nutzerentscheidung

Surfer, Kitesurfer, Windsurfer und Foiler müssen vor der Anfahrt erkennen, ob
der Wasserstand steigt oder fällt und wann die nächsten Hoch- und
Niedrigwasserpunkte erwartet werden. Dafür müssen Produktart, Bezugsniveau,
Quelle und Unsicherheit sichtbar bleiben. Ein modellierter Meeresspiegel darf
nicht als astronomische oder navigationsgeeignete Tide erscheinen.

## Datenstrategie

1. **FES2022b hat Vorrang.** Eine freigegebene, lokal geprüfte FES-Berechnung
   bleibt die astronomische Tide und wird unverändert veröffentlicht.
2. **Kostenloser Sofort-Fallback.** Fehlt FES an einem veröffentlichten Spot
   vom Typ `ocean`, `sea` oder `lagoon`, wird `sea_level_height_msl` aus der
   bereits verwendeten und gecachten Open-Meteo-Marine-Antwort gelesen. Die UI
   lädt den Wasserstand erst nach dem Forecast, damit sie im normalen Seitenfluss
   dieselbe Providerantwort wiederverwendet.
3. **Keine Anwendung im Binnenland.** Seen, Flüsse und Reservoirs erhalten
   diesen Fallback nicht.
4. **Fail closed.** Fehlende, unvollständige oder ungültige Modellwerte führen
   zu einem erklärten Nicht-verfügbar-Zustand statt zu geschätzten Werten.

Open-Meteo beschreibt `sea_level_height_msl` als Kombination aus Tide,
Luftdruckeinfluss und weiteren Meeresspiegelanteilen. Das Produkt ist deshalb
als `modelled_sea_level` mit Datum `mean_sea_level`, hoher Zeitunsicherheit und
`navigational=false` Teil des öffentlichen Vertrags.

## API und Berechnung

- Der bestehende Marine-Request enthält zusätzlich `sea_level_height_msl`.
- Der Cache-Key wurde versioniert, damit ältere Antworten ohne das Feld nicht
  als vollständig gelten.
- Die Kurve wird auf den angeforderten Horizont begrenzt. Aus lokalen Extrema
  entstehen Hoch-/Niedrigwasserereignisse; Nullwerte und unvollständige
  Zeitachsen werden übersprungen.
- Der öffentliche Vertrag liefert Produktart, absoluten Modellwert in Metern,
  Datum, Quelle, Attribution und Navigationsstatus.
- Der Fallback kann mit
  `TIDE_MODELLED_SEA_LEVEL_FALLBACK_ENABLED=false` sofort deaktiviert werden.

## UI-Einbau

Das vorhandene Tide-Modul auf der Daten-Seite bleibt die einzige Oberfläche:

- FES: Überschrift **Astronomische Tide**, relativer Pegelstand.
- Fallback: Überschrift **Modellierter Meeresspiegel**, Meter über mittlerem
  Meeresspiegel, Quelle und deutlicher Hinweis auf begrenzte Küstengenauigkeit.
- Beide Produkte zeigen Phase, Kurve und nächste Extrema, aber niemals eine
  Eignungsampel.
- Nicht verfügbare Küstendaten werden als ruhiger, verständlicher Zustand
  angezeigt. Bei Binnengewässern wird das Modul nicht eingeblendet.
- Die Darstellung bleibt im bestehenden dunklen Instrumentenstil und
  funktioniert ohne Hover auf Mobilgeräten.

## Ausbau zu echter europaweiter astronomischer Tide

Der Fallback ist eine sofort nutzbare Abdeckung, aber kein Ersatz für FES. Für
das Zielprodukt wird der vorhandene Worker schrittweise aktiviert:

1. FES2022b-Höhendaten nach kostenloser AVISO-Registrierung und Lizenzannahme
   privat in den Worker einspielen; Modelldateien nicht ins Repository legen.
2. Küstenanker automatisch setzen, Wet-Mask prüfen und problematische Buchten,
   Flussmündungen und Inselgruppen in einer Review-Queue halten.
3. Erst geprüfte Profile veröffentlichen; Fallback bleibt bis dahin aktiv.
4. Gegen frei zugängliche Pegelquellen je Region stichprobenartig prüfen und
   Offset/Unsicherheit dokumentieren.
5. Abdeckung, Providerfehler, Cache-Trefferrate und Anteil partieller Horizonte
   überwachen. Ein kostenpflichtiger Provider ist dafür nicht erforderlich.

## Abnahmekriterien

- Kein Küsten-Spot zeigt modellierte Werte als astronomische Tide.
- FES überschreibt den Fallback deterministisch.
- Wellen- und Wasserstandsmodul teilen denselben Marine-Cache; die UI vermeidet
  parallele Erstabrufe.
- Keine externe Anfrage bei Binnengewässern.
- Quelle, Bezugsniveau, Aktualität, Teilhorizont und Warnhinweis sind sichtbar.
- Providerfehler lassen die Spot-Seite funktionsfähig.
