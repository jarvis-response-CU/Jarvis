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

const startButton = document.getElementById("sim-start");
const hoursSelect = document.getElementById("sim-hours");
const status = document.getElementById("sim-status");
const controls = document.getElementById("sim-controls");
const slider = document.getElementById("sim-time");
const playButton = document.getElementById("sim-play");
const clearButton = document.getElementById("sim-clear");
const timeLabel = document.getElementById("sim-time-label");
const windSource = document.getElementById("sim-wind-source");
const windCustom = document.getElementById("sim-wind-custom");
const windSpeedInput = document.getElementById("sim-wind-speed");
const windFromInput = document.getElementById("sim-wind-from");
const enhancedBox = document.getElementById("sim-enhanced-damage-fire");
const enhancedStatus = document.getElementById("sim-enhanced-damage-fire-status");

let run = null; // { result, overlay, canvas, wind }
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

// Draws every cell that has ignited by `minute` into the run's canvas.
function drawFrame(minute) {
  const { result, canvas, overlay } = run;
  const ctx = canvas.getContext("2d");
  const image = ctx.createImageData(result.cols, result.rows);
  const cells = result.cells;
  let burned = 0;
  for (let i = 0; i < cells.length; i += 3) {
    const row = cells[i];
    const col = cells[i + 1];
    const ignitionMinute = cells[i + 2];
    if (ignitionMinute > minute) {
      continue;
    }
    burned++;
    // Row 0 is the south edge, but canvas row 0 is the top.
    const canvasRow = result.rows - 1 - row;
    const pixelIndex = canvasRow * result.cols + col;
    image.data.set(BURNED_COLOR, pixelIndex * 4);
  }
  ctx.putImageData(image, 0, 0);
  overlay.setUrl(canvas.toDataURL());

  const cellArea = result.cell_m ** 2;
  const hectares = Math.round((burned * cellArea) / 10_000);
  let label = `${formatMinutes(minute)} · ${hectares.toLocaleString()} ha burned`;
  if (result.damage) {
    const damageSoFar = result.damage.by_minute;
    label += ` · ${damageSoFar.properties[minute].toLocaleString()} properties`;
    label += ` · ${formatDollars(damageSoFar.expected_loss[minute])} expected loss`;
  }
  timeLabel.textContent = label;
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
    wind = { speedMps, fromDeg, label: `${speedMps} m/s from ${fromDeg}° (specified)` };
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
  run = { result, canvas, overlay, wind };

  slider.max = result.duration_min;
  slider.value = 0;
  controls.hidden = false;
  status.textContent = "";
  const enhancedAvailable = result.damage ? result.damage.enhanced_available : result.inventory?.enhanced_available;
  enhancedStatus.textContent = enhancedBox.checked && !enhancedAvailable ? "no data yet" : "";
  showDetails("Simulated fire", [
    ["Ignition", `${latlng.lat.toFixed(4)}, ${latlng.lng.toFixed(4)}`],
    ["Duration", formatMinutes(result.duration_min)],
    [isCustomWind ? "Wind (specified, held constant)" : "Wind (NWS, held constant)", wind.label],
    ["Model", "Wind-driven cellular automaton (Ebby & Farazmand 2025); ignores fuel, terrain and humidity"],
    ["Grid", `${result.cell_m.toFixed(0)} m cells`],
    ...damageRows(result.damage),
  ]);
  drawFrame(0);
  play();
}

function damageRows(damage) {
  if (!damage) {
    return [["Inventory", "Unavailable: the NSI structure inventory could not be loaded"]];
  }
  const isEnhanced = damage.inventory.includes("boulder_local");
  const lossNote = isEnhanced
    ? "Enhanced with Boulder County assessor wall/roof attributes; loss factors calibrated from the 2021 Marshall Fire, which burned in extreme wind"
    : "NSI building type with loss factors calibrated from the 2021 Marshall Fire; screening-level estimate and likely high for calmer fires";
  return [
    ["Inventory", isEnhanced ? "NSI 2026 + Boulder County enhancement" : "NSI 2026"],
    ["Properties reached", damage.properties.toLocaleString()],
    ["Exposed building value", formatDollars(damage.exposed_value)],
    ["Expected loss (Beta)", `${formatDollars(damage.expected_loss)}. ${lossNote}`],
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
