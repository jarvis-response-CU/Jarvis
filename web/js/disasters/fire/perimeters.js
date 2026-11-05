/*
 * References:
 *   https://data-nifc.opendata.arcgis.com/
 *   https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
 */

import { COLORADO, viewBbox, viewSimplification } from "../../map.js";
import { fetchJson, formatDate, isLocalScan, setStatus, showDetails } from "../../util.js";

const PERIMETERS_URL =
  "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0/query";
const FIELDS = [
  "poly_IncidentName", "poly_GISAcres", "poly_DateCurrent", "attr_PercentContained",
  "attr_POOState", "attr_FireCause", "attr_FireDiscoveryDateTime", "attr_IncidentTypeCategory",
].join(",");
// Full-resolution perimeters nationwide are ~30 MB; the same simplification
// keeps the statewide download small.
const STATE_SIMPLIFICATION = 0.001;

function containmentColor(percent) {
  if (percent == null) return "#e2664a";
  if (percent >= 90) return "#9ca3af";
  if (percent >= 50) return "#f59e0b";
  return "#dc2626";
}

export function showPerimeter(p) {
  const type = p.attr_IncidentTypeCategory === "RX" ? "Prescribed burn" : "Wildfire";

  let acres = p.poly_GISAcres;
  if (acres) {
    acres = Math.round(acres).toLocaleString();
  }

  let contained = "Unknown";
  if (p.attr_PercentContained != null) {
    contained = `${p.attr_PercentContained}%`;
  }

  showDetails(p.poly_IncidentName, [
    ["Type", type],
    ["Acres", acres],
    ["Contained", contained],
    ["State", p.attr_POOState?.replace("US-", "")],
    ["Cause", p.attr_FireCause],
    ["Discovered", formatDate(p.attr_FireDiscoveryDateTime)],
    ["Perimeter updated", formatDate(p.poly_DateCurrent)],
  ]);
}

const layer = L.geoJSON(null, {
  style: (f) => ({
    color: containmentColor(f.properties.attr_PercentContained),
    weight: 2,
    fillOpacity: 0.25,
  }),
  onEachFeature: (f, l) => l.on("click", () => showPerimeter(f.properties)),
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
  return `${PERIMETERS_URL}?${params}`;
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
    setStatus("perimeters", `${layer.getLayers().length} in Colorado`);
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

  setStatus("perimeters", "loading…");
  try {
    const data = await fetchJson(url);
    layer.clearLayers().addData(data);
    hasStateData = !local;
    const scope = local ? "in view" : "in Colorado";
    setStatus("perimeters", `${data.features.length} ${scope}`);
  } catch (err) {
    setStatus("perimeters", "unavailable");
    console.error("perimeters", err);
  }
}

// Asks the service directly so a fire outside the current view is still found,
// as long as it's in Colorado.
export async function findFire(name) {
  const escaped = name.toUpperCase().replaceAll("'", "''");
  const params = new URLSearchParams({
    where: `UPPER(poly_IncidentName) LIKE '%${escaped}%'`,
    outFields: FIELDS,
    ...envelope(COLORADO.toBBoxString()),
    orderByFields: "poly_GISAcres DESC",
    resultRecordCount: "1",
    maxAllowableOffset: "0.01",
    f: "geojson",
  });
  const data = await fetchJson(`${PERIMETERS_URL}?${params}`);
  const fire = data.features[0];
  if (!fire) return null;

  const bounds = L.geoJSON(fire).getBounds();
  return { bounds, properties: fire.properties };
}

export const perimeters = { name: "perimeters", layer, load, reloadOnMove: true };
