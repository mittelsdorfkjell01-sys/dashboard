import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  copyTrip, createTrip, deleteTrip, getTrips, searchTripSpots, setTripSharing, updateTrip,
  type TripChecklistItem, type TripDay, type TripPlan, type TripStop,
} from "../../lib/account";
import { CalendarIcon, ChevronDownIcon, PlusIcon, SearchIcon, TrashIcon } from "../../lib/icons";
import { AccountPage } from "./AccountLayout";

type DraftStop = Pick<TripStop, "spotId" | "spotName" | "plannedDate" | "notes" | "role">;

const dateString = (offset = 0) => {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
};

const daysBetween = (start: string, end: string): TripDay[] => {
  if (!start || !end || end < start) return [];
  const rows: TripDay[] = [];
  const cursor = new Date(`${start}T12:00:00`);
  const last = new Date(`${end}T12:00:00`);
  while (cursor <= last && rows.length < 31) {
    rows.push({ date: dateStringFromDate(cursor), notes: null, accommodation: null, travel: null });
    cursor.setDate(cursor.getDate() + 1);
  }
  return rows;
};

const dateStringFromDate = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

export default function Reiseplaner() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const importedSpot = useRef(false);
  const [trips, setTrips] = useState<TripPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<TripPlan | "new" | null>(null);
  const [title, setTitle] = useState("");
  const [startDate, setStartDate] = useState(dateString());
  const [endDate, setEndDate] = useState(dateString(2));
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState<TripPlan["status"]>("draft");
  const [stops, setStops] = useState<DraftStop[]>([]);
  const [days, setDays] = useState<TripDay[]>(daysBetween(dateString(), dateString(2)));
  const [checklist, setChecklist] = useState<TripChecklistItem[]>([]);
  const [spotQuery, setSpotQuery] = useState("");
  const [spotResults, setSpotResults] = useState<{ id: string; name: string }[]>([]);
  const [searched, setSearched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [sharingId, setSharingId] = useState<string | null>(null);

  const reload = async () => {
    setLoading(true);
    try { setTrips(await getTrips()); setError(null); }
    catch { setError(t("trips.loadFailed")); }
    finally { setLoading(false); }
  };
  useEffect(() => { void reload(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const open = (trip: TripPlan | "new") => {
    setEditing(trip);
    setTitle(trip === "new" ? "" : trip.title);
    setStartDate(trip === "new" ? dateString() : trip.startDate);
    setEndDate(trip === "new" ? dateString(2) : trip.endDate);
    setNotes(trip === "new" ? "" : trip.notes ?? "");
    setStatus(trip === "new" ? "draft" : trip.status);
    setStops(trip === "new" ? [] : trip.stops.map(({ spotId, spotName, plannedDate, notes: stopNotes, role }) => ({ spotId, spotName, plannedDate, notes: stopNotes, role })));
    setDays(trip === "new" ? daysBetween(dateString(), dateString(2)) : trip.days);
    setChecklist(trip === "new" ? [] : trip.checklist);
    setSpotQuery(""); setSpotResults([]); setSearched(false); setError(null);
  };

  useEffect(() => {
    const spotId = searchParams.get("spotId");
    const spotName = searchParams.get("spotName");
    if (importedSpot.current || !spotId || !spotName) return;
    importedSpot.current = true;
    open("new");
    setStops([{ spotId, spotName, plannedDate: dateString(), notes: null, role: "main" }]);
    setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (!editing) return;
    setDays((current) => daysBetween(startDate, endDate).map((day) => current.find((item) => item.date === day.date) ?? day));
  }, [startDate, endDate, editing]);

  const search = async () => {
    if (spotQuery.trim().length < 2) return;
    try { setSpotResults(await searchTripSpots(spotQuery.trim())); setSearched(true); }
    catch { setError(t("trips.loadFailed")); }
  };

  const move = (index: number, delta: number) => {
    const next = [...stops];
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    setStops(next);
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (endDate < startDate) { setError(t("trips.dateError")); return; }
    setSaving(true); setError(null);
    const payload = {
      title: title.trim(), startDate, endDate, notes: notes.trim() || null, status, checklist, days,
      stops: stops.filter((stop) => stop.spotId && stop.plannedDate).map((stop) => ({ spotId: stop.spotId!, plannedDate: stop.plannedDate!, notes: stop.notes, role: stop.role })),
    };
    try {
      if (editing === "new") await createTrip(payload);
      else if (editing) await updateTrip(editing.id, payload);
      setEditing(null); await reload();
    } catch { setError(t("trips.saveFailed")); }
    finally { setSaving(false); }
  };

  const copy = async (id: string) => {
    try { await copyTrip(id); await reload(); }
    catch { setError(t("trips.copyFailed")); }
  };

  const toggleShare = async (trip: TripPlan) => {
    setSharingId(trip.id);
    try {
      const updated = await setTripSharing(trip.id, !trip.shareUrl);
      if (updated.shareUrl) await navigator.clipboard.writeText(new URL(updated.shareUrl, window.location.origin).toString());
      await reload();
    } catch { setError(t("trips.shareFailed")); }
    finally { setSharingId(null); }
  };

  const removeTrip = async (id: string) => {
    if (deleteConfirm !== id) { setDeleteConfirm(id); return; }
    try { await deleteTrip(id); setDeleteConfirm(null); await reload(); }
    catch { setError(t("trips.deleteFailed")); }
  };

  if (editing) return (
    <AccountPage title={editing === "new" ? t("trips.new") : editing.title} intro={t("trips.manualNote")}>
      {error && <p role="alert" className="mb-4 rounded-card border border-danger/30 bg-danger/5 p-3 text-ui text-danger">{error}</p>}
      <form onSubmit={save} className="space-y-8">
        <section className="grid gap-4 rounded-card border border-line bg-surface p-4 sm:grid-cols-2 sm:p-6">
          <label className="sm:col-span-2"><span className="text-ui font-semibold text-ink">{t("trips.name")}</span><input required maxLength={160} value={title} onChange={(e) => setTitle(e.target.value)} className="mt-2 min-h-11 w-full rounded-card border border-line bg-page px-3 text-ui text-ink" /></label>
          <label><span className="text-ui font-semibold text-ink">{t("trips.start")}</span><input required type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="mt-2 min-h-11 w-full rounded-card border border-line bg-page px-3 text-ui text-ink" /></label>
          <label><span className="text-ui font-semibold text-ink">{t("trips.end")}</span><input required type="date" min={startDate} value={endDate} onChange={(e) => setEndDate(e.target.value)} className="mt-2 min-h-11 w-full rounded-card border border-line bg-page px-3 text-ui text-ink" /></label>
          <label><span className="text-ui font-semibold text-ink">{t("trips.status")}</span><select value={status} onChange={(e) => setStatus(e.target.value as TripPlan["status"])} className="mt-2 min-h-11 w-full rounded-card border border-line bg-page px-3 text-ui text-ink">{(["draft", "planned", "completed", "cancelled"] as const).map((value) => <option key={value} value={value}>{t(`trips.${value}`)}</option>)}</select></label>
          <label className="sm:col-span-2"><span className="text-ui font-semibold text-ink">{t("trips.notes")}</span><textarea maxLength={5000} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder={t("trips.notesPlaceholder")} className="mt-2 min-h-28 w-full resize-y rounded-card border border-line bg-page p-3 text-ui text-ink" /></label>
        </section>

        <section><h2 className="text-title font-semibold text-ink">{t("trips.days")}</h2><p className="mt-1 text-ui text-muted">{t("trips.daysHint")}</p><div className="mt-3 space-y-3">{days.map((day) => <div key={day.date} className="grid gap-3 rounded-card border border-line bg-surface p-4 sm:grid-cols-3"><h3 className="sm:col-span-3 text-body font-semibold text-ink">{new Intl.DateTimeFormat(undefined, { weekday: "long", dateStyle: "medium" }).format(new Date(`${day.date}T12:00:00`))}</h3>{(["notes", "accommodation", "travel"] as const).map((field) => <label key={field}><span className="text-caption font-semibold text-muted">{t(`trips.day.${field}`)}</span><input maxLength={field === "notes" ? 2000 : 1000} value={day[field] ?? ""} onChange={(event) => setDays(days.map((item) => item.date === day.date ? { ...item, [field]: event.target.value || null } : item))} className="mt-1 min-h-11 w-full rounded-card border border-line bg-page px-3 text-ui" /></label>)}</div>)}</div></section>

        <section><h2 className="text-title font-semibold text-ink">{t("trips.spots")}</h2>
          <div className="mt-3 flex gap-2"><label className="relative min-w-0 flex-1"><span className="sr-only">{t("trips.spotSearch")}</span><SearchIcon className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-body text-muted" /><input value={spotQuery} onChange={(e) => setSpotQuery(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void search(); } }} placeholder={t("trips.spotSearch")} className="min-h-11 w-full rounded-card border border-line bg-surface pl-10 pr-3 text-ui text-ink" /></label><button type="button" onClick={() => void search()} className="min-h-11 rounded-card bg-ink px-4 text-ui font-semibold text-surface">{t("trips.search")}</button></div>
          {searched && spotResults.length === 0 && <p className="mt-2 text-ui text-muted">{t("trips.noSearch")}</p>}
          {spotResults.length > 0 && <ul className="mt-2 divide-y divide-line rounded-card border border-line bg-surface">{spotResults.map((spot) => <li key={spot.id} className="flex min-h-12 items-center justify-between gap-3 px-3"><span className="text-ui font-medium text-ink">{spot.name}</span><button type="button" onClick={() => setStops([...stops, { spotId: spot.id, spotName: spot.name, plannedDate: days[0]?.date ?? null, notes: null, role: "alternative" }])} className="min-h-11 px-2 text-ui font-semibold text-ink">{t("trips.add")}</button></li>)}</ul>}
          <ol className="mt-4 space-y-3">{stops.map((stop, index) => <li key={`${stop.spotId}-${index}`} className="rounded-card border border-line bg-surface p-4"><div className="flex items-center gap-2"><span className="min-w-0 flex-1 truncate text-body font-semibold text-ink">{index + 1}. {stop.spotName}</span><button type="button" aria-label={t("trips.moveUp")} disabled={index === 0} onClick={() => move(index, -1)} className="grid h-11 w-11 place-items-center disabled:opacity-30"><ChevronDownIcon className="rotate-180" /></button><button type="button" aria-label={t("trips.moveDown")} disabled={index === stops.length - 1} onClick={() => move(index, 1)} className="grid h-11 w-11 place-items-center disabled:opacity-30"><ChevronDownIcon /></button><button type="button" aria-label={t("trips.remove")} onClick={() => setStops(stops.filter((_, itemIndex) => itemIndex !== index))} className="grid h-11 w-11 place-items-center text-danger"><TrashIcon /></button></div><div className="mt-3 grid gap-3 sm:grid-cols-3"><label><span className="text-caption font-semibold text-muted">{t("trips.plannedDate")}</span><input required type="date" min={startDate} max={endDate} value={stop.plannedDate ?? ""} onChange={(e) => setStops(stops.map((item, itemIndex) => itemIndex === index ? { ...item, plannedDate: e.target.value || null } : item))} className="mt-1 min-h-11 w-full rounded-card border border-line bg-page px-3 text-ui" /></label><label><span className="text-caption font-semibold text-muted">{t("trips.role")}</span><select value={stop.role} onChange={(e) => setStops(stops.map((item, itemIndex) => itemIndex === index ? { ...item, role: e.target.value as DraftStop["role"] } : item))} className="mt-1 min-h-11 w-full rounded-card border border-line bg-page px-3 text-ui"><option value="main">{t("trips.mainSpot")}</option><option value="alternative">{t("trips.alternativeSpot")}</option></select></label><label><span className="text-caption font-semibold text-muted">{t("trips.stopNotes")}</span><input maxLength={1000} value={stop.notes ?? ""} onChange={(e) => setStops(stops.map((item, itemIndex) => itemIndex === index ? { ...item, notes: e.target.value || null } : item))} className="mt-1 min-h-11 w-full rounded-card border border-line bg-page px-3 text-ui" /></label></div></li>)}</ol>
        </section>

        <section><h2 className="text-title font-semibold text-ink">{t("trips.checklist")}</h2><div className="mt-3 space-y-2">{checklist.map((item, index) => <div key={index} className="flex items-center gap-2"><input type="checkbox" checked={item.done} onChange={(e) => setChecklist(checklist.map((entry, itemIndex) => itemIndex === index ? { ...entry, done: e.target.checked } : entry))} className="h-5 w-5" /><input value={item.text} maxLength={160} onChange={(e) => setChecklist(checklist.map((entry, itemIndex) => itemIndex === index ? { ...entry, text: e.target.value } : entry))} className="min-h-11 min-w-0 flex-1 rounded-card border border-line bg-surface px-3 text-ui" /><button type="button" aria-label={t("trips.remove")} onClick={() => setChecklist(checklist.filter((_, itemIndex) => itemIndex !== index))} className="grid h-11 w-11 place-items-center text-danger"><TrashIcon /></button></div>)}</div><button type="button" onClick={() => setChecklist([...checklist, { text: "", done: false }])} className="mt-3 inline-flex min-h-11 items-center gap-2 font-semibold text-ink"><PlusIcon />{t("trips.addChecklist")}</button></section>
        <div className="flex flex-wrap gap-3 border-t border-line pt-5"><button type="submit" disabled={saving || !title.trim() || checklist.some((item) => !item.text.trim())} className="min-h-11 rounded-card bg-ink px-5 text-ui font-semibold text-surface disabled:opacity-50">{saving ? t("trips.saving") : t("trips.save")}</button><button type="button" onClick={() => setEditing(null)} className="min-h-11 rounded-card border border-line px-5 text-ui font-semibold text-ink">{t("trips.cancel")}</button></div>
      </form>
    </AccountPage>
  );

  return <AccountPage title={t("trips.title")} intro={t("trips.intro")} action={<button type="button" onClick={() => open("new")} className="inline-flex min-h-11 items-center gap-2 rounded-card bg-ink px-4 text-ui font-semibold text-surface"><PlusIcon />{t("trips.new")}</button>}>
    {error && <p role="alert" className="mb-4 rounded-card border border-danger/30 p-3 text-ui text-danger">{error}</p>}
    {loading ? <p role="status" className="py-12 text-center text-ui text-muted">{t("common.loading")}</p> : trips.length === 0 ? <div className="rounded-card border border-dashed border-line bg-surface px-6 py-14 text-center"><CalendarIcon className="mx-auto text-heading text-ink" /><h2 className="mt-4 text-body font-semibold text-ink">{t("trips.emptyTitle")}</h2><p className="mx-auto mt-1 max-w-[38ch] text-ui text-muted">{t("trips.emptyBody")}</p></div> : <ul className="space-y-3">{trips.map((trip) => <li key={trip.id} className="rounded-card border border-line bg-surface p-4 sm:p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-body font-semibold text-ink">{trip.title}</h2><p className="mt-1 text-ui text-muted">{trip.startDate} – {trip.endDate} · {trip.stops.length} Spots · {t(`trips.${trip.status}`)}</p></div><div className="flex flex-wrap gap-2"><button type="button" onClick={() => open(trip)} className="min-h-11 rounded-card border border-line px-3 text-ui font-semibold text-ink">{t("trips.edit")}</button><button type="button" onClick={() => void copy(trip.id)} className="min-h-11 rounded-card border border-line px-3 text-ui font-semibold text-ink">{t("trips.copy")}</button><button type="button" disabled={sharingId === trip.id} onClick={() => void toggleShare(trip)} className="min-h-11 rounded-card border border-line px-3 text-ui font-semibold text-ink">{trip.shareUrl ? t("trips.revokeShare") : t("trips.share")}</button><button type="button" onClick={() => void removeTrip(trip.id)} className="min-h-11 rounded-card px-3 text-ui font-semibold text-danger">{deleteConfirm === trip.id ? t("trips.confirmDelete") : t("trips.delete")}</button></div></div>{trip.shareUrl && <p className="mt-2 text-caption text-muted">{t("trips.sharedCopied")}</p>}{trip.stops.some((stop) => stop.contentChanged || !stop.spotAvailable) && <p className="mt-2 text-ui text-warning">{t("trips.contentChanged")}</p>}{trip.stops.length > 0 && <p className="mt-3 text-ui text-ink-soft">{trip.stops.map((stop) => stop.spotName).join(" → ")}</p>}</li>)}</ul>}
  </AccountPage>;
}
