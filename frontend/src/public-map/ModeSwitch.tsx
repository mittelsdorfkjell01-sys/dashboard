import { MapIcon, WaveIcon, WindIcon } from "../lib/icons";
import type { ExplorerMode } from "../weather-map/fieldUrlState";

const MODES: Array<{ mode: ExplorerMode; label: string; Icon: typeof WindIcon }> = [
  { mode: "spots", label: "Spots", Icon: MapIcon },
  { mode: "wind", label: "Wind", Icon: WindIcon },
  { mode: "waves", label: "Wellen", Icon: WaveIcon },
];

/**
 * The map's one mode switch, centred at the top edge (2026-11-20: moved up
 * from the bottom island on request). A segmented pill: the active mode shows
 * its word, the others their icon only — on desktop all three carry words.
 */
export default function ModeSwitch({ mode, onMode }: { mode: ExplorerMode; onMode: (mode: ExplorerMode) => void }) {
  return (
    <div className="swd-pm-modeswitch" role="group" aria-label="Kartenmodus">
      {MODES.map(({ mode: key, label, Icon }) => (
        <button key={key} type="button" className="swd-pm-mode" aria-pressed={mode === key} aria-label={label} onClick={() => onMode(key)}>
          <Icon className="text-lead" />
          <span className="swd-pm-mode-label text-ui">{label}</span>
        </button>
      ))}
    </div>
  );
}
