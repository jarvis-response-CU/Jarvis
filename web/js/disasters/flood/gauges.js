/*
 * References:
 *   https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
 *   https://leafletjs.com/examples/geojson/
 */

import { map, viewBbox } from "../../map.js";
import { fetchJson, formatDate, setStatus, showDetails } from "../../util.js";

// USGS and NWS gauges, as Esri's live feed (refreshed about every 15 minutes).
const GAUGES_URL =
  "https://services9.arcgis.com/RHVPKKiFTONKtxq3/arcgis/rest/services/Live_Stream_Gauges_v1/FeatureServer/0/query";
const MIN_ZOOM = 9;
// NWS flood categories the feed reports in "status".
const FLOODING = ["Minor Flood", "Moderate Flood", "Major Flood"];

function showGauge(properties, latlng) {
  let height = null;
  if (properties.stage_ft != null) {
    height = `${properties.stage_ft} ft`;
  }

  showDetails(properties.name || "Stream gauge", [
    ["Water level", height],
    ["Status", properties.status],
    ["Reading", formatDate(properties.lastupdate)],
    ["Location", `${latlng.lat.toFixed(4)}, ${latlng.lng.toFixed(4)}`],
  ]);
}

const layer = L.geoJSON(null, {
  pointToLayer: (feature, latlng) => {
    const isFlooding = FLOODING.includes(feature.properties.status);
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
    outFields: "name,stage_ft,status,lastupdate",
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
