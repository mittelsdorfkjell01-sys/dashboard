"""Warm the featured Top-Spots cache off the request path.

:func:`app.discovery.service.top_spot_ids` is read-through: the first request
after the daily entry expires (UTC midnight) pays the full cost of one forecast
fetch per published spot. This job pre-pays that cost so real visitors always hit
a warm cache.

It is **cheap when the cache is already warm** — a single Redis GET, no fetching —
because it goes through the same read-through path the endpoint uses. So it is
safe to run on a short interval: the heavy recompute happens only on the first
run after the entry expires; every other run is a near-free no-op. The interval
therefore bounds the worst-case cold window (how long after midnight an unlucky
visitor might still trigger the recompute themselves).

Warm the cache key the landing endpoint requests (``limit=8``: five visible
tiles plus three malformed-row reserves, no sport filter):

    python -m app.discovery.warmup                       # limit=8, sport=any
    python -m app.discovery.warmup --limit 5 --limit 8   # several sizes
    python -m app.discovery.warmup --sport kitesurf      # a sport-filtered list
    python -m app.discovery.warmup --loop --interval 1800

Single-shot by default (a scheduler / the compose sidecar wraps the loop, like
the ``backup`` service); ``--loop`` self-schedules for bare-metal deploys.
"""

from __future__ import annotations

import argparse
import time
from datetime import date

from app.db.session import SessionLocal
from app.discovery.service import top_spot_ids
from app.live.cache import Cache
from app.live.client import OpenMeteoClient


def warm_once(
    *,
    limits: list[int],
    sports: list[str | None],
    db=None,
    client: OpenMeteoClient | None = None,
    cache: Cache | None = None,
    today: date | None = None,
) -> list[tuple[str | None, int, int]]:
    """Ensure the cache holds each ``(sport, limit)`` list for today.

    Returns ``[(sport, limit, n_spots)]``. Opens its own DB session when ``db``
    is not supplied; ``client`` / ``cache`` may be injected for tests.
    """
    own_session = db is None
    db = db or SessionLocal()
    results: list[tuple[str | None, int, int]] = []
    try:
        for sport in sports:
            for limit in limits:
                ids = top_spot_ids(
                    db,
                    limit=limit,
                    sport=sport,
                    client=client,
                    cache=cache,
                    today=today,
                    allow_stale=False,
                )
                results.append((sport, limit, len(ids)))
                print(
                    f"[warm] sport={sport or 'any'} limit={limit} -> {len(ids)} spots",
                    flush=True,
                )
        return results
    finally:
        if own_session:
            db.close()


def run_loop(
    *,
    limits: list[int],
    sports: list[str | None],
    interval: float,
) -> None:
    """Warm on a fixed interval forever. A failed run is logged, not fatal."""
    while True:
        try:
            warm_once(limits=limits, sports=sports)
        except Exception as exc:  # keep the loop alive across a transient failure
            print(f"[warm] run FAILED: {type(exc).__name__}: {exc}", flush=True)
        time.sleep(interval)


def run_in_background(
    *,
    interval: float,
    limits: list[int] | None = None,
    sports: list[str | None] | None = None,
) -> None:
    """Spawn a daemon thread running :func:`run_loop`.

    Used from the app startup hook so production keeps the featured cache warm
    without a separate always-on container (leaner on a small VPS). Defaults warm
    the landing endpoint's ranking key (``limit=8``, no sport filter).
    """
    import threading

    limits = limits or [8]
    sports = sports if sports is not None else [None]

    threading.Thread(
        target=run_loop,
        kwargs={"limits": limits, "sports": sports, "interval": interval},
        name="featured-warmup",
        daemon=True,
    ).start()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="app.discovery.warmup", description=__doc__.split("\n")[0]
    )
    parser.add_argument(
        "--limit",
        type=int,
        action="append",
        metavar="N",
        help="Top-Spots ranking size to warm (repeatable; default: 8 — five "
        "landing tiles plus three serialization reserves)",
    )
    parser.add_argument(
        "--sport",
        action="append",
        metavar="SPORT",
        help="warm a sport-filtered list (repeatable; default: the unfiltered list)",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="warm repeatedly instead of once (self-scheduling for bare-metal)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1800.0,
        help="seconds between runs in --loop mode (default: 1800)",
    )
    args = parser.parse_args(argv)

    limits = args.limit or [8]
    # ``[None]`` = the unfiltered list the landing page requests.
    sports: list[str | None] = list(args.sport) if args.sport else [None]

    if args.loop:
        run_loop(limits=limits, sports=sports, interval=args.interval)
    else:
        warm_once(limits=limits, sports=sports)


if __name__ == "__main__":
    main()
