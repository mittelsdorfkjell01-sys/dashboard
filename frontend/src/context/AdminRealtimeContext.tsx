import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { getAdminRealtimeVersion } from "../lib/api";

const ACTIVE_POLL_MS = 2_000;
const BACKGROUND_POLL_MS = 15_000;
const AdminRealtimeContext = createContext(0);

export function AdminRealtimeProvider({ children }: { children: ReactNode }) {
  const [changeTick, setChangeTick] = useState(0);
  const serverRevision = useRef<number | null>(null);
  const stopped = useRef(false);
  const inFlight = useRef(false);
  const timer = useRef<number | null>(null);

  const poll = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const { revision } = await getAdminRealtimeVersion();
      if (serverRevision.current === null) {
        serverRevision.current = revision;
      } else if (serverRevision.current !== revision) {
        serverRevision.current = revision;
        setChangeTick((value) => value + 1);
      }
    } catch {
      // A transient sync failure must not block any normal dashboard action.
    } finally {
      inFlight.current = false;
      if (!stopped.current) {
        timer.current = window.setTimeout(
          poll,
          document.visibilityState === "visible" ? ACTIVE_POLL_MS : BACKGROUND_POLL_MS,
        );
      }
    }
  }, []);

  useEffect(() => {
    stopped.current = false;
    void poll();
    const refreshNow = (event: Event) => {
      if (document.visibilityState !== "visible" && event.type === "visibilitychange") return;
      if (timer.current !== null) window.clearTimeout(timer.current);
      void poll();
    };
    const onVisibility = (event: Event) => refreshNow(event);
    const onFocus = (event: Event) => refreshNow(event);
    const onOnline = (event: Event) => refreshNow(event);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("focus", onFocus);
    window.addEventListener("online", onOnline);
    return () => {
      stopped.current = true;
      if (timer.current !== null) window.clearTimeout(timer.current);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("online", onOnline);
    };
  }, [poll]);

  return (
    <AdminRealtimeContext.Provider value={changeTick}>
      {children}
    </AdminRealtimeContext.Provider>
  );
}

export function useAdminRealtimeRefresh(
  refresh: () => void | Promise<void>,
  enabled = true,
): void {
  const changeTick = useContext(AdminRealtimeContext);
  const refreshRef = useRef(refresh);
  const seenTick = useRef(changeTick);
  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);
  useEffect(() => {
    if (!enabled || seenTick.current === changeTick) return;
    seenTick.current = changeTick;
    void refreshRef.current();
  }, [changeTick, enabled]);
}
