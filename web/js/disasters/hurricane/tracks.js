/*
 * References:
 *   https://leafletjs.com/examples/geojson/
 *   https://www.nhc.noaa.gov/aboutsshws.php
 */

import { fetchJson, setStatus, showDetails } from "../../util.js";

// Historical storms that passed near Miami, read by the server from the team's data.
const TRACKS_URL = "/api/hurricane/tracks";
const MPH_PER_KNOT = 1.15078;
// Lowest sustained wind, in knots, for Saffir-Simpson categories 1 through 5.
const CATEGORY_MIN_KNOTS = [64, 83, 96, 113, 137];

// 0 below hurricane strength.
function category(windKnots) {
  if (windKnots == null) return null;
  return CATEGORY_MIN_KNOTS.filter((min) => windKnots >= min).length;
}

// 3 and up is a major hurricane.
function categoryColor(level) {
  if (level == null) return "#9ca3af";
  if (level >= 3) return "#991b1b";
  if (level >= 1) return "#ea580c";
  return "#facc15";
}

function showTrack(p) {
  const level = category(p.max_wind_kt);
  let peak = "Unknown";
  if (level > 0) {
    peak = `Category ${level}`;
  } else if (level === 0) {
    peak = "Below hurricane strength";
  }

  let wind = null;
  if (p.max_wind_kt != null) {
    wind = `${Math.round(p.max_wind_kt * MPH_PER_KNOT)} mph`;
  }

  showDetails(p.name || "Storm", [
    ["Season", p.season],
    ["Peak strength", peak],
    ["Peak wind", wind],
  ]);
}

const layer = L.geoJSON(null, {
  style: (f) => ({
    color: categoryColor(category(f.properties.max_wind_kt)),
    weight: 2,
    opacity: 0.8,
  }),
  onEachFeature: (f, l) => l.on("click", () => showTrack(f.properties)),
});

async function load() {
  setStatus("hurricane-tracks", "loading…");
  try {
    const data = await fetchJson(TRACKS_URL);
    layer.clearLayers().addData(data);
    setStatus("hurricane-tracks", `${data.features.length} storms since 1950`);
  } catch (err) {
    setStatus("hurricane-tracks", "unavailable");
    console.error("hurricane-tracks", err);
  }
}

export const tracks = { name: "hurricane-tracks", layer, load, url: TRACKS_URL };
