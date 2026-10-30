# Production monitoring policy

Provider selection remains open until project access, cost and retention needs
are reviewed. Every alert must link to the production recovery runbook and name
the on-call repository/operator owner.

| Signal | Initial alert | Reason |
|---|---|---|
| Liveness | 2 of 3 failures over 5 minutes | Avoid one cold-start false alarm while detecting an unavailable process quickly. |
| Readiness | DB/schema failure for 2 probes; Redis degraded for 10 minutes | DB/schema blocks serving; Redis is a recoverable cache degradation. |
| HTTP errors | 5xx above 2% for 5 minutes with at least 20 requests; critical above 10% | Minimum volume avoids low-traffic noise. Tune after four weeks of baseline data. |
| Latency | Public read p95 above 1.5 s for 10 minutes; admin p95 above 2.5 s | Users check conditions on mobile; recalibrate from real traffic. |
| Saturation | DB pool, provider quota or storage above 80% for 10 minutes | Leaves intervention headroom before hard limits. |
| Backup | Backup container unhealthy or no success within 26 hours | Daily schedule plus two hours for transient delay. |
| Weather evidence | Existing field/campaign health workflow failure | Weather freshness must not be inferred from generic API uptime. |

Alert payloads contain route class, timestamp, deployment commit and sanitized
error category, never credentials, cookies, tokens, raw DSNs or private content.
