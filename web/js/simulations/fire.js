/*
 * References:
 *   https://arxiv.org/abs/2509.16018
 *   https://developer.mozilla.org/en-US/docs/Web/API/ImageData
 *   https://leafletjs.com/reference.html#imageoverlay
 *   https://www.weather.gov/documentation/services-web-api
 */

import { map } from "../map.js";
import { fetchJson, showDetails } from "../util.js";
import { weatherAt } from "../disasters/fire/weather.js";

const BURNED_COLOR = [234, 88, 12, 150]; // translucent orange (RGBA)
const PLAY_SECONDS = 8;
const SQ_METERS_PER_ACRE = 4046.86;
const MPS_TO_MPH = 2.23694;
const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

const startButton = document.getElementById("sim-start");
const hoursSelect = document.getElementById("sim-hours");
const status = document.getElementById("sim-status");
const controls = document.getElementById("sim-controls");
const slider = document.getElementById("sim-time");
const playButton = document.getElementById("sim-play");
const clearButton = document.getElementById("sim-clear");
const timeValue = document.getElementById("sim-time-value");
const timeEnd = document.getElementById("sim-time-end");
const summary = document.getElementById("sim-summary");
const statArea = document.getElementById("sim-stat-area");
const statProperties = document.getElementById("sim-stat-properties");
const statExposed = document.getElementById("sim-stat-exposed");
const statLoss = document.getElementById("sim-stat-loss");
const damageNote = document.getElementById("sim-damage-note");
const notesList = document.getElementById("sim-notes");
const windSource = document.getElementById("sim-wind-source");
const windCustom = document.getElementById("sim-wind-custom");
const windSpeedInput = document.getElementById("sim-wind-speed");
const windFromInput = document.getElementById("sim-wind-from");
const enhancedBox = document.getElementById("sim-enhanced-damage-fire");
const enhancedStatus = document.getElementById("sim-enhanced-damage-fire-status");

let run = null; // { result, overlay, canvas, wind, burnedByMinute }
let playTimer = null;
let runId = 0;

function formatMinutes(total) {
  const h = Math.floor(total / 60);
  const m = total % 60;
  return h ? `${h} h ${m} min` : `${m} min`;
}

function formatDollars(amount) {
  if (amount >= 1e9) {
    return `$${(amount / 1e9).toFixed(2)}B`;
  }
  if (amount >= 1e6) {
    return `$${(amount / 1e6).toFixed(1)}M`;
  }
  return `$${Math.round(amount / 1e3)}K`;
}

// "12 mph toward NE". People picture a fire being pushed, so the UI says where
// the wind blows TOWARD; the backend and weather data use where it comes FROM.
function describeWind(speedMps, fromDeg) {
  const mph = Math.round(speedMps * MPS_TO_MPH);
  if (mph === 0) return "Calm";
  const toward = (fromDeg + 180) % 360;
  return `${mph} mph toward ${COMPASS[Math.round(toward / 45) % 8]}`;
}

// How many cells have burned by each minute, counted once per run so moving
// the slider is a lookup instead of a recount.
function countBurnedByMinute(result) {
  const counts = new Array(result.duration_min + 1).fill(0);
  for (let i = 2; i < result.cells.length; i += 3) {
    counts[Math.min(result.cells[i], result.duration_min)] += 1;
  }
  for (let m = 1; m < counts.length; m++) counts[m] += counts[m - 1];
  return counts;
}

// The by-minute damage lists can end a minute early; past the end, the last value holds.
function atMinute(list, minute) {
  return list[Math.min(minute, list.length - 1)];
}

// Draws every cell that has ignited by `minute` into the run's canvas.
function drawFrame(minute) {
  const { result, canvas, overlay } = run;
  const ctx = canvas.getContext("2d");
  const image = ctx.createImageData(result.cols, result.rows);
  const cells = result.cells;
  for (let i = 0; i < cells.length; i += 3) {
    const row = cells[i];
    const col = cells[i + 1];
    const ignitionMinute = cells[i + 2];
    if (ignitionMinute > minute) {
      continue;
    }
    // Row 0 is the south edge, but canvas row 0 is the top.
    const canvasRow = result.rows - 1 - row;
    const pixelIndex = canvasRow * result.cols + col;
    image.data.set(BURNED_COLOR, pixelIndex * 4);
  }
  ctx.putImageData(image, 0, 0);
  overlay.setUrl(canvas.toDataURL());
  showStats(minute);
}

// Fills the stat cards for `minute`.
function showStats(minute) {
  const { result, burnedByMinute } = run;
  timeValue.textContent = formatMinutes(minute);

  const acres = (burnedByMinute[minute] * result.cell_m ** 2) / SQ_METERS_PER_ACRE;
  statArea.textContent = `${Math.round(acres).toLocaleString()} acres`;

  const damage = result.damage;
  if (damage) {
    const byMinute = damage.by_minute;
    statProperties.textContent = atMinute(byMinute.properties, minute).toLocaleString();
    statExposed.textContent = formatDollars(atMinute(byMinute.exposed_value, minute));
    statLoss.textContent = formatDollars(atMinute(byMinute.expected_loss, minute));
  } else {
    statProperties.textContent = statExposed.textContent = statLoss.textContent = "N/A";
  }
}

// The assumptions and limits behind the numbers, from the backend where it says.
function showNotes(result) {
  const notes = [
    ...(result.model?.assumptions ?? ["wind held constant", "fuel, terrain and humidity omitted"]),
    ...(result.damage_model?.limitations ?? []),
  ];
  notesList.replaceChildren(
    ...notes.map((text) => {
      const item = document.createElement("li");
      item.textContent = text.charAt(0).toUpperCase() + text.slice(1);
      return item;
    })
  );
}

function stop() {
  clearInterval(playTimer);
  playTimer = null;
  playButton.textContent = "Play";
}

function play() {
  if (playTimer) {
    stop();
    return;
  }
  const max = Number(slider.max);
  if (Number(slider.value) >= max) {
    slider.value = 0;
  }
  playButton.textContent = "Pause";
  // 20 ticks per second (50 ms interval) spread over PLAY_SECONDS.
  const step = Math.max(1, Math.round(max / (PLAY_SECONDS * 20)));
  playTimer = setInterval(() => {
    const nextMinute = Math.min(max, Number(slider.value) + step);
    slider.value = nextMinute;
    drawFrame(Number(slider.value));
    if (Number(slider.value) >= max) {
      stop();
    }
  }, 50);
}

function clear() {
  runId++;
  stop();
  if (run) {
    map.removeLayer(run.overlay);
  }
  run = null;
  controls.hidden = true;
  status.textContent = "";
  enhancedStatus.textContent = "";
}

async function lightFire(latlng) {
  delete map.getContainer().dataset.clickClaimed;
  map.getContainer().style.cursor = "";
  clear();
  const thisRun = runId;
  const isCustomWind = windSource.value === "custom";
  let wind;
  if (isCustomWind) {
    const speedMps = Number(windSpeedInput.value);
    const fromDeg = Number(windFromInput.value);
    if (!(speedMps >= 0 && speedMps <= 40 && fromDeg >= 0 && fromDeg <= 360)) {
      status.textContent = "Wind speed must be 0-40 m/s and direction 0-360°";
      return;
    }
    wind = { speedMps, fromDeg, label: describeWind(speedMps, fromDeg) };
  } else {
    status.textContent = "Getting wind…";
    try {
      const weather = await weatherAt(latlng.lat, latlng.lng);
      wind = weather.wind;
    } catch (err) {
      console.warn("simulation wind", err);
      wind = { speedMps: 0, fromDeg: 0, label: "unavailable, running with no wind" };
    }
    if (thisRun !== runId) return;
  }

  status.textContent = "Simulating…";
  let result;
  try {
    result = await fetchJson("/api/fire/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lat: latlng.lat,
        lng: latlng.lng,
        hours: Number(hoursSelect.value),
        wind_speed_mps: wind.speedMps,
        wind_from_deg: wind.fromDeg,
        enhanced_damage: enhancedBox.checked,
      }),
    });
  } catch (err) {
    status.textContent = "Simulation failed";
    console.error("simulation", err);
    return;
  }
  if (thisRun !== runId) return;

  const canvas = document.createElement("canvas");
  canvas.width = result.cols;
  canvas.height = result.rows;
  const southWest = [result.bounds.south, result.bounds.west];
  const northEast = [result.bounds.north, result.bounds.east];
  const overlay = L.imageOverlay(canvas.toDataURL(), [southWest, northEast], {
    pane: "points",
    interactive: false,
    className: "sim-overlay",
  }).addTo(map);
  run = { result, canvas, overlay, wind, burnedByMinute: countBurnedByMinute(result) };

  slider.max = result.duration_min;
  slider.value = 0;
  timeEnd.textContent = formatMinutes(result.duration_min);
  summary.textContent = `${describeWind(wind.speedMps, wind.fromDeg)}, ${formatMinutes(result.duration_min)} run`;
  damageNote.hidden = Boolean(result.damage);
  damageNote.textContent = "Building data couldn't be loaded for this area, so damage can't be estimated.";
  showNotes(result);
  controls.hidden = false;
  status.textContent = "";
  const enhancedAvailable = result.damage ? result.damage.enhanced_available : result.inventory?.enhanced_available;
  enhancedStatus.textContent = enhancedBox.checked && !enhancedAvailable ? "no data yet" : "";
  showDetails("Simulated fire", [
    ["Ignition", `${latlng.lat.toFixed(4)}, ${latlng.lng.toFixed(4)}`],
    ["Duration", formatMinutes(result.duration_min)],
    [isCustomWind ? "Wind (custom, held constant)" : "Wind (NWS, held constant)", wind.label],
    ["Model", "Wind-driven cellular automaton (Ebby & Farazmand 2025)"],
    ["Grid", `${result.cell_m.toFixed(0)} m cells`],
    ...inventoryRows(result.damage),
  ]);
  drawFrame(0);
  play();
}

// The numbers are in the stat cards; Details says where they came from.
function inventoryRows(damage) {
  if (!damage) {
    return [["Inventory", "Unavailable: the NSI structure inventory could not be loaded"]];
  }
  const isEnhanced = damage.inventory.includes("boulder_local");
  return [
    ["Inventory", isEnhanced ? "NSI 2026 + Boulder County enhancement" : "NSI 2026"],
    [
      "Loss estimate",
      isEnhanced
        ? "Boulder County assessor wall/roof attributes; loss factors from the 2021 Marshall Fire, which burned in extreme wind"
        : "NSI building type with loss factors from the 2021 Marshall Fire; screening-level and likely high for calmer fires",
    ],
  ];
}

function onLightClick(event) {
  lightFire(event.latlng);
}

startButton.addEventListener("click", () => {
  // Tells the point report to ignore the click that lights the fire.
  map.getContainer().dataset.clickClaimed = "true";
  map.getContainer().style.cursor = "crosshair";
  status.textContent = "Click the map to light a fire";
  map.once("click", onLightClick);
});

windSource.addEventListener("change", () => {
  windCustom.hidden = windSource.value !== "custom";
});
slider.addEventListener("input", () => {
  stop();
  drawFrame(Number(slider.value));
});
playButton.addEventListener("click", play);
clearButton.addEventListener("click", clear);
// Another disaster gets a clean map: no fire, and no "Start a fire" still waiting for a click.
document.getElementById("disaster").addEventListener("change", () => {
  map.off("click", onLightClick);
  delete map.getContainer().dataset.clickClaimed;
  map.getContainer().style.cursor = "";
  clear();
});
