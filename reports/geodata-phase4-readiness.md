# Phase-4 shadow readiness

Status: `scheduler_verified_collecting`. Five class-A profiles are frozen into `swd-phase4-shadow-v1`. GFS collection works; ICON-EU is budget-blocked and observation bindings are unavailable. GitHub Actions enqueues `/cron/weather-shadow` every six hours and runs the asynchronous worker; der Production-Smoke-Test wurde erfolgreich dedupliziert. Public effect: none.

## Observation coverage

| Spot | Official candidate | Approx. distance | Assessment |
|---|---|---:|---|
| Baleal | IPMA Cabo Carvoeiro 531 | 6.0 km | Review required; API adapter is not implemented and live availability varies. |
| Brouwersdam | KNMI Oosterschelde WP | 15.5 km | Review required; station identifier/API availability must be confirmed. |
| Mundaka | AEMET Matxitxako 1057B | 6.8 km | Review required; 93 m cliff exposure is not automatically representative. |
| Lo Stagnone | Trapani Birgi | 4.0 km | Blocked; no official surface API, licence and sensor metadata confirmed. |
| Pozo Izquierdo | AEMET Gran Canaria Aeropuerto C649I | 12.2 km | Review required; airport exposure differs from the accelerated coastal spot. |

No station is activated as ground truth. Bias correction therefore remains disabled.

## Scheduler readiness

Endpoint, authentication, atomic deduplication, bounded retries and worker isolation
are locally and in production verified. The Vercel deploy is ready and the
authenticated accepted/deduplicated smoke sequence passed. See
`docs/weather-shadow-scheduler-setup.md`.
