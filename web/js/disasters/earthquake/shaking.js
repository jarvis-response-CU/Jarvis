/*
 * References:
 *   https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
 *   https://leafletjs.com/examples/geojson/
 */

import { COLORADO, viewBbox, viewSimplification } from "../../map.js";
import { fetchJson, formatDate, isLocalScan, setStatus, showDetails } from "../../util.js";

// Empty until we have the data.
const SHAKING_URL = "";
const FIELDS = ["name", "mmi", "updated"].join(",");
// Same simplification fire perimeters use for the statewide download.
const STATE_SIMPLIFICATION = 0.001;

// Modified Mercalli intensity: damage starts around VI, and VIII and up is severe.
function intensityColor(mmi) {
  if (mmi == null) return "#9ca3af";
  if (mmi >= 8) return "#991b1b";
  if (mmi >= 6) return "#ea580c";
  if (mmi >= 4) return "#facc15";
  return "#84cc16";
}

function showShaking(p) {
  let intensity = "Unknown";
  if (p.mmi != null) {
    intensity = `MMI ${p.mmi}`;
  }

  showDetails(p.name || "Shaking", [
    ["Intensity", intensity],
    ["Updated", formatDate(p.updated)],
  ]);
}

const layer = L.geoJSON(null, {
  style: (f) => ({
    color: intensityColor(f.properties.mmi),
    weight: 1,
    fillOpacity: 0.3,
  }),
  onEachFeature: (f, l) => l.on("click", () => showShaking(f.properties)),
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
  return `${SHAKING_URL}?${params}`;
}

// Statewide mode downloads all of Colorado once and pans for free after that;
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
    setStatus("earthquake-shaking", `${layer.getLayers().length} in Colorado`);
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
      ...envelope(COLORADO.toBBoxString()),
      maxAllowableOffset: String(STATE_SIMPLIFICATION),
    });
  }

  setStatus("earthquake-shaking", "loading…");
  try {
    const data = await fetchJson(url);
    layer.clearLayers().addData(data);
    hasStateData = !local;
    const scope = local ? "in view" : "in Colorado";
    setStatus("earthquake-shaking", `${data.features.length} ${scope}`);
  } catch (err) {
    setStatus("earthquake-shaking", "unavailable");
    console.error("earthquake-shaking", err);
  }
}

export const shaking = { name: "earthquake-shaking", layer, load, reloadOnMove: true, url: SHAKING_URL };
