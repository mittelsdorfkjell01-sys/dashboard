import { useEffect, useRef } from "react";
import type { Spot } from "../lib/types";
import type { LiveConditionsRead } from "../lib/api";
import { CloseIcon } from "../lib/icons";

/**
 * Textbasierte Alternative zur interaktiven Karte: dieselben Spots, dieselbe
 * Sortierung wie die Kartenleiste (`railSpots`/`live` kommen unverändert von
 * MapView) — keine zweite Datenlogik. Mobile: Bottom Sheet. Desktop: schmales
 * Seitenpanel. Auswahl eines Eintrags wählt den Spot auf der Karte aus; die
 * Spotdetailseite bleibt über die (synchron ausgewählte) Kartenleiste oder
 * den Marker erreichbar.
 */
export default function MapResultsList({
  open,
  onClose,
  spots,
  live,
  selectedId,
  onSelect,
  emptyLabel,
}: {
  open: boolean;
  onClose: () => void;
  spots: Spot[];
  live?: Map<string, LiveConditionsRead> | null;
  selectedId?: string;
  onSelect: (id: string) => void;
  emptyLabel: string;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const frame = window.requestAnimationFrame(() => closeRef.current?.focus());
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("keydown", onKey);
      previouslyFocused?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="swd-map-list-overlay" role="presentation" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Surfspots im Kartenausschnitt als Liste"
        className="swd-map-list-panel"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="swd-map-list-head">
          <p className="swd-map-list-title">Spots im Ausschnitt</p>
          <button ref={closeRef} type="button" onClick={onClose} aria-label="Liste schließen" className="swd-map-control h-9 w-9">
            <CloseIcon className="text-[16px]" />
          </button>
        </div>
        {spots.length === 0 ? (
          <p role="status" className="swd-map-list-empty">{emptyLabel}</p>
        ) : (
          <ul className="swd-map-list-items">
            {spots.map((spot) => {
              const windLive = live?.get(spot.id)?.current.wind;
              const wind = windLive ?? spot.typicalWindKt;
              const region = [spot.regionName, spot.regionCountry].filter(Boolean).join(" · ");
              return (
                <li key={spot.id}>
                  <button
                    type="button"
                    aria-current={spot.id === selectedId ? "true" : undefined}
                    onClick={() => onSelect(spot.id)}
                    className={`swd-map-list-item ${spot.id === selectedId ? "is-selected" : ""}`}
                  >
                    <span className="swd-map-list-name">{spot.name}</span>
                    <span className="swd-map-list-meta">
                      {region}
                      {wind != null && `${region ? " · " : ""}${wind} kts${windLive != null ? " · live" : ""}`}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
