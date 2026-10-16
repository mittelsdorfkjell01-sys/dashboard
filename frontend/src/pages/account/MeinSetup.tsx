import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { AccountPage } from "./AccountLayout";
import { Button, Field, Input, Select } from "../../components/ui";
import {
  AccountError,
  createGearItem,
  deleteGearItem,
  getGear,
  getRiderProfile,
  getRiderSportProfile,
  putRiderProfile,
  putRiderSportProfile,
  updateGearItem,
  type GearItem,
  type GearItemInput,
  type RiderLevel,
  type RiderProfile,
  type RiderSportProfile,
  type TravelMode,
} from "../../lib/account";
import QuiverEditor, { type QuiverDraft } from "./QuiverEditor";
import { useTranslation } from "react-i18next";
import type { TranslationKey } from "../../lib/i18n";

const LEVELS: { value: RiderLevel; key: TranslationKey }[] = [
  { value: "beginner", key: "setup.levels.beginner" },
  { value: "advanced", key: "setup.levels.advanced" },
  { value: "expert", key: "setup.levels.expert" },
  { value: "competition", key: "setup.levels.competition" },
];

const STYLES = [
  ["freeride", "setup.styles.freeride"], ["freestyle", "setup.styles.freestyle"],
  ["big_air", "setup.styles.bigAir"], ["wave_riding", "setup.styles.waveRiding"],
  ["wavekite", "setup.styles.wavekite"],
] as const;

const WATER = [
  ["flach", "setup.waterKinds.flach"], ["chop", "setup.waterKinds.chop"],
  ["welle_klein", "setup.waterKinds.welleKlein"], ["welle_gross", "setup.waterKinds.welleGross"],
  ["tiefes_wasser", "setup.waterKinds.tiefesWasser"],
] as const;

const EMPTY_PROFILE: RiderProfile = {
  weightKg: null, homeLocation: null, maxTravelKm: null, travelMode: "day_trip",
  availability: [], minWaterTempC: null, excludedBottoms: [], profileVersion: 0,
};

const EMPTY_SPORT: RiderSportProfile = {
  sport: "kitesurf", level: null, styleWeights: {},
  preferredWaterCharacter: [], profileVersion: 0,
};

function drafts(items: GearItem[]): QuiverDraft[] {
  return items.map((item) => ({ ...item, clientId: item.id }));
}

function Section({ title, intro, children }: { title: string; intro?: string; children: ReactNode }) {
  return (
    <section className="border-t border-line pt-8 first:border-t-0 first:pt-0">
      <h2 className="text-lead font-semibold text-ink">{title}</h2>
      {intro && <p className="mt-1 max-w-measure text-ui text-muted">{intro}</p>}
      <div className="mt-5">{children}</div>
    </section>
  );
}

export default function MeinSetup() {
  const { t } = useTranslation();
  const [profile, setProfile] = useState<RiderProfile>(EMPTY_PROFILE);
  const [sport, setSport] = useState<RiderSportProfile>(EMPTY_SPORT);
  const [gear, setGear] = useState<QuiverDraft[]>([]);
  const [storedGear, setStoredGear] = useState<GearItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  /** `text` is a server-supplied sentence, `key` one of ours — never both.
   *  Resolved in render so the message follows a language change, and so the
   *  load effect does not need `t` in its dependency list. */
  const [message, setMessage] = useState<
    { kind: "ok" | "error"; text: string; key?: undefined } | { kind: "ok" | "error"; key: TranslationKey; text?: undefined } | null
  >(null);

  useEffect(() => {
    let active = true;
    Promise.all([getRiderProfile(), getRiderSportProfile("kitesurf"), getGear("kitesurf")])
      .then(([base, kite, items]) => {
        if (!active) return;
        setProfile(base);
        setSport(kite);
        setGear(drafts(items));
        setStoredGear(items);
      })
      .catch((error) => active && setMessage(
        error instanceof Error
          ? { kind: "error", text: error.message }
          : { kind: "error", key: "setup.loadFailed" },
      ))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  const complete = useMemo(() => (
    profile.weightKg !== null
    && sport.level !== null
    && gear.some((item) => item.kind === "kite" && item.active && (item.size ?? 0) > 0)
  ), [gear, profile.weightKg, sport.level]);

  const setCoordinate = (axis: "lat" | "lon", raw: string) => {
    const otherAxis = axis === "lat" ? "lon" : "lat";
    const other = profile.homeLocation?.[otherAxis] ?? Number.NaN;
    if (raw === "" && !Number.isFinite(other)) {
      setProfile({ ...profile, homeLocation: null });
      return;
    }
    setProfile({
      ...profile,
      homeLocation: {
        lat: axis === "lat" ? (raw === "" ? Number.NaN : Number(raw)) : other,
        lon: axis === "lon" ? (raw === "" ? Number.NaN : Number(raw)) : other,
      },
    });
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setMessage(null);
    if (!complete) {
      setMessage({ kind: "error", text: "Ergänze Gewicht, Level und mindestens einen Kite." });
      return;
    }
    if (profile.homeLocation && (
      !Number.isFinite(profile.homeLocation.lat) || !Number.isFinite(profile.homeLocation.lon)
    )) {
      setMessage({ kind: "error", text: "Prüfe die Koordinaten deines Heimatorts." });
      return;
    }

    setSaving(true);
    try {
      const savedProfile = await putRiderProfile({
        weightKg: profile.weightKg,
        homeLocation: profile.homeLocation,
        maxTravelKm: profile.maxTravelKm,
        travelMode: profile.travelMode,
        availability: profile.availability,
        minWaterTempC: profile.minWaterTempC,
        excludedBottoms: profile.excludedBottoms,
      });
      const savedSport = await putRiderSportProfile("kitesurf", {
        level: sport.level,
        styleWeights: sport.styleWeights,
        preferredWaterCharacter: sport.preferredWaterCharacter,
      });

      const keptIds = new Set(gear.flatMap((item) => item.id ? [item.id] : []));
      await Promise.all(storedGear.filter((item) => !keptIds.has(item.id)).map((item) => deleteGearItem(item.id)));
      await Promise.all(gear.map((item) => {
        const input: GearItemInput = {
          sport: "kitesurf", kind: item.kind, size: item.size,
          boardType: item.boardType, active: item.active, sortOrder: item.sortOrder,
        };
        return item.id ? updateGearItem(item.id, input) : createGearItem(input);
      }));
      const reloaded = await getGear("kitesurf");
      setProfile(savedProfile);
      setSport(savedSport);
      setStoredGear(reloaded);
      setGear(drafts(reloaded));
      setMessage({ kind: "ok", text: "Dein Setup wurde gespeichert." });
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof AccountError ? error.message : t("setup.saveFailed"),
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <AccountPage title={t("setup.pageTitle")}><p role="status" className="text-ui text-muted">{t("setup.loading")}</p></AccountPage>;
  }

  return (
    <AccountPage
      title={t("setup.pageTitle")}
      intro={t("setup.intro")}
    >
      <form onSubmit={save} className="space-y-10" noValidate>
        <Section title={t("setup.basics.title")} intro={t("setup.basics.intro")}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("setup.basics.weight")} hint={t("setup.required")}>
              <div className="relative">
                <Input
                  type="number" min="30" max="160" step="0.5" inputMode="decimal"
                  value={profile.weightKg ?? ""} disabled={saving}
                  onChange={(event) => setProfile({ ...profile, weightKg: event.target.value === "" ? null : Number(event.target.value) })}
                  className="pr-12"
                />
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ui text-muted">{t("setup.unitKg")}</span>
              </div>
            </Field>
            <Field label={t("setup.basics.level")} hint={t("setup.required")}>
              <Select
                value={sport.level ?? ""} disabled={saving}
                onChange={(event) => setSport({ ...sport, level: (event.target.value || null) as RiderLevel | null })}
              >
                <option value="">{t("setup.choose")}</option>
                {LEVELS.map((level) => <option key={level.value} value={level.value}>{t(level.key)}</option>)}
              </Select>
            </Field>
          </div>
        </Section>

        <Section title={t("setup.gear.title")} intro={t("setup.gear.intro")}>
          <QuiverEditor items={gear} onChange={setGear} disabled={saving} />
        </Section>

        <Section title={t("setup.style.title")} intro={t("setup.style.intro")}>
          <div className="space-y-4">
            {STYLES.map(([style, labelKey]) => {
              const value = sport.styleWeights[style] ?? 0;
              return (
                <label key={style} className="grid min-h-11 grid-cols-[minmax(0,1fr)_8rem_1.5rem] items-center gap-3 text-ui text-ink">
                  <span>{t(labelKey)}</span>
                  <input
                    aria-label={t("setup.style.weighting", { style: t(labelKey) })}
                    type="range" min="0" max="3" step="1" value={value} disabled={saving}
                    onChange={(event) => setSport({
                      ...sport,
                      styleWeights: { ...sport.styleWeights, [style]: Number(event.target.value) },
                    })}
                    className="h-11 accent-ink"
                  />
                  <span className="text-right font-semibold tabular-nums">{value}</span>
                </label>
              );
            })}
          </div>
        </Section>

        <Section title={t("setup.water.title")} intro={t("setup.water.intro")}>
          <div className="flex flex-wrap gap-2">
            {WATER.map(([kind, labelKey]) => {
              const checked = sport.preferredWaterCharacter.includes(kind);
              return (
                <label key={kind} className={`inline-flex min-h-11 cursor-pointer items-center rounded-card border px-4 text-ui font-medium transition-colors ${checked ? "border-ink bg-ink text-surface" : "border-line bg-surface text-ink hover:bg-band"}`}>
                  <input
                    type="checkbox" className="sr-only" checked={checked} disabled={saving}
                    onChange={() => setSport({
                      ...sport,
                      preferredWaterCharacter: checked
                        ? sport.preferredWaterCharacter.filter((item) => item !== kind)
                        : [...sport.preferredWaterCharacter, kind],
                    })}
                  />
                  {t(labelKey)}
                </label>
              );
            })}
          </div>
        </Section>

        <Section title={t("setup.travel.title")} intro={t("setup.travel.intro")}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("setup.travel.lat")} hint={t("setup.travel.home")}>
              <Input
                type="number" min="-90" max="90" step="any" inputMode="decimal"
                value={Number.isFinite(profile.homeLocation?.lat) ? profile.homeLocation?.lat : ""} disabled={saving}
                onChange={(event) => setCoordinate("lat", event.target.value)}
              />
            </Field>
            <Field label={t("setup.travel.lon")} hint={t("setup.travel.home")}>
              <Input
                type="number" min="-180" max="180" step="any" inputMode="decimal"
                value={Number.isFinite(profile.homeLocation?.lon) ? profile.homeLocation?.lon : ""} disabled={saving}
                onChange={(event) => setCoordinate("lon", event.target.value)}
              />
            </Field>
            <Field label={t("setup.travel.mode")}>
              <Select
                value={profile.travelMode} disabled={saving}
                onChange={(event) => setProfile({ ...profile, travelMode: event.target.value as TravelMode })}
              >
                <option value="day_trip">{t("setup.travel.dayTrip")}</option>
                <option value="weekend">{t("setup.travel.weekend")}</option>
                <option value="trip">{t("setup.travel.trip")}</option>
                <option value="camper">{t("setup.travel.camper")}</option>
              </Select>
            </Field>
            <Field label={t("setup.travel.maxDistance")} hint={t("setup.optional")}>
              <div className="relative">
                <Input
                  type="number" min="0" max="20000" step="10" inputMode="decimal"
                  value={profile.maxTravelKm ?? ""} disabled={saving}
                  onChange={(event) => setProfile({ ...profile, maxTravelKm: event.target.value === "" ? null : Number(event.target.value) })}
                  className="pr-12"
                />
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ui text-muted">{t("setup.unitKm")}</span>
              </div>
            </Field>
          </div>
        </Section>

        {message && (
          <p role={message.kind === "error" ? "alert" : "status"} className={`text-ui font-medium ${message.kind === "error" ? "text-danger" : "text-success"}`}>
            {message.key ? t(message.key) : message.text}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-4 border-t border-line pt-6">
          <Button type="submit" disabled={saving}>{saving ? t("setup.submitting") : t("setup.submit")}</Button>
          {!complete && <p className="text-caption text-muted">{t("setup.incomplete")}</p>}
        </div>
      </form>
    </AccountPage>
  );
}
