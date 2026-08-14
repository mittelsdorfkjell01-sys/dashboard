# Phase-4 shadow readiness

Status: `awaiting_deployment_confirmation`. Five class-A profiles are frozen into `swd-phase4-shadow-v1`. GFS collection works; ICON-EU is budget-blocked and observation bindings are unavailable. GitHub Actions is configured to enqueue `/cron/weather-shadow` every six hours and run the asynchronous worker. Public effect: none.

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
are locally verified. Production activation is blocked until a successful Vercel
deploy exists and the authenticated live smoke test passes. See
`docs/weather-shadow-scheduler-setup.md`.
