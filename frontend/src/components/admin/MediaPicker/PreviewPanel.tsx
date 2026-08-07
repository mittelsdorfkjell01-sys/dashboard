// The right-hand third of the picker: not a photo viewer, an art-direction tool.
//
// It renders the *real* hero composition — the same EditorialHero the public
// page uses — in both crops, with the entity's own typography and the credit
// line that will be stored. A photo with a bright sky exactly where the spot
// name sits is unusable, and a 200px thumbnail never shows that.

import { useRef } from "react";
import EditorialHero from "../../editorial/EditorialHero";
import { focalFromPoint, type MediaItem } from "../../../lib/mediaPicker";
import type { CreditSource } from "../../../lib/imageCredit";

export default function PreviewPanel({
  item,
  title,
  kicker,
  focal,
  onFocalChange,
}: {
  item: MediaItem;
  title: string;
  kicker?: string;
  focal: { x: number; y: number };
  onFocalChange: (focal: { x: number; y: number }) => void;
}) {
  const desktopRef = useRef<HTMLDivElement>(null);
  const mobileRef = useRef<HTMLDivElement>(null);

  // Exactly the attribution that adoption will store — the preview shows the
  // finished thing, credit line included, not an approximation of it.
  const credit: CreditSource = {
    credit: item.credit.name,
    creditUrl: item.credit.url,
    provider: item.provider,
    source: item.provider,
    sourcePage: item.source_page,
    license: item.license.name,
    licenseUrl: item.license.url,
  };

  const pick = (container: HTMLDivElement | null) => (event: React.MouseEvent) => {
    if (!container) return;
    const rect = container.getBoundingClientRect();
    onFocalChange(focalFromPoint(rect, event.clientX, event.clientY));
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="text-label font-medium text-admin-fg">Vorschau — Desktop</p>
        <p className="mt-0.5 text-caption text-admin-muted">
          Klick ins Bild setzt den Bildausschnitt. Beide Zuschnitte aktualisieren
          sich sofort.
        </p>
        <div ref={desktopRef} className="mt-2 overflow-hidden rounded-lg">
          <EditorialHero
            image={item.preview_url}
            focal={focal}
            alt={title}
            kicker={kicker}
            title={title}
            credit={credit}
            delivery={item.delivery}
            parallax={false}
            frameClassName="aspect-[2/1] min-h-0"
            onImageClick={pick(desktopRef.current)}
          />
        </div>
      </div>

      <div>
        <p className="text-label font-medium text-admin-fg">Vorschau — Mobil</p>
        <div
          ref={mobileRef}
          className="mx-auto mt-2 max-w-[240px] overflow-hidden rounded-lg"
        >
          <EditorialHero
            image={item.preview_url}
            focal={focal}
            alt={title}
            kicker={kicker}
            title={title}
            credit={credit}
            delivery={item.delivery}
            parallax={false}
            frameClassName="aspect-[3/4] min-h-0"
            onImageClick={pick(mobileRef.current)}
          />
        </div>
      </div>
    </div>
  );
}
