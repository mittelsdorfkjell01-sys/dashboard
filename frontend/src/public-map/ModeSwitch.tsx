import { MapIcon, WaveIcon, WindIcon } from "../lib/icons";
import type { ExplorerMode } from "../weather-map/fieldUrlState";

const MODES: Array<{ mode: ExplorerMode; label: string; Icon: typeof WindIcon }> = [
  { mode: "spots", label: "Spots", Icon: MapIcon },
  { mode: "wind", label: "Wind", Icon: WindIcon },
  { mode: "waves", label: "Wellen", Icon: WaveIcon },
];

const ALL_MODES: ExplorerMode[] = ["spots", "wind", "waves"];

/**
 * The map's one mode switch, centred at the top edge. Since 2026-11-25 it
 * looks like the small switches on the Daten tab's Windmonate: a tray of
 * equal 28px segments, each with icon and word, the chosen one on an ink
 * surface. That surface slides to a new choice with the switch curve the
 * theme and language switches use (a slight overshoot, 240 ms), and leans
 * in while pressed. Until then the pill showed the active word only and
 * stretched with the house curve.
 *
 * `modes` narrows the choice: a map opened from a spot (`toggle=0`) offers
 * only Wind and Wellen (2026-11-25).
 */
export default function ModeSwitch({
  mode,
  onMode,
  modes = ALL_MODES,
}: {
  mode: ExplorerMode;
  onMode: (mode: ExplorerMode) => void;
  modes?: ExplorerMode[];
}) {
  const options = MODES.filter((option) => modes.includes(option.mode));
  const index = options.findIndex((option) => option.mode === mode);

  return (
    <div className="swd-pm-modeswitch" role="group" aria-label="Kartenmodus">
      <span
        className="swd-pm-mode-indicator"
        aria-hidden="true"
        style={{ transform: `translateX(${Math.max(0, index) * 100}%)`, opacity: index < 0 ? 0 : 1 }}
      />
      {options.map(({ mode: key, label, Icon }) => (
        <button key={key} type="button" className="swd-pm-mode" aria-pressed={mode === key} onClick={() => onMode(key)}>
          <Icon />
          <span className="text-caption">{label}</span>
        </button>
      ))}
    </div>
  );
}
