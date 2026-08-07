// The rights record exactly as it will be stored.
//
// Shown in full before adoption, not summarised: provenance is the product of
// this whole feature, and an operator should be able to see what they are
// committing the catalogue to.

import type { MediaItem } from "../../../lib/mediaPicker";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2 py-1">
      <dt className="w-28 shrink-0 text-caption text-admin-muted">{label}</dt>
      <dd className="min-w-0 flex-1 break-words text-caption text-admin-fg2">
        {children}
      </dd>
    </div>
  );
}

function Link({ href, children }: { href?: string | null; children: React.ReactNode }) {
  if (!href) return <>{children}</>;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-admin-primary hover:underline"
    >
      {children}
    </a>
  );
}

export default function LicenseCard({ item }: { item: MediaItem }) {
  return (
    <div className="rounded-lg border border-admin-border bg-admin-bg p-3">
      <p className="text-label font-semibold text-admin-fg">Bildnachweis</p>
      <p className="mt-0.5 text-caption text-admin-muted">
        Wird automatisch gespeichert und im Hero angezeigt.
      </p>
      <dl className="mt-2 divide-y divide-admin-border-subtle">
        <Row label="Urheber">
          <Link href={item.credit.url}>{item.credit.name}</Link>
        </Row>
        <Row label="Lizenz">
          <Link href={item.license.url}>{item.license.name}</Link>
        </Row>
        <Row label="Quelle">
          <Link href={item.source_page}>{item.provider}</Link>
        </Row>
        <Row label="Auslieferung">
          {item.delivery === "hotlinked"
            ? "Hotlink (Provider-CDN)"
            : "Eigener Speicher"}
        </Row>
        <Row label="Auflösung">
          {item.width && item.height ? `${item.width}×${item.height} px` : "unbekannt"}
        </Row>
        <Row label="Ortsbezug">
          {item.geo_verified ? "über Koordinaten belegt" : "ungeprüft"}
        </Row>
      </dl>
    </div>
  );
}
