/*
 * References:
 *   https://data-nifc.opendata.arcgis.com/
 *   https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
 */

import { viewBbox, viewSimplification } from "../../map.js";
import { fetchJson, formatDate, isLocalScan, setStatus, showDetails } from "../../util.js";

const PERIMETERS_URL =
  "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0/query";
const FIELDS = [
  "poly_IncidentName", "poly_GISAcres", "poly_DateCurrent", "attr_PercentContained",
  "attr_POOState", "attr_FireCause", "attr_FireDiscoveryDateTime", "attr_IncidentTypeCategory",
].join(",");
// Full-resolution national perimeters are ~30 MB; this brings them under 1 MB.
const NATIONAL_SIMPLIFICATION = 0.001;

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

// Global mode downloads the whole country once and pans for free after that;
// local mode asks for just the view, at detail matched to the zoom level.
let hasNationalData = false;

async function load() {
  const local = isLocalScan();
  if (!local && hasNationalData) return;

  let url;
  if (local) {
    const { west, south, east, north } = viewBbox();
    url = queryUrl({
      geometry: `${west},${south},${east},${north}`,
      geometryType: "esriGeometryEnvelope",
      inSR: "4326",
      spatialRel: "esriSpatialRelIntersects",
      maxAllowableOffset: String(viewSimplification()),
    });
  } else {
    url = queryUrl({ maxAllowableOffset: String(NATIONAL_SIMPLIFICATION) });
  }

  setStatus("perimeters", "loading…");
  try {
    const data = await fetchJson(url);
    layer.clearLayers().addData(data);
    hasNationalData = !local;
    const scope = local ? "in view" : "active";
    setStatus("perimeters", `${data.features.length} ${scope}`);
  } catch (err) {
    setStatus("perimeters", "unavailable");
    console.error("perimeters", err);
  }
}

// Asks the service directly so a fire outside the current view is still found.
export async function findFire(name) {
  const escaped = name.toUpperCase().replaceAll("'", "''");
  const params = new URLSearchParams({
    where: `UPPER(poly_IncidentName) LIKE '%${escaped}%'`,
    outFields: FIELDS,
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
