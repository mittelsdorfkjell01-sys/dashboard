import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "../../lib/api/client";
import { reportImage, type CommunityImage } from "../../lib/api/community";
import { resolveMediaUrl } from "../../lib/api";
import { ChevronDownIcon, CloseIcon } from "../../lib/icons";
import type { TranslationKey } from "../../lib/i18n";
import { responsiveImageAttributes } from "../../lib/heroSource";
import { Button, Select, Textarea } from "../ui";

const REPORT_REASONS: { key: string; labelKey: TranslationKey }[] = [
  { key: "copyright", labelKey: "community.report.reasons.copyright" },
  { key: "inappropriate", labelKey: "community.report.reasons.inappropriate" },
  { key: "wrong_spot", labelKey: "community.report.reasons.wrongSpot" },
  { key: "other", labelKey: "community.report.reasons.other" },
];

export function CommonsBadge({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  return (
    <span className="absolute bottom-1.5 left-1.5 rounded-card bg-ink px-2 py-0.5 text-caption font-medium text-white">
      {compact ? t("community.commons.badge") : t("community.commons.full")}
    </span>
  );
}

export function Lightbox({
  items,
  index,
  onClose,
  onIndexChange,
  onReport,
}: {
  items: CommunityImage[];
  index: number;
  onClose: () => void;
  onIndexChange: (index: number) => void;
  onReport: (imageId: string) => void;
}) {
  const { t } = useTranslation();
  const dialogRef = useRef<HTMLDivElement>(null);
  const touchStartX = useRef<number | null>(null);
  const go = useCallback(
    (delta: number) => onIndexChange((index + delta + items.length) % items.length),
    [index, items.length, onIndexChange],
  );

  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key === "ArrowRight") return go(1);
      if (event.key === "ArrowLeft") return go(-1);
      if (event.key !== "Tab") return;

      const root = dialogRef.current;
      if (!root) return;
      const focusables = root.querySelectorAll<HTMLElement>(
        'button, [href], [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, onClose]);

  const image = items[index];

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label={t("community.lightbox.label")}
      tabIndex={-1}
      className="fixed inset-0 z-header flex items-center justify-center bg-ink p-4"
      onClick={onClose}
      onTouchStart={(event) => {
        touchStartX.current = event.touches[0].clientX;
      }}
      onTouchEnd={(event) => {
        if (touchStartX.current == null) return;
        const deltaX = event.changedTouches[0].clientX - touchStartX.current;
        if (Math.abs(deltaX) > 40) go(deltaX > 0 ? -1 : 1);
        touchStartX.current = null;
      }}
    >
      <div className="absolute right-4 top-4 flex items-center gap-2">
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onReport(image.id);
          }}
          className="rounded-card bg-white/10 px-3 py-2 text-caption font-medium text-white transition-colors hover:bg-white/20"
        >
          {t("community.post.report")}
        </button>
        <button
          type="button"
          onClick={onClose}
          aria-label={t("common.close")}
          className="grid h-11 w-11 place-items-center rounded-card bg-white/10 text-white transition-colors hover:bg-white/20"
        >
          <CloseIcon width={20} height={20} />
        </button>
      </div>

      {items.length > 1 && (
        <>
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              go(-1);
            }}
            aria-label={t("community.lightbox.prev")}
            className="absolute left-4 top-1/2 hidden h-11 w-11 -translate-y-1/2 place-items-center rounded-card bg-white/10 text-white transition-colors hover:bg-white/20 sm:grid"
          >
            <ChevronDownIcon width={20} height={20} className="rotate-90" />
          </button>
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              go(1);
            }}
            aria-label={t("community.lightbox.next")}
            className="absolute right-4 top-1/2 hidden h-11 w-11 -translate-y-1/2 place-items-center rounded-card bg-white/10 text-white transition-colors hover:bg-white/20 sm:grid"
          >
            <ChevronDownIcon width={20} height={20} className="-rotate-90" />
          </button>
        </>
      )}

      <figure className="max-w-[92vw]" onClick={(event) => event.stopPropagation()}>
        <div className="relative">
          <img
            {...responsiveImageAttributes(resolveMediaUrl(image.url), image.width, "100vw")}
            alt={image.credit ?? ""}
            className="max-h-[80vh] max-w-[92vw] rounded-card object-contain"
            decoding="async"
          />
          {image.source === "wikimedia_commons" && <CommonsBadge />}
        </div>
        {(image.credit || image.license_name) && (
          <figcaption className="mt-3 text-center text-caption text-on-photo">
            {image.credit}
            {image.credit && image.license_name && " · "}
            {image.license_name &&
              (image.license_url ? (
                <a
                  href={image.license_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-white"
                >
                  {image.license_name}
                </a>
              ) : (
                image.license_name
              ))}
          </figcaption>
        )}
      </figure>
    </div>
  );
}

export function ReportDialog({
  imageId,
  onClose,
  onDone,
}: {
  imageId: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const [reason, setReason] = useState("copyright");
  const [note, setNote] = useState("");
  const [contact, setContact] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await reportImage(imageId, { reason, note: note || undefined });
      setContact(response.takedown_contact);
      setTimeout(onDone, 1_600);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : t("community.report.failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-4 rounded-card border border-line bg-band p-4">
      <div className="flex items-center justify-between">
        <p className="text-ui font-medium text-ink">{t("community.report.title")}</p>
        <button type="button" onClick={onClose} className="text-ui text-muted hover:text-accent">
          {t("common.close")}
        </button>
      </div>
      {contact !== null ? (
        <p role="status" className="mt-2 text-ui text-green">
          {t("community.report.thanks")}
          {contact && <> {t("community.report.contact", { contact })}</>}
        </p>
      ) : (
        <>
          <Select value={reason} onChange={(event) => setReason(event.target.value)} className="mt-2">
            {REPORT_REASONS.map((item) => (
              <option key={item.key} value={item.key}>{t(item.labelKey)}</option>
            ))}
          </Select>
          <Textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder={t("community.report.notePlaceholder")}
            className="mt-2"
            rows={2}
          />
          {error && <p role="alert" className="mt-2 text-ui text-danger">{error}</p>}
          <Button type="button" disabled={busy} onClick={submit} className="mt-3">
            {busy ? t("common.sending") : t("community.report.submit")}
          </Button>
        </>
      )}
    </div>
  );
}
