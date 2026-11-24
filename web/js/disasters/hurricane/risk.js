/*
 * References:
 *   https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Census_Tracts/FeatureServer/0
 *   https://www.fema.gov/api/open/v3/NfipClaims
 *   https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/HurricaneEvacZone_gdb/FeatureServer/0
 */

import { map } from "../../map.js";
import { fetchJson, setStatus, showDetails } from "../../util.js";

// Census tracts with FEMA's National Risk Index hurricane rating and the
// NFIP flood claims paid in each, read by the server from the team's data.
const TRACTS_URL = "/api/hurricane/tracts";

// National Risk Index ratings, in the colors FEMA's own layer draws them with.
const RATING_COLORS = {
  "Very High": "#c7445d",
  "Relatively High": "#e07069",
  "Relatively Moderate": "#f0d55d",
  "Relatively Low": "#509bc7",
  "Very Low": "#4d6dbd",
};

// Drawn under the situation layers, and faded as one pane so the border
// two tracts share isn't drawn twice as strong.
const pane = map.createPane("hurricane-risk");
pane.style.zIndex = 250;
pane.style.opacity = 0.35;

const dollars = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

// "Not Applicable", "No Rating" and "Insufficient Data" tracts stay clear.
function ratingStyle(feature) {
  const fillColor = RATING_COLORS[feature.properties.hrcn_riskr];
  if (!fillColor) {
    return { stroke: false, fillOpacity: 0 };
  }
  return { color: "#fff", weight: 0.5, fillColor, fillOpacity: 1 };
}

function showRisk(p) {
  showDetails("Hurricane risk", [
    ["Census tract", p.tractfips],
    ["Rating", p.hrcn_riskr],
    ["Population", p.population?.toLocaleString()],
    ["Expected yearly loss", p.hrcn_ealt != null ? dollars.format(p.hrcn_ealt) : null],
    ["Flood claims", p.claim_count.toLocaleString()],
    ["Claims paid", dollars.format(p.paid)],
  ]);
}

const layer = L.geoJSON(null, {
  pane: "hurricane-risk",
  style: ratingStyle,
  onEachFeature: (feature, featureLayer) => {
    featureLayer.on("click", () => showRisk(feature.properties));
  },
});

async function load() {
  setStatus("hurricane-risk", "loading…");
  try {
    const data = await fetchJson(TRACTS_URL);
    layer.clearLayers().addData(data);
    setStatus("hurricane-risk", `${data.features.length} tracts`);
  } catch (err) {
    setStatus("hurricane-risk", "unavailable");
    console.error("hurricane-risk", err);
  }
}

export const risk = { name: "hurricane-risk", layer, load, reloadOnMove: false, url: TRACTS_URL };

// Miami-Dade's storm surge planning zones: A can flood from a Category 1, E only from a Category 5.
const SURGE_URL = "/api/hurricane/surge_zones";
const SURGE_COLORS = { A: "#7f1d1d", B: "#b91c1c", C: "#ea580c", D: "#f59e0b", E: "#fde047" };

const surgeLayer = L.geoJSON(null, {
  pane: "hurricane-risk",
  style: (f) => ({ stroke: false, fillColor: SURGE_COLORS[f.properties.surge_zone], fillOpacity: 1 }),
  onEachFeature: (feature, featureLayer) => {
    featureLayer.on("click", () => {
      showDetails("Storm surge zone", [["Zone", feature.properties.surge_zone]]);
    });
  },
});

async function loadSurge() {
  setStatus("hurricane-surge", "loading…");
  try {
    const data = await fetchJson(SURGE_URL);
    surgeLayer.clearLayers().addData(data);
    setStatus("hurricane-surge", "zones A–E");
  } catch (err) {
    setStatus("hurricane-surge", "unavailable");
    console.error("hurricane-surge", err);
  }
}

export const surge = { name: "hurricane-surge", layer: surgeLayer, load: loadSurge, reloadOnMove: false, url: SURGE_URL };
