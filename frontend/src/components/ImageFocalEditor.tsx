// Drag the image within a fixed frame to choose which part shows (the focal
// point / crop). The frame uses object-fit: cover; dragging pans the image by
// adjusting object-position, then persists it as focal { x, y } percentages.

import { useRef, useState, type PointerEvent } from "react";
import { resolveMediaUrl } from "../lib/api";

const clamp = (n: number) => Math.max(0, Math.min(100, n));

export default function ImageFocalEditor({
  url,
  focal,
  onSave,
  aspect = "16 / 6",
}: {
  url: string;
  focal?: { x: number; y: number } | null;
  onSave: (x: number, y: number) => Promise<void>;
  aspect?: string;
}) {
  const [pos, setPos] = useState({ x: focal?.x ?? 50, y: focal?.y ?? 50 });
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
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

  return (
    <div>
      <div
        ref={frameRef}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        className="relative w-full cursor-grab touch-none overflow-hidden rounded-xl border border-line bg-band active:cursor-grabbing"
        style={{ aspectRatio: aspect }}
      >
        <img
          src={resolveMediaUrl(url)}
          alt=""
          draggable={false}
          className="h-full w-full select-none object-cover"
          style={{ objectPosition: `${pos.x}% ${pos.y}%` }}
        />
        {/* subtle rule-of-thirds guides */}
        <div className="pointer-events-none absolute inset-0 opacity-40">
          <div className="absolute left-1/3 top-0 h-full w-px bg-white/60" />
          <div className="absolute left-2/3 top-0 h-full w-px bg-white/60" />
          <div className="absolute top-1/3 left-0 h-px w-full bg-white/60" />
          <div className="absolute top-2/3 left-0 h-px w-full bg-white/60" />
        </div>
      </div>
      <p className="mt-1.5 text-[12px] text-muted">
        Bild ziehen, um den sichtbaren Ausschnitt zu wählen.{" "}
        {busy ? "Speichern…" : saved ? "✓ Gespeichert" : ""}
      </p>
    </div>
  );
}
