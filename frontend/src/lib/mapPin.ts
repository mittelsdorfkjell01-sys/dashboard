import L from "leaflet";

/**
 * The navy teardrop marker used on every public Leaflet map (map view, search
 * results, region page). One definition so the pin can't drift between pages.
 *
 * The two literal colours are intentional and theme-independent: the pin is
 * always drawn over map tiles, so it stays brand-ink (#241C17) with a white
 * outline in both light and dark themes rather than flipping with the UI.
 */
export const pinIcon = L.divIcon({
  className: "swd-pin",
  html: `<svg width="30" height="38" viewBox="0 0 24 30" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 0C5.7 0 1 4.7 1 10.7 1 18.4 12 30 12 30s11-11.6 11-19.3C23 4.7 18.3 0 12 0Z"
        fill="#241C17" stroke="#ffffff" stroke-width="1.4"/>
      <circle cx="12" cy="10.5" r="3.4" fill="#ffffff"/>
    </svg>`,
  iconSize: [30, 38],
  iconAnchor: [15, 38],
  popupAnchor: [0, -34],
});
