/*
 * References:
 *   https://www.arcgis.com/home/item.html?id=dece90af1a0242dcbf0ca36d30276aa3
 *   https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
 *   https://leafletjs.com/examples/geojson/
 */

import { map, viewBbox } from "../../map.js";
import { fetchJson, formatDate, setStatus, showDetails } from "../../util.js";

const HOTSPOTS_URL =
  "https://services9.arcgis.com/RHVPKKiFTONKtxq3/arcgis/rest/services/Satellite_VIIRS_Thermal_Hotspots_and_Fire_Activity/FeatureServer/0/query";
const MIN_ZOOM = 6;

function showHotspot(properties) {
  showDetails("Satellite heat detection", [
    ["Detected", formatDate(properties.acq_time)],
    ["Hours ago", properties.hours_old],
    ["Confidence", properties.confidence],
    ["Fire radiative power", properties.frp != null ? `${properties.frp} MW` : null],
    ["Location", `${properties.latitude.toFixed(4)}, ${properties.longitude.toFixed(4)}`],
  ]);
}

const layer = L.geoJSON(null, {
  pointToLayer: (feature, latlng) => {
    const isRecent = feature.properties.hours_old < 12;
    return L.circleMarker(latlng, {
      pane: "points",
      radius: 4,
      color: "#fbbf24",
      fillColor: isRecent ? "#ef4444" : "#f97316",
      fillOpacity: 0.9,
      weight: 1,
    });
  },
  onEachFeature: (feature, marker) => {
    marker.on("click", () => showHotspot(feature.properties));
  },
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
    layer.clearLayers();
    layer.addData(data);
    const capped = data.properties?.exceededTransferLimit ? "+" : "";
    setStatus("hotspots", `${data.features.length}${capped} in view`);
  } catch (err) {
    setStatus("hotspots", "unavailable");
    console.error("hotspots", err);
  }
}

export const hotspots = { name: "hotspots", layer, load, reloadOnMove: true };
