/** Shared loading/empty/error states so no page ever shows a blank screen. */

/** A grid of shimmering placeholder cards while spots load. */
export function SpotGridSkeleton({ count = 10 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-3 lg:grid-cols-5">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="animate-pulse">
          <div className="aspect-video rounded-2xl bg-line" />
          <div className="mt-3 h-3 w-2/3 rounded bg-line" />
          <div className="mt-2 h-4 w-1/2 rounded bg-line" />
        </div>
      ))}
    </div>
  );
}

/** An inline error banner with an optional retry. Uses the app's own tokens
 *  (surface + hairline + the `orange` attention colour) so it reads as part of
 *  the warm sand/petrol system and stays correct in dark mode — no raw
 *  Tailwind `red-*` values, which have no dark-mode variant here. */
export function ErrorBanner({
  message,
  onRetry,
  title = "Daten konnten nicht geladen werden.",
}: {
  message: string;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <div
      role="alert"
      className="rounded-2xl border border-line bg-surface px-5 py-4 text-ui text-ink-soft"
    >
      <p className="font-semibold text-orange">{title}</p>
      <p className="mt-1 text-muted">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 min-h-11 text-label font-semibold text-ink hover:underline hover:underline-offset-4"
        >
          Erneut versuchen
        </button>
      )}
    </div>
  );
}

/** A neutral empty state on the alternating band surface. */
export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl bg-band px-5 py-10 text-center text-ui text-muted">
      {message}
    </div>
  );
}
