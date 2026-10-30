import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import LandingHeader from "../components/LandingHeader";
import { getSharedTrip, type TripPlan } from "../lib/account";
import { spotPath } from "../lib/spotRoutes";

export default function SharedTrip() {
  const { token = "" } = useParams();
  const { t } = useTranslation();
  const [trip, setTrip] = useState<TripPlan | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    void getSharedTrip(token)
      .then((value) => { if (active) setTrip(value); })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [token]);

  return <>
    <LandingHeader />
    <main className="mx-auto min-h-[70vh] w-full max-w-content px-4 py-8 sm:px-6 sm:py-12">
      {!trip && !failed && <p role="status" className="py-16 text-center text-ui text-muted">{t("common.loading")}</p>}
      {failed && <div role="alert" className="rounded-card border border-line bg-surface p-8 text-center"><h1 className="text-title font-semibold text-ink">{t("trips.sharedNotFound")}</h1><p className="mt-2 text-ui text-muted">{t("trips.sharedNotFoundBody")}</p></div>}
      {trip && <article>
        <p className="text-caption font-semibold uppercase tracking-wide text-muted">{t("trips.sharedLabel")}</p>
        <h1 className="mt-2 text-heading font-semibold text-ink">{trip.title}</h1>
        <p className="mt-2 text-body text-muted">{trip.startDate} – {trip.endDate}</p>
        <p className="mt-4 max-w-measure text-ui text-muted">{t("trips.sharedManualNote")}</p>
        {trip.notes && <p className="mt-6 max-w-measure whitespace-pre-wrap text-ui text-ink-soft">{trip.notes}</p>}
        <div className="mt-8 space-y-4">
          {trip.days.map((day) => {
            const stops = trip.stops.filter((stop) => stop.plannedDate === day.date);
            return <section key={day.date} className="rounded-card border border-line bg-surface p-4 sm:p-6">
              <h2 className="text-title font-semibold text-ink">{new Intl.DateTimeFormat(undefined, { weekday: "long", dateStyle: "medium" }).format(new Date(`${day.date}T12:00:00`))}</h2>
              {(day.notes || day.accommodation || day.travel) && <dl className="mt-3 grid gap-3 text-ui sm:grid-cols-3">{day.notes && <div><dt className="font-semibold text-muted">{t("trips.day.notes")}</dt><dd>{day.notes}</dd></div>}{day.accommodation && <div><dt className="font-semibold text-muted">{t("trips.day.accommodation")}</dt><dd>{day.accommodation}</dd></div>}{day.travel && <div><dt className="font-semibold text-muted">{t("trips.day.travel")}</dt><dd>{day.travel}</dd></div>}</dl>}
              {stops.length === 0 ? <p className="mt-3 text-ui text-muted">{t("trips.noDaySpots")}</p> : <ol className="mt-4 space-y-2">{stops.map((stop) => <li key={stop.id ?? `${stop.spotId}-${stop.position}`} className="flex flex-wrap items-center justify-between gap-2 rounded-card bg-band p-3"><div><span className="text-caption font-semibold text-muted">{stop.role === "main" ? t("trips.mainSpot") : t("trips.alternativeSpot")}</span><p className="font-semibold text-ink">{stop.spotName}</p>{stop.notes && <p className="text-caption text-muted">{stop.notes}</p>}</div>{stop.spotId && stop.spotAvailable && <Link to={spotPath({ id: stop.spotId, name: stop.spotName })} className="min-h-11 content-center px-2 text-ui font-semibold text-ink underline">{t("trips.openSpot")}</Link>}</li>)}</ol>}
            </section>;
          })}
        </div>
      </article>}
    </main>
  </>;
}
