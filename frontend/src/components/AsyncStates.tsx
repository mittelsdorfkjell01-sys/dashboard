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

/** An inline error banner with an optional retry. */
export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700"
    >
      <p className="font-medium">Daten konnten nicht geladen werden.</p>
      <p className="mt-1 text-red-600/90">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 min-h-11 px-3 text-[13px] font-semibold text-ink hover:underline hover:underline-offset-4"
        >
          Erneut versuchen
        </button>
      )}
    </div>
  );
}

/** A neutral empty state. */
export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl bg-[#F1F5FA] px-5 py-10 text-center text-[14px] text-muted">
      {message}
    </div>
  );
}
