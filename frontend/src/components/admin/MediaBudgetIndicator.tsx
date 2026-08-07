// Compact provider-budget readout for the admin header.
//
// Unsplash's demo tier is 50 requests/hour and there is no in-app warning
// besides this — an operator who burns through it mid-session otherwise only
// finds out when a tab goes quiet. Polls occasionally rather than on a socket;
// the budget does not change fast enough to justify more.

import { useEffect, useState } from "react";
import { getMediaProviders, type MediaProviderStatus } from "../../lib/api";

const POLL_MS = 5 * 60 * 1000;

export default function MediaBudgetIndicator() {
  const [providers, setProviders] = useState<MediaProviderStatus[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      getMediaProviders()
        .then((res) => {
          if (!cancelled) setProviders(res.providers);
        })
        .catch(() => {
          /* best-effort — a failed poll just keeps the last known state */
        });
    };
    load();
    const timer = window.setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const tightest = (providers ?? [])
    .filter((p) => p.available && p.budget.limit > 0)
    .sort((a, b) => b.budget.used / b.budget.limit - a.budget.used / a.budget.limit)[0];

  if (!tightest) return null;

  const ratio = tightest.budget.used / tightest.budget.limit;
  const tone =
    tightest.budget.exhausted
      ? "text-admin-danger"
      : ratio >= 0.8
        ? "text-admin-warning"
        : "text-admin-muted";

  return (
    <span
      title={`${tightest.provider}: ${tightest.budget.used}/${tightest.budget.limit} Anfragen diese Stunde`}
      className={`hidden items-center gap-1 text-caption font-medium sm:flex ${tone}`}
    >
      {tightest.provider} {tightest.budget.used}/{tightest.budget.limit}/h
    </span>
  );
}
