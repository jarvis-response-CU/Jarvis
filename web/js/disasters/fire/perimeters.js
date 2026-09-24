import { fetchJson, formatDate, setStatus, showDetails } from "../../util.js";

const PERIMETERS_URL =
  "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0/query";

function containmentColor(percent) {
  if (percent == null) return "#e2664a";
  if (percent >= 90) return "#9ca3af";
  if (percent >= 50) return "#f59e0b";
  return "#dc2626";
}

function showPerimeter(p) {
  showDetails(p.poly_IncidentName, [
    ["Type", p.attr_IncidentTypeCategory === "RX" ? "Prescribed burn" : "Wildfire"],
    ["Acres", p.poly_GISAcres && Math.round(p.poly_GISAcres).toLocaleString()],
    ["Contained", p.attr_PercentContained != null ? `${p.attr_PercentContained}%` : "Unknown"],
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

async function load() {
  setStatus("perimeters", "loading…");
  const params = new URLSearchParams({
    where: "1=1",
    outFields: [
      "poly_IncidentName", "poly_GISAcres", "poly_DateCurrent", "attr_PercentContained",
      "attr_POOState", "attr_FireCause", "attr_FireDiscoveryDateTime", "attr_IncidentTypeCategory",
    ].join(","),
    // Full-resolution perimeters are ~30 MB; this simplification brings it under 1 MB.
    maxAllowableOffset: "0.001",
    geometryPrecision: "4",
    f: "geojson",
  });
  try {
    const data = await fetchJson(`${PERIMETERS_URL}?${params}`);
    layer.clearLayers().addData(data);
    setStatus("perimeters", `${data.features.length} active`);
  } catch (err) {
    setStatus("perimeters", "unavailable");
    console.error("perimeters", err);
  }
}

export function findFireByName(query) {
  const needle = query.toLowerCase();
  return layer
    .getLayers()
    .find((l) => l.feature.properties.poly_IncidentName?.toLowerCase().includes(needle));
}

export const perimeters = { name: "perimeters", layer, load, reloadOnMove: false };
