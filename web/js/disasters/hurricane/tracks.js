/*
 * References:
 *   https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
 *   https://leafletjs.com/examples/geojson/
 */

import { REGIONS, viewBbox, viewSimplification } from "../../map.js";
import { fetchJson, formatDate, isLocalScan, setStatus, showDetails } from "../../util.js";

// Empty until we have the data.
const TRACKS_URL = "";
const FIELDS = ["name", "category", "wind_mph", "pressure_mb", "updated"].join(",");
const REGION = REGIONS.hurricane;
// Same simplification fire perimeters use for the statewide download.
const REGION_SIMPLIFICATION = 0.001;

// Saffir-Simpson category, 0 below hurricane strength; 3 and up is a major hurricane.
function categoryColor(category) {
  if (category == null) return "#9ca3af";
  if (category >= 3) return "#991b1b";
  if (category >= 1) return "#ea580c";
  return "#facc15";
}

function showTrack(p) {
  let category = "Unknown";
  if (p.category > 0) {
    category = `Category ${p.category}`;
  } else if (p.category === 0) {
    category = "Below hurricane strength";
  }

  let wind = null;
  if (p.wind_mph != null) {
    wind = `${p.wind_mph} mph`;
  }

  let pressure = null;
  if (p.pressure_mb != null) {
    pressure = `${p.pressure_mb} mb`;
  }

  showDetails(p.name || "Storm", [
    ["Category", category],
    ["Max wind", wind],
    ["Pressure", pressure],
    ["Updated", formatDate(p.updated)],
  ]);
}

const layer = L.geoJSON(null, {
  style: (f) => ({
    color: categoryColor(f.properties.category),
    weight: 2,
    fillOpacity: 0.2,
  }),
  onEachFeature: (f, l) => l.on("click", () => showTrack(f.properties)),
});

function queryUrl(extra) {
  const params = new URLSearchParams({
    where: "1=1",
    outFields: FIELDS,
    geometryPrecision: "5",
    f: "geojson",
  });
  for (const [key, value] of Object.entries(extra)) {
    params.set(key, value);
  }
  return `${TRACKS_URL}?${params}`;
}

// Region-wide mode downloads the whole county once and pans for free after that;
// local mode asks for just the view, at detail matched to the zoom level.
function envelope(bbox) {
  return {
    geometry: bbox,
    geometryType: "esriGeometryEnvelope",
    inSR: "4326",
    spatialRel: "esriSpatialRelIntersects",
  };
}

let hasStateData = false;

async function load() {
  const local = isLocalScan();
  // Hiding the layer cleared its status, so showing it again puts the count back.
  if (!local && hasStateData) {
    setStatus("hurricane-tracks", `${layer.getLayers().length} in ${REGION.name}`);
    return;
  }

  let url;
  if (local) {
    const { west, south, east, north } = viewBbox();
    url = queryUrl({
      ...envelope(`${west},${south},${east},${north}`),
      maxAllowableOffset: String(viewSimplification()),
    });
  } else {
    url = queryUrl({
      ...envelope(REGION.bounds.toBBoxString()),
      maxAllowableOffset: String(REGION_SIMPLIFICATION),
    });
  }

  setStatus("hurricane-tracks", "loading…");
  try {
    const data = await fetchJson(url);
    layer.clearLayers().addData(data);
    hasStateData = !local;
    const scope = local ? "in view" : `in ${REGION.name}`;
    setStatus("hurricane-tracks", `${data.features.length} ${scope}`);
  } catch (err) {
    setStatus("hurricane-tracks", "unavailable");
    console.error("hurricane-tracks", err);
  }
}

export const tracks = { name: "hurricane-tracks", layer, load, reloadOnMove: true, url: TRACKS_URL };
