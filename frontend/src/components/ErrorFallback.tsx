import { Button, Wordmark } from "./ui";

/**
 * Presentational error screen shared by the router error page and the top-level
 * ErrorBoundary. Uses plain <a> (not <Link>) so it renders safely even outside
 * a Router context (the class boundary wraps the RouterProvider itself).
 */
export default function ErrorFallback({
  title = "Etwas ist schiefgelaufen",
  detail = "Es ist ein unerwarteter Fehler aufgetreten.",
}: {
  title?: string;
  detail?: string;
}) {
  return (
    <div className="grid min-h-screen place-items-center bg-band px-6 text-center">
      <div>
        <a href="/" className="mb-6 inline-block">
          <Wordmark size="lg" />
        </a>
        <h1 className="text-sz-22 font-semibold text-ink">{title}</h1>
        <p className="mx-auto mt-2 max-w-sm text-ui text-muted">{detail}</p>
        <div className="mt-6 flex justify-center gap-3">
          <Button onClick={() => window.location.reload()}>Neu laden</Button>
          <a
            href="/"
            className="inline-flex items-center px-4 py-2 text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70"
          >
            Zur Startseite
          </a>
        </div>
      </div>
    </div>
  );
}
