/*
 * References:
 *   https://droughtmonitor.unl.edu/
 *   https://www.arcgis.com/home/item.html?id=7d4cc55ecaef4ceb82c8d05b13e0d049
 *   https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
 */

import { map } from "../../map.js";
import { fetchJson, setStatus } from "../../util.js";

const DROUGHT_URL =
  "https://services9.arcgis.com/RHVPKKiFTONKtxq3/arcgis/rest/services/US_Drought_Intensity_v1/FeatureServer/3/query";

// US Drought Monitor categories and their official colors.
const CATEGORIES = [
  ["D0", "Abnormally dry", "#ffff00"],
  ["D1", "Moderate drought", "#fcd37f"],
  ["D2", "Severe drought", "#ffaa00"],
  ["D3", "Extreme drought", "#e60000"],
  ["D4", "Exceptional drought", "#730000"],
];

export function droughtLabel(dm) {
  const category = CATEGORIES[dm];
  return category ? `${category[0]} · ${category[1]}` : "No drought";
}

// Categories are nested, so solid fills in one translucent pane show each spot's
// worst category evenly instead of stacking darker.
const pane = map.createPane("drought");
pane.style.zIndex = 250;
pane.style.opacity = 0.35;

function categoryStyle(feature) {
  const category = CATEGORIES[feature.properties.dm];
  let fillColor;
  if (category) {
    fillColor = category[2];
  }
  return { stroke: false, fillColor, fillOpacity: 1 };
}

// Not interactive so clicks fall through to the point report.
const layer = L.geoJSON(null, {
  pane: "drought",
  interactive: false,
  style: categoryStyle,
});

async function load() {
  setStatus("drought", "loading…");
  const params = new URLSearchParams({
    where: "1=1",
    outFields: "dm,ddate",
    maxAllowableOffset: "0.01",
    geometryPrecision: "3",
    f: "geojson",
  });
  try {
    const data = await fetchJson(`${DROUGHT_URL}?${params}`);
    // Mildest first so each worse category paints over the one containing it.
    data.features.sort((a, b) => a.properties.dm - b.properties.dm);
    layer.clearLayers().addData(data);
    const firstFeature = data.features[0];
    if (!firstFeature || !firstFeature.properties.ddate) {
      setStatus("drought", "");
      return;
    }
    // Stored as midnight UTC; local time would slip a day.
    const weekDate = new Date(firstFeature.properties.ddate);
    const weekText = weekDate.toLocaleDateString(undefined, { timeZone: "UTC" });
    setStatus("drought", `week of ${weekText}`);
  } catch (err) {
    setStatus("drought", "unavailable");
    console.error("drought", err);
  }
}

export async function droughtAt(lat, lng) {
  const params = new URLSearchParams({
    where: "1=1",
    geometry: `${lng},${lat}`,
    geometryType: "esriGeometryPoint",
    inSR: "4326",
    spatialRel: "esriSpatialRelIntersects",
    outFields: "dm",
    returnGeometry: "false",
    f: "json",
  });
  const data = await fetchJson(`${DROUGHT_URL}?${params}`);
  let worst = -1;
  for (const feature of data.features) {
    worst = Math.max(worst, feature.attributes.dm);
  }
  return droughtLabel(worst);
}

export const drought = { name: "drought", layer, load, reloadOnMove: false };
