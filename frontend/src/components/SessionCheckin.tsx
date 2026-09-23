import { useState } from "react";
import { flushEvents, trackEvent } from "../lib/events";

type Outcome = "worthwhile" | "not_worthwhile";

export default function SessionCheckin({ spotId }: { spotId: string }) {
  const [checkedIn, setCheckedIn] = useState(false);
  const [outcome, setOutcome] = useState<Outcome>();

  const record = (next?: Outcome) => {
    trackEvent("session_checkin", {
      spotId,
      surface: "spot",
      context: next ? { outcome: next } : {},
    });
    void flushEvents();
    setCheckedIn(true);
    if (next) setOutcome(next);
  };

  return (
    <div className="mt-6 border-t border-line/70 pt-5">
      {!checkedIn ? (
        <button
          type="button"
          onClick={() => record()}
          className="min-h-11 rounded-[14px] border border-line bg-surface px-4 text-ui font-semibold text-ink transition-colors hover:bg-band"
        >
          War heute hier
        </button>
      ) : (
        <div aria-live="polite">
          <p className="text-label font-medium text-ink">Heute eingecheckt</p>
          <div className="mt-3 flex flex-wrap gap-2" aria-label="Optionaler Eindruck">
            <button
              type="button"
              aria-pressed={outcome === "worthwhile"}
              onClick={() => record("worthwhile")}
              className={`min-h-11 rounded-[14px] border px-4 text-label font-medium transition-colors ${outcome === "worthwhile" ? "border-ink bg-ink text-white" : "border-line bg-surface text-ink hover:bg-band"}`}
            >
              Lohnend
            </button>
            <button
              type="button"
              aria-pressed={outcome === "not_worthwhile"}
              onClick={() => record("not_worthwhile")}
              className={`min-h-11 rounded-[14px] border px-4 text-label font-medium transition-colors ${outcome === "not_worthwhile" ? "border-ink bg-ink text-white" : "border-line bg-surface text-ink hover:bg-band"}`}
            >
              Nicht lohnend
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
