// Public community section on the spot page, split across two page
// positions since Sprint 3: `CommunityGalleryMosaic` sits next to the lede
// in the Überblick module, `SpotCommunityFeed` (default export) is the
// chronological feed further down. Both call `useCommunityFeed` — ratings,
// tips and images merged client-side (see lib/communityFeed; the backend
// still has three separate endpoints and no sprint has added a combined
// one) — independently; the shared useSwr cache means that's one set of
// requests, not two. The composer (in the feed) is the only place a photo
// gets attached to a post; the gallery only ever reads photos back out.

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import {
  ApiError,
  getImageLicense,
  postRating,
  reportImage,
  resolveMediaUrl,
  uploadSpotImage,
  type CommunityImage,
} from "../lib/api";
import { HERO_REQ, validateHeroFile } from "./ImageUpload";
import { LEVELS, levelLabel, sportLabel } from "../lib/labels";
import { ChevronDownIcon, CloseIcon } from "../lib/icons";
import { Button, Input, Select, Textarea } from "./ui";
import { useCommunityFeed, usePersistedState } from "../lib/hooks";
import { coloredTileUrl } from "../lib/mapLinks";
import {
  avatarColor,
  encodeVisitDate,
  formatVisitDate,
  initials,
  relativeTime,
  sortFeed,
  type FeedPost,
  type FeedSort,
} from "../lib/communityFeed";

const SPORTS = ["kitesurf", "wavekite", "windsurf", "wing", "surf"];
const REPORT_REASONS: { key: string; label: string }[] = [
  { key: "copyright", label: "Urheberrecht / mein Bild" },
  { key: "inappropriate", label: "Unangemessen" },
  { key: "wrong_spot", label: "Falscher Spot" },
  { key: "other", label: "Sonstiges" },
];

const COMPOSER_ID = "community-composer";

// Name must be a first name, or first + last (1–2 words, letters only).
const NAME_RE = /^\p{L}[\p{L}'.-]*(?:\s+\p{L}[\p{L}'.-]*)?$/u;
const validName = (n: string) => NAME_RE.test(n.trim());

const STAR_PATH =
  "M12 2.5l2.7 5.6 6.1.9-4.4 4.4 1 6.1L12 16.6l-5.4 2.9 1-6.1-4.4-4.4 6.1-.9L12 2.5Z";

/** Solid single-color star — the clickable rating picker (binary filled/empty
 *  per star; only the read-only `Stars` below needs fractional fill). */
function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true">
      <path d={STAR_PATH} className={filled ? "fill-orange" : "fill-line"} />
    </svg>
  );
}

/** Read-only fractional-fill star row. */
function Stars({ value, size = 16 }: { value: number; size?: number }) {
  const uid = useId();
  return (
    <span className="inline-flex items-center gap-0.5" aria-label={`${value} von 5 Sternen`}>
      {[0, 1, 2, 3, 4].map((i) => {
        const pct = Math.max(0, Math.min(1, value - i));
        const clipId = `${uid}-${i}`;
        return (
          <svg key={i} width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
            <defs>
              <clipPath id={clipId}>
                <rect x="0" y="0" width={24 * pct} height="24" />
              </clipPath>
            </defs>
            <path d={STAR_PATH} className="fill-line" />
            <path d={STAR_PATH} className="fill-orange" clipPath={`url(#${clipId})`} />
          </svg>
        );
      })}
    </span>
  );
}

/** Marks a photo as auto-fetched from Wikimedia Commons rather than posted by
 *  a community member — required by the sprint spec so the two sources never
 *  get confused for one another. */
function CommonsBadge({ compact = false }: { compact?: boolean }) {
  return (
    <span className="absolute bottom-1.5 left-1.5 rounded-2xl bg-ink px-2 py-0.5 text-caption font-medium text-white">
      {compact ? "Commons" : "Aus Wikimedia Commons"}
    </span>
  );
}

// --- gallery mosaic ----------------------------------------------------------

/**
 * The Überblick module's photo tile: one big image (16:10) over three
 * thumbnails, the last carrying a "+N" overlay once there are more than
 * four. Looks right at 4 photos or 40. "Bilder hinzufügen" is its own small
 * upload form (`GalleryUploadForm`), independent of the community composer
 * further down — adding a photo here doesn't require writing a rating/tip.
 */
export function CommunityGalleryMosaic({ spotId, coords }: { spotId: string; coords?: [number, number] }) {
  const { photos } = useCommunityFeed(spotId);
  const [heroFormOpen, setHeroFormOpen] = useState(false);
  const [uploadFormOpen, setUploadFormOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [reportFor, setReportFor] = useState<string | null>(null);

  const big = photos[0];
  const thumbs = photos.slice(1, 4);
  const extra = photos.length - 4;

  return (
    <div>
      {photos.length === 0 ? (
        <GalleryEmptyState coords={coords} onAdd={() => setUploadFormOpen(true)} />
      ) : (
        <div className="grid gap-2">
          <button
            type="button"
            onClick={() => setLightboxIndex(0)}
            aria-label={`Bild vergrößern${big.credit ? ` — ${big.credit}` : ""}`}
            className="relative aspect-[4/5] overflow-hidden rounded-xl"
          >
            <img
              src={resolveMediaUrl(big.url)}
              alt={big.credit ?? ""}
              className="h-full w-full object-cover"
              loading="lazy"
            />
            {big.source === "wikimedia_commons" && <CommonsBadge />}
          </button>
          {thumbs.length > 0 && (
            <div className="grid grid-cols-3 gap-2">
              {thumbs.map((img, i) => {
                const isLast = i === thumbs.length - 1;
                return (
                  <button
                    key={img.id}
                    type="button"
                    onClick={() => setLightboxIndex(i + 1)}
                    aria-label={
                      isLast && extra > 0
                        ? `Alle ${photos.length} Bilder ansehen`
                        : `Bild vergrößern${img.credit ? ` — ${img.credit}` : ""}`
                    }
                    className="relative aspect-square overflow-hidden rounded-xl"
                  >
                    <img
                      src={resolveMediaUrl(img.url)}
                      alt={img.credit ?? ""}
                      className="h-full w-full object-cover"
                      loading="lazy"
                    />
                    {isLast && extra > 0 && (
                      <span className="absolute inset-0 flex items-center justify-center bg-ink/60 text-body font-semibold text-white">
                        +{extra}
                      </span>
                    )}
                    {img.source === "wikimedia_commons" && !(isLast && extra > 0) && <CommonsBadge compact />}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        {photos.length > 0 && !uploadFormOpen && (
          <button
            type="button"
            onClick={() => {
              setUploadFormOpen(true);
              setHeroFormOpen(false);
            }}
            className="rounded-2xl border border-teal/30 px-4 py-2 text-label font-medium text-teal transition-colors hover:bg-teal/5"
          >
            Bilder hinzufügen
          </button>
        )}
        {!heroFormOpen && (
          <button
            type="button"
            onClick={() => {
              setHeroFormOpen(true);
              setUploadFormOpen(false);
            }}
            className="text-label font-medium text-teal hover:text-teal-hover"
          >
            Titelbild vorschlagen
          </button>
        )}
      </div>

      {uploadFormOpen && (
        <GalleryUploadForm spotId={spotId} onCancel={() => setUploadFormOpen(false)} onDone={() => setUploadFormOpen(false)} />
      )}

      {heroFormOpen && (
        <HeroCandidateForm spotId={spotId} onCancel={() => setHeroFormOpen(false)} onDone={() => setHeroFormOpen(false)} />
      )}

      {reportFor && (
        <ReportDialog imageId={reportFor} onClose={() => setReportFor(null)} onDone={() => setReportFor(null)} />
      )}

      {lightboxIndex !== null && (
        <Lightbox
          items={photos}
          index={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
          onIndexChange={setLightboxIndex}
          onReport={setReportFor}
        />
      )}
    </div>
  );
}

/** No grey box: a colored map crop of the spot itself stands in for "no
 *  photos yet", so the empty state still shows *something real* about the
 *  place. */
function GalleryEmptyState({ coords, onAdd }: { coords?: [number, number]; onAdd: () => void }) {
  const bg = coords ? coloredTileUrl(coords[0], coords[1], 15) : null;
  return (
    <div
      className="relative aspect-[4/5] overflow-hidden rounded-xl bg-band bg-cover bg-center"
      style={bg ? { backgroundImage: `url(${bg})` } : undefined}
    >
      <div className="absolute inset-0 bg-ink/55" />
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-body font-medium text-white">Noch keine Fotos von hier</p>
        <button
          type="button"
          onClick={onAdd}
          className="rounded-2xl bg-teal px-4 py-2 text-label font-medium text-white transition-colors hover:bg-teal-hover"
        >
          Bilder hinzufügen
        </button>
      </div>
    </div>
  );
}

// --- composer ----------------------------------------------------------------

/** Always visible, star-first: no "Bewerten" button to reveal it. Picking a
 *  star expands the rest (text, sport, level, visit date, photo). Submits a
 *  single rating (stars + free text) and, if a photo was attached, a second
 *  upload call right after — the closest the current API gets to "one post,
 *  one action" without a dedicated endpoint. */
function Composer({
  spotId,
  spotName,
  onPosted,
}: {
  spotId: string;
  spotName: string;
  onPosted: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [stars, setStars] = useState(0);
  const [text, setText] = useState("");
  const [sport, setSport] = useState("kitesurf");
  const [skill, setSkill] = useState("intermediate");
  const [visitedAt, setVisitedAt] = useState("");
  const [author, setAuthor] = useState("");
  const [website, setWebsite] = useState(""); // honeypot
  const [file, setFile] = useState<File | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [terms, setTerms] = useState<{ version: string; terms: string } | null>(null);
  const [showTerms, setShowTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getImageLicense().then(setTerms).catch(() => {});
  }, []);

  const pickStar = (n: number) => {
    setStars(n);
    setExpanded(true);
  };

  const reset = () => {
    setExpanded(false);
    setStars(0);
    setText("");
    setVisitedAt("");
    setFile(null);
    setAccepted(false);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (stars < 1) return setError("Bitte eine Sternebewertung wählen.");
    if (!text.trim()) return setError("Bitte kurz schreiben, wie es war.");
    if (!validName(author)) return setError("Bitte Vorname (oder Vor- und Nachname) angeben.");
    if (file && !accepted) return setError("Bitte die Rechteerklärung fürs Foto bestätigen.");
    setError(null);
    setBusy(true);
    try {
      const conditions = encodeVisitDate(visitedAt, text.trim());
      await postRating(spotId, {
        stars,
        skill_level: skill,
        sport,
        conditions,
        author_name: author.trim(),
        website,
      });
      if (file) {
        await uploadSpotImage(spotId, file, "gallery", { credit: author.trim(), licenseAccept: accepted });
      }
      reset();
      onPosted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Senden fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form id={COMPOSER_ID} onSubmit={submit} className="scroll-mt-24 rounded-3xl border border-line bg-white p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-body font-medium text-ink">Wie war's am {spotName}?</p>
        <div className="flex gap-1">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              aria-label={`${n} Sterne`}
              onClick={() => pickStar(n)}
              className="transition-transform hover:scale-110"
            >
              <StarIcon filled={n <= stars} />
            </button>
          ))}
        </div>
      </div>

      {expanded && (
        <div className="mt-4 space-y-3">
          <Textarea
            required
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Wie waren die Bedingungen? Was sollten andere wissen? (Pflichtfeld)"
            rows={3}
          />
          <div className="flex flex-wrap gap-3">
            <label className="text-label text-muted">
              Sportart
              <Select value={sport} onChange={(e) => setSport(e.target.value)} className="mt-1">
                {SPORTS.map((s) => (
                  <option key={s} value={s}>
                    {sportLabel(s)}
                  </option>
                ))}
              </Select>
            </label>
            <label className="text-label text-muted">
              Level
              <Select value={skill} onChange={(e) => setSkill(e.target.value)} className="mt-1">
                {LEVELS.map((l) => (
                  <option key={l} value={l}>
                    {levelLabel(l)}
                  </option>
                ))}
              </Select>
            </label>
            <label className="text-label text-muted">
              Besuchsdatum
              <Input
                type="date"
                value={visitedAt}
                onChange={(e) => setVisitedAt(e.target.value)}
                max={new Date().toISOString().slice(0, 10)}
                className="mt-1"
              />
            </label>
          </div>

          <Input
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            placeholder="Vorname oder Vor- und Nachname (Pflichtfeld)"
            required
          />

          <div>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-label text-ink"
            />
            {file && (
              <label className="mt-2 flex items-start gap-2 text-label text-ink">
                <input
                  type="checkbox"
                  checked={accepted}
                  onChange={(e) => setAccepted(e.target.checked)}
                  className="mt-0.5"
                />
                <span>
                  Ich bestätige die{" "}
                  <button type="button" onClick={() => setShowTerms((v) => !v)} className="underline">
                    Rechte- &amp; Einwilligungserklärung{terms ? ` (${terms.version})` : ""}
                  </button>
                  .
                </span>
              </label>
            )}
            {showTerms && terms && (
              <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-band p-3 text-caption text-ink-soft">
                {terms.terms}
              </pre>
            )}
          </div>

          <Honeypot value={website} onChange={setWebsite} />
          {error && (
            <p role="alert" className="text-label text-red-600">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            <Button type="submit" disabled={busy}>
              {busy ? "Senden…" : "Veröffentlichen"}
            </Button>
            <Button type="button" variant="ghost" onClick={reset}>
              Abbrechen
            </Button>
          </div>
        </div>
      )}
    </form>
  );
}

// --- feed ----------------------------------------------------------------

/** The chronological feed itself: composer up top, "Neueste"/"Hilfreichste"
 *  toggle, then the posts (or an inviting empty state with the composer
 *  directly under it). Headless — the caller's SectionBand supplies the
 *  section heading (this used to also render the gallery; that moved up to
 *  the Überblick module in Sprint 3, see `CommunityGalleryMosaic`). */
export default function SpotCommunityFeed({ spotId, spotName }: { spotId: string; spotName: string }) {
  const { posts, loading, error, reload } = useCommunityFeed(spotId);
  const [sort, setSort] = usePersistedState<FeedSort>("swd.communityFeedSort", "newest");
  // Client-side only — there's no backend counter for "helpful" (no new
  // endpoint has ever added one), so this reflects this browser, not every visitor.
  const [helpfulCounts, setHelpfulCounts] = usePersistedState<Record<string, number>>(
    `swd.communityHelpful.${spotId}`,
    {}
  );
  const [votedIds, setVotedIds] = usePersistedState<string[]>(`swd.communityVoted.${spotId}`, []);
  const [reportFor, setReportFor] = useState<string | null>(null);

  const sorted = sortFeed(posts, sort, helpfulCounts);

  const markHelpful = (id: string) => {
    if (votedIds.includes(id)) return;
    setHelpfulCounts((prev) => ({ ...prev, [id]: (prev[id] ?? 0) + 1 }));
    setVotedIds((prev) => [...prev, id]);
  };

  const composer = <Composer spotId={spotId} spotName={spotName} onPosted={reload} />;

  return (
    <div>
      {!loading && posts.length === 0 ? (
        <>
          <div className="rounded-3xl border border-dashed border-line bg-white px-6 py-8 text-center">
            <p className="text-body font-medium text-ink">Sei der Erste, der von hier berichtet.</p>
            <p className="mx-auto mt-2 max-w-[46ch] text-caption text-muted">
              Hilfreiche Beiträge nennen Bedingungen, Level und was andere vor Ort wissen sollten.
            </p>
          </div>
          <div className="mt-4">{composer}</div>
        </>
      ) : (
        <>
          {composer}

          {posts.length > 0 && (
            <>
              <div className="mt-6 flex items-center justify-end gap-1 text-label">
                {(["newest", "helpful"] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSort(s)}
                    aria-pressed={sort === s}
                    className={`rounded-2xl px-3 py-1.5 font-medium transition-colors ${
                      sort === s ? "bg-teal text-white" : "text-muted hover:text-teal"
                    }`}
                  >
                    {s === "newest" ? "Neueste" : "Hilfreichste"}
                  </button>
                ))}
              </div>

              <ul className="mt-4 space-y-4">
                {sorted.map((post) => (
                  <li key={post.id}>
                    <FeedPostCard
                      post={post}
                      helpfulCount={helpfulCounts[post.id] ?? 0}
                      voted={votedIds.includes(post.id)}
                      onHelpful={() => markHelpful(post.id)}
                      onReport={setReportFor}
                    />
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}

      {error && (
        <p role="alert" className="mt-4 text-label text-red-600">
          {error}
        </p>
      )}

      {reportFor && (
        <ReportDialog imageId={reportFor} onClose={() => setReportFor(null)} onDone={() => setReportFor(null)} />
      )}
    </div>
  );
}

function FeedPostCard({
  post,
  helpfulCount,
  voted,
  onHelpful,
  onReport,
}: {
  post: FeedPost;
  helpfulCount: number;
  voted: boolean;
  onHelpful: () => void;
  onReport: (imageId: string) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  return (
    <article className="rounded-3xl border border-line bg-white p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="grid h-10 w-10 shrink-0 place-items-center rounded-full text-label font-semibold text-white"
          style={{ backgroundColor: avatarColor(post.authorName) }}
        >
          {initials(post.authorName)}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-body font-semibold text-ink">{post.authorName}</span>
            {post.skillLevel && (
              <span className="rounded-2xl bg-ink/5 px-2 py-0.5 text-caption font-medium text-muted">
                {levelLabel(post.skillLevel)}
              </span>
            )}
            {post.sport && (
              <span className="rounded-2xl bg-teal/10 px-2 py-0.5 text-caption font-medium text-teal">
                {sportLabel(post.sport)}
              </span>
            )}
          </div>

          {post.stars != null && (
            <div className="mt-1.5">
              <Stars value={post.stars} size={14} />
            </div>
          )}

          {post.text && <p className="mt-2 text-ui leading-relaxed text-ink-soft">{post.text}</p>}

          {post.photo && (
            <img
              src={resolveMediaUrl(post.photo.url)}
              alt={post.photo.credit ?? ""}
              className="mt-3 max-h-96 w-full rounded-2xl object-cover"
              loading="lazy"
            />
          )}

          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted">
            {post.visitedAt && <span className="font-medium text-muted">{formatVisitDate(post.visitedAt)}</span>}
            <span>{relativeTime(post.createdAt)}</span>
          </div>

          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              onClick={onHelpful}
              disabled={voted}
              aria-pressed={voted}
              className={`inline-flex items-center gap-1.5 rounded-2xl border px-3 py-1.5 text-caption font-medium transition-colors disabled:cursor-default ${
                voted
                  ? "border-green/30 bg-green/10 text-green"
                  : "border-line text-muted hover:text-teal"
              }`}
            >
              Hilfreich{helpfulCount > 0 ? ` · ${helpfulCount}` : ""}
            </button>

            {post.reportImageId && (
              <div ref={menuRef} className="relative ml-auto">
                <button
                  type="button"
                  onClick={() => setMenuOpen((v) => !v)}
                  aria-haspopup="menu"
                  aria-expanded={menuOpen}
                  aria-label="Weitere Aktionen"
                  className="grid h-8 w-8 place-items-center rounded-2xl text-label text-muted hover:bg-ink/5 hover:text-teal"
                >
                  ⋯
                </button>
                {menuOpen && (
                  <div
                    role="menu"
                    className="absolute right-0 top-[calc(100%+6px)] z-10 w-40 rounded-xl border border-line bg-white p-1"
                  >
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setMenuOpen(false);
                        onReport(post.reportImageId!);
                      }}
                      className="block w-full rounded-lg px-3 py-2 text-left text-label text-ink hover:bg-band"
                    >
                      Melden
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

// --- lightbox + report + hero-candidate proposal -----------------------------

/** Full-screen lightbox: blurred scrim, swipe (touch) / arrow keys (desktop)
 *  to move between images, Esc to close, a Tab-cycling focus trap so
 *  keyboard focus can't escape onto the page behind it, and a quiet "Melden"
 *  action (the mosaic's own thumbnails are too small to carry one each). */
function Lightbox({
  items,
  index,
  onClose,
  onIndexChange,
  onReport,
}: {
  items: CommunityImage[];
  index: number;
  onClose: () => void;
  onIndexChange: (i: number) => void;
  onReport: (imageId: string) => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const touchStartX = useRef<number | null>(null);
  const go = (delta: number) => onIndexChange((index + delta + items.length) % items.length);

  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "ArrowRight") return go(1);
      if (e.key === "ArrowLeft") return go(-1);
      if (e.key === "Tab") {
        const root = dialogRef.current;
        if (!root) return;
        const focusables = root.querySelectorAll<HTMLElement>(
          'button, [href], [tabindex]:not([tabindex="-1"])'
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, items.length]);

  const img = items[index];

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label="Bildergalerie, groß"
      tabIndex={-1}
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-ink p-4"
      onClick={onClose}
      onTouchStart={(e) => {
        touchStartX.current = e.touches[0].clientX;
      }}
      onTouchEnd={(e) => {
        if (touchStartX.current == null) return;
        const dx = e.changedTouches[0].clientX - touchStartX.current;
        if (Math.abs(dx) > 40) go(dx > 0 ? -1 : 1);
        touchStartX.current = null;
      }}
    >
      <div className="absolute right-4 top-4 flex items-center gap-2">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onReport(img.id);
          }}
          className="rounded-2xl bg-white/10 px-3 py-2 text-caption font-medium text-white transition-colors hover:bg-white/20"
        >
          Melden
        </button>
        <button
          type="button"
          onClick={onClose}
          aria-label="Schließen"
          className="grid h-10 w-10 place-items-center rounded-2xl bg-white/10 text-white transition-colors hover:bg-white/20"
        >
          <CloseIcon width={20} height={20} />
        </button>
      </div>

      {items.length > 1 && (
        <>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              go(-1);
            }}
            aria-label="Vorheriges Bild"
            className="absolute left-4 top-1/2 hidden h-11 w-11 -translate-y-1/2 place-items-center rounded-2xl bg-white/10 text-white transition-colors hover:bg-white/20 sm:grid"
          >
            <ChevronDownIcon width={20} height={20} className="rotate-90" />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              go(1);
            }}
            aria-label="Nächstes Bild"
            className="absolute right-4 top-1/2 hidden h-11 w-11 -translate-y-1/2 place-items-center rounded-2xl bg-white/10 text-white transition-colors hover:bg-white/20 sm:grid"
          >
            <ChevronDownIcon width={20} height={20} className="-rotate-90" />
          </button>
        </>
      )}

      <figure className="max-w-[92vw]" onClick={(e) => e.stopPropagation()}>
        <div className="relative">
          <img
            src={resolveMediaUrl(img.url)}
            alt={img.credit ?? ""}
            className="max-h-[80vh] max-w-[92vw] rounded-2xl object-contain"
          />
          {img.source === "wikimedia_commons" && <CommonsBadge />}
        </div>
        {(img.credit || img.license_name) && (
          <figcaption className="mt-3 text-center text-caption text-white/80">
            {img.credit}
            {img.credit && img.license_name && " · "}
            {img.license_name &&
              (img.license_url ? (
                <a
                  href={img.license_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-white"
                >
                  {img.license_name}
                </a>
              ) : (
                img.license_name
              ))}
          </figcaption>
        )}
      </figure>
    </div>
  );
}

function ReportDialog({
  imageId,
  onClose,
  onDone,
}: {
  imageId: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const [reason, setReason] = useState("copyright");
  const [note, setNote] = useState("");
  const [contact, setContact] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await reportImage(imageId, { reason, note: note || undefined });
      setContact(res.takedown_contact);
      setTimeout(onDone, 1600);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Meldung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-4 rounded-3xl border border-line bg-band p-4">
      <div className="flex items-center justify-between">
        <p className="text-ui font-medium text-ink">Bild melden</p>
        <button type="button" onClick={onClose} className="text-label text-muted hover:text-teal">
          Schließen
        </button>
      </div>
      {contact !== null ? (
        <p role="status" className="mt-2 text-label text-green">
          Danke, deine Meldung ist eingegangen.
          {contact && <> Bei dringenden Rechtefragen: {contact}</>}
        </p>
      ) : (
        <>
          <Select value={reason} onChange={(e) => setReason(e.target.value)} className="mt-2">
            {REPORT_REASONS.map((r) => (
              <option key={r.key} value={r.key}>{r.label}</option>
            ))}
          </Select>
          <Textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Anmerkung (optional)"
            className="mt-2"
            rows={2}
          />
          {error && <p role="alert" className="mt-2 text-label text-red-600">{error}</p>}
          <Button type="button" disabled={busy} onClick={submit} className="mt-3">
            {busy ? "Senden…" : "Melden"}
          </Button>
        </>
      )}
    </div>
  );
}

/** Standalone "add a photo" form — independent of the community composer
 *  (that's for posting a rating/tip; this is just "I have a photo of this
 *  spot", no text required). Uploads immediately but lands in the admin
 *  review queue rather than the public gallery straight away — an admin
 *  approves it from there before it shows up for everyone else. */
export function GalleryUploadForm({
  spotId,
  onDone,
  onCancel,
}: {
  spotId: string;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [credit, setCredit] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [website, setWebsite] = useState("");
  const [terms, setTerms] = useState<{ version: string; terms: string } | null>(null);
  const [showTerms, setShowTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getImageLicense().then(setTerms).catch(() => {});
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    if (website) return; // honeypot
    if (!accepted) return setError("Bitte die Rechteerklärung fürs Foto bestätigen.");
    setBusy(true);
    setError(null);
    try {
      await uploadSpotImage(spotId, file, "gallery", {
        credit: credit || undefined,
        licenseAccept: accepted,
        review: true,
      });
      setFile(null);
      setCredit("");
      setAccepted(false);
      setNotice("Danke! Dein Bild wartet auf Freigabe.");
      setTimeout(() => {
        setNotice(null);
        onDone();
      }, 1800);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="mt-4 rounded-3xl bg-ink/5 p-4">
      <div className="flex items-center justify-between">
        <p className="text-ui font-medium text-ink">Bild hinzufügen</p>
        <button type="button" onClick={onCancel} className="text-label text-muted hover:text-teal">
          Schließen
        </button>
      </div>
      <p className="mt-1 text-caption text-muted">
        Wird sofort hochgeladen, ist aber erst nach kurzer Prüfung für alle sichtbar.
      </p>
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="mt-2 text-label text-ink"
      />
      <Input
        value={credit}
        onChange={(e) => setCredit(e.target.value)}
        placeholder="Credit: Name oder Instagram (optional)"
        className="mt-2"
      />
      <label className="mt-3 flex items-start gap-2 text-label text-ink">
        <input
          type="checkbox"
          checked={accepted}
          onChange={(e) => setAccepted(e.target.checked)}
          className="mt-0.5"
        />
        <span>
          Ich bestätige die{" "}
          <button type="button" onClick={() => setShowTerms((v) => !v)} className="underline">
            Rechte- &amp; Einwilligungserklärung{terms ? ` (${terms.version})` : ""}
          </button>
          .
        </span>
      </label>
      {showTerms && terms && (
        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-band p-3 text-caption text-ink-soft">
          {terms.terms}
        </pre>
      )}
      <Honeypot value={website} onChange={setWebsite} />
      {error && <p role="alert" className="mt-2 text-label text-red-600">{error}</p>}
      {notice && <p role="status" className="mt-2 text-label text-green">{notice}</p>}
      <Button type="submit" disabled={busy || !file || !accepted} className="mt-3">
        {busy ? "Hochladen…" : "Hochladen"}
      </Button>
    </form>
  );
}

/** Proposing the page's *hero* photo is a different action from adding a
 *  gallery photo (it goes through its own admin review queue) — kept as its
 *  own small, deliberately understated form rather than folded into the main
 *  composer, so "share what happened here" and "suggest a new cover photo"
 *  don't compete for attention. */
function HeroCandidateForm({
  spotId,
  onDone,
  onCancel,
}: {
  spotId: string;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [credit, setCredit] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [website, setWebsite] = useState("");
  const [terms, setTerms] = useState<{ version: string; terms: string } | null>(null);
  const [showTerms, setShowTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getImageLicense().then(setTerms).catch(() => {});
  }, []);

  const pickFile = async (f: File | null) => {
    setError(null);
    if (f) {
      const res = await validateHeroFile(f);
      if (!res.ok) {
        setError(res.reason ?? "Bild erfüllt die Hero-Vorgaben nicht.");
        setFile(null);
        return;
      }
    }
    setFile(f);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    if (website) return; // honeypot
    setBusy(true);
    setError(null);
    try {
      await uploadSpotImage(spotId, file, "hero_candidate", { credit: credit || undefined, licenseAccept: accepted });
      setFile(null);
      setCredit("");
      setAccepted(false);
      setNotice("Danke! Dein Titelbild-Vorschlag wartet auf Freigabe.");
      setTimeout(() => {
        setNotice(null);
        onDone();
      }, 1800);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="mt-4 rounded-3xl bg-ink/5 p-4">
      <div className="flex items-center justify-between">
        <p className="text-ui font-medium text-ink">Titelbild vorschlagen</p>
        <button type="button" onClick={onCancel} className="text-label text-muted hover:text-teal">
          Schließen
        </button>
      </div>
      <p className="mt-1 text-caption text-muted">
        Mind. {HERO_REQ.minWidth}×{HERO_REQ.minHeight} px, Querformat, JPG/PNG/WebP.
      </p>
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
        className="mt-2 text-label text-ink"
      />
      <Input
        value={credit}
        onChange={(e) => setCredit(e.target.value)}
        placeholder="Credit: Name oder Instagram (optional)"
        className="mt-2"
      />
      <label className="mt-3 flex items-start gap-2 text-label text-ink">
        <input
          type="checkbox"
          checked={accepted}
          onChange={(e) => setAccepted(e.target.checked)}
          className="mt-0.5"
        />
        <span>
          Ich bestätige die{" "}
          <button type="button" onClick={() => setShowTerms((v) => !v)} className="underline">
            Rechte- &amp; Einwilligungserklärung{terms ? ` (${terms.version})` : ""}
          </button>
          .
        </span>
      </label>
      {showTerms && terms && (
        <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-band p-3 text-caption text-ink-soft">
          {terms.terms}
        </pre>
      )}
      <Honeypot value={website} onChange={setWebsite} />
      {error && <p role="alert" className="mt-2 text-label text-red-600">{error}</p>}
      {notice && <p role="status" className="mt-2 text-label text-green">{notice}</p>}
      <Button type="submit" disabled={busy || !file || !accepted} className="mt-3">
        {busy ? "Hochladen…" : "Vorschlagen"}
      </Button>
    </form>
  );
}

// A visually-hidden honeypot field: real users never fill it, bots often do.
function Honeypot({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <input
      type="text"
      name="website"
      tabIndex={-1}
      autoComplete="off"
      aria-hidden="true"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="absolute left-[-9999px] h-0 w-0 opacity-0"
    />
  );
}
