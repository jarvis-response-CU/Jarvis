/*
 * References:
 *   https://doi.org/10.5194/nhess-15-381-2015
 *   https://doi.org/10.1016/j.envsoft.2016.07.008
 *   https://leafletjs.com/reference.html#imageoverlay
 */

import { map } from "../map.js";
import { fetchJson, showDetails } from "../util.js";

const FLOOD_COLOR = [37, 99, 235, 150]; // translucent blue (RGBA)
const PLAY_SECONDS = 8;
const METERS_PER_DEGREE = 111_320;
const DEFAULT_DISPLAY_DEPTH_M = 0.01;

const startButton = document.getElementById("flood-sim-start");
const hoursSelect = document.getElementById("flood-sim-hours");
const status = document.getElementById("flood-sim-status");
const controls = document.getElementById("flood-sim-controls");
const slider = document.getElementById("flood-sim-time");
const playButton = document.getElementById("flood-sim-play");
const clearButton = document.getElementById("flood-sim-clear");
const timeLabel = document.getElementById("flood-sim-time-label");
const modeSelect = document.getElementById("flood-sim-mode");
const areaSelect = document.getElementById("flood-sim-area");
const rainRow = document.getElementById("flood-sim-rain-row");
const rainInput = document.getElementById("flood-sim-rain");
const inflowRow = document.getElementById("flood-sim-inflow-row");
const inflowInput = document.getElementById("flood-sim-inflow");
const infiltrationInput = document.getElementById("flood-sim-infiltration");
const roughnessInput = document.getElementById("flood-sim-roughness");
const enhancedBox = document.getElementById("flood-sim-enhanced-damage");
const enhancedStatus = document.getElementById("flood-sim-enhanced-damage-status");

let run = null; // { result, overlay, canvas }
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

// draws the water at frame `index` into the run's canvas.
function drawFrame(index) {
  const { result, canvas, overlay } = run;
  const ctx = canvas.getContext("2d");
  const image = ctx.createImageData(result.cols, result.rows);
  const cells = result.frames[index];
  const threshold = result.exposure?.display_depth_m ?? DEFAULT_DISPLAY_DEPTH_M;
  let flooded = 0;
  for (let i = 0; i < cells.length; i += 3) {
    if (cells[i + 2] * result.value_scale < threshold) {
      continue;
    }
    flooded++;
    // row 0 is the south edge, but canvas row 0 is the top.
    const canvasRow = result.rows - 1 - cells[i];
    image.data.set(FLOOD_COLOR, (canvasRow * result.cols + cells[i + 1]) * 4);
  }
  ctx.putImageData(image, 0, 0);
  overlay.setUrl(canvas.toDataURL());

  const hectares = Math.round((flooded * result.cell_m ** 2) / 10_000);
  let label = `${formatMinutes(Math.round(result.frame_minutes[index]))} · ${hectares.toLocaleString()} ha flooded`;
  if (result.exposure) {
    label += ` · ${result.exposure.by_frame.properties[index].toLocaleString()} properties`;
  }
  if (result.damage) {
    label += ` · ${formatDollars(result.damage.by_frame.expected_loss[index])} expected loss`;
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
    slider.value = Math.min(max, Number(slider.value) + step);
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
}

function domainAround(latlng) {
  const halfWidthM = Number(areaSelect.value) / 2;
  const dLat = halfWidthM / METERS_PER_DEGREE;
  const dLng = halfWidthM / (METERS_PER_DEGREE * Math.cos((latlng.lat * Math.PI) / 180));
  return {
    south: latlng.lat - dLat,
    west: latlng.lng - dLng,
    north: latlng.lat + dLat,
    east: latlng.lng + dLng,
  };
}

async function startFlood(latlng) {
  delete map.getContainer().dataset.clickClaimed;
  map.getContainer().style.cursor = "";
  clear();
  const thisRun = runId;

  const isPoint = modeSelect.value === "point";
  const rainfall = isPoint ? 0 : Number(rainInput.value);
  const inflow = isPoint ? Number(inflowInput.value) : 0;
  const roughness = Number(roughnessInput.value);
  const infiltration = Number(infiltrationInput.value);
  if (!(rainfall >= 0 && inflow >= 0 && infiltration >= 0 && roughness > 0)) {
    status.textContent = "Enter non-negative rain, inflow and infiltration, and a positive roughness";
    return;
  }
  if (rainfall + inflow <= 0) {
    status.textContent = isPoint ? "Enter an inflow above zero" : "Enter a rainfall above zero";
    return;
  }
  status.textContent = "Simulating…";

  let result;
  try {
    result = await fetchJson("/api/flood/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...domainAround(latlng),
        hours: Number(hoursSelect.value),
        rainfall_mm_hr: rainfall,
        source_lat: isPoint ? latlng.lat : null,
        source_lng: isPoint ? latlng.lng : null,
        point_inflow_m3_s: inflow,
        roughness_n: roughness,
        infiltration_mm_hr: infiltration,
      }),
    });
  } catch (err) {
    status.textContent = "Simulation failed";
    console.error("flood simulation", err);
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
  run = { result, canvas, overlay };

  slider.max = result.frames.length - 1;
  slider.value = 0;
  controls.hidden = false;
  status.textContent = "";
  showDetails("Simulated flood", [
    ["Source", result.source.mode === "point_inflow"
      ? `${result.source.lat.toFixed(4)}, ${result.source.lng.toFixed(4)}`
      : "Rain on grid"],
    ["Duration", formatMinutes(result.duration_min)],
    ["Rainfall", result.inputs.rainfall_mm_hr > 0 ? `${result.inputs.rainfall_mm_hr} mm/h, held constant` : null],
    ["Inflow", result.inputs.point_inflow_m3_s > 0 ? `${result.inputs.point_inflow_m3_s} m³/s` : null],
    ["Model", "Time-resolved weighted cellular automaton (Liu et al. 2015; Guidolin et al. 2016); diffusive-like approximation"],
    ["Grid", `${result.cell_m.toFixed(0)} m cells`],
    ["Maximum depth", `${result.max_depth_m.toFixed(2)} m`],
    ...exposureRows(result.exposure, result.damage),
  ]);
  drawFrame(0);
  play();
}

function exposureRows(exposure, damage) {
  if (!exposure) {
    return [["Inventory", "Unavailable: the NSI structure inventory could not be loaded"]];
  }
  let lossText = "Unavailable: flood damage functions could not be evaluated";
  if (damage) {
    lossText = `${formatDollars(damage.expected_loss)}. FEMA Hazus Flood v6.1 depth-damage curves on maximum depth above the first floor, structure and contents`;
    if (damage.assets_without_loss_model) {
      lossText += `; ${damage.assets_without_loss_model.toLocaleString()} reached properties have no matching curve and are left out`;
    }
  }
  return [
    ["Inventory", "NSI 2026"],
    ["Properties reached", exposure.properties_affected.toLocaleString()],
    ["Exposed building value", formatDollars(exposure.affected_building_value)],
    ["Expected loss (Beta)", lossText],
  ];
}

function onStartClick(event) {
  startFlood(event.latlng);
}

startButton.addEventListener("click", () => {
  // tells the point report to ignore the click that starts the flood.
  map.getContainer().dataset.clickClaimed = "true";
  map.getContainer().style.cursor = "crosshair";
  status.textContent = modeSelect.value === "point" ? "Click the map to place the inflow" : "Click the map to center a flood";
  map.once("click", onStartClick);
});

slider.addEventListener("input", () => {
  stop();
  drawFrame(Number(slider.value));
});
playButton.addEventListener("click", play);
modeSelect.addEventListener("change", () => {
  inflowRow.hidden = modeSelect.value !== "point";
  rainRow.hidden = modeSelect.value === "point";
});
clearButton.addEventListener("click", clear);
enhancedBox.addEventListener("change", () => {
  enhancedStatus.textContent = enhancedBox.checked ? "no data yet" : "";
});
// another disaster gets a clean map: no flood, and no "Start a flood" still waiting for a click.
document.getElementById("disaster").addEventListener("change", () => {
  map.off("click", onStartClick);
  delete map.getContainer().dataset.clickClaimed;
  map.getContainer().style.cursor = "";
  clear();
});
