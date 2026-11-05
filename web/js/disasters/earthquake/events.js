/*
 * References:
 *   https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
 *   https://leafletjs.com/examples/geojson/
 */

import { map, viewBbox } from "../../map.js";
import { fetchJson, formatDate, setStatus, showDetails } from "../../util.js";

// Empty until we have the data.
const EVENTS_URL = "";
const MIN_ZOOM = 6;
const DAY_MS = 24 * 60 * 60 * 1000;

function showEvent(properties, latlng) {
  showDetails("Earthquake", [
    ["Magnitude", properties.mag],
    ["Place", properties.place],
    ["Time", formatDate(properties.time)],
    ["Location", `${latlng.lat.toFixed(4)}, ${latlng.lng.toFixed(4)}`],
  ]);
}

const layer = L.geoJSON(null, {
  pointToLayer: (feature, latlng) => {
    const magnitude = feature.properties.mag || 0;
    const isRecent = Date.now() - feature.properties.time < DAY_MS;
    return L.circleMarker(latlng, {
      pane: "points",
      radius: 3 + magnitude * 2,
      color: "#fff",
      fillColor: isRecent ? "#dc2626" : "#f59e0b",
      fillOpacity: 0.85,
      weight: 1,
    });
  },
  onEachFeature: (feature, marker) => {
    marker.on("click", () => showEvent(feature.properties, marker.getLatLng()));
  },
});

async function load() {
  if (map.getZoom() < MIN_ZOOM) {
    layer.clearLayers();
    setStatus("earthquake-events", "zoom in");
    return;
  }
  setStatus("earthquake-events", "loading…");
  const { west, south, east, north } = viewBbox();
  const params = new URLSearchParams({
    where: "1=1",
    geometry: `${west},${south},${east},${north}`,
    geometryType: "esriGeometryEnvelope",
    inSR: "4326",
    spatialRel: "esriSpatialRelIntersects",
    outFields: "mag,place,time",
    resultRecordCount: "2000",
    f: "geojson",
  });
  try {
    const data = await fetchJson(`${EVENTS_URL}?${params}`);
    layer.clearLayers();
    layer.addData(data);
    const capped = data.properties?.exceededTransferLimit ? "+" : "";
    setStatus("earthquake-events", `${data.features.length}${capped} in view`);
  } catch (err) {
    setStatus("earthquake-events", "unavailable");
    console.error("earthquake-events", err);
  }
}

export const events = { name: "earthquake-events", layer, load, reloadOnMove: true, url: EVENTS_URL };
