import { map, viewBbox } from "../../map.js";
import { fetchJson, formatDate, setStatus, showDetails } from "../../util.js";

const HOTSPOTS_URL =
  "https://services9.arcgis.com/RHVPKKiFTONKtxq3/arcgis/rest/services/Satellite_VIIRS_Thermal_Hotspots_and_Fire_Activity/FeatureServer/0/query";
const MIN_ZOOM = 6;

function showHotspot(p) {
  showDetails("Satellite heat detection", [
    ["Detected", formatDate(p.acq_time)],
    ["Hours ago", p.hours_old],
    ["Confidence", p.confidence],
    ["Fire radiative power", p.frp != null ? `${p.frp} MW` : null],
    ["Location", `${p.latitude.toFixed(4)}, ${p.longitude.toFixed(4)}`],
  ]);
}

const layer = L.geoJSON(null, {
  pointToLayer: (f, latlng) =>
    L.circleMarker(latlng, {
      pane: "points",
      radius: 4,
      color: "#fbbf24",
      fillColor: f.properties.hours_old < 12 ? "#ef4444" : "#f97316",
      fillOpacity: 0.9,
      weight: 1,
    }),
  onEachFeature: (f, l) => l.on("click", () => showHotspot(f.properties)),
});

async function load() {
  if (map.getZoom() < MIN_ZOOM) {
    layer.clearLayers();
    setStatus("hotspots", "zoom in");
    return;
  }
  setStatus("hotspots", "loading…");
  const { west, south, east, north } = viewBbox();
  const params = new URLSearchParams({
    where: "1=1",
    geometry: `${west},${south},${east},${north}`,
    geometryType: "esriGeometryEnvelope",
    inSR: "4326",
    spatialRel: "esriSpatialRelIntersects",
    outFields: "latitude,longitude,acq_time,hours_old,confidence,frp",
    resultRecordCount: "2000",
    f: "geojson",
  });
  try {
    const data = await fetchJson(`${HOTSPOTS_URL}?${params}`);
    layer.clearLayers().addData(data);
    const capped = data.properties?.exceededTransferLimit ? "+" : "";
    setStatus("hotspots", `${data.features.length}${capped} in view`);
  } catch (err) {
    setStatus("hotspots", "unavailable");
    console.error("hotspots", err);
  }
}

export const hotspots = { name: "hotspots", layer, load, reloadOnMove: true };
