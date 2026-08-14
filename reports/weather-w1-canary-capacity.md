# Wetterdaten W1 – Canary/Capacity

**Status: `ready_for_user_review`**

- Exakt drei Spots: Baleal, Lo Stagnone und Fischbach Ost.
- Requests: 3 Atmosphäre + 2 Marine = 5; Retries 0.
- Bytes: Atmosphäre 517.818, Marine 27.841, gesamt 545.659.
- Baleal: Marine verfügbar, Rasterdistanz 3,146 km.
- Lo Stagnone: Marine verfügbar, Rasterdistanz 8,356 km.
- Fischbach Ost: `lake`, Marine `not_applicable_inland`, 0 Marinerequests und 0 Marinewerte.
- Alle drei Snapshots: weather-v2, korrekte IANA-Zeitzone, zehn lokale Tage und strikt eindeutige UTC-Stunden.
- Snapshotgrößen: Baleal 42.843 B, Fischbach Ost 41.937 B, Lo Stagnone 41.863 B.
- Laufzeiten: 2,406 s, 1,204 s und 2,093 s.
- Backend 52/52 und Frontend 181/181 bestanden; Build, Ruff, ESLint, Compilecheck und UI-Detektor bestanden.
- Kein Validationlauf oder Bestandsbackfill wurde gestartet.
