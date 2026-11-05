/*
 * References:
 *   https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Counties/FeatureServer/0
 *   https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
 */

import { map } from "../../map.js";
import { fetchJson, setStatus, showDetails } from "../../util.js";

// Empty until we have the data.
const RISK_URL = "";
// The National Risk Index field with each county's earthquake rating.
const RATING_FIELD = "ERQK_RISKR";

// National Risk Index ratings, in the colors FEMA's own layer draws them with.
const RATING_COLORS = {
  "Very High": "#c7445d",
  "Relatively High": "#e07069",
  "Relatively Moderate": "#f0d55d",
  "Relatively Low": "#509bc7",
  "Very Low": "#4d6dbd",
};

// Drawn under the situation layers, and faded as one pane so the border
// two counties share isn't drawn twice as strong.
const pane = map.createPane("earthquake-risk");
pane.style.zIndex = 250;
pane.style.opacity = 0.35;

// "Not Applicable", "No Rating" and "Insufficient Data" counties stay clear.
function ratingStyle(feature) {
  const fillColor = RATING_COLORS[feature.properties[RATING_FIELD]];
  if (!fillColor) {
    return { stroke: false, fillOpacity: 0 };
  }
  return { color: "#fff", weight: 0.5, fillColor, fillOpacity: 1 };
}

function showRisk(p) {
  showDetails("Earthquake risk", [
    ["County", p.COUNTY],
    ["State", p.STATEABBRV],
    ["Rating", p[RATING_FIELD]],
  ]);
}

const layer = L.geoJSON(null, {
  pane: "earthquake-risk",
  style: ratingStyle,
  onEachFeature: (feature, featureLayer) => {
    featureLayer.on("click", () => showRisk(feature.properties));
  },
});

async function load() {
  setStatus("earthquake-risk", "loading…");
  const params = new URLSearchParams({
    // The map stops at Colorado, and the full layer is past the 2000-record cap anyway.
    where: "STATEABBRV = 'CO'",
    outFields: `COUNTY,STATEABBRV,${RATING_FIELD}`,
    maxAllowableOffset: "0.001",
    geometryPrecision: "3",
    f: "geojson",
  });
  try {
    const data = await fetchJson(`${RISK_URL}?${params}`);
    layer.clearLayers().addData(data);
    setStatus("earthquake-risk", `${data.features.length} counties`);
  } catch (err) {
    setStatus("earthquake-risk", "unavailable");
    console.error("earthquake-risk", err);
  }
}

export const risk = { name: "earthquake-risk", layer, load, reloadOnMove: false, url: RISK_URL };
