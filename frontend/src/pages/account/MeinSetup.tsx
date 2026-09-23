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

const LEVELS: { value: RiderLevel; label: string }[] = [
  { value: "beginner", label: "Einsteiger" },
  { value: "advanced", label: "Fortgeschritten" },
  { value: "expert", label: "Experte" },
  { value: "competition", label: "Competition" },
];

const STYLES = [
  ["freeride", "Freeride"], ["freestyle", "Freestyle"],
  ["big_air", "Big Air"], ["wave_riding", "Wave Riding"], ["wavekite", "Wavekite"],
] as const;

const WATER = [
  ["flach", "Flachwasser"], ["chop", "Chop"], ["welle_klein", "Kleine Welle"],
  ["welle_gross", "Große Welle"], ["tiefes_wasser", "Tiefes Wasser"],
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
      <h2 className="text-sz-18 font-semibold text-ink">{title}</h2>
      {intro && <p className="mt-1 max-w-[65ch] text-ui text-muted">{intro}</p>}
      <div className="mt-5">{children}</div>
    </section>
  );
}

export default function MeinSetup() {
  const [profile, setProfile] = useState<RiderProfile>(EMPTY_PROFILE);
  const [sport, setSport] = useState<RiderSportProfile>(EMPTY_SPORT);
  const [gear, setGear] = useState<QuiverDraft[]>([]);
  const [storedGear, setStoredGear] = useState<GearItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

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
      .catch((error) => active && setMessage({
        kind: "error",
        text: error instanceof Error ? error.message : "Dein Setup konnte nicht geladen werden.",
      }))
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
        text: error instanceof AccountError ? error.message : "Speichern fehlgeschlagen. Bitte versuche es erneut.",
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <AccountPage title="Mein Setup"><p role="status" className="text-ui text-muted">Setup wird geladen …</p></AccountPage>;
  }

  return (
    <AccountPage
      title="Mein Setup"
      intro="Halte deine Kite-Ausrüstung und deine Vorlieben an einem Ort aktuell."
    >
      <form onSubmit={save} className="space-y-10" noValidate>
        <Section title="Grundangaben" intro="Gewicht, Level und ein Kite reichen für den Start.">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Gewicht" hint="Pflichtfeld">
              <div className="relative">
                <Input
                  type="number" min="30" max="160" step="0.5" inputMode="decimal"
                  value={profile.weightKg ?? ""} disabled={saving}
                  onChange={(event) => setProfile({ ...profile, weightKg: event.target.value === "" ? null : Number(event.target.value) })}
                  className="pr-12"
                />
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-label text-muted">kg</span>
              </div>
            </Field>
            <Field label="Kite-Level" hint="Pflichtfeld">
              <Select
                value={sport.level ?? ""} disabled={saving}
                onChange={(event) => setSport({ ...sport, level: (event.target.value || null) as RiderLevel | null })}
              >
                <option value="">Bitte wählen</option>
                {LEVELS.map((level) => <option key={level.value} value={level.value}>{level.label}</option>)}
              </Select>
            </Field>
          </div>
        </Section>

        <Section title="Deine Ausrüstung" intro="Trage deine aktiven Kites und den Board-Typ ein.">
          <QuiverEditor items={gear} onChange={setGear} disabled={saving} />
        </Section>

        <Section title="Fahrstil" intro="Stelle für jeden Stil ein, wie wichtig er dir ist: 0 steht für unwichtig, 3 für sehr wichtig.">
          <div className="space-y-4">
            {STYLES.map(([key, label]) => {
              const value = sport.styleWeights[key] ?? 0;
              return (
                <label key={key} className="grid min-h-11 grid-cols-[minmax(0,1fr)_8rem_1.5rem] items-center gap-3 text-ui text-ink">
                  <span>{label}</span>
                  <input
                    aria-label={`${label} Gewichtung`}
                    type="range" min="0" max="3" step="1" value={value} disabled={saving}
                    onChange={(event) => setSport({
                      ...sport,
                      styleWeights: { ...sport.styleWeights, [key]: Number(event.target.value) },
                    })}
                    className="h-11 accent-[var(--sw-teal)]"
                  />
                  <span className="text-right font-semibold tabular-nums">{value}</span>
                </label>
              );
            })}
          </div>
        </Section>

        <Section title="Wasser" intro="Optional: Wähle die Bedingungen, die du besonders gern fährst.">
          <div className="flex flex-wrap gap-2">
            {WATER.map(([key, label]) => {
              const checked = sport.preferredWaterCharacter.includes(key);
              return (
                <label key={key} className={`inline-flex min-h-11 cursor-pointer items-center rounded-full border px-4 text-label font-medium transition-colors ${checked ? "border-ink bg-ink text-surface" : "border-line bg-surface text-ink hover:bg-band"}`}>
                  <input
                    type="checkbox" className="sr-only" checked={checked} disabled={saving}
                    onChange={() => setSport({
                      ...sport,
                      preferredWaterCharacter: checked
                        ? sport.preferredWaterCharacter.filter((item) => item !== key)
                        : [...sport.preferredWaterCharacter, key],
                    })}
                  />
                  {label}
                </label>
              );
            })}
          </div>
        </Section>

        <Section title="Unterwegs" intro="Heimatort und Reisemodus sind optional und jederzeit änderbar.">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Breitengrad" hint="Heimatort">
              <Input
                type="number" min="-90" max="90" step="any" inputMode="decimal"
                value={Number.isFinite(profile.homeLocation?.lat) ? profile.homeLocation?.lat : ""} disabled={saving}
                onChange={(event) => setCoordinate("lat", event.target.value)}
              />
            </Field>
            <Field label="Längengrad" hint="Heimatort">
              <Input
                type="number" min="-180" max="180" step="any" inputMode="decimal"
                value={Number.isFinite(profile.homeLocation?.lon) ? profile.homeLocation?.lon : ""} disabled={saving}
                onChange={(event) => setCoordinate("lon", event.target.value)}
              />
            </Field>
            <Field label="Reisemodus">
              <Select
                value={profile.travelMode} disabled={saving}
                onChange={(event) => setProfile({ ...profile, travelMode: event.target.value as TravelMode })}
              >
                <option value="day_trip">Tagesausflug</option>
                <option value="weekend">Wochenende</option>
                <option value="trip">Reise</option>
                <option value="camper">Camper</option>
              </Select>
            </Field>
            <Field label="Maximale Entfernung" hint="Optional">
              <div className="relative">
                <Input
                  type="number" min="0" max="20000" step="10" inputMode="decimal"
                  value={profile.maxTravelKm ?? ""} disabled={saving}
                  onChange={(event) => setProfile({ ...profile, maxTravelKm: event.target.value === "" ? null : Number(event.target.value) })}
                  className="pr-12"
                />
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-label text-muted">km</span>
              </div>
            </Field>
          </div>
        </Section>

        {message && (
          <p role={message.kind === "error" ? "alert" : "status"} className={`text-label font-medium ${message.kind === "error" ? "text-danger" : "text-success"}`}>
            {message.text}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-4 border-t border-line pt-6">
          <Button type="submit" disabled={saving}>{saving ? "Speichert …" : "Setup speichern"}</Button>
          {!complete && <p className="text-caption text-muted">Noch offen: Gewicht, Level oder Kite.</p>}
        </div>
      </form>
    </AccountPage>
  );
}
