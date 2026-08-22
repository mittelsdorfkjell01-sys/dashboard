# Wind climatology V3 pilot

Generated: 2026-08-22T20:43:29.331524+00:00

Read-only feasibility run; no V3 run, raw history or public value was persisted.

V2 and V3 percentages below answer different questions and are not treated as interchangeable scores.

| Spot | Country | Complete | V2 pooled median | V3 reliability median | Fetch | Aggregate | Peak RAM | Grid distance | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Brandenburger Strand | DE | 100.0% | 26.38% | 80.0% | 2.278 s | 14.65 s | 60.74 MB | 9.756 km | suitable |
| Pozo Izquierdo | ES | 100.0% | 11.43% | 32.5% | 2.022 s | 14.395 s | 56.05 MB | 11.887 km | suitable |
| Almanarre | FR | 100.0% | 11.52% | 37.5% | 2.003 s | 14.192 s | 57.87 MB | 11.295 km | suitable |
| Thurso East | GB | 100.0% | 17.04% | 47.5% | 2.072 s | 14.426 s | 57.19 MB | 10.937 km | suitable |
| Keros | GR | 100.0% | 21.45% | 70.0% | 1.968 s | 14.9 s | 56.38 MB | 15.843 km | suitable |
| Aileen's | IE | 100.0% | 22.57% | 65.0% | 2.045 s | 13.535 s | 57.32 MB | 5.688 km | suitable |
| Lo Stagnone | IT | 100.0% | 9.84% | 32.5% | 1.963 s | 14.353 s | 57.82 MB | 13.601 km | suitable |
| Brouwersdam | NL | 100.0% | 17.13% | 55.0% | 1.926 s | 14.371 s | 56.94 MB | 7.225 km | suitable |
| Chałupy | PL | 100.0% | 17.52% | 60.0% | 1.839 s | 14.0 s | 57.28 MB | 1.97 km | suitable |
| Baleal | PT | 100.0% | 11.04% | 35.0% | 1.952 s | 14.934 s | 58.11 MB | 15.702 km | suitable |

Suitable: 10/10.

No pilot spot had reviewed canonical direction sectors. Legacy editorial directions were intentionally not promoted; therefore this pilot validates `all` mode only.

## Benchmark

- Real full 20-year cube, one spot, `all` mode: 666 variants in 456.815 s.
- Additional peak memory during cube build: 25.9 MB.
- Rejected monolithic artifact: 247,225 bytes and 1,000.911 ms to select after full decompression.
- Chosen indexed per-variant artifacts: mean 1,207 bytes and 1.409 ms decode time across the pilots.
- Estimated 51-spot `all`-mode artifact payload: about 41.0 MB, excluding row/index overhead.

The calculation is technically feasible for shadow pilots, but full-catalogue generation must be vectorized before Phase 4. No production mass backfill was run.
