# Parameter-Log des personalisierten Scorings

Alle wirksamen Änderungen werden als unveränderliche Version in
`scoring_params` gespeichert. Admin-Freigaben erzeugen stets eine neue Version;
vorhandene Versionen werden nicht überschrieben.

| Version | Inhalt | Aktivierung |
|---:|---|---|
| 1 | Globales Sport-Scoring | historischer Seed |
| 2 | Kanonisches Level `competition` | historischer Seed |
| 3 | Kite-Rider-Modell, Personal Band und Durchschnitts-Rider | Phase B |
| 4 | Sozialsignal mit Startgewicht `0,02`, Mindestgruppe `20` | Konfiguration aktiv, Signalgewicht bleibt durch `validated=false` effektiv `0` |

## Freigaberegeln

- Ein neuer Durchschnitts-Rider braucht mindestens
  `SCORING_CALIBRATION_MIN_PROFILES` vollständige Profile.
- Neue Personal-Band-Faktoren brauchen mindestens
  `SCORING_CALIBRATION_MIN_CHECKINS` lohnende Check-ins mit Beobachtungswind.
- Ein Sozialgewicht braucht einen dokumentierten Backtest- oder
  Online-Vergleich, eine positive Verbesserung und mindestens
  `SCORING_SOCIAL_MIN_GROUP_SIZE` Fälle.
- Vorschläge werden in `scoring_calibration_proposals` nachvollziehbar
  gespeichert. Nur Admins dürfen sie freigeben oder ablehnen.
- Eine Prozessinitialisierung lässt bereits freigegebene Versionen oberhalb
  der Code-Basis aktiv.

Jede Admin-Freigabe ergänzt im Parameterpayload `parameter_log` um Art,
Vorschlags-ID, Bearbeiter und Zeitpunkt.
