import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import ImageUpload from "../components/ImageUpload";
import ImageFocalEditor from "../components/ImageFocalEditor";
import SpotOpsPanel from "../components/SpotOpsPanel";
import SpotMapEditor, { type MapView } from "../components/SpotMapEditor";
import ConflictDialog from "../components/admin/ConflictDialog";
import DuplicateWarningDialog from "../components/admin/DuplicateWarningDialog";
import ConfirmToast from "../components/admin/ConfirmToast";
import SpotCommentsPanel from "../components/admin/SpotCommentsPanel";
import TideAdminPanel from "../components/admin/TideAdminPanel";
import CollapsibleSection from "../components/admin/CollapsibleSection";
import FormNavBar from "../components/admin/FormNavBar";
import { ErrorBanner } from "../components/AsyncStates";
import { useAdminRegions } from "../lib/hooks";
import {
  createSpot,
  deleteSpot,
  fetchCommonsImages,
  getAdminSpot,
  getReadiness,
  setHeroAttribution,
  setSpotImageFocal,
  setSpotImageFocalMobile,
  updateSpot,
  uploadHeroImage,
  ApiError,
  type FacilityKind,
  type ImageRecord,
  type Readiness,
  type SpotCreateBody,
} from "../lib/api";
import {
  FACILITY_KINDS,
  BOTTOM_TYPES,
  LEVELS,
  MODEL_PREF_OPTIONS,
  STYLES,
  WATER_CHARACTERS,
  WATER_TYPES,
  facilityLabel,
  bottomTypeLabel,
  gapAnchor,
  gapLabel,
  levelLabel,
  sportLabel,
  styleLabel,
  waterCharacterLabel,
  waterTypeLabel,
} from "../lib/labels";
import { Chip, Field, fieldClass as inputCls } from "../components/ui";
import { PageHeader } from "../components/admin/ui";
import AdminBackButton, {
  useAdminBackNavigation,
} from "../components/admin/AdminBackButton";
import UnsavedChangesDialog from "../components/admin/UnsavedChangesDialog";
import MediaPicker from "../components/admin/MediaPicker";
import GalleryManager from "../components/admin/GalleryManager";
import type { MediaRole } from "../lib/mediaPicker";
import { type AdminNavigationState } from "../lib/adminNavigation";
import {
  stableFormValue,
  useUnsavedChangesGuard,
} from "../lib/useUnsavedChangesGuard";
import {
  parseDuplicateConflict,
  type DuplicateConflict,
} from "../lib/duplicateConflicts";

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
  const location = useLocation();
  const back = useAdminBackNavigation({
    fallbackTo: "/admin/spots",
    fallbackLabel: "Spots",
  });
  const { blocker, markDirty, markClean, setDirty } = useUnsavedChangesGuard();
  const { data: regions } = useAdminRegions();

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [regionId, setRegionId] = useState("");
  const [description, setDescription] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [mapView, setMapView] = useState<MapView | null>(null);
  const [sports, setSports] = useState<string[]>([]);
  const [level, setLevel] = useState<string[]>([]);
  const [waterCharacter, setWaterCharacter] = useState<string[]>([]);
  const [styles, setStyles] = useState<string[]>([]);
  const [facing, setFacing] = useState("");
  const [waterType, setWaterType] = useState<string[]>([]);
  const [bottomType, setBottomType] = useState<string[]>([]);
  const [tide, setTide] = useState("");
  const [facilities, setFacilities] = useState<
    Record<FacilityKind, { state: Availability; note: string }>
  >(
    () =>
      Object.fromEntries(
        FACILITY_KINDS.map((k) => [k, { state: "unknown", note: "" }])
      ) as Record<FacilityKind, { state: Availability; note: string }>
  );
  const [modelPref, setModelPref] = useState("");
  const [heroFile, setHeroFile] = useState<File | null>(null);
  const [currentImage, setCurrentImage] = useState<ImageRecord | null>(null);
  const [credit, setCredit] = useState("");
  // Attribution of the *current* hero (edited in place, url + focal preserved).
  const [attrCredit, setAttrCredit] = useState("");
  const [attrLicense, setAttrLicense] = useState("");
  const [attrSource, setAttrSource] = useState("");
  const [attrBusy, setAttrBusy] = useState(false);
  const [attrMsg, setAttrMsg] = useState<string | null>(null);
  // Bumped after a Commons fetch to force GalleryManager to reload — it and
  // the Commons-fetch button write to the same spot_images rows through
  // different endpoints, so a fetch elsewhere must invalidate its cache.
  const [galleryVersion, setGalleryVersion] = useState(0);
  const [commonsBusy, setCommonsBusy] = useState(false);
  const [commonsError, setCommonsError] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState<MediaRole | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [loadingExisting, setLoadingExisting] = useState(isEdit);
  // Optimistic locking: the `updated_at` the form loaded, sent back on save so
  // the server can reject a stale overwrite (409). Refreshed on every save.
  const [loadedUpdatedAt, setLoadedUpdatedAt] = useState<string | null>(null);
  const [conflictOpen, setConflictOpen] = useState(false);
  const [duplicateConflict, setDuplicateConflict] = useState<DuplicateConflict | null>(null);
  const [pendingDelete, setPendingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [mainBaseline, setMainBaseline] = useState<string | null>(null);
  const [captureMainBaseline, setCaptureMainBaseline] = useState(!isEdit);
  const [attributionBaseline, setAttributionBaseline] = useState(
    stableFormValue({ credit: "", license: "", source: "" })
  );

  const onDelete = async () => {
    if (!id) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteSpot(id);
      markClean();
      back.goBack();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Löschen fehlgeschlagen.");
      setPendingDelete(false);
    } finally {
      setDeleting(false);
    }
  };

  const effectiveSlug = slugTouched ? slug : slugify(name);
  const isSurf = sports.includes("surf");
  const mainFormValue = stableFormValue({
    name,
    slug: effectiveSlug,
    regionId,
    description,
    lat,
    lon,
    mapView,
    sports,
    level,
    waterCharacter,
    styles,
    facing,
    waterType,
    bottomType,
    tide,
    facilities,
    modelPref,
    heroFile,
    credit,
  });
  const attributionValue = stableFormValue({
    credit: attrCredit,
    license: attrLicense,
    source: attrSource,
  });

  useEffect(() => {
    if (!captureMainBaseline) return;
    setMainBaseline(mainFormValue);
    setCaptureMainBaseline(false);
  }, [captureMainBaseline, mainFormValue]);

  useEffect(() => {
    setDirty(
      "main",
      !captureMainBaseline && mainBaseline !== null && mainFormValue !== mainBaseline
    );
  }, [captureMainBaseline, mainBaseline, mainFormValue, setDirty]);

  useEffect(() => {
    setDirty("attribution", attributionValue !== attributionBaseline);
  }, [attributionBaseline, attributionValue, setDirty]);

  const focusGap = (gap: string) => {
    const el = document.getElementById(gapAnchor(gap));
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    if (typeof el.focus === "function") el.focus({ preventScroll: true });
  };

  // Set the current hero + seed its attribution editor fields.
  const seedImage = (img: ImageRecord | null) => {
    setCurrentImage(img);
    setAttrCredit(img?.credit ?? "");
    setAttrLicense(img?.license ?? "");
    setAttrSource(img?.source ?? "");
    setAttributionBaseline(
      stableFormValue({
        credit: img?.credit ?? "",
        license: img?.license ?? "",
        source: img?.source ?? "",
      })
    );
  };

  const saveAttribution = async () => {
    if (!id || !currentImage) return;
    setAttrBusy(true);
    setAttrMsg(null);
    try {
      const spot = await setHeroAttribution(id, {
        credit: attrCredit.trim(),
        license: attrLicense.trim(),
        source: attrSource.trim(),
      });
      seedImage((spot.image as ImageRecord | null) ?? null);
      markClean("attribution");
      setAttrMsg("Attribution gespeichert.");
      setTimeout(() => setAttrMsg(null), 2500);
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Attribution speichern fehlgeschlagen."
      );
    } finally {
      setAttrBusy(false);
    }
  };

  // Populate every field from a freshly-loaded spot. Also captures the
  // `updated_at` used as the optimistic-locking token on save. Reused by the
  // edit-mode prefill and by the conflict dialog's "Neu laden".
  const applySpot = (s: Awaited<ReturnType<typeof getAdminSpot>>) => {
    setLoadedUpdatedAt(s.updated_at);
    setModelPref(s.model_pref ?? "");
    setName(s.name);
    setSlug(s.slug);
    setSlugTouched(true);
    setRegionId(s.region_id ?? "");
    setDescription((s.editorial?.description as string) ?? "");
    seedImage((s.image as ImageRecord | null) ?? null);
    setHeroFile(null);
    setCredit("");
    if (s.location) {
      setLat(String(s.location.lat));
      setLon(String(s.location.lon));
    } else {
      setLat("");
      setLon("");
    }
    const mv = s.editorial?.map_view;
    if (mv && Array.isArray(mv.center) && typeof mv.zoom === "number") {
      setMapView({ center: mv.center as [number, number], zoom: mv.zoom });
    } else {
      setMapView(null);
    }
    setSports(s.sports ?? []);
    setLevel(s.level ?? []);
    setWaterCharacter(s.water_character ?? []);
    setStyles(s.style ?? []);
    setFacing(s.facing != null ? String(s.facing) : "");
    setWaterType(s.water_type ?? []);
    setBottomType(s.bottom_type ?? []);
    setTide(typeof s.editorial?.tide === "string" ? s.editorial.tide : "");
    setFacilities(() => {
      const next = {} as Record<FacilityKind, { state: Availability; note: string }>;
      for (const k of FACILITY_KINDS) {
        const entry = s.facilities?.[k];
        next[k] = entry
          ? { state: entry.available ? "yes" : "no", note: entry.note ?? "" }
          : { state: "unknown", note: "" };
      }
      return next;
    });
    setCaptureMainBaseline(true);
  };

  // Prefill in edit mode.
  useEffect(() => {
    if (!id) return;
    let alive = true;
    getAdminSpot(id)
      .then((s) => {
        if (!alive) return;
        applySpot(s);
        markClean();
        const state = location.state as AdminNavigationState | null;
        if (state?.adminJustCreated?.id === id) {
          getReadiness(id)
            .then((result) => {
              if (!alive) return;
              setReadiness(result);
              setSavedId(id);
            })
            .catch(() => {});
        }
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

  useEffect(() => {
    if (loadingExisting || !location.hash) return;
    const target = document.getElementById(location.hash.slice(1));
    if (target) window.setTimeout(() => target.scrollIntoView({ block: "start" }), 0);
  }, [loadingExisting, location.hash]);

  const runCommonsFetch = async () => {
    if (!id) return;
    setCommonsBusy(true);
    setCommonsError(null);
    try {
      await fetchCommonsImages(id);
      setGalleryVersion((v) => v + 1);
    } catch (e) {
      setCommonsError(e instanceof ApiError ? e.message : "Abruf fehlgeschlagen.");
    } finally {
      setCommonsBusy(false);
    }
  };

  const toggle = (list: string[], v: string) =>
    list.includes(v) ? list.filter((x) => x !== v) : [...list, v];

  const buildEditorial = (): Record<string, any> => {
    const ed: Record<string, any> = {};
    if (description.trim()) ed.description = description.trim();
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
  const doSave = async (force: boolean, allowDuplicate = false) => {
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
        level,
        water_character: waterCharacter,
        style: styles,
        water_type: waterType,
        bottom_type: bottomType,
        facing: facing !== "" ? Number(facing) : null,
        facilities: buildFacilities(),
        editorial: Object.keys(buildEditorial()).length ? buildEditorial() : null,
        allow_duplicate: allowDuplicate,
      };

      let spot;
      if (isEdit && id) {
        spot = await updateSpot(id, {
          ...body,
          model_pref: modelPref || null,
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
      setHeroFile(null);
      setCredit("");
      markClean("main");
      setCaptureMainBaseline(true);
      if (!isEdit) {
        navigate(`/admin/spot/${spot.id}/edit`, {
          replace: true,
          state: {
            ...((location.state as AdminNavigationState | null) ?? {}),
            adminJustCreated: { id: spot.id },
          },
        });
      }
    } catch (err) {
      if (err instanceof ApiError) {
        const duplicate = parseDuplicateConflict(err);
        if (duplicate) {
          setDuplicateConflict(duplicate);
          return;
        }
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
    // Operator opt-in: always force. The conflict dialog was routinely
    // waved through, so we skip it — a stale write wins silently. If a
    // second editor becomes a real risk, restore the optimistic-locking
    // token here and reopen the dialog on 409.
    void doSave(true);
  };

  // Conflict dialog: discard local edits and reload the server's version.
  const reloadFromServer = () => {
    setConflictOpen(false);
    if (!id) return;
    setLoadingExisting(true);
    getAdminSpot(id)
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
  const selectedRegionName =
    regionOptions.find((region) => region.id === regionId)?.name ?? "Ohne Region";

  if (loadingExisting) {
    return (
      <div className="mx-auto max-w-[820px]">
        <div className="h-8 w-64 animate-pulse rounded bg-line" />
      </div>
    );
  }

  return (
    <div className="w-full">
      <AdminBackButton onClick={back.goBack} label={back.label} className="mb-2" />
      <PageHeader
        title={isEdit ? `Spot bearbeiten — ${name || "Spot"}` : "Neuen Spot anlegen"}
      />
      <form
        id="admin-spot-form"
        onSubmit={onSubmit}
        className="pb-20 xl:pb-0 xl:pr-[352px]"
      >
        {/* Left column: editorial fields (scrolls) */}
        <div className="min-w-0 space-y-8">
          {/* Basisdaten */}
          <CollapsibleSection id="f-basisdaten" title="Basisdaten" bodyClassName="space-y-4">
            <Field label="Name" error={fieldErrors.name}>
              <input
                className={inputCls}
                value={name}
                onChange={(e) => {
                  markDirty("main");
                  setName(e.target.value);
                }}
                placeholder="z. B. Laboe"
              />
            </Field>
            {/* Slug ausgeblendet — wird automatisch aus dem Namen erzeugt
                (Spots werden im Admin über die ID adressiert). */}
            <Field label="Region" error={fieldErrors.region_id}>
              <select
                className={inputCls}
                value={regionId}
                onChange={(e) => {
                  markDirty("main");
                  setRegionId(e.target.value);
                }}
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
            {isEdit && (
              <Field label="Wettermodell">
                <select
                  className={inputCls}
                  value={modelPref}
                  onChange={(e) => {
                    markDirty("main");
                    setModelPref(e.target.value);
                  }}
                >
                  <option value="">— vom Region-Default erben —</option>
                  {MODEL_PREF_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Breitengrad (lat)" error={fieldErrors.lat}>
                <input
                  className={inputCls}
                  value={lat}
                  onChange={(e) => {
                    markDirty("main");
                    setLat(e.target.value);
                  }}
                  inputMode="decimal"
                  placeholder="54.41"
                />
              </Field>
              <Field label="Längengrad (lon)" error={fieldErrors.lon}>
                <input
                  className={inputCls}
                  value={lon}
                  onChange={(e) => {
                    markDirty("main");
                    setLon(e.target.value);
                  }}
                  inputMode="decimal"
                  placeholder="10.22"
                />
              </Field>
            </div>
            <div>
              <span className="text-label font-medium text-ink">
                Position &amp; Karten-Ausschnitt
              </span>
              <div className="mt-1.5">
                <SpotMapEditor
                  lat={lat === "" ? null : Number(lat)}
                  lon={lon === "" ? null : Number(lon)}
                  mapView={mapView}
                  onPositionChange={(la, lo) => {
                    markDirty("main");
                    setLat(String(la));
                    setLon(String(lo));
                    setFieldErrors((prev) => {
                      const { lat: _l, lon: _o, ...rest } = prev;
                      return rest;
                    });
                  }}
                  onViewChange={(view) => {
                    markDirty("main");
                    setMapView(view);
                  }}
                />
              </div>
            </div>
            <Field label="Beschreibung">
              <textarea
                id="f-description"
                className={`${inputCls} min-h-[120px] resize-y scroll-mt-24`}
                value={description}
                onChange={(e) => {
                  markDirty("main");
                  setDescription(e.target.value);
                }}
                placeholder="Charakter des Spots, Bedingungen, Besonderheiten …"
              />
            </Field>
          </CollapsibleSection>

          {/* Sportarten */}
          <CollapsibleSection id="f-sportarten" title="Sportarten">
            <div className="flex flex-wrap gap-1.5">
              {SPORTS.map((s) => (
                <Chip
                  key={s}
                  active={sports.includes(s)}
                  onClick={() => {
                    markDirty("main");
                    setSports(toggle(sports, s));
                  }}
                >
                  {sportLabel(s)}
                </Chip>
              ))}
            </div>
          </CollapsibleSection>

          {/* Kategorien */}
          <CollapsibleSection id="f-kategorien" title="Kategorien" bodyClassName="space-y-4">
            <Field label="Level (Mehrfachauswahl)">
              <div id="f-level" className="flex flex-wrap gap-1.5 scroll-mt-24">
                {LEVELS.map((l) => (
                  <Chip
                    key={l}
                    active={level.includes(l)}
                    onClick={() => {
                      markDirty("main");
                      setLevel(toggle(level, l));
                    }}
                  >
                    {levelLabel(l)}
                  </Chip>
                ))}
              </div>
            </Field>
            <Field
              label="Wasserart (Mehrfachauswahl)"
              hint="Pflichtfeld für die Veröffentlichung."
            >
              <div
                id="f-water_character"
                className="flex flex-wrap gap-1.5 scroll-mt-24"
              >
                {WATER_CHARACTERS.map((w) => (
                  <Chip
                    key={w}
                    active={waterCharacter.includes(w)}
                    onClick={() => {
                      markDirty("main");
                      setWaterCharacter(toggle(waterCharacter, w));
                    }}
                  >
                    {waterCharacterLabel(w)}
                  </Chip>
                ))}
              </div>
            </Field>
            <Field label="Wassertyp (Mehrfachauswahl)">
              <div id="f-water_type" className="flex flex-wrap gap-1.5 scroll-mt-24">
                {WATER_TYPES.map((w) => (
                  <Chip
                    key={w}
                    active={waterType.includes(w)}
                    onClick={() => {
                      markDirty("main");
                      setWaterType(toggle(waterType, w));
                    }}
                  >
                    {waterTypeLabel(w)}
                  </Chip>
                ))}
              </div>
            </Field>
            <Field label="Fahrstil (Mehrfachauswahl)">
              <div className="flex flex-wrap gap-1.5">
                {STYLES.map((s) => (
                  <Chip
                    key={s}
                    active={styles.includes(s)}
                    onClick={() => {
                      markDirty("main");
                      setStyles(toggle(styles, s));
                    }}
                  >
                    {styleLabel(s)}
                  </Chip>
                ))}
              </div>
            </Field>
            <Field label="Untergrund (Mehrfachauswahl)">
              <div id="f-bottom_type" className="flex flex-wrap gap-1.5 scroll-mt-24">
                {BOTTOM_TYPES.map((bottom) => (
                  <Chip
                    key={bottom}
                    active={bottomType.includes(bottom)}
                    onClick={() => {
                      markDirty("main");
                      if (bottom === "mixed") {
                        setBottomType(bottomType.includes(bottom) ? [] : [bottom]);
                      } else {
                        setBottomType(toggle(bottomType.filter((v) => v !== "mixed"), bottom));
                      }
                    }}
                  >
                    {bottomTypeLabel(bottom)}
                  </Chip>
                ))}
              </div>
            </Field>
          </CollapsibleSection>

          {/* Ausrichtung */}
          <CollapsibleSection id="f-ausrichtung" title="Ausrichtung" bodyClassName="space-y-4">
            <Field label="Strandausrichtung (facing, 0–359)">
              <input
                className={inputCls}
                value={facing}
                onChange={(e) => {
                  markDirty("main");
                  setFacing(e.target.value);
                }}
                inputMode="numeric"
                placeholder="45"
              />
            </Field>
            {/* Gezeiten (Tide) ausgeblendet — wird später überarbeitet. Wert
                bleibt erhalten und wird weiterhin gespeichert. */}
          </CollapsibleSection>

          {/* Facilities */}
          <CollapsibleSection id="f-facilities" title="Facilities">
            <p className="-mt-3 text-caption text-muted">
              „Unbekannt" zeigt auf der Spot-Seite einen eigenen, gedämpften Zustand — nicht
              „nicht vorhanden".
            </p>
            <div className="mt-3 space-y-3">
              {FACILITY_KINDS.map((k) => (
                <div
                  key={k}
                  className="rounded-lg border border-admin-border bg-admin-bg p-3 sm:flex sm:items-center sm:gap-3"
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
                        onClick={() => {
                          markDirty("main");
                          setFacilities((prev) => ({
                            ...prev,
                            [k]: { ...prev[k], state: st },
                          }));
                        }}
                      >
                        {label}
                      </Chip>
                    ))}
                  </div>
                  <input
                    className={`${inputCls} mt-2 sm:mt-0 disabled:cursor-not-allowed disabled:opacity-50`}
                    value={facilities[k].note}
                    disabled={facilities[k].state === "unknown"}
                    onChange={(e) => {
                      markDirty("main");
                      setFacilities((prev) => ({
                        ...prev,
                        [k]: { ...prev[k], note: e.target.value },
                      }));
                    }}
                    placeholder={
                      facilities[k].state === "unknown" ? "Notiz (erst bei ja/nein)" : "Notiz (optional)"
                    }
                  />
                </div>
              ))}
            </div>
          </CollapsibleSection>

          <CollapsibleSection
            id="f-hero"
            title="Header-Bild"
            aside={
              isEdit && id ? (
                <button
                  type="button"
                  onClick={() => setPickerOpen("hero")}
                  className="rounded-md bg-admin-primary px-3 py-1.5 text-label font-medium text-admin-primary-fg transition-colors hover:bg-admin-primary-hover"
                >
                  Bild suchen
                </button>
              ) : null
            }
          >
            {currentImage?.url && (
              <div className="mt-3">
                <p className="text-label font-medium text-ink">Ausschnitt Desktop (21:9)</p>
                <div className="mt-1.5 max-w-[560px]">
                  <ImageFocalEditor
                    url={currentImage.url}
                    focal={currentImage.focal}
                    aspect="21 / 9"
                    onSave={async (x, y) => {
                      if (!id) return;
                      const spot = await setSpotImageFocal(id, x, y);
                      seedImage((spot.image as ImageRecord | null) ?? null);
                    }}
                  />
                </div>
                <p className="mt-5 text-label font-medium text-ink">Ausschnitt Mobile (16:9)</p>
                <p className="mt-0.5 text-caption text-muted">
                  Optional. Wenn leer, gilt der Desktop-Ausschnitt auch auf dem Handy.
                </p>
                <div className="mt-1.5 max-w-[320px]">
                  <ImageFocalEditor
                    url={currentImage.url}
                    focal={currentImage.focal_mobile ?? currentImage.focal}
                    aspect="16 / 9"
                    onSave={async (x, y) => {
                      if (!id) return;
                      const spot = await setSpotImageFocalMobile(id, { x, y });
                      seedImage((spot.image as ImageRecord | null) ?? null);
                    }}
                  />
                </div>
                <div className="mt-4 rounded-lg border border-admin-border bg-admin-bg p-4">
                  <p className="text-label font-semibold text-admin-fg">Bildnachweis</p>
                  <p className="mt-0.5 text-caption text-muted">
                    Urheber, Lizenz und Quelle des aktuellen Bilds — ohne neu
                    hochzuladen.
                  </p>
                  <div className="mt-3 grid gap-3 sm:grid-cols-3">
                    <Field label="Urheber / Credit">
                      <input
                        className={inputCls}
                        value={attrCredit}
                        onChange={(e) => {
                          markDirty("attribution");
                          setAttrCredit(e.target.value);
                        }}
                        placeholder="Fotograf:in"
                      />
                    </Field>
                    <Field label="Lizenz">
                      <input
                        className={inputCls}
                        value={attrLicense}
                        onChange={(e) => {
                          markDirty("attribution");
                          setAttrLicense(e.target.value);
                        }}
                        placeholder="z. B. CC BY-SA 4.0"
                      />
                    </Field>
                    <Field label="Quelle">
                      <input
                        className={inputCls}
                        value={attrSource}
                        onChange={(e) => {
                          markDirty("attribution");
                          setAttrSource(e.target.value);
                        }}
                        placeholder="z. B. wikimedia_commons"
                      />
                    </Field>
                  </div>
                  <div className="mt-3 flex items-center gap-3">
                    <button
                      type="button"
                      onClick={saveAttribution}
                      disabled={
                        attrBusy ||
                        !attrCredit.trim() ||
                        !attrLicense.trim() ||
                        !attrSource.trim()
                      }
                      className="rounded-md border border-admin-border bg-admin-surface px-3 py-1.5 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-50"
                    >
                      {attrBusy ? "Speichern…" : "Bildnachweis speichern"}
                    </button>
                    {attrMsg && (
                      <span className="text-caption font-medium text-admin-success">{attrMsg}</span>
                    )}
                  </div>
                </div>
                <p className="mt-3 text-caption text-muted">
                  Neues Bild ersetzt das aktuelle:
                </p>
              </div>
            )}
            <div className="mt-3">
              <ImageUpload
                onAccept={(file) => {
                  markDirty("main");
                  setHeroFile(file);
                }}
                allowBelowMin
              />
            </div>
            {heroFile && (
              <div className="mt-3">
                <Field label="Bild-Credit / Urheber" error={fieldErrors.credit}>
                  <input
                    className={inputCls}
                    value={credit}
                    onChange={(e) => {
                      markDirty("main");
                      setCredit(e.target.value);
                    }}
                    placeholder="Fotograf:in / Quelle"
                  />
                </Field>
              </div>
            )}
          </CollapsibleSection>

          {/* Galerie: community photos + Wikimedia Commons */}
          {isEdit && id && (
            <CollapsibleSection
              id="f-galerie"
              title="Galerie"
              aside={
                <button
                  type="button"
                  onClick={runCommonsFetch}
                  disabled={commonsBusy}
                  className="rounded-md border border-admin-border bg-admin-surface px-3.5 py-2 text-label font-medium text-admin-fg2 transition-colors hover:bg-admin-hover hover:text-admin-fg disabled:opacity-50"
                >
                  {commonsBusy ? "Abrufen…" : "Wikimedia-Bilder abrufen"}
                </button>
              }
            >
              <p className="-mt-3 text-caption text-muted">
                Sucht georeferenzierte Fotos in der Nähe des Spots auf Wikimedia Commons und
                übernimmt nur Treffer mit erkennbarer Lizenz. Die Geo-Suche liefert auch
                Parkplätze oder Ortsschilder — einzelne Treffer unten entfernen.
              </p>
              {commonsError && (
                <p role="alert" className="mt-2 text-label text-red-600">
                  {commonsError}
                </p>
              )}

              <div className="mt-4">
                <GalleryManager
                  key={galleryVersion}
                  entityType="spot"
                  entityId={id}
                  onHeroChanged={async () => {
                    const spot = await getAdminSpot(id);
                    seedImage((spot.image as ImageRecord | null) ?? null);
                  }}
                />
              </div>
            </CollapsibleSection>
          )}

          {isEdit && id && pickerOpen && (
            <MediaPicker
              entityType="spot"
              entityId={id}
              open
              initialRole={pickerOpen}
              onClose={() => setPickerOpen(null)}
              onAdopted={async () => {
                const spot = await getAdminSpot(id);
                seedImage((spot.image as ImageRecord | null) ?? null);
                setGalleryVersion((v) => v + 1);
              }}
            />
          )}

          {/* Kommentare: per-spot moderation (verbergen/wiederherstellen) */}
          {isEdit && id && (
            <CollapsibleSection id="f-kommentare" title="Kommentare">
              <p className="-mt-3 mb-4 text-caption text-muted">
                Alle Kommentare zu diesem Spot — Antworten stehen unter ihrem
                Ausgangskommentar. Verborgene bleiben hier sichtbar und lassen
                sich wiederherstellen.
              </p>
              <SpotCommentsPanel spotId={id} />
            </CollapsibleSection>
          )}

          {/* Gezeiten — sitzt zwischen Kommentaren und dem Löschen-Block, damit
              tägliche Redigierarbeit oben bleibt und die Kalibrier-Kachel nicht
              beim Speichern durch das halbe Formular scrollt. */}
          {id && Number.isFinite(Number(lat)) && Number.isFinite(Number(lon)) && (
            <CollapsibleSection id="f-gezeiten" title="Gezeiten">
              <TideAdminPanel spotId={id} spotLat={Number(lat)} spotLon={Number(lon)} />
            </CollapsibleSection>
          )}

          {/* Danger zone: permanently delete the spot (edit mode only). */}
          {isEdit && id && (
            <CollapsibleSection id="f-loeschen" title="Spot löschen" tone="danger">
              <p className="-mt-3 text-label text-admin-fg2">
                Löscht diesen Spot endgültig samt aller Bewertungen, Tipps, Bilder
                und Klimatologie. Das lässt sich nicht rückgängig machen — zum
                Ausblenden lieber „Archivieren" verwenden.
              </p>
              <button
                type="button"
                disabled={deleting}
                onClick={() => setPendingDelete(true)}
                className="mt-4 rounded-md border border-admin-danger-border bg-admin-surface px-3 py-1.5 text-label font-medium text-admin-danger transition-colors hover:bg-admin-danger-bg disabled:cursor-not-allowed disabled:opacity-50"
              >
                Spot löschen
              </button>
            </CollapsibleSection>
          )}

        </div>

        {/* Right column: fixed on wide viewports so the actions do not shift
            with the form's initial scroll. Below xl it stacks below the form
            as before. The form uses xl:pr-[352px] to reserve the space. */}
        <aside className="mt-8 space-y-4 xl:mt-0 xl:fixed xl:right-8 xl:top-[79px] xl:w-[320px] xl:max-h-[calc(100vh-95px)] xl:overflow-y-auto xl:pr-1 no-scrollbar">
          {isEdit && (
            <div className="border-b border-admin-border px-1 pb-3">
              <p className="truncate text-body font-semibold text-admin-fg">
                {name.trim() || "Unbenannter Spot"}
              </p>
              <p className="mt-0.5 truncate text-label text-admin-muted">
                {selectedRegionName}
              </p>
            </div>
          )}
          {isEdit && id && (
            <div id="f-operations" className="scroll-mt-24">
              <SpotOpsPanel spotId={id} onGapClick={focusGap} />
            </div>
          )}

          {savedId && readiness && (
            <div className="rounded-lg border border-admin-success-border bg-admin-success-bg p-4">
              <p className="text-ui font-semibold text-admin-success">
                ✓ Gespeichert.{" "}
                {readiness.ready
                  ? "Der Spot erfüllt alle Pflichtfelder und kann live gehen."
                  : "Für die Veröffentlichung fehlen noch Angaben:"}
              </p>
              {!readiness.ready && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {readiness.gaps.map((g) => (
                    <button
                      key={g}
                      type="button"
                      onClick={() => focusGap(g)}
                      className="rounded-md border border-admin-border bg-admin-surface px-2 py-0.5 text-caption font-medium text-admin-fg2 transition-colors hover:border-admin-border-strong"
                    >
                      {gapLabel(g)}
                    </button>
                  ))}
                </div>
              )}
              <div className="mt-4 flex flex-wrap gap-2">
                <a
                  href={`/spot/${savedId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-md bg-admin-primary px-3 py-1.5 text-label font-medium text-admin-primary-fg transition-colors hover:bg-admin-primary-hover"
                >
                  Ansehen ↗
                </a>
              </div>
            </div>
          )}

          {error && <ErrorBanner message={error} />}

          <div className="rounded-lg border border-admin-border bg-admin-surface p-4">
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-md bg-admin-primary px-5 py-2.5 text-ui font-medium text-admin-primary-fg transition-colors hover:bg-admin-primary-hover disabled:opacity-50"
            >
              {submitting
                ? "Speichern …"
                : isEdit
                ? "Änderungen speichern"
                : "Spot anlegen"}
            </button>
            <div className="mt-3 flex items-center justify-between text-label">
              <AdminBackButton
                onClick={back.goBack}
                label={back.label}
                text="Abbrechen"
                showIcon={false}
              />
              {isEdit && id && (
                <a
                  href={`/spot/${id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-admin-primary hover:underline"
                  title="Öffnet die öffentliche Spot-Seite — funktioniert auch für Entwürfe."
                >
                  Öffentliche Vorschau ↗
                </a>
              )}
            </div>
          </div>
        </aside>
      </form>

      <FormNavBar />

      <div className="fixed inset-x-0 bottom-0 z-30 flex items-center gap-2 border-t border-admin-border bg-admin-surface/95 px-4 py-3 backdrop-blur xl:hidden">
        <AdminBackButton
          onClick={back.goBack}
          label={back.label}
          text="Abbrechen"
          showIcon={false}
          className="min-h-11 flex-1 justify-center"
        />
        <button
          type="submit"
          form="admin-spot-form"
          disabled={submitting}
          className="min-h-11 flex-1 rounded-md bg-admin-primary px-4 py-2 text-label font-medium text-admin-primary-fg disabled:opacity-50"
        >
          {submitting ? "Speichern …" : isEdit ? "Speichern" : "Spot anlegen"}
        </button>
      </div>

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
      <DuplicateWarningDialog
        conflict={duplicateConflict}
        busy={submitting}
        onClose={() => setDuplicateConflict(null)}
        onOverride={() => {
          setDuplicateConflict(null);
          void doSave(false, true);
        }}
      />
      <UnsavedChangesDialog blocker={blocker} />

      <ConfirmToast
        open={pendingDelete}
        tone="danger"
        message="Spot endgültig löschen?"
        busy={deleting}
        onConfirm={onDelete}
        onCancel={() => setPendingDelete(false)}
      />
    </div>
  );
}
