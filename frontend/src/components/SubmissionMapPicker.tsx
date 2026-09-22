import { useEffect } from "react";
import { CircleMarker, MapContainer, TileLayer, useMap, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { CARTO_ATTRIBUTION, CARTO_VOYAGER, cartoTileUrl } from "../lib/basemaps";

function MapControls({
  center, onPick,
}: {
  center: [number, number];
  onPick: (lat: number, lon: number) => void;
}) {
  const map = useMap();
  const [centerLat, centerLon] = center;
  useEffect(() => { map.setView([centerLat, centerLon], Math.max(map.getZoom(), 8)); }, [map, centerLat, centerLon]);
  useMapEvents({ click(event) { onPick(
    Number(event.latlng.lat.toFixed(5)), Number(event.latlng.lng.toFixed(5))
  ); } });
  return null;
}

export default function SubmissionMapPicker({
  center, position, onPick,
}: {
  center: [number, number];
  position: [number, number] | null;
  onPick: (lat: number, lon: number) => void;
}) {
  return (
    <div className="h-56 overflow-hidden rounded-[14px] border border-line" aria-label="Karte zur Auswahl der Spotposition">
      <MapContainer center={center} zoom={8} scrollWheelZoom={false} className="h-full w-full">
        <TileLayer url={cartoTileUrl(CARTO_VOYAGER)} attribution={CARTO_ATTRIBUTION} />
        <MapControls center={center} onPick={onPick} />
        {position && <CircleMarker center={position} radius={9} pathOptions={{ color: "#fff", weight: 3, fillColor: "#E0823C", fillOpacity: 1 }} />}
      </MapContainer>
    </div>
  );
}
