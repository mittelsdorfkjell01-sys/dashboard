import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, getAdminWeatherProfiles, type WeatherProfileListItem } from "../lib/api";
import { Badge, PageHeader } from "../components/admin/ui";

const stateLabel: Record<string, string> = { none: "Kein Profil", coordinates: "Nur Koordinaten", incomplete: "Basis unvollständig", complete: "Basis vollständig", advanced_draft: "Advanced-Entwurf", advanced_released: "Advanced freigegeben" };

export default function AdminWeatherProfiles() {
  const [country, setCountry] = useState("");
  const [state, setState] = useState("");
  const [items, setItems] = useState<WeatherProfileListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setError(null);
    getAdminWeatherProfiles({ country: country || undefined, state: state || undefined })
      .then((result) => setItems(result.items))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Wetterprofile konnten nicht geladen werden."));
  }, [country, state]);
  const select = "h-9 rounded-md border border-admin-border-strong bg-admin-surface px-3 text-ui text-admin-fg";
  return <div>
    <PageHeader title="Wetterprofile" />
    <div className="mb-5 flex flex-wrap gap-2">
      <select aria-label="Land" value={country} onChange={(e) => setCountry(e.target.value)} className={select}>
        <option value="">DE, NL und DK</option><option value="DE">Deutschland</option><option value="NL">Niederlande</option><option value="DK">Dänemark</option>
      </select>
      <select aria-label="Profilstatus" value={state} onChange={(e) => setState(e.target.value)} className={select}>
        <option value="">Alle Profilstatus</option>{Object.entries(stateLabel).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select>
    </div>
    {error && <p role="alert" className="mb-4 text-admin-danger">{error}</p>}
    <div className="overflow-x-auto rounded-md border border-admin-border">
      <table className="w-full text-left text-ui"><caption className="sr-only">Status aller Spot-Wetterprofile</caption>
        <thead className="bg-admin-hover text-admin-muted"><tr><th className="p-3">Spot</th><th className="p-3">Land</th><th className="p-3">Status</th><th className="p-3">Fehlend</th><th className="p-3">Änderung</th><th className="p-3">Aktion</th></tr></thead>
        <tbody>{items.map((item) => <tr key={item.spot_id} className="border-t border-admin-border">
          <td className="p-3"><span className="font-medium">{item.spot_name}</span><span className="block text-caption text-admin-muted">{item.region ?? "Ohne Region"}</span></td>
          <td className="p-3">{item.country ?? "—"}</td>
          <td className="p-3"><Badge tone={item.profile_state === "advanced_released" || item.profile_state === "complete" ? "success" : item.profile_state === "none" ? "danger" : "warning"}>{stateLabel[item.profile_state] ?? item.profile_state}</Badge></td>
          <td className="p-3 text-caption">{item.missing.join(", ") || "—"}</td>
          <td className="p-3 text-caption">{item.updated_at ? new Date(item.updated_at).toLocaleString("de-DE") : "—"}</td>
          <td className="p-3"><Link className="text-admin-primary underline" to={`/admin/weather/${item.spot_id}`}>Profil & Diagnostik</Link></td>
        </tr>)}</tbody>
      </table>
    </div>
  </div>;
}
