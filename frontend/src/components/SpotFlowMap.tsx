import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, Marker, TileLayer, useMap } from "react-leaflet";
import { animate as animateValue, motion, useInView, useReducedMotion } from "framer-motion";
import L from "leaflet";
import type { LiveConditionsRead } from "../lib/api";
import type { WaterType } from "../lib/types";
import { windColor } from "../lib/windScale";
import { degToCompass } from "./WindRose";
import WindArrow from "./WindArrow";

const rad = (deg: number) => (deg * Math.PI) / 180;
const MAP_ZOOM = 14.5;

/** Leaflet renders no tiles when its container was sized 0 / resized after
 *  init (classic flex/grid bug). Nudge it once mounted and on every resize. */
function InvalidateSize() {
  const map = useMap();
  useEffect(() => {
    map.invalidateSize();
    const t = setTimeout(() => map.invalidateSize(), 250);
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(map.getContainer());
    return () => {
      clearTimeout(t);
      ro.disconnect();
    };
  }, [map]);
  return null;
}

/** Zooms from the map's initial (already zoomed-out) framing up to the real
 *  target once, when `active` first turns true. Reduced motion jumps straight
 *  to the target instead of flying. */
function EntranceFlyTo({
  center,
  zoom,
  active,
  reduce,
}: {
  center: [number, number];
  zoom: number;
  active: boolean;
  reduce: boolean | null;
}) {
  const map = useMap();
  const done = useRef(false);
  useEffect(() => {
    if (!active || done.current) return;
    done.current = true;
    if (reduce) {
      map.setView(center, zoom, { animate: false });
    } else {
      map.flyTo(center, zoom, { duration: 1.1 });
    }
  }, [active, center, zoom, reduce, map]);
  return null;
}

/** Toggles Leaflet's own interaction handlers post-mount — the tap-to-interact
 *  gate. The map is constructed fully non-interactive (see the `MapContainer`
 *  props below) so it never hijacks page scroll on mobile; tapping once
 *  enables real pan/zoom. */
function InteractionControl({ enabled }: { enabled: boolean }) {
  const map = useMap();
  useEffect(() => {
    const handlers = [map.dragging, map.scrollWheelZoom, map.doubleClickZoom, map.touchZoom, map.keyboard];
    handlers.forEach((h) => (enabled ? h.enable() : h.disable()));
  }, [enabled, map]);
  return null;
}

/** A live numeric reading, honestly "—" (never 0) when missing. */
function Metric({ value }: { value: string | null }) {
  if (value === null) {
    return (
      <span className="text-line" title="keine Daten" aria-label="keine Daten">
        —
      </span>
    );
  }
  return <span className="tabular-nums">{value}</span>;
}

/** Counts up from 0 to `target` once `trigger` flips true (600ms, one-shot).
 *  Reduced motion / no trigger yet just shows the target directly. */
function useCountUp(target: number | null, trigger: boolean, reduce: boolean | null): number | null {
  const [display, setDisplay] = useState<number | null>(reduce ? target : null);
  useEffect(() => {
    if (target == null) return;
    if (reduce || !trigger) {
      setDisplay(target);
      return;
    }
    setDisplay(0);
    const controls = animateValue(0, target, {
      duration: 0.6,
      ease: "easeOut",
      onUpdate: (v) => setDisplay(Math.round(v)),
    });
    return () => controls.stop();
  }, [target, trigger, reduce]);
  return display;
}

/**
 * Spot map: the label-free CARTO Voyager basemap (same look as the big map),
 * tightly framed on the spot. A canvas overlay animates the live conditions:
 *
 *  • Wind — parallel particle streaks flowing toward where the wind blows
 *    (windDir + 180). Speed and streak length scale with wind strength.
 *  • Waves — crest lines rolling toward the coast (onshore bearing) and
 *    breaking into foam near the beach. Their speed and spacing come from the
 *    swell period (spacing = phase-speed × period); chop breaks jagged, swell
 *    rolls smooth.
 *
 * An opaque card top-left shows the live reading (`live`) — separate from the
 * windKts/windDir/waveDir/period/coast props below, which only drive the
 * canvas animation and are untouched. The map itself starts non-interactive
 * (so it never hijacks page scroll on mobile) and stays that way until
 * tapped; scrolling it into view flies the zoom in, fades the streaks in,
 * then drops the marker — all skipped in favour of the end state under
 * prefers-reduced-motion.
 */
export default function SpotFlowMap({
  coords,
  windDir,
  windKts,
  waveDir,
  coast,
  period,
  waterType,
  zoom,
  mapCenter,
  aspect = "sm:aspect-[21/9]",
  rounded = true,
  live = null,
}: {
  coords: [number, number];
  windDir: number; // degrees wind comes FROM
  windKts: number;
  waveDir: number; // degrees the swell comes FROM
  coast: number; // onshore bearing (degrees) — the beach the waves break onto
  period: number; // s
  waterType: WaterType;
  zoom?: number; // admin-set preview zoom (default MAP_ZOOM)
  mapCenter?: [number, number]; // admin-set preview center (default = coords)
  /** Desktop/tablet aspect ratio, as a full `sm:`-prefixed utility class (it
   *  has to appear literally somewhere in source for Tailwind's scanner to
   *  generate it — that's why this isn't just a bare ratio string). Mobile is
   *  always the taller `aspect-[4/5]` — coastal spots show more of what
   *  matters in portrait. */
  aspect?: string;
  /** Off for the full-bleed page treatment, where the map runs edge to edge. */
  rounded?: boolean;
  /** Live reading for the top-left conditions overlay. Omitted/null → no
   *  overlay at all (never an empty card). */
  live?: LiveConditionsRead | null;
}) {
  // Effective framing: admin's saved view wins, else default (spot-centred).
  const effZoom = zoom ?? MAP_ZOOM;
  const effCenter: [number, number] = mapCenter ?? coords;
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const reduce = useReducedMotion();
  const inView = useInView(wrapRef, { once: true, amount: 0.3 });

  const [interactive, setInteractive] = useState(false);
  const [streaksVisible, setStreaksVisible] = useState(false);
  const [markerVisible, setMarkerVisible] = useState(false);
  const [overlayVisible, setOverlayVisible] = useState(false);

  // Staggered entrance once the map scrolls into view: EntranceFlyTo handles
  // the zoom itself; this drives what comes after — streaks at 1100ms (when
  // the fly finishes), the marker 400ms after that. The overlay's own 300ms
  // reveal runs off the same trigger. Reduced motion collapses straight to
  // the end state for all of it.
  useEffect(() => {
    if (!inView) return;
    if (reduce) {
      setStreaksVisible(true);
      setMarkerVisible(true);
      setOverlayVisible(true);
      return;
    }
    const tStreaks = setTimeout(() => setStreaksVisible(true), 1100);
    const tMarker = setTimeout(() => setMarkerVisible(true), 1100 + 400);
    const tOverlay = setTimeout(() => setOverlayVisible(true), 300);
    return () => {
      clearTimeout(tStreaks);
      clearTimeout(tMarker);
      clearTimeout(tOverlay);
    };
  }, [inView, reduce]);

  const initialZoom = reduce ? effZoom : Math.max(0, effZoom - 1.5);

  const dropIcon = useMemo(
    () =>
      L.divIcon({
        className: reduce ? "swd-flowmap-pin" : "swd-flowmap-pin swd-marker-drop",
        html: `<svg width="26" height="34" viewBox="0 0 24 30" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 0C5.7 0 1 4.7 1 10.7 1 18.4 12 30 12 30s11-11.6 11-19.3C23 4.7 18.3 0 12 0Z"
              fill="#E0823C" stroke="#ffffff" stroke-width="1.4"/>
            <circle cx="12" cy="10.5" r="3.4" fill="#ffffff"/>
          </svg>`,
        iconSize: [26, 34],
        iconAnchor: [13, 34],
      }),
    [reduce]
  );

  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let w = wrap.clientWidth || 380;
    let h = wrap.clientHeight || 320;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);
    const sizeCanvas = () => {
      w = wrap.clientWidth || 380;
      h = wrap.clientHeight || 320;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    };
    sizeCanvas();

    // ---- Wind: parallel particles toward windTo ----
    const windTo = (windDir + 180) % 360;
    const wv = { x: Math.sin(rad(windTo)), y: -Math.cos(rad(windTo)) };
    const windSpeed = 6 + windKts * 2.7; // px/sec — scales with wind (20 kts ≈ old 30)
    const vx = wv.x * windSpeed;
    const vy = wv.y * windSpeed;
    const trailMax = Math.round(22 + windKts * 2.4);
    const perp = { x: -wv.y, y: wv.x }; // for the arrowheads
    // Cap raised from the original 170 for the Sprint 3 full-bleed variant —
    // at ~21:9 on a wide viewport the canvas area is several times the old
    // fixed 360px-tall box, and the old cap left the streaks looking thin.
    const N = Math.max(50, Math.min(340, Math.round((w * h) / 1900)));
    type P = { x: number; y: number; life: number; max: number; trail: number[][] };
    const seedTrail = (x: number, y: number) => {
      const t: number[][] = [];
      for (let k = 4; k >= 1; k--) t.push([x - vx * 0.05 * k, y - vy * 0.05 * k]);
      t.push([x, y]);
      return t;
    };
    const respawn = (p: P) => {
      p.x = Math.random() * w;
      p.y = Math.random() * h;
      p.life = 0;
      p.max = 60 + Math.random() * 90;
      p.trail = seedTrail(p.x, p.y);
    };
    const particles: P[] = Array.from({ length: N }, () => {
      const p = { x: 0, y: 0, life: 0, max: 0, trail: [] as number[][] };
      respawn(p);
      p.life = Math.random() * p.max;
      return p;
    });

    // ---- Swell: crests travel along the swell direction and break along the
    //      coast. The angle between the two makes the break peel down the beach.
    const diag = Math.hypot(w, h);
    const half = diag / 2;
    const swellTravel = (waveDir + 180) % 360; // bearing the waves move toward
    const travelRad = rad(swellTravel);
    const cosT = Math.cos(travelRad);
    const sinT = Math.sin(travelRad); // to map rotated crest points → screen px
    // Oblique angle between swell travel and onshore direction, clamped so the
    // waves always progress onshore (extreme obliquity would refract anyway).
    let dphi = ((coast - swellTravel + 540) % 360) - 180;
    dphi = Math.max(-70, Math.min(70, dphi));
    const sinP = Math.sin(rad(dphi));
    const cosP = Math.cos(rad(dphi));
    const crestSpeed = 9 * period; // px/sec along travel; spacing = 9·T²
    const Dbreak = -0.13 * half; // starts breaking offshore, before the beach
    const Dshore = 0.05 * half; // the beach edge — waves stop here (no overrun)
    const sSpawn = -(half + 40) / cosP; // spawn offshore
    const amp = waterType === "swell" ? 7 : 2;
    const beyondShore = (s: number) => s * cosP - half * Math.abs(sinP) > Dshore;
    let crests: number[] = [];
    {
      const stepS = Math.max(24, crestSpeed * period);
      for (let s = sSpawn, n = 0; !beyondShore(s) && n < 60; s += stepS, n++) crests.push(s);
    }
    let acc = 0;

    // ---- Chop: a field of whitecaps that twinkle in place (no travel/period) ----
    type Mark = { x: number; y: number; ph: number; spd: number; size: number };
    let chopMarks: Mark[] = [];
    // Set once the basemap has been sampled; keeps chop off the land.
    let waterMask: ((x: number, y: number) => boolean) | null = null;
    const buildChop = () => {
      chopMarks = [];
      if (waterType !== "chop") return;
      const gap = 28;
      for (let gy = gap * 0.5; gy < h; gy += gap)
        for (let gx = gap * 0.5; gx < w; gx += gap) {
          const x = gx + (Math.random() - 0.5) * gap * 0.7;
          const y = gy + (Math.random() - 0.5) * gap * 0.7;
          if (waterMask && !waterMask(x, y)) continue; // waves only over water
          chopMarks.push({
            x,
            y,
            ph: Math.random() * Math.PI * 2,
            spd: 0.7 + Math.random() * 0.8,
            size: 3 + Math.random() * 3,
          });
        }
    };
    buildChop();

    // Sample the Voyager basemap to tell water (bluish) from land (warm), so the
    // chop can be restricted to the water. Falls back to "everywhere" if the
    // tiles can't be read (e.g. no CORS).
    async function buildWaterMask() {
      // Built for chop (place whitecaps on water) AND swell (clip crests off land).
      if ((waterType !== "chop" && waterType !== "swell") || w === 0 || h === 0)
        return;
      // Sampling at tile-zoom 14: bail on very wide framings (the offscreen mask
      // canvas would explode). Spot framings are ~13-15, so this only skips
      // extreme region-wide zooms, where a land mask isn't meaningful anyway.
      if (effZoom < 11) return;
      const scale = 256 * Math.pow(2, effZoom);
      const latRad = rad(effCenter[0]);
      const cwx = ((effCenter[1] + 180) / 360) * scale;
      const cwy = ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * scale;
      const tlx = cwx - w / 2;
      const tly = cwy - h / 2;
      const zt = 14;
      const f = Math.pow(2, zt - effZoom); // display px → tile-zoom px
      const mw = Math.max(1, Math.ceil(w * f));
      const mh = Math.max(1, Math.ceil(h * f));
      const tlxZt = tlx * f;
      const tlyZt = tly * f;
      const off = document.createElement("canvas");
      off.width = mw;
      off.height = mh;
      const octx = off.getContext("2d", { willReadFrequently: true });
      if (!octx) return;
      const x0 = Math.floor(tlxZt / 256);
      const x1 = Math.floor((tlxZt + mw) / 256);
      const y0 = Math.floor(tlyZt / 256);
      const y1 = Math.floor((tlyZt + mh) / 256);
      const jobs: Promise<void>[] = [];
      for (let tx = x0; tx <= x1; tx++)
        for (let ty = y0; ty <= y1; ty++)
          jobs.push(
            new Promise<void>((res) => {
              const img = new Image();
              img.crossOrigin = "anonymous";
              img.onload = () => {
                octx.drawImage(img, tx * 256 - tlxZt, ty * 256 - tlyZt);
                res();
              };
              img.onerror = () => res();
              img.src = `https://a.basemaps.cartocdn.com/rastertiles/voyager_nolabels/${zt}/${tx}/${ty}.png`;
            })
          );
      await Promise.all(jobs);
      let data: Uint8ClampedArray;
      try {
        data = octx.getImageData(0, 0, mw, mh).data;
      } catch {
        return; // tainted canvas → keep the fallback (chop everywhere)
      }
      waterMask = (px, py) => {
        const mx = Math.floor(px * f);
        const my = Math.floor(py * f);
        if (mx < 0 || my < 0 || mx >= mw || my >= mh) return true;
        const i = (my * mw + mx) * 4;
        return data[i + 2] - data[i] >= 6; // Voyager water is bluish (b − r ≥ 6)
      };
      buildChop();
    }
    void buildWaterMask();

    let raf = 0;
    let last = performance.now();

    const draw = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      // Swell — crests roll along the swell direction; each point breaks when it
      // reaches the shore (onshore distance d), so an oblique crest peels.
      if (waterType === "swell") {
        acc += dt;
        while (acc >= period) {
          acc -= period;
          crests.push(sSpawn);
        }
        crests = crests.map((s) => s + crestSpeed * dt).filter((s) => !beyondShore(s));

        ctx.save();
        ctx.translate(w / 2, h / 2);
        ctx.rotate(travelRad);
        ctx.lineCap = "round";
        for (const s of crests) {
          const yBase = -s;
          let px = 0;
          let py = 0;
          let has = false;
          for (let x = -half - 20; x <= half + 20; x += 6) {
            const d = x * sinP + s * cosP; // onshore distance of this point
            if (d > Dshore) {
              has = false; // reached the beach — waves stop here, no overrun
              continue;
            }
            const yy = yBase + Math.sin(x * 0.03 + s * 0.05) * amp;
            // Real coastlines aren't the straight modelled beach — clip any crest
            // point that lands on actual land (sampled from the basemap tiles).
            if (waterMask) {
              const sx = w / 2 + (x * cosT - yy * sinT);
              const sy = h / 2 + (x * sinT + yy * cosT);
              if (!waterMask(sx, sy)) {
                has = false; // over land → break the crest line here
                continue;
              }
            }
            if (has) {
              if (d >= Dbreak) {
                const p = Math.min(1, (d - Dbreak) / (Dshore - Dbreak));
                ctx.strokeStyle = `rgba(255,255,255,${0.9 * (1 - p * 0.4)})`;
                ctx.lineWidth = 2 + 3 * (1 - p); // foam thickest at the break
              } else {
                const a = 0.3 + 0.4 * Math.min(1, (s * cosP + half) / (2 * half));
                ctx.strokeStyle = `rgba(47,111,176,${a})`;
                ctx.lineWidth = 3;
              }
              ctx.beginPath();
              ctx.moveTo(px, py);
              ctx.lineTo(x, yy);
              ctx.stroke();
            }
            px = x;
            py = yy;
            has = true;
          }
        }
        ctx.restore();
      } else if (waterType === "chop") {
        // Chop / Kabbelwasser — a rippled surface: whitecaps twinkle in place,
        // no travel and no period, just an agitated sea. A soft dark shadow
        // keeps the white caps readable on the light basemap.
        ctx.lineCap = "round";
        ctx.lineWidth = 1.8;
        ctx.shadowColor = "rgba(15,39,72,0.45)";
        ctx.shadowBlur = 2.5;
        for (const m of chopMarks) {
          const tw = Math.sin(now * 0.0035 * m.spd + m.ph);
          if (tw < 0.15) continue;
          const a = ((tw - 0.15) / 0.85) * 0.9;
          const yb = m.y + Math.sin(now * 0.004 + m.ph) * 1.4;
          ctx.strokeStyle = `rgba(255,255,255,${a})`;
          ctx.beginPath();
          ctx.moveTo(m.x - m.size, yb + 1.4);
          ctx.quadraticCurveTo(m.x, yb - m.size * 0.7, m.x + m.size, yb + 1.4);
          ctx.stroke();
        }
        ctx.shadowBlur = 0;
      }
      // flat: no wave animation

      // Wind (screen space, parallel)
      ctx.lineCap = "round";
      ctx.lineWidth = 1.5;
      for (const p of particles) {
        p.x += vx * dt;
        p.y += vy * dt;
        p.life += dt * 60;
        p.trail.push([p.x, p.y]);
        if (p.trail.length > trailMax) p.trail.shift();
        if (p.life > p.max || p.x < -24 || p.x > w + 24 || p.y < -24 || p.y > h + 24) {
          respawn(p);
          continue;
        }
        const t = p.trail;
        const fade = Math.min(1, p.life / 10);
        for (let i = 1; i < t.length; i++) {
          const a = (i / t.length) * fade * 0.5;
          ctx.strokeStyle = `rgba(36,28,23,${a})`;
          ctx.beginPath();
          ctx.moveTo(t[i - 1][0], t[i - 1][1]);
          ctx.lineTo(t[i][0], t[i][1]);
          ctx.stroke();
        }
        // arrowhead at the leading tip, pointing downwind
        const ah = 3.8;
        ctx.fillStyle = `rgba(36,28,23,${fade * 0.5})`;
        ctx.beginPath();
        ctx.moveTo(p.x + wv.x * ah, p.y + wv.y * ah);
        ctx.lineTo(p.x - perp.x * ah * 0.6 - wv.x * ah * 0.35, p.y - perp.y * ah * 0.6 - wv.y * ah * 0.35);
        ctx.lineTo(p.x + perp.x * ah * 0.6 - wv.x * ah * 0.35, p.y + perp.y * ah * 0.6 - wv.y * ah * 0.35);
        ctx.closePath();
        ctx.fill();
      }

      raf = requestAnimationFrame(draw);
    };

    if (reduce) {
      last = performance.now();
      draw(last + 16);
      cancelAnimationFrame(raf); // one static frame only
    } else {
      raf = requestAnimationFrame(draw);
    }

    const ro = new ResizeObserver(() => {
      sizeCanvas();
      buildChop();
      void buildWaterMask();
    });
    ro.observe(wrap);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [effCenter[0], effCenter[1], effZoom, windDir, windKts, waveDir, coast, period, waterType]);

  const c = live?.current;
  const windValue = useCountUp(typeof c?.wind === "number" ? Math.round(c.wind) : null, overlayVisible, reduce);

  return (
    <div
      ref={wrapRef}
      className={`relative aspect-[4/5] w-full overflow-hidden ${aspect} ${rounded ? "rounded-3xl" : ""}`}
    >
      <MapContainer
        center={effCenter}
        zoom={initialZoom}
        zoomSnap={0.5}
        zoomControl={false}
        scrollWheelZoom={false}
        dragging={false}
        doubleClickZoom={false}
        touchZoom={false}
        keyboard={false}
        attributionControl={false}
        className="h-full w-full"
      >
        <TileLayer url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png" subdomains="abcd" />
        <InvalidateSize />
        <EntranceFlyTo center={effCenter} zoom={effZoom} active={inView} reduce={reduce} />
        <InteractionControl enabled={interactive} />
        {markerVisible && <Marker position={coords} icon={dropIcon} />}
      </MapContainer>

      <canvas
        ref={canvasRef}
        className={`pointer-events-none absolute inset-0 z-[500] h-full w-full transition-opacity duration-[400ms] ${
          streaksVisible ? "opacity-100" : "opacity-0"
        }`}
      />

      {live && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={overlayVisible ? { opacity: 1, y: 0 } : { opacity: 0, y: -8 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className="pointer-events-none absolute left-4 top-4 z-[520] rounded-2xl border border-line bg-white px-4 py-3 text-ink"
        >
          <div className="flex items-baseline gap-2">
            <span className="text-title font-semibold tabular-nums" style={{ color: windColor(windValue) }}>
              {windValue ?? "—"}
            </span>
            <span className="text-caption text-muted">kts</span>
            {typeof c?.dir === "number" && (
              <span className="flex items-center gap-1">
                <WindArrow dir={c.dir} size={16} animate className="text-ink-soft" />
                <span className="text-caption font-medium text-ink-soft">{degToCompass(c.dir)}</span>
              </span>
            )}
          </div>
          <div className="mt-1 text-caption text-muted">
            Böen <Metric value={typeof c?.gust === "number" ? String(Math.round(c.gust)) : null} /> kts
          </div>
          <div className="mt-1 flex items-center gap-2 text-caption text-muted">
            <span>
              <Metric value={typeof c?.swell === "number" ? c.swell.toFixed(1) : null} /> m
            </span>
            <span>
              <Metric value={typeof c?.period === "number" ? String(Math.round(c.period)) : null} /> s
            </span>
            <span>
              <Metric value={typeof c?.sst === "number" ? String(Math.round(c.sst)) : null} />° /{" "}
              <Metric value={typeof c?.air === "number" ? String(Math.round(c.air)) : null} />°
            </span>
          </div>
        </motion.div>
      )}

      {!interactive && (
        <button
          type="button"
          onClick={() => setInteractive(true)}
          aria-label="Karte zum Verschieben und Zoomen aktivieren"
          className="absolute inset-0 z-[540] flex items-end justify-center pb-4 sm:items-center sm:pb-0"
        >
          <span className="rounded-full border border-line bg-ink px-4 py-2 text-caption font-medium text-white">
            Antippen zum Verschieben &amp; Zoomen
          </span>
        </button>
      )}
    </div>
  );
}
