import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  getCatalogCoverage,
  type CatalogCoverage,
} from "../lib/api";
import { sportLabel } from "../lib/labels";
import {
  Badge,
  Button,
  PageHeader,
  Table,
  TableFrame,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "../components/admin/ui";

export default function AdminCatalogCoverage() {
  const [data, setData] = useState<CatalogCoverage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [onlyGaps, setOnlyGaps] = useState(true);

  const load = () => {
    setError(null);
    getCatalogCoverage()
      .then(setData)
      .catch((reason) => setError(
        reason instanceof ApiError ? reason.message : "Katalogabdeckung konnte nicht geladen werden.",
      ));
  };

  useEffect(load, []);

  const rows = useMemo(() => {
    const all = data?.rows ?? [];
    return onlyGaps
      ? all.filter((row) => row.total === 0 || row.content.verified < row.total || row.classification.unranked > 0)
      : all;
  }, [data, onlyGaps]);

  return (
    <div>
      <PageHeader
        title="Katalogabdeckung"
        description="Region × Sport × Veröffentlichung × Inhaltsreife. Mehrfachsport-Spots zählen je Sport, aber nur einmal in der Gesamtsumme."
        actions={
          <Button onClick={() => setOnlyGaps((value) => !value)}>
            {onlyGaps ? "Alle Zellen zeigen" : "Nur Lücken zeigen"}
          </Button>
        }
      />

      {error && (
        <div role="alert" className="mb-4 rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-3 text-ui text-admin-danger">
          <p>{error}</p>
          <button type="button" onClick={load} className="mt-2 min-h-11 font-medium underline underline-offset-2">
            Erneut laden
          </button>
        </div>
      )}

      {data && (
        <div className="mb-5 flex flex-wrap gap-x-5 gap-y-2 border-y border-admin-border py-3 text-ui text-admin-fg2">
          <span><strong className="text-admin-fg">{data.summary.spots}</strong> Spots gesamt</span>
          <span><strong className="text-admin-fg">{data.summary.publication.published}</strong> veröffentlicht</span>
          <span><strong className="text-admin-fg">{data.summary.publication.draft}</strong> Entwürfe</span>
          <span><strong className="text-admin-fg">{data.summary.content.verified}</strong> inhaltlich geprüft</span>
          <span><strong className="text-admin-fg">{data.summary.single_spot_regions}</strong> Ein-Spot-Regionen</span>
          <span><strong className="text-admin-fg">{data.summary.unassigned}</strong> ohne Region</span>
        </div>
      )}

      {!data && !error ? (
        <p role="status" className="py-10 text-center text-ui text-admin-muted">Abdeckung wird berechnet …</p>
      ) : data && rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-admin-border px-4 py-10 text-center">
          <p className="text-ui font-medium text-admin-fg">Keine offenen Abdeckungslücken</p>
          <p className="mt-1 text-caption text-admin-muted">Wechsle zu „Alle Zellen zeigen“, um den vollständigen Katalog zu sehen.</p>
        </div>
      ) : data ? (
        <TableFrame>
          <Table className="min-w-[980px]">
            <Thead>
              <Tr>
                <Th>Region</Th>
                <Th>Sport</Th>
                <Th className="text-right">Gesamt</Th>
                <Th>Veröffentlichung</Th>
                <Th>Inhaltsreife</Th>
                <Th>Relevanz</Th>
              </Tr>
            </Thead>
            <Tbody>
              {rows.map((row) => (
                <Tr key={`${row.region_id}:${row.sport}`}>
                  <Td>
                    <Link to={`/admin/region/${row.region_id}/edit`} className="font-medium text-admin-fg underline-offset-2 hover:underline">
                      {row.region_name}
                    </Link>
                    <p className="mt-0.5 text-caption text-admin-muted">
                      {[row.country, `${row.region_spot_count} Spot${row.region_spot_count === 1 ? "" : "s"}`].filter(Boolean).join(" · ")}
                    </p>
                    {row.region_spot_count === 1 && <Badge tone="warning" className="mt-1">Ein-Spot-Region</Badge>}
                  </Td>
                  <Td>{sportLabel(row.sport)}</Td>
                  <Td className="admin-mono text-right font-medium">{row.total || "—"}</Td>
                  <Td className="text-caption">
                    {row.total ? `Live ${row.publication.published} · Entwurf ${row.publication.draft} · Archiv ${row.publication.archived}` : "—"}
                  </Td>
                  <Td className="text-caption">
                    {row.total ? `Geprüft ${row.content.verified} · Offen ${row.total - row.content.verified}` : "—"}
                  </Td>
                  <Td className="text-caption">
                    {row.total
                      ? `World Class ${row.classification.world_class} · Reise ${row.classification.worth_trip} · Check ${row.classification.worth_checking_out} · Offen ${row.classification.unranked}`
                      : "—"}
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </TableFrame>
      ) : null}
    </div>
  );
}
