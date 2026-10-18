import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, getAdminWeatherProfiles, type WeatherProfileListItem } from "../lib/api";
import {
  Badge,
  EmptyState,
  PageHeader,
  Select,
  Table,
  TableFrame,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
} from "../components/admin/ui";

const stateLabel: Record<string, string> = {
  none: "Kein Profil",
  coordinates: "Nur Koordinaten",
  incomplete: "Basis unvollständig",
  complete: "Basis vollständig",
  advanced: "Advanced",
};

export default function AdminWeatherProfiles() {
  const [country, setCountry] = useState("");
  const [state, setState] = useState("");
  const [items, setItems] = useState<WeatherProfileListItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    getAdminWeatherProfiles({ country: country || undefined, state: state || undefined })
      .then((result) => setItems(result.items))
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Wetterprofile konnten nicht geladen werden.")
      );
  }, [country, state]);

  return (
    <div>
      <PageHeader
        title="Wetterprofile"
        description="Vollständigkeit der Spot-Wetterprofile — gefiltert nach Land und Profilstatus."
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <Select
          aria-label="Land"
          value={country}
          onChange={(e) => setCountry(e.target.value)}
        >
          <option value="">DE, NL und DK</option>
          <option value="DE">Deutschland</option>
          <option value="NL">Niederlande</option>
          <option value="DK">Dänemark</option>
        </Select>
        <Select
          aria-label="Profilstatus"
          value={state}
          onChange={(e) => setState(e.target.value)}
        >
          <option value="">Alle Profilstatus</option>
          {Object.entries(stateLabel).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </Select>
      </div>

      {error && (
        <p
          role="alert"
          className="mb-4 rounded-md border border-admin-danger-border bg-admin-danger-bg px-3 py-2 text-label text-admin-danger"
        >
          {error}
        </p>
      )}

      <TableFrame>
        <Table>
          <caption className="sr-only">Status aller Spot-Wetterprofile</caption>
          <Thead>
            <tr>
              <Th>Spot</Th>
              <Th>Land</Th>
              <Th>Status</Th>
              <Th>Fehlend</Th>
              <Th>Änderung</Th>
              <Th>Aktion</Th>
            </tr>
          </Thead>
          <Tbody>
            {items.map((item) => (
              <Tr key={item.spot_id} interactive>
                <Td>
                  <span className="font-medium text-admin-fg">{item.spot_name}</span>
                  <span className="block text-caption text-admin-muted">
                    {item.region ?? "Ohne Region"}
                  </span>
                </Td>
                <Td>{item.country ?? "—"}</Td>
                <Td>
                  <Badge
                    tone={
                      item.profile_state === "advanced" || item.profile_state === "complete"
                        ? "success"
                        : item.profile_state === "none"
                          ? "danger"
                          : "warning"
                    }
                  >
                    {stateLabel[item.profile_state] ?? item.profile_state}
                  </Badge>
                </Td>
                <Td className="text-caption">
                  {[...item.missing, ...item.direction_missing].join(", ") || "—"}
                </Td>
                <Td className="admin-mono text-caption">
                  {item.updated_at ? new Date(item.updated_at).toLocaleString("de-DE") : "—"}
                </Td>
                <Td>
                  <Link
                    className="font-medium text-admin-fg underline underline-offset-2"
                    to={`/admin/weather/${item.spot_id}`}
                  >
                    Profil &amp; Diagnostik
                  </Link>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
        {items.length === 0 && !error && (
          <EmptyState
            title="Keine Wetterprofile"
            description="Für die gewählte Kombination aus Land und Profilstatus gibt es keine Spots."
          />
        )}
      </TableFrame>
    </div>
  );
}
