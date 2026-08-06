import type { DuplicateConflict } from "../../lib/duplicateConflicts";
import Button from "../ui/Button";
import Modal from "../ui/Modal";

const distanceLabel = (metres?: number | null) => {
  if (metres == null) return null;
  return metres < 1000 ? `${Math.round(metres)} m entfernt` : `${(metres / 1000).toFixed(1)} km entfernt`;
};

export default function DuplicateWarningDialog({
  conflict,
  busy = false,
  onClose,
  onOverride,
}: {
  conflict: DuplicateConflict | null;
  busy?: boolean;
  onClose: () => void;
  onOverride: () => void;
}) {
  if (!conflict) return null;
  const exact = conflict.code === "exact_duplicate";
  return (
    <Modal open onClose={onClose} labelledBy="duplicate-title" describedBy="duplicate-message">
      <h2 id="duplicate-title" className="text-ui font-semibold text-ink">
        {exact ? "Dublette kann nicht gespeichert werden" : "Mögliche Dublette gefunden"}
      </h2>
      <p id="duplicate-message" className="mt-2 text-label text-ink-soft">
        {conflict.message}
      </p>
      {conflict.candidates.length > 0 && (
        <ul className="mt-4 max-h-64 space-y-2 overflow-y-auto">
          {conflict.candidates.map((candidate) => {
            const details = [
              conflict.entity === "spot"
                ? candidate.region_name ?? "Ohne Region"
                : candidate.country,
              distanceLabel(candidate.distance_m),
              candidate.similarity != null
                ? `${Math.round(candidate.similarity * 100)} % Namensähnlichkeit`
                : null,
            ].filter(Boolean);
            return (
              <li key={candidate.id} className="rounded-md border border-admin-border bg-admin-bg px-3 py-2">
                <p className="text-label font-semibold text-admin-fg">{candidate.name}</p>
                {details.length > 0 && (
                  <p className="mt-0.5 text-caption text-admin-muted">{details.join(" · ")}</p>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <div className="mt-5 flex items-center justify-end gap-2">
        <Button variant="ghost" onClick={onClose} disabled={busy}>
          Schließen
        </Button>
        {!exact && conflict.override_allowed && (
          <Button onClick={onOverride} disabled={busy}>
            {busy ? "Speichern …" : "Trotzdem speichern"}
          </Button>
        )}
      </div>
    </Modal>
  );
}
