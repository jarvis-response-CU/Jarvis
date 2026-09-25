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

let run = null; // { result, overlay, canvas, wind }
let playTimer = null;

function formatMinutes(total) {
  const h = Math.floor(total / 60);
  const m = total % 60;
  return h ? `${h} h ${m} min` : `${m} min`;
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
  timeLabel.textContent = `${formatMinutes(minute)} · ${hectares.toLocaleString()} ha burned`;
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
  stop();
  if (run) {
    map.removeLayer(run.overlay);
  }
  run = null;
  controls.hidden = true;
  status.textContent = "";
}

async function lightFire(latlng) {
  delete map.getContainer().dataset.clickClaimed;
  map.getContainer().style.cursor = "";
  clear();
  status.textContent = "Getting wind…";

  let wind;
  try {
    const weather = await weatherAt(latlng.lat, latlng.lng);
    wind = weather.wind;
  } catch (err) {
    console.warn("simulation wind", err);
    wind = { speedMps: 0, fromDeg: 0, label: "unavailable, running with no wind" };
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
      }),
    });
  } catch (err) {
    status.textContent = "Simulation failed";
    console.error("simulation", err);
    return;
  }

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
  showDetails("Simulated fire", [
    ["Ignition", `${latlng.lat.toFixed(4)}, ${latlng.lng.toFixed(4)}`],
    ["Duration", formatMinutes(result.duration_min)],
    ["Wind (NWS, held constant)", wind.label],
    ["Model", "Beta: wind-driven cellular automaton (Ebby & Farazmand 2025); ignores fuel, terrain and humidity"],
    ["Grid", `${result.cell_m.toFixed(0)} m cells`],
  ]);
  drawFrame(0);
  play();
}

startButton.addEventListener("click", () => {
  // Tells the point report to ignore the click that lights the fire.
  map.getContainer().dataset.clickClaimed = "true";
  map.getContainer().style.cursor = "crosshair";
  status.textContent = "Click the map to light a fire";
  map.once("click", (event) => lightFire(event.latlng));
});

slider.addEventListener("input", () => {
  stop();
  drawFrame(Number(slider.value));
});
playButton.addEventListener("click", play);
clearButton.addEventListener("click", clear);
