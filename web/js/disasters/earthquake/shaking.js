/*
 * References:
 *   https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
 *   https://leafletjs.com/examples/geojson/
 */

import { REGIONS, viewBbox, viewSimplification } from "../../map.js";
import { fetchJson, formatDate, isLocalScan, setStatus, showDetails } from "../../util.js";

// USGS ShakeMap intensity areas for the past week's quakes, as Esri's live feed.
// grid_value is the area's highest Modified Mercalli intensity.
const SHAKING_URL =
  "https://services9.arcgis.com/RHVPKKiFTONKtxq3/arcgis/rest/services/USGS_Seismic_Data_v1/FeatureServer/1/query";
const FIELDS = ["mag", "grid_value", "updated"].join(",");
const REGION = REGIONS.earthquake;
// Same simplification fire perimeters use for the statewide download.
const REGION_SIMPLIFICATION = 0.001;

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
  if (p.grid_value != null) {
    intensity = `MMI ${p.grid_value}`;
  }

  showDetails(p.mag != null ? `M${p.mag} shaking` : "Shaking", [
    ["Intensity", intensity],
    ["Updated", formatDate(p.updated)],
  ]);
}

const layer = L.geoJSON(null, {
  style: (f) => ({
    color: intensityColor(f.properties.grid_value),
    weight: 1,
    fillOpacity: 0.3,
  }),
  onEachFeature: (f, l) => l.on("click", () => showShaking(f.properties)),
});

function queryUrl(extra) {
  const params = new URLSearchParams({
    // Below IV hardly anyone feels it, and every small quake's rings would
    // otherwise stack into one green sheet over the city.
    where: "grid_value >= 4",
    outFields: FIELDS,
    geometryPrecision: "5",
    f: "geojson",
  });
  for (const [key, value] of Object.entries(extra)) {
    params.set(key, value);
  }
  return `${SHAKING_URL}?${params}`;
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
    setStatus("earthquake-shaking", `${layer.getLayers().length} in ${REGION.name}`);
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

  setStatus("earthquake-shaking", "loading…");
  try {
    const data = await fetchJson(url);
    layer.clearLayers().addData(data);
    hasStateData = !local;
    const scope = local ? "in view" : `in ${REGION.name}`;
    setStatus("earthquake-shaking", `${data.features.length} ${scope}`);
  } catch (err) {
    setStatus("earthquake-shaking", "unavailable");
    console.error("earthquake-shaking", err);
  }
}

export const shaking = { name: "earthquake-shaking", layer, load, reloadOnMove: true, url: SHAKING_URL };
