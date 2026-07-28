import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import ImageUpload from "../components/ImageUpload";
import ImageFocalEditor from "../components/ImageFocalEditor";
import SpotOpsPanel from "../components/SpotOpsPanel";
import SpotMapEditor, { type MapView } from "../components/SpotMapEditor";
import ConflictDialog from "../components/admin/ConflictDialog";
import SpotCommentsPanel from "../components/admin/SpotCommentsPanel";
import { ErrorBanner } from "../components/AsyncStates";
import { useRegions } from "../lib/hooks";
import {
  createSpot,
  fetchCommonsImages,
  getSpot,
  getReadiness,
  getSpotImages,
  removeImage,
  resolveMediaUrl,
  setSpotImageFocal,
  updateSpot,
  uploadHeroImage,
  ApiError,
  type CommunityImage,
  type FacilityKind,
  type ImageRecord,
  type Readiness,
  type SpotCreateBody,
} from "../lib/api";
import {
  FACILITY_KINDS,
  LEVELS,
  STYLES,
  WATER_CHARACTERS,
  facilityLabel,
  levelLabel,
  sportLabel,
  styleLabel,
  waterCharacterLabel,
} from "../lib/labels";
import { Chip, Field, fieldClass as inputCls } from "../components/ui";

const SPORTS = ["kitesurf", "wavekite", "windsurf", "wing", "surf"] as const;
type Availability = "yes" | "no" | "unknown";

const slugify = (s: string) =>
  s
    .toLowerCase()
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");

// --- page ------------------------------------------------------------------

export default function AdminSpotForm() {
  const { id } = useParams(); // present => edit mode
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const { data: regions } = useRegions();

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [regionId, setRegionId] = useState("");
  const [description, setDescription] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [mapView, setMapView] = useState<MapView | null>(null);
  const [sports, setSports] = useState<string[]>([]);
  const [level, setLevel] = useState("");
  const [waterCharacter, setWaterCharacter] = useState("");
  const [styles, setStyles] = useState<string[]>([]);
  const [facing, setFacing] = useState("");
  const [waterType, setWaterType] = useState("");
  const [bottomType, setBottomType] = useState("");
  const [windDirMin, setWindDirMin] = useState("");
  const [windDirMax, setWindDirMax] = useState("");
  const [tide, setTide] = useState("");
  const [facilities, setFacilities] = useState<
    Record<FacilityKind, { state: Availability; note: string }>
  >(
    () =>
      Object.fromEntries(
        FACILITY_KINDS.map((k) => [k, { state: "unknown", note: "" }])
      ) as Record<FacilityKind, { state: Availability; note: string }>
  );
  const [heroFile, setHeroFile] = useState<File | null>(null);
  const [currentImage, setCurrentImage] = useState<ImageRecord | null>(null);
  const [credit, setCredit] = useState("");
  const [galleryImages, setGalleryImages] = useState<CommunityImage[]>([]);
  const [commonsBusy, setCommonsBusy] = useState(false);
  const [commonsError, setCommonsError] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [loadingExisting, setLoadingExisting] = useState(isEdit);
  // Optimistic locking: the `updated_at` the form loaded, sent back on save so
  // the server can reject a stale overwrite (409). Refreshed on every save.
  const [loadedUpdatedAt, setLoadedUpdatedAt] = useState<string | null>(null);
  const [conflictOpen, setConflictOpen] = useState(false);

  const effectiveSlug = slugTouched ? slug : slugify(name);
  const isSurf = sports.includes("surf");

  // Populate every field from a freshly-loaded spot. Also captures the
  // `updated_at` used as the optimistic-locking token on save. Reused by the
  // edit-mode prefill and by the conflict dialog's "Neu laden".
  const applySpot = (s: Awaited<ReturnType<typeof getSpot>>) => {
    setLoadedUpdatedAt(s.updated_at);
    setName(s.name);
    setSlug(s.slug);
    setSlugTouched(true);
    setRegionId(s.region_id);
    setDescription((s.editorial?.description as string) ?? "");
    setCurrentImage((s.image as ImageRecord | null) ?? null);
    if (s.location) {
      setLat(String(s.location.lat));
      setLon(String(s.location.lon));
    }
    const mv = s.editorial?.map_view;
    if (mv && Array.isArray(mv.center) && typeof mv.zoom === "number") {
      setMapView({ center: mv.center as [number, number], zoom: mv.zoom });
    }
    setSports(s.sports ?? []);
    setLevel(s.level ?? "");
    setWaterCharacter(s.water_character ?? "");
    setStyles(s.style ?? []);
    setFacing(s.facing != null ? String(s.facing) : "");
    setWaterType(s.water_type ?? "");
    setBottomType(s.bottom_type ?? "");
    const uwd = s.editorial?.usable_wind_directions;
    if (uwd && typeof uwd === "object") {
      setWindDirMin(uwd.min != null ? String(uwd.min) : "");
      setWindDirMax(uwd.max != null ? String(uwd.max) : "");
    }
    setTide(typeof s.editorial?.tide === "string" ? s.editorial.tide : "");
    if (s.facilities) {
      setFacilities((prev) => {
        const next = { ...prev };
        for (const k of FACILITY_KINDS) {
          const entry = s.facilities?.[k];
          next[k] = entry
            ? { state: entry.available ? "yes" : "no", note: entry.note ?? "" }
            : { state: "unknown", note: "" };
        }
        return next;
      });
    }
  };

  // Prefill in edit mode.
  useEffect(() => {
    if (!id) return;
    let alive = true;
    getSpot(id)
      .then((s) => {
        if (alive) applySpot(s);
      })
      .catch((e) =>
        alive && setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen.")
      )
      .finally(() => alive && setLoadingExisting(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const reloadGallery = () => {
    if (!id) return;
    getSpotImages(id)
      .then((r) => setGalleryImages(r.items.filter((i) => i.kind === "gallery")))
      .catch(() => {});
  };

  useEffect(reloadGallery, [id]);

  const runCommonsFetch = async () => {
    if (!id) return;
    setCommonsBusy(true);
    setCommonsError(null);
    try {
      await fetchCommonsImages(id);
      reloadGallery();
    } catch (e) {
      setCommonsError(e instanceof ApiError ? e.message : "Abruf fehlgeschlagen.");
    } finally {
      setCommonsBusy(false);
    }
  };

  const removeGalleryImage = async (imageId: string) => {
    setGalleryImages((prev) => prev.filter((i) => i.id !== imageId)); // optimistic
    try {
      await removeImage(imageId);
    } catch {
      reloadGallery(); // roll back on failure
    }
  };

  const toggle = (list: string[], v: string) =>
    list.includes(v) ? list.filter((x) => x !== v) : [...list, v];

  const buildEditorial = (): Record<string, any> => {
    const ed: Record<string, any> = {};
    if (description.trim()) ed.description = description.trim();
    if (windDirMin !== "" && windDirMax !== "")
      ed.usable_wind_directions = { min: Number(windDirMin), max: Number(windDirMax) };
    if (isSurf && tide.trim()) ed.tide = tide.trim();
    if (mapView) ed.map_view = mapView; // preview frame for the spot's flow map
    return ed;
  };

  const buildFacilities = () => {
    const out: Record<string, { available: boolean; note?: string }> = {};
    for (const k of FACILITY_KINDS) {
      const f = facilities[k];
      if (f.state === "unknown") continue; // omit the key entirely → shown as "unbekannt" on the spot page
      out[k] = {
        available: f.state === "yes",
        ...(f.note.trim() ? { note: f.note.trim() } : {}),
      };
    }
    return Object.keys(out).length ? out : null;
  };

  const validateLocal = (): boolean => {
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = "Name ist erforderlich.";
    if (!regionId) errs.region_id = "Region wählen.";
    if (lat === "" || Number.isNaN(Number(lat))) errs.lat = "Breitengrad angeben.";
    if (lon === "" || Number.isNaN(Number(lon))) errs.lon = "Längengrad angeben.";
    if (heroFile && !credit.trim()) errs.credit = "Bild-Credit angeben.";
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  // `force` skips the optimistic-locking token — used by the conflict dialog's
  // "Trotzdem überschreiben" after the operator has been warned.
  const doSave = async (force: boolean) => {
    setError(null);
    setReadiness(null);
    setSubmitting(true);
    try {
      const body: SpotCreateBody = {
        name: name.trim(),
        slug: effectiveSlug || undefined,
        region_id: regionId,
        lat: Number(lat),
        lon: Number(lon),
        sports,
        level: level || null,
        water_character: waterCharacter || null,
        style: styles,
        water_type: waterType || null,
        bottom_type: bottomType || null,
        facing: facing !== "" ? Number(facing) : null,
        facilities: buildFacilities(),
        editorial: Object.keys(buildEditorial()).length ? buildEditorial() : null,
      };

      let spot;
      if (isEdit && id) {
        spot = await updateSpot(id, {
          ...body,
          expected_updated_at: force ? undefined : loadedUpdatedAt ?? undefined,
        });
        // Adopt the new version so a second save in the same session isn't
        // rejected as stale against its own successful write.
        setLoadedUpdatedAt(spot.updated_at);
      } else {
        spot = await createSpot(body);
      }

      if (heroFile) {
        await uploadHeroImage(spot.id, heroFile, credit.trim());
      }

      const r = await getReadiness(spot.id);
      setReadiness(r);
      setSavedId(spot.id);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setConflictOpen(true);
          return;
        }
        setError(err.message);
        // FastAPI/Pydantic 422: detail may be a list of {loc, msg}.
        if (Array.isArray((err.detail as any)?.detail)) {
          const fe: Record<string, string> = {};
          for (const d of (err.detail as any).detail) {
            const loc = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : d.loc;
            fe[String(loc)] = d.msg;
          }
          setFieldErrors((prev) => ({ ...prev, ...fe }));
        }
      } else {
        setError("Unerwarteter Fehler beim Speichern.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!validateLocal()) return;
    void doSave(false);
  };

  // Conflict dialog: discard local edits and reload the server's version.
  const reloadFromServer = () => {
    setConflictOpen(false);
    if (!id) return;
    setLoadingExisting(true);
    getSpot(id)
      .then(applySpot)
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Laden fehlgeschlagen.")
      )
      .finally(() => setLoadingExisting(false));
  };

  const regionOptions = useMemo(
    () =>
      (regions ?? [])
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name, "de")),
    [regions]
  );

  if (loadingExisting) {
    return (
      <div className="mx-auto max-w-[820px]">
        <div className="h-8 w-64 animate-pulse rounded bg-line" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1100px]">
      <h1 className="text-[24px] font-semibold text-ink">
        {isEdit ? "Spot bearbeiten" : "Neuen Spot anlegen"}
      </h1>
      <p className="mt-2 text-[15px] text-muted">
        Nur Name, Region und Position sind zum Speichern nötig — fehlende Teile
        sind ok: der Spot wird als Entwurf gespeichert und erscheint in der
        Übersicht unter „Offene Punkte", um ihn später zu ergänzen.
      </p>

      <form
        onSubmit={onSubmit}
        className="mt-6 lg:grid lg:grid-cols-[minmax(0,1fr)_300px] lg:items-start lg:gap-8"
      >
        {/* Left column: editorial fields (scrolls) */}
        <div className="min-w-0 space-y-8">
          {/* Basisdaten */}
          <section className="space-y-4">
            <h2 className="text-[15px] font-semibold text-ink">Basisdaten</h2>
            <Field label="Name" error={fieldErrors.name}>
              <input
                className={inputCls}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="z. B. Laboe"
              />
            </Field>
            <Field
              label="Slug"
              hint="Wird automatisch aus dem Namen erzeugt — überschreibbar."
            >
              <input
                className={inputCls}
                value={effectiveSlug}
                onChange={(e) => {
                  setSlugTouched(true);
                  setSlug(e.target.value);
                }}
              />
            </Field>
            <Field label="Region" error={fieldErrors.region_id}>
              <select
                className={inputCls}
                value={regionId}
                onChange={(e) => setRegionId(e.target.value)}
              >
                <option value="">— Region wählen —</option>
                {regionOptions.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                    {r.country ? `, ${r.country}` : ""}
                  </option>
                ))}
              </select>
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Breitengrad (lat)" error={fieldErrors.lat}>
                <input
                  className={inputCls}
                  value={lat}
                  onChange={(e) => setLat(e.target.value)}
                  inputMode="decimal"
                  placeholder="54.41"
                />
              </Field>
              <Field label="Längengrad (lon)" error={fieldErrors.lon}>
                <input
                  className={inputCls}
                  value={lon}
                  onChange={(e) => setLon(e.target.value)}
                  inputMode="decimal"
                  placeholder="10.22"
                />
              </Field>
            </div>
            <div>
              <span className="text-[13px] font-medium text-ink">
                Position &amp; Karten-Ausschnitt
              </span>
              <div className="mt-1.5">
                <SpotMapEditor
                  lat={lat === "" ? null : Number(lat)}
                  lon={lon === "" ? null : Number(lon)}
                  mapView={mapView}
                  onPositionChange={(la, lo) => {
                    setLat(String(la));
                    setLon(String(lo));
                    setFieldErrors((prev) => {
                      const { lat: _l, lon: _o, ...rest } = prev;
                      return rest;
                    });
                  }}
                  onViewChange={setMapView}
                />
              </div>
            </div>
            <Field label="Beschreibung">
              <textarea
                className={`${inputCls} min-h-[120px] resize-y`}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Charakter des Spots, Bedingungen, Besonderheiten …"
              />
            </Field>
          </section>

          {/* Sportarten */}
          <section>
            <h2 className="text-[15px] font-semibold text-ink">Sportarten</h2>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {SPORTS.map((s) => (
                <Chip
                  key={s}
                  active={sports.includes(s)}
                  onClick={() => setSports(toggle(sports, s))}
                >
                  {sportLabel(s)}
                </Chip>
              ))}
            </div>
          </section>

          {/* Kategorien */}
          <section className="space-y-4">
            <h2 className="text-[15px] font-semibold text-ink">Kategorien</h2>
            <Field label="Level">
              <select
                className={inputCls}
                value={level}
                onChange={(e) => setLevel(e.target.value)}
              >
                <option value="">— unbekannt —</option>
                {LEVELS.map((l) => (
                  <option key={l} value={l}>
                    {levelLabel(l)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Wasserart" hint="Pflichtfeld für die Veröffentlichung.">
              <select
                className={inputCls}
                value={waterCharacter}
                onChange={(e) => setWaterCharacter(e.target.value)}
              >
                <option value="">— unbekannt —</option>
                {WATER_CHARACTERS.map((w) => (
                  <option key={w} value={w}>
                    {waterCharacterLabel(w)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Fahrstil (Mehrfachauswahl)">
              <div className="flex flex-wrap gap-1.5">
                {STYLES.map((s) => (
                  <Chip
                    key={s}
                    active={styles.includes(s)}
                    onClick={() => setStyles(toggle(styles, s))}
                  >
                    {styleLabel(s)}
                  </Chip>
                ))}
              </div>
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Wassertyp" hint="ocean | sea | lake | lagoon">
                <input
                  className={inputCls}
                  value={waterType}
                  onChange={(e) => setWaterType(e.target.value)}
                  placeholder="sea"
                />
              </Field>
              <Field label="Untergrund" hint="sand | rock | reef | mixed">
                <input
                  className={inputCls}
                  value={bottomType}
                  onChange={(e) => setBottomType(e.target.value)}
                  placeholder="sand"
                />
              </Field>
            </div>
          </section>

          {/* Wind & Gezeiten */}
          <section className="space-y-4">
            <h2 className="text-[15px] font-semibold text-ink">Wind & Ausrichtung</h2>
            <Field
              label="Nutzbare Windrichtungen"
              hint="Sektor in Grad (0 = N). Pflichtfeld für Kite/Wind/Wing."
            >
              <div className="flex items-center gap-2">
                <input
                  className={inputCls}
                  value={windDirMin}
                  onChange={(e) => setWindDirMin(e.target.value)}
                  inputMode="numeric"
                  placeholder="von (z. B. 180)"
                />
                <span className="text-muted">–</span>
                <input
                  className={inputCls}
                  value={windDirMax}
                  onChange={(e) => setWindDirMax(e.target.value)}
                  inputMode="numeric"
                  placeholder="bis (z. B. 260)"
                />
              </div>
            </Field>
            <Field label="Strandausrichtung (facing, 0–359)">
              <input
                className={inputCls}
                value={facing}
                onChange={(e) => setFacing(e.target.value)}
                inputMode="numeric"
                placeholder="45"
              />
            </Field>
            {isSurf && (
              <Field label="Gezeiten (Tide)" hint="Pflichtfeld für Surf-Spots.">
                <input
                  className={inputCls}
                  value={tide}
                  onChange={(e) => setTide(e.target.value)}
                  placeholder="z. B. bei auflaufendem Wasser am besten"
                />
              </Field>
            )}
          </section>

          {/* Facilities */}
          <section>
            <h2 className="text-[15px] font-semibold text-ink">Facilities</h2>
            <p className="mt-1 text-[12px] text-muted">
              „Unbekannt" zeigt auf der Spot-Seite einen eigenen, gedämpften Zustand — nicht
              „nicht vorhanden".
            </p>
            <div className="mt-3 space-y-3">
              {FACILITY_KINDS.map((k) => (
                <div
                  key={k}
                  className="rounded-xl bg-[#F1F5FA] p-3 sm:flex sm:items-center sm:gap-3"
                >
                  <span className="w-40 shrink-0 text-[13.5px] font-medium text-ink">
                    {facilityLabel(k)}
                  </span>
                  <div className="mt-2 flex gap-1.5 sm:mt-0">
                    {(
                      [
                        ["yes", "Vorhanden"],
                        ["no", "Nicht vorhanden"],
                        ["unknown", "Unbekannt"],
                      ] as [Availability, string][]
                    ).map(([st, label]) => (
                      <Chip
                        key={st}
                        active={facilities[k].state === st}
                        onClick={() =>
                          setFacilities((prev) => ({
                            ...prev,
                            [k]: { ...prev[k], state: st },
                          }))
                        }
                      >
                        {label}
                      </Chip>
                    ))}
                  </div>
                  <input
                    className={`${inputCls} mt-2 sm:mt-0 disabled:cursor-not-allowed disabled:opacity-50`}
                    value={facilities[k].note}
                    disabled={facilities[k].state === "unknown"}
                    onChange={(e) =>
                      setFacilities((prev) => ({
                        ...prev,
                        [k]: { ...prev[k], note: e.target.value },
                      }))
                    }
                    placeholder={
                      facilities[k].state === "unknown" ? "Notiz (erst bei ja/nein)" : "Notiz (optional)"
                    }
                  />
                </div>
              ))}
            </div>
          </section>

          {/* Hero-Bild */}
          <section>
            <h2 className="text-[15px] font-semibold text-ink">Header-Bild</h2>
            {currentImage?.url && (
              <div className="mt-3">
                <p className="text-[13px] font-medium text-ink">Ausschnitt wählen</p>
                <div className="mt-1.5 max-w-[560px]">
                  <ImageFocalEditor
                    url={currentImage.url}
                    focal={currentImage.focal}
                    aspect="21 / 9"
                    onSave={async (x, y) => {
                      if (!id) return;
                      const spot = await setSpotImageFocal(id, x, y);
                      setCurrentImage((spot.image as ImageRecord | null) ?? null);
                    }}
                  />
                </div>
                <p className="mt-2 text-[12px] text-muted">
                  Neues Bild ersetzt das aktuelle:
                </p>
              </div>
            )}
            <div className="mt-3">
              <ImageUpload onAccept={setHeroFile} />
            </div>
            {heroFile && (
              <div className="mt-3">
                <Field label="Bild-Credit / Urheber" error={fieldErrors.credit}>
                  <input
                    className={inputCls}
                    value={credit}
                    onChange={(e) => setCredit(e.target.value)}
                    placeholder="Fotograf:in / Quelle"
                  />
                </Field>
              </div>
            )}
          </section>

          {/* Galerie: community photos + Wikimedia Commons */}
          {isEdit && id && (
            <section>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-[15px] font-semibold text-ink">Galerie</h2>
                <button
                  type="button"
                  onClick={runCommonsFetch}
                  disabled={commonsBusy}
                  className="rounded-2xl border border-teal/30 px-4 py-2 text-label font-medium text-teal transition-colors hover:bg-teal/5 disabled:opacity-50"
                >
                  {commonsBusy ? "Abrufen…" : "Wikimedia-Bilder abrufen"}
                </button>
              </div>
              <p className="mt-1 text-caption text-muted">
                Sucht georeferenzierte Fotos in der Nähe des Spots auf Wikimedia Commons und
                übernimmt nur Treffer mit erkennbarer Lizenz. Die Geo-Suche liefert auch
                Parkplätze oder Ortsschilder — einzelne Treffer unten entfernen.
              </p>
              {commonsError && (
                <p role="alert" className="mt-2 text-label text-red-600">
                  {commonsError}
                </p>
              )}

              {galleryImages.length > 0 && (
                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  {galleryImages.map((img) => (
                    <div key={img.id} className="group relative aspect-square overflow-hidden rounded-xl">
                      <img
                        src={resolveMediaUrl(img.url)}
                        alt={img.credit ?? ""}
                        className="h-full w-full object-cover"
                        loading="lazy"
                      />
                      {img.source === "wikimedia_commons" && (
                        <span className="absolute bottom-1.5 left-1.5 rounded-2xl bg-ink px-2 py-0.5 text-caption font-medium text-white">
                          Commons
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={() => removeGalleryImage(img.id)}
                        className="absolute right-1.5 top-1.5 rounded-2xl bg-ink px-2.5 py-1 text-caption font-medium text-white opacity-0 transition-opacity hover:bg-red-600 group-hover:opacity-100"
                      >
                        Entfernen
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Kommentare: per-spot moderation (verbergen/wiederherstellen) */}
          {isEdit && id && (
            <section>
              <h2 className="text-[15px] font-semibold text-ink">Kommentare</h2>
              <p className="mb-4 mt-1 text-caption text-muted">
                Alle Kommentare zu diesem Spot — Antworten stehen unter ihrem
                Ausgangskommentar. Verborgene bleiben hier sichtbar und lassen
                sich wiederherstellen.
              </p>
              <SpotCommentsPanel spotId={id} />
            </section>
          )}

        </div>

        {/* Right column: sticky actions — stay put while the form scrolls */}
        <aside className="mt-8 space-y-4 lg:mt-0 lg:sticky lg:top-6">
          {isEdit && id && <SpotOpsPanel spotId={id} />}

          {savedId && readiness && (
            <div className="rounded-2xl bg-green/10 p-4">
              <p className="text-[14px] font-semibold text-green">
                ✓ Gespeichert.{" "}
                {readiness.ready
                  ? "Der Spot erfüllt alle Pflichtfelder und kann live gehen."
                  : "Für die Veröffentlichung fehlen noch Angaben:"}
              </p>
              {!readiness.ready && (
                <ul className="mt-2 list-inside list-disc text-[13px] text-ink-soft">
                  {readiness.gaps.map((g) => (
                    <li key={g}>{g}</li>
                  ))}
                </ul>
              )}
              <div className="mt-4 flex flex-wrap gap-2">
                <Link
                  to={`/spot/${savedId}`}
                  className="rounded-lg bg-teal px-3 py-1.5 text-[13px] font-medium text-white hover:bg-teal-hover"
                >
                  Zur Spot-Seite
                </Link>
                {!isEdit && (
                  <button
                    type="button"
                    onClick={() => navigate(`/admin/spot/${savedId}/edit`)}
                    className="rounded-lg px-3 py-1.5 text-[13px] font-medium text-teal ring-1 ring-teal/30 hover:ring-teal/50"
                  >
                    Weiter bearbeiten
                  </button>
                )}
              </div>
            </div>
          )}

          {error && <ErrorBanner message={error} />}

          <div className="rounded-2xl border border-line bg-white p-4">
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-xl bg-teal px-5 py-2.5 text-[14px] font-medium text-white hover:bg-teal-hover disabled:opacity-50"
            >
              {submitting
                ? "Speichern …"
                : isEdit
                ? "Änderungen speichern"
                : "Spot anlegen"}
            </button>
            <div className="mt-3 flex items-center justify-between text-[13px]">
              <Link to="/" className="text-muted hover:text-teal">
                Abbrechen
              </Link>
              {isEdit && id && (
                <a
                  href={`/spot/${id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-teal hover:underline"
                >
                  Vorschau ↗
                </a>
              )}
            </div>
          </div>
        </aside>
      </form>

      <ConflictDialog
        open={conflictOpen}
        busy={submitting}
        onReload={reloadFromServer}
        onOverwrite={() => {
          setConflictOpen(false);
          void doSave(true);
        }}
        onClose={() => setConflictOpen(false)}
      />
    </div>
  );
}
