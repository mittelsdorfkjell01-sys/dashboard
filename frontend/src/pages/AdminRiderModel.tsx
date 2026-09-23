import { useEffect, useState } from "react";
import {
  ApiError,
  getAdminRiderModel,
  previewAdminRiderModel,
  saveAdminRiderModel,
  type PersonalBandPreview,
  type RiderModelBoardType,
  type RiderModelDocument,
  type RiderModelLevel,
} from "../lib/api";
import { Button, Input, PageHeader, adminFieldClass } from "../components/admin/ui";

const BOARD: { key: RiderModelBoardType; label: string }[] = [
  { key: "twintip", label: "Twintip" },
  { key: "surfboard", label: "Surfboard" },
  { key: "foil", label: "Foil" },
  { key: "bigair_twintip", label: "Big-Air-Twintip" },
];
const LEVELS: { key: RiderModelLevel; label: string }[] = [
  { key: "beginner", label: "Einsteiger" },
  { key: "advanced", label: "Fortgeschritten" },
  { key: "expert", label: "Experte" },
  { key: "competition", label: "Competition" },
];
const STYLES = ["freeride", "freestyle", "big_air", "wave_riding", "wavekite"];

function NumberField({ label, value, onChange, step = 0.05 }: {
  label: string; value: number; onChange: (value: number) => void; step?: number;
}) {
  return (
    <label className="block">
      <span className="text-label font-medium text-admin-fg2">{label}</span>
      <Input type="number" step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} className="mt-1.5" />
    </label>
  );
}

function parseKites(value: string): number[] {
  return value.split(",").map((item) => Number(item.trim())).filter((item) => Number.isFinite(item) && item > 0);
}

export default function AdminRiderModel() {
  const [document, setDocument] = useState<RiderModelDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<PersonalBandPreview | null>(null);
  const [previewWeight, setPreviewWeight] = useState(78);
  const [previewLevel, setPreviewLevel] = useState<RiderModelLevel>("advanced");
  const [previewKites, setPreviewKites] = useState("9, 12");
  const [previewBoard, setPreviewBoard] = useState<RiderModelBoardType>("twintip");
  const [defaultKitesText, setDefaultKitesText] = useState("");

  useEffect(() => {
    getAdminRiderModel()
      .then((data) => {
        setDocument(data);
        setDefaultKitesText(data.default_rider.quiver
          .filter((item) => item.kind === "kite")
          .map((item) => item.size)
          .filter((item): item is number => typeof item === "number")
          .join(", "));
      })
      .catch((reason) => setError(reason instanceof ApiError ? reason.message : "Rider-Modell konnte nicht geladen werden."));
  }, []);

  const defaultBoard = document?.default_rider.quiver.find((item) => item.kind === "board" || item.kind === "foil")?.board_type ?? "twintip";

  if (!document) {
    return <div><PageHeader title="Rider-Modell" /><p role={error ? "alert" : "status"} className={error ? "text-admin-danger" : "text-admin-muted"}>{error ?? "Rider-Modell wird geladen …"}</p></div>;
  }

  const updateBoardFactor = (key: RiderModelBoardType, value: number) => setDocument({
    ...document,
    rider_model: { ...document.rider_model, k_board: { ...document.rider_model.k_board, [key]: value } },
  });
  const updateLevel = (key: RiderModelLevel, field: "max_kt" | "gust_tolerance_kt", value: number) => setDocument({
    ...document,
    rider_model: {
      ...document.rider_model,
      levels: { ...document.rider_model.levels, [key]: { ...document.rider_model.levels[key], [field]: value } },
    },
  });
  const setDefaultQuiver = (kiteText: string, board: RiderModelBoardType) => {
    setDefaultKitesText(kiteText);
    const kites = parseKites(kiteText);
    setDocument({
      ...document,
      default_rider: {
        ...document.default_rider,
        quiver: [
          ...kites.map((size) => ({ kind: "kite" as const, size, active: true })),
          { kind: "board", board_type: board, active: true },
        ],
      },
    });
  };

  const save = async () => {
    setSaving(true); setError(null); setMessage(null);
    try {
      const saved = await saveAdminRiderModel({
        rider_model: document.rider_model,
        default_rider: document.default_rider,
      });
      setDocument(saved);
      setMessage(`Version ${saved.version} wurde angelegt und aktiviert.`);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Rider-Modell konnte nicht gespeichert werden.");
    } finally { setSaving(false); }
  };

  const runPreview = async () => {
    const sizes = parseKites(previewKites);
    if (sizes.length === 0) { setError("Gib für die Vorschau mindestens eine Kite-Größe ein."); return; }
    setPreviewing(true); setError(null);
    try {
      setPreview(await previewAdminRiderModel({
        rider_model: document.rider_model,
        default_rider: document.default_rider,
        weight_kg: previewWeight,
        level: previewLevel,
        quiver: [
          ...sizes.map((size) => ({ kind: "kite" as const, size, active: true })),
          { kind: "board", board_type: previewBoard, active: true },
        ],
        style_weights: document.default_rider.style_weights,
        travel_mode: document.default_rider.travel_mode,
      }));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Vorschau konnte nicht berechnet werden.");
    } finally { setPreviewing(false); }
  };

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Rider-Modell" actions={<Button variant="primary" disabled={saving} onClick={() => void save()}>{saving ? "Speichert …" : "Neue Version speichern"}</Button>} />
      <div className="mb-7 flex flex-wrap items-baseline justify-between gap-3 border-b border-admin-border pb-5">
        <div>
          <h2 className="text-xl font-semibold text-admin-fg">Rider-Modell</h2>
          <p className="mt-1 max-w-[70ch] text-ui text-admin-muted">Kalibrierung für Kitesurf. Beim Speichern entsteht eine neue unveränderliche Parameterversion.</p>
        </div>
        <span className="text-label tabular-nums text-admin-muted">Aktiv: Version {document.version}</span>
      </div>

      {(error || message) && <p role={error ? "alert" : "status"} className={`mb-5 rounded-md border px-4 py-3 text-label ${error ? "border-admin-danger-border bg-admin-danger-bg text-admin-danger" : "border-admin-success-border bg-admin-success-bg text-admin-success"}`}>{error ?? message}</p>}

      <div className="grid gap-10 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-10">
          <section>
            <h3 className="text-base font-semibold text-admin-fg">Band-Faktoren</h3>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {BOARD.map(({ key, label }) => <NumberField key={key} label={`k_board · ${label}`} value={document.rider_model.k_board[key]} onChange={(value) => updateBoardFactor(key, value)} />)}
              <NumberField label="Unterer Faktor f_lo" value={document.rider_model.f_lo} onChange={(value) => setDocument({ ...document, rider_model: { ...document.rider_model, f_lo: value } })} />
              <NumberField label="Oberer Faktor f_hi" value={document.rider_model.f_hi} onChange={(value) => setDocument({ ...document, rider_model: { ...document.rider_model, f_hi: value } })} />
            </div>
          </section>

          <section className="border-t border-admin-border pt-8">
            <h3 className="text-base font-semibold text-admin-fg">Level-Grenzen</h3>
            <div className="mt-4 space-y-5">
              {LEVELS.map(({ key, label }) => <div key={key} className="grid gap-3 sm:grid-cols-[10rem_1fr_1fr] sm:items-end">
                <p className="pb-2 text-label font-medium text-admin-fg2">{label}</p>
                <NumberField label="Maximum (kt)" step={0.5} value={document.rider_model.levels[key].max_kt} onChange={(value) => updateLevel(key, "max_kt", value)} />
                <NumberField label="Böentoleranz (kt)" step={0.5} value={document.rider_model.levels[key].gust_tolerance_kt} onChange={(value) => updateLevel(key, "gust_tolerance_kt", value)} />
              </div>)}
            </div>
          </section>

          <section className="border-t border-admin-border pt-8">
            <h3 className="text-base font-semibold text-admin-fg">Durchschnitts-Rider</h3>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <NumberField label="Gewicht (kg)" step={0.5} value={document.default_rider.weight_kg} onChange={(value) => setDocument({ ...document, default_rider: { ...document.default_rider, weight_kg: value } })} />
              <label className="block"><span className="text-label font-medium text-admin-fg2">Level</span><select className={`${adminFieldClass} mt-1.5 w-full`} value={document.default_rider.level} onChange={(event) => setDocument({ ...document, default_rider: { ...document.default_rider, level: event.target.value as RiderModelLevel } })}>{LEVELS.map(({ key, label }) => <option key={key} value={key}>{label}</option>)}</select></label>
              <label className="block"><span className="text-label font-medium text-admin-fg2">Reisemodus</span><select className={`${adminFieldClass} mt-1.5 w-full`} value={document.default_rider.travel_mode} onChange={(event) => setDocument({ ...document, default_rider: { ...document.default_rider, travel_mode: event.target.value as RiderModelDocument["default_rider"]["travel_mode"] } })}><option value="day_trip">Tagesausflug</option><option value="weekend">Wochenende</option><option value="trip">Reise</option><option value="camper">Camper</option></select></label>
              <label className="block"><span className="text-label font-medium text-admin-fg2">Kites (m², kommagetrennt)</span><Input className="mt-1.5" value={defaultKitesText} onChange={(event) => setDefaultQuiver(event.target.value, defaultBoard)} /></label>
              <label className="block"><span className="text-label font-medium text-admin-fg2">Board</span><select className={`${adminFieldClass} mt-1.5 w-full`} value={defaultBoard} onChange={(event) => setDefaultQuiver(defaultKitesText, event.target.value as RiderModelBoardType)}>{BOARD.map(({ key, label }) => <option key={key} value={key}>{label}</option>)}</select></label>
              {STYLES.map((style) => <NumberField key={style} label={`Stil · ${style}`} step={1} value={document.default_rider.style_weights[style] ?? 0} onChange={(value) => setDocument({ ...document, default_rider: { ...document.default_rider, style_weights: { ...document.default_rider.style_weights, [style]: value } } })} />)}
            </div>
          </section>
        </div>

        <aside className="h-fit border-t border-admin-border pt-6 xl:sticky xl:top-[calc(var(--admin-header-h,4rem)+1.5rem)]">
          <h3 className="text-base font-semibold text-admin-fg">Vorschau</h3>
          <p className="mt-1 text-label text-admin-muted">Berechnung mit den aktuell sichtbaren, noch nicht gespeicherten Werten.</p>
          <div className="mt-5 space-y-4">
            <NumberField label="Gewicht (kg)" step={0.5} value={previewWeight} onChange={setPreviewWeight} />
            <label className="block"><span className="text-label font-medium text-admin-fg2">Level</span><select className={`${adminFieldClass} mt-1.5 w-full`} value={previewLevel} onChange={(event) => setPreviewLevel(event.target.value as RiderModelLevel)}>{LEVELS.map(({ key, label }) => <option key={key} value={key}>{label}</option>)}</select></label>
            <label className="block"><span className="text-label font-medium text-admin-fg2">Kites (m²)</span><Input className="mt-1.5" value={previewKites} onChange={(event) => setPreviewKites(event.target.value)} /></label>
            <label className="block"><span className="text-label font-medium text-admin-fg2">Board</span><select className={`${adminFieldClass} mt-1.5 w-full`} value={previewBoard} onChange={(event) => setPreviewBoard(event.target.value as RiderModelBoardType)}>{BOARD.map(({ key, label }) => <option key={key} value={key}>{label}</option>)}</select></label>
            <Button variant="secondary" className="min-h-11 w-full" disabled={previewing} onClick={() => void runPreview()}>{previewing ? "Berechnet …" : "Band berechnen"}</Button>
          </div>
          {preview && <dl className="mt-6 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-admin-border pt-5 text-label">
            <div><dt className="text-admin-muted">Minimum</dt><dd className="mt-0.5 font-semibold tabular-nums text-admin-fg">{preview.min_kt.toFixed(1)} kt</dd></div>
            <div><dt className="text-admin-muted">Ideal</dt><dd className="mt-0.5 font-semibold tabular-nums text-admin-fg">{preview.ideal_lo_kt.toFixed(1)}–{preview.ideal_hi_kt.toFixed(1)} kt</dd></div>
            <div><dt className="text-admin-muted">Maximum</dt><dd className="mt-0.5 font-semibold tabular-nums text-admin-fg">{preview.max_kt.toFixed(1)} kt</dd></div>
            <div><dt className="text-admin-muted">Böentoleranz</dt><dd className="mt-0.5 font-semibold tabular-nums text-admin-fg">{preview.gust_tolerance_kt.toFixed(1)} kt</dd></div>
          </dl>}
        </aside>
      </div>
    </div>
  );
}
