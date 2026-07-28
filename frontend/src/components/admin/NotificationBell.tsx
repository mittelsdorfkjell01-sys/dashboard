import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getNotifications,
  getUnreadNotificationCount,
  markAllNotificationsRead,
  markNotificationRead,
  type AdminNotification,
} from "../../lib/api";

const POLL_MS = 60_000; // minute polling for the badge

/**
 * Operator-notification bell for the admin chrome (Sprint 9). Polls the cheap
 * unread-count every minute; opening the panel loads the list and offers
 * mark-read / mark-all-read. Clicking one that links a spot jumps to it.
 */
export default function NotificationBell() {
  const navigate = useNavigate();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AdminNotification[] | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  // Badge: poll the count on a minute interval (and once on mount).
  useEffect(() => {
    let alive = true;
    const tick = () =>
      getUnreadNotificationCount()
        .then((r) => alive && setUnread(r.count))
        .catch(() => {});
    tick();
    const t = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) {
      getNotifications()
        .then((r) => {
          setItems(r.items);
          setUnread(r.unread);
        })
        .catch(() => setItems([]));
    }
  };

  const onItem = async (n: AdminNotification) => {
    if (!n.read) {
      await markNotificationRead(n.id).catch(() => {});
      setItems((prev) => prev?.map((x) => (x.id === n.id ? { ...x, read: true } : x)) ?? null);
      setUnread((u) => Math.max(0, u - 1));
    }
    if (n.spot_id) {
      setOpen(false);
      navigate(`/admin/spot/${n.spot_id}/edit`);
    } else {
      setOpen(false);
      navigate("/admin/review");
    }
  };

  const markAll = async () => {
    await markAllNotificationsRead().catch(() => {});
    setItems((prev) => prev?.map((x) => ({ ...x, read: true })) ?? null);
    setUnread(0);
  };

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={toggle}
        aria-label={`Benachrichtigungen${unread ? `, ${unread} ungelesen` : ""}`}
        className="relative grid h-9 w-9 place-items-center rounded-lg text-ink-soft hover:bg-ink/5"
      >
        <span aria-hidden className="text-[18px]">🔔</span>
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 grid min-w-[18px] place-items-center rounded-full bg-orange px-1 text-[11px] font-semibold leading-[18px] text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-xl border border-line bg-white shadow-float">
          <div className="flex items-center justify-between border-b border-line px-3 py-2">
            <span className="text-label font-semibold text-ink">Benachrichtigungen</span>
            {(items?.some((i) => !i.read) ?? false) && (
              <button
                type="button"
                onClick={markAll}
                className="text-caption font-medium text-teal hover:underline"
              >
                Alle gelesen
              </button>
            )}
          </div>
          <div className="max-h-[360px] overflow-y-auto">
            {items === null ? (
              <p className="px-3 py-6 text-center text-caption text-muted">Lädt…</p>
            ) : items.length === 0 ? (
              <p className="px-3 py-6 text-center text-caption text-muted">
                Keine Benachrichtigungen.
              </p>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => onItem(n)}
                  className={`block w-full border-b border-line px-3 py-2 text-left last:border-0 hover:bg-band/60 ${
                    n.read ? "" : "bg-teal/5"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    {!n.read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-orange" />}
                    <div className="min-w-0">
                      <p className="text-label text-ink">{n.message}</p>
                      <p className="mt-0.5 text-caption text-muted">
                        {new Date(n.created_at).toLocaleString("de-DE")}
                      </p>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
