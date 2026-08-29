// Drag the image within a fixed frame to choose which part shows (the focal
// point / crop). The frame uses object-fit: cover; dragging pans the image by
// adjusting object-position, then persists it as focal { x, y } percentages.

import { useEffect, useRef, useState, type PointerEvent } from "react";
import { resolveMediaUrl } from "../lib/api";
import { responsiveImageAttributes } from "../lib/heroSource";

const clamp = (n: number) => Math.max(0, Math.min(100, n));

export default function ImageFocalEditor({
  url,
  width,
  focal,
  onSave,
  aspect = "16 / 6",
  rotation = 0,
  onRotationSave,
  showRotationControl = false,
}: {
  url: string;
  width?: number | null;
  focal?: { x: number; y: number } | null;
  onSave: (x: number, y: number) => Promise<void>;
  aspect?: string;
  rotation?: number;
  onRotationSave?: (rotation: number) => Promise<void>;
  showRotationControl?: boolean;
}) {
  const [pos, setPos] = useState({ x: focal?.x ?? 50, y: focal?.y ?? 50 });
  const [angle, setAngle] = useState(rotation);
  const [savedAngle, setSavedAngle] = useState(rotation);

  // Sync local pos back to the incoming focal whenever the parent re-loads
  // the spot (e.g. after a save from a sibling editor) so the two crops stay
  // consistent. Skipped while the operator is actively dragging so their
  // input is never overwritten mid-gesture.
  const px = focal?.x ?? null;
  const py = focal?.y ?? null;
  useEffect(() => {
    if (px == null || py == null) return;
    setPos((current) => (current.x === px && current.y === py ? current : { x: px, y: py }));
  }, [px, py]);
  useEffect(() => {
    setAngle(rotation);
    setSavedAngle(rotation);
  }, [rotation]);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [rotationBusy, setRotationBusy] = useState(false);
  const [rotationSaved, setRotationSaved] = useState(false);
  const start = useRef<{ px: number; py: number; x: number; y: number } | null>(null);
  const frameRef = useRef<HTMLDivElement>(null);

  const onDown = (e: PointerEvent) => {
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    start.current = { px: e.clientX, py: e.clientY, x: pos.x, y: pos.y };
    setDragging(true);
    setSaved(false);
  };

  const onMove = (e: PointerEvent) => {
    if (!dragging || !start.current || !frameRef.current) return;
    const rect = frameRef.current.getBoundingClientRect();
    const dx = ((e.clientX - start.current.px) / rect.width) * 100;
    const dy = ((e.clientY - start.current.py) / rect.height) * 100;
    // Drag right → reveal the left part → decrease object-position X.
    setPos({ x: clamp(start.current.x - dx), y: clamp(start.current.y - dy) });
  };

  const onUp = async () => {
    if (!dragging) return;
    setDragging(false);
    start.current = null;
    setBusy(true);
    try {
      await onSave(Math.round(pos.x), Math.round(pos.y));
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } finally {
      setBusy(false);
    }
  };

  const saveRotation = async () => {
    if (!onRotationSave || angle === savedAngle) return;
    setRotationBusy(true);
    setRotationSaved(false);
    try {
      await onRotationSave(angle);
      setSavedAngle(angle);
      setRotationSaved(true);
      setTimeout(() => setRotationSaved(false), 1500);
    } finally {
      setRotationBusy(false);
    }
  };

  const rotationScale = 1 + Math.abs(angle) * 0.04;

  return (
    <div>
      {showRotationControl && onRotationSave && (
        <div id="hero-rotation" className="mb-4 rounded-lg bg-admin-bg p-4">
          <div className="flex items-center justify-between gap-4">
            <label htmlFor="hero-rotation-range" className="text-ui font-semibold text-admin-fg">
              Bild gerade drehen
            </label>
            <output htmlFor="hero-rotation-range" className="min-w-12 text-right text-label tabular-nums text-admin-fg2">
              {angle > 0 ? "+" : ""}{angle.toFixed(1)}°
            </output>
          </div>
          <p id="hero-rotation-help" className="mt-1 text-caption text-muted">
            Regler bewegen, bis der Horizont gerade ist. Gilt für Desktop und Mobile.
          </p>
          <input
            id="hero-rotation-range"
            type="range"
            min={-5}
            max={5}
            step={0.1}
            value={angle}
            onChange={(event) => {
              setAngle(Number(event.target.value));
              setRotationSaved(false);
            }}
            className="mt-2 h-11 w-full cursor-ew-resize accent-admin-primary"
            aria-describedby="hero-rotation-help"
          />
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => setAngle(0)}
              disabled={angle === 0 || rotationBusy}
              className="min-h-11 text-label font-medium text-admin-fg2 underline-offset-4 hover:underline disabled:opacity-45"
            >
              Auf 0° zurücksetzen
            </button>
            <button
              type="button"
              onClick={saveRotation}
              disabled={angle === savedAngle || rotationBusy}
              className="min-h-11 rounded-md bg-admin-primary px-4 text-label font-medium text-admin-primary-fg transition-colors hover:bg-admin-primary-hover disabled:opacity-50"
            >
              {rotationBusy ? "Speichern…" : "Drehung speichern"}
            </button>
            {rotationSaved && <span className="text-caption text-admin-success">Gespeichert</span>}
          </div>
        </div>
      )}
      <div
        ref={frameRef}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        className="relative w-full cursor-grab touch-none overflow-hidden rounded-xl border border-line bg-band active:cursor-grabbing"
        style={{ aspectRatio: aspect }}
      >
        <img
          {...responsiveImageAttributes(resolveMediaUrl(url), width, "100vw")}
          alt=""
          decoding="async"
          draggable={false}
          className="h-full w-full select-none object-cover"
          style={{
            objectPosition: `${pos.x}% ${pos.y}%`,
            transform: angle ? `rotate(${angle}deg) scale(${rotationScale})` : undefined,
          }}
        />
        {/* subtle rule-of-thirds guides */}
        <div className="pointer-events-none absolute inset-0 opacity-40">
          <div className="absolute left-1/3 top-0 h-full w-px bg-white/60" />
          <div className="absolute left-2/3 top-0 h-full w-px bg-white/60" />
          <div className="absolute top-1/3 left-0 h-px w-full bg-white/60" />
          <div className="absolute top-2/3 left-0 h-px w-full bg-white/60" />
        </div>
      </div>
      <p className="mt-1.5 text-caption text-muted">
        Bild ziehen, um den sichtbaren Ausschnitt zu wählen.{" "}
        {busy ? "Speichern…" : saved ? "✓ Gespeichert" : ""}
      </p>
    </div>
  );
}
