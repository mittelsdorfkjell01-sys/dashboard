import type { ReactNode } from "react";
import type { MapPoi } from "../../lib/api";
import type { MapLocation } from "../../lib/account";
import { CloseIcon } from "../../lib/icons";
import { mapsAppName } from "../../lib/mapLinks";
import { formatDistance, type DistanceUnit } from "../../lib/units";
import { openingState } from "./openingStatus";
import { POI_META, poiTitle, readableOpeningHours } from "./poiMeta";

/* The cards' two action looks. The hand-off to the maps app is the one
   action a place card has: an outline the full width of the card, so it is
   easy to hit without becoming a filled block (No Fat Button Rule).
   Everything else is text. */
const OPEN_ACTION =
  "flex min-h-11 w-full items-center justify-center gap-1.5 rounded-card border border-line px-4 text-ui font-semibold text-ink transition-[background-color,transform] hover:bg-band active:scale-[0.98] motion-reduce:active:scale-100";
export const TEXT_ACTION =
  "inline-flex min-h-11 items-center text-ui font-semibold text-ink transition-opacity hover:underline hover:underline-offset-4 hover:opacity-70";

export function formatMeters(meters: number, unit: DistanceUnit): string {
  if (unit === "km" && meters < 1_000) return `${Math.max(10, Math.round(meters / 10) * 10)} m`;
  return formatDistance(meters / 1_000, unit);
}

/**
 * The map's one panel (Variante B, 2026-11-21): the place's map symbol in
 * front of its name, one quiet line underneath, then at most the opening
 * hours and the hand-off to the rider's maps app. Photos, reviews, phone and
 * website live there, not here. Card and map follow the site theme.
 */
export function LocatorSheet({
  label,
  glyph,
  title,
  status,
  subtitle,
  onClose,
  children,
}: {
  label: string;
  glyph?: ReactNode;
  title: ReactNode;
  /** Sits on the name's line, flush right (the café's open/closed state). */
  status?: ReactNode;
  subtitle?: ReactNode;
  onClose?: () => void;
  children?: ReactNode;
}) {
  return (
    <aside aria-label={label} className="swd-locator-sheet">
      <div className={`flex items-start gap-2.5 pb-4 pl-4 pt-3.5 ${onClose ? "pr-12" : "pr-4"}`}>
        {glyph && <span aria-hidden className="mt-0.5 grid shrink-0 place-items-center">{glyph}</span>}
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-3">
            <h3 className="min-w-0 flex-1 break-words text-body font-semibold leading-snug text-ink">{title}</h3>
            {status}
          </div>
          {subtitle && <p className="text-caption text-muted">{subtitle}</p>}
        </div>
      </div>
      {onClose && (
        <button
          type="button"
          aria-label="Schließen"
          onClick={onClose}
          className="absolute right-1 top-1 grid h-11 w-11 place-items-center rounded-card text-muted transition-colors hover:text-ink"
        >
          <CloseIcon width={13} height={13} />
        </button>
      )}
      {children && <div className="-mt-1.5 flex flex-col gap-3 px-4 pb-4">{children}</div>}
    </aside>
  );
}

function OpenInMaps({ href }: { href: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={OPEN_ACTION}>
      In {mapsAppName()} öffnen
      <svg aria-hidden width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3.5 8.5 8.5 3.5M4.5 3.5h4v4" />
      </svg>
    </a>
  );
}

/** Parking and camping are where a charge changes the plan; only what is mapped. */
function feeWord(poi: MapPoi): string | null {
  if (poi.fee == null || (poi.category !== "parking" && poi.category !== "campsite")) return null;
  return poi.fee ? "kostenpflichtig" : "kostenlos";
}

/**
 * Open or closed right now, from the mapped hours at the spot's local time.
 * Green and red on purpose (user decision 2026-11-22, DESIGN.md Standard Map
 * Rule): the one place outside a hazard sentence where red appears. Nothing
 * is shown when the hours are missing or too rich to read with certainty.
 */
function OpeningBadge({ state }: { state: "open" | "closed" }) {
  return (
    <span
      title="Laut OpenStreetMap-Eintrag, Ortszeit am Spot"
      className={`shrink-0 text-caption font-semibold ${state === "open" ? "text-success" : "text-danger"}`}
    >
      {state === "open" ? "Geöffnet" : "Geschlossen"}
    </span>
  );
}

export function PoiSheet({
  poi,
  openHref,
  unit,
  timeZone,
  now = new Date(),
  onClose,
}: {
  poi: MapPoi;
  openHref: string;
  unit: DistanceUnit;
  /** The spot's IANA time zone; without it no open/closed state is shown. */
  timeZone?: string | null;
  now?: Date;
  onClose: () => void;
}) {
  const meta = POI_META[poi.category];
  const hours = poi.opening_hours ? readableOpeningHours(poi.opening_hours) : [];
  const state = openingState(poi.opening_hours, now, timeZone);
  const fee = feeWord(poi);
  return (
    <LocatorSheet
      label={`${meta.label}: ${poiTitle(poi)}`}
      glyph={
        <span className={`swd-poi-${poi.category}`}>
          <span className="swd-poi-disc">
            <svg viewBox="0 0 20 20" focusable="false"><path d={meta.path} /></svg>
          </span>
        </span>
      }
      title={poiTitle(poi)}
      status={state && <OpeningBadge state={state} />}
      subtitle={<>{meta.label} · {formatMeters(poi.distance_m, unit)} vom Spot{fee && <> · {fee}</>}</>}
      onClose={onClose}
    >
      {hours.length > 0 && (
        <p className="text-caption text-ink-soft">
          <span className="sr-only">Öffnungszeiten: </span>
          {hours.map((line) => <span key={line} className="block">{line}</span>)}
        </p>
      )}
      <OpenInMaps href={openHref} />
      {/* The card covers the map's sources glyph on a phone; the place data
          is OpenStreetMap's, so the card names it (ODbL attribution). */}
      <p className="-mt-1 text-micro text-muted">Daten © OpenStreetMap-Mitwirkende</p>
    </LocatorSheet>
  );
}

export function SpotSheet({
  name,
  glyph,
  openHref,
  distanceFromYou,
  onClose,
}: {
  name: string;
  glyph: ReactNode;
  openHref: string;
  distanceFromYou: string | null;
  onClose: () => void;
}) {
  return (
    <LocatorSheet
      label={`Spot ${name}`}
      glyph={glyph}
      title={name}
      subtitle={<>Spot{distanceFromYou && <> · {distanceFromYou} Luftlinie von dir</>}</>}
      onClose={onClose}
    >
      <OpenInMaps href={openHref} />
    </LocatorSheet>
  );
}

export type LocateStatus = "idle" | "locating" | "denied" | "unavailable";

export function LocationSheet({
  location,
  distanceToSpot,
  status,
  canLocate,
  syncError,
  onLocate,
  onPick,
  onRemove,
  onClose,
}: {
  location: MapLocation | null;
  distanceToSpot: string | null;
  status: LocateStatus;
  canLocate: boolean;
  syncError: boolean;
  onLocate: () => void;
  onPick: () => void;
  onRemove: () => void;
  onClose: () => void;
}) {
  const message =
    status === "denied"
      ? "Standortfreigabe abgelehnt. Wähle ihn auf der Karte."
      : status === "unavailable"
        ? "Standort gerade nicht verfügbar."
        : syncError
          ? "Nur in diesem Browser gespeichert."
          : null;
  return (
    <LocatorSheet
      label="Dein Standort"
      glyph={<span className="swd-sheet-user" />}
      title="Dein Standort"
      subtitle={location
        ? <>{location.source === "gps" ? "GPS" : "Auf der Karte gesetzt"}{distanceToSpot && <> · {distanceToSpot} zum Spot</>}</>
        : "Noch nicht festgelegt"}
      onClose={onClose}
    >
      {message && <p role="status" className="text-caption text-ink">{message}</p>}
      <div className="-my-1.5 flex flex-wrap items-center gap-x-5">
        {canLocate && (
          <button
            type="button"
            onClick={onLocate}
            disabled={status === "locating"}
            aria-busy={status === "locating" || undefined}
            className={TEXT_ACTION}
          >
            {status === "locating" ? "Wird bestimmt …" : location ? "Neu bestimmen" : "Aktuellen Standort verwenden"}
          </button>
        )}
        <button type="button" onClick={onPick} className={TEXT_ACTION}>Auf der Karte wählen</button>
        {location && <button type="button" onClick={onRemove} className={`${TEXT_ACTION} text-muted`}>Entfernen</button>}
      </div>
    </LocatorSheet>
  );
}

/** While the rider moves the map under the crosshair. */
export function PickSheet({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="swd-locator-sheet px-4 pb-1.5 pt-3.5" role="group" aria-label="Standort auf der Karte wählen">
      <p className="text-body font-semibold leading-snug text-ink">Standort wählen</p>
      <p className="text-caption text-muted">Verschiebe die Karte, bis das Kreuz auf deinem Startpunkt liegt.</p>
      <div className="mt-1 flex flex-wrap items-center gap-x-5">
        <button type="button" onClick={onConfirm} className={TEXT_ACTION}>Hier setzen</button>
        <button type="button" onClick={onCancel} className={`${TEXT_ACTION} text-muted`}>Abbrechen</button>
      </div>
    </div>
  );
}
