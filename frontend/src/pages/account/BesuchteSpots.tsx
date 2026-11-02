import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  getVisitsState, markVisited, refreshVisits, unmarkVisited, VISITS_EVENT,
  type CollectionState, type VisitedSpot,
} from "../../lib/account";
import { PinIcon, SearchIcon, TrashIcon } from "../../lib/icons";
import { spotPath } from "../../lib/spotRoutes";
import { AccountPage } from "./AccountLayout";

export default function BesuchteSpots() {
  const { t, i18n } = useTranslation();
  const [state, setState] = useState<CollectionState<VisitedSpot>>(getVisitsState);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<VisitedSpot["outcome"]>(null);
  const [notes, setNotes] = useState("");

  useEffect(() => {
    const sync = () => setState(getVisitsState());
    window.addEventListener(VISITS_EVENT, sync);
    void refreshVisits();
    return () => window.removeEventListener(VISITS_EVENT, sync);
  }, []);

  const remove = async (spotId: string) => {
    setBusyId(spotId); setError(null);
    try { await unmarkVisited(spotId); }
    catch { setError(t("visits.actionFailed")); }
    finally { setBusyId(null); }
  };

  const edit = (visit: VisitedSpot) => {
    setEditing(visit.spotId); setOutcome(visit.outcome); setNotes(visit.notes ?? "");
  };

  const saveFeedback = async (visit: VisitedSpot) => {
    setBusyId(visit.spotId); setError(null);
    try {
      await markVisited(visit.spotId, { visitedAt: visit.visitedAt, outcome, notes: notes.trim() || null });
      setEditing(null);
    } catch { setError(t("visits.actionFailed")); }
    finally { setBusyId(null); }
  };

  if (state.status === "loading" && state.items.length === 0) return <AccountPage title={t("visits.title")}><p role="status" className="py-12 text-center text-ui text-muted">{t("common.loading")}</p></AccountPage>;
  if (state.status === "error") return <AccountPage title={t("visits.title")}><div role="alert" className="rounded-card border border-line p-6 text-ui"><p>{state.error || t("visits.loadFailed")}</p><button type="button" onClick={() => void refreshVisits()} className="mt-3 min-h-11 font-semibold underline">{t("common.retry")}</button></div></AccountPage>;

  return (
    <AccountPage title={t("visits.title")} intro={state.items.length > 0 ? `${state.items.length}` : undefined}>
      {error && <p role="alert" className="mb-3 text-ui text-danger">{error}</p>}
      {state.items.length === 0 ? (
        <div className="rounded-card border border-dashed border-line bg-surface px-6 py-14 text-center">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-card bg-band text-ink"><PinIcon className="text-title" /></span>
          <h2 className="mt-4 text-body font-semibold text-ink">{t("visits.emptyTitle")}</h2>
          <p className="mx-auto mt-1 max-w-[38ch] text-ui text-muted">{t("visits.emptyBody")}</p>
          <Link to="/search" className="mt-5 inline-flex min-h-11 items-center gap-2 px-4 text-ui font-semibold text-ink hover:underline"><SearchIcon className="text-body" />{t("visits.discover")}</Link>
        </div>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {state.items.map((visit) => (
            <li key={visit.id} className="rounded-card border border-line bg-surface p-4">
              <div className="flex items-center gap-3"><Link to={spotPath({ id: visit.spotId, name: visit.name })} className="min-w-0 flex-1">
                <span className="block truncate text-body font-semibold text-ink">{visit.name}</span>
                <span className="block truncate text-caption text-muted">{visit.region ? `${visit.region} · ` : ""}{t("visits.visitedOn", { date: new Intl.DateTimeFormat(i18n.resolvedLanguage === "en" ? "en" : "de").format(new Date(`${visit.visitedAt}T12:00:00`)) })}</span>
              </Link><button type="button" onClick={() => edit(visit)} className="min-h-11 px-2 text-caption font-semibold text-ink underline">{t("visits.feedback")}</button>
              <button type="button" disabled={busyId === visit.spotId} onClick={() => void remove(visit.spotId)} aria-label={t("visits.remove")} className="grid h-11 w-11 shrink-0 place-items-center rounded-card text-danger hover:bg-band disabled:opacity-50"><TrashIcon /></button>
              </div>{editing === visit.spotId && <div className="mt-3 grid gap-3 border-t border-line pt-3"><label><span className="text-caption font-semibold text-muted">{t("visits.outcome")}</span><select value={outcome ?? ""} onChange={(event) => setOutcome((event.target.value || null) as VisitedSpot["outcome"])} className="mt-1 min-h-11 w-full rounded-card border border-line bg-page px-3 text-ui"><option value="">{t("visits.noOutcome")}</option><option value="worthwhile">{t("visits.worthwhile")}</option><option value="neutral">{t("visits.neutral")}</option><option value="not_worthwhile">{t("visits.notWorthwhile")}</option></select></label><label><span className="text-caption font-semibold text-muted">{t("visits.notes")}</span><textarea maxLength={2000} value={notes} onChange={(event) => setNotes(event.target.value)} className="mt-1 min-h-24 w-full rounded-card border border-line bg-page p-3 text-ui" /></label><div className="flex gap-2"><button type="button" disabled={busyId === visit.spotId} onClick={() => void saveFeedback(visit)} className="min-h-11 rounded-card bg-ink px-4 text-ui font-semibold text-surface">{t("visits.save")}</button><button type="button" onClick={() => setEditing(null)} className="min-h-11 px-3 text-ui font-semibold text-ink">{t("common.cancel")}</button></div></div>}
            </li>
          ))}
        </ul>
      )}
    </AccountPage>
  );
}
