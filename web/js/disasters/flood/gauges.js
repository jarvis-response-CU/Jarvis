/*
 * References:
 *   https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
 *   https://leafletjs.com/examples/geojson/
 */

import { map, viewBbox } from "../../map.js";
import { fetchJson, formatDate, setStatus, showDetails } from "../../util.js";

// Empty until we have the data.
const GAUGES_URL = "";
const MIN_ZOOM = 9;

function showGauge(properties, latlng) {
  let height = null;
  if (properties.height_ft != null) {
    height = `${properties.height_ft} ft`;
  }

  showDetails(properties.name || "Stream gauge", [
    ["Water level", height],
    ["Flood stage", properties.flood_stage_ft != null ? `${properties.flood_stage_ft} ft` : null],
    ["Reading", formatDate(properties.time)],
    ["Location", `${latlng.lat.toFixed(4)}, ${latlng.lng.toFixed(4)}`],
  ]);
}

const layer = L.geoJSON(null, {
  pointToLayer: (feature, latlng) => {
    const height = feature.properties.height_ft;
    const floodStage = feature.properties.flood_stage_ft;
    const isFlooding = height != null && floodStage != null && height >= floodStage;
    return L.circleMarker(latlng, {
      pane: "points",
      radius: 5,
      color: "#fff",
      fillColor: isFlooding ? "#dc2626" : "#0284c7",
      fillOpacity: 0.9,
      weight: 1,
    });
  },
  onEachFeature: (feature, marker) => {
    marker.on("click", () => showGauge(feature.properties, marker.getLatLng()));
  },
});

async function load() {
  if (map.getZoom() < MIN_ZOOM) {
    layer.clearLayers();
    setStatus("flood-gauges", "zoom in");
    return;
  }
  setStatus("flood-gauges", "loading…");
  const { west, south, east, north } = viewBbox();
  const params = new URLSearchParams({
    where: "1=1",
    geometry: `${west},${south},${east},${north}`,
    geometryType: "esriGeometryEnvelope",
    inSR: "4326",
    spatialRel: "esriSpatialRelIntersects",
    outFields: "name,height_ft,flood_stage_ft,time",
    resultRecordCount: "2000",
    f: "geojson",
  });
  try {
    const data = await fetchJson(`${GAUGES_URL}?${params}`);
    layer.clearLayers();
    layer.addData(data);
    const capped = data.properties?.exceededTransferLimit ? "+" : "";
    setStatus("flood-gauges", `${data.features.length}${capped} in view`);
  } catch (err) {
    setStatus("flood-gauges", "unavailable");
    console.error("flood-gauges", err);
  }
}

export const gauges = { name: "flood-gauges", layer, load, reloadOnMove: true, url: GAUGES_URL };
