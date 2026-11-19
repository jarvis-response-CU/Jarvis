/*
 * References:
 *   https://doi.org/10.1193/070113EQS184M
 *   https://leafletjs.com/reference.html#imageoverlay
 */

import { map } from "../map.js";
import { fetchJson, showDetails } from "../util.js";

const SHAKING_COLOR = [22, 163, 74]; // green; alpha scales with PGA
const MAX_ALPHA = 200;
const MIN_ALPHA = 60;
const PGA_FULL_ALPHA_G = 0.5;
const MECHANISM_NAMES = {
  unspecified: "unspecified",
  strike_slip: "strike-slip",
  reverse: "reverse",
  normal: "normal",
};

const startButton = document.getElementById("quake-sim-start");
const magnitudeInput = document.getElementById("quake-sim-magnitude");
const mechanismSelect = document.getElementById("quake-sim-mechanism");
const vs30Input = document.getElementById("quake-sim-vs30");
const status = document.getElementById("quake-sim-status");
const controls = document.getElementById("quake-sim-controls");
const clearButton = document.getElementById("quake-sim-clear");
const enhancedBox = document.getElementById("quake-sim-enhanced-damage");
const enhancedStatus = document.getElementById("quake-sim-enhanced-damage-status");

let run = null; // { overlay }
let runId = 0;

function formatDollars(amount) {
  if (amount >= 1e9) {
    return `$${(amount / 1e9).toFixed(2)}B`;
  }
  if (amount >= 1e6) {
    return `$${(amount / 1e6).toFixed(1)}M`;
  }
  return `$${Math.round(amount / 1e3)}K`;
}

function drawField(result) {
  const canvas = document.createElement("canvas");
  canvas.width = result.cols;
  canvas.height = result.rows;
  const ctx = canvas.getContext("2d");
  const image = ctx.createImageData(result.cols, result.rows);
  const cells = result.cells;
  for (let i = 0; i < cells.length; i += 3) {
    const pga = cells[i + 2] * result.value_scale;
    const alpha = Math.round(MIN_ALPHA + (MAX_ALPHA - MIN_ALPHA) * Math.min(1, pga / PGA_FULL_ALPHA_G));
    // row 0 is the south edge, but canvas row 0 is the top.
    const canvasRow = result.rows - 1 - cells[i];
    image.data.set([...SHAKING_COLOR, alpha], (canvasRow * result.cols + cells[i + 1]) * 4);
  }
  ctx.putImageData(image, 0, 0);
  const southWest = [result.bounds.south, result.bounds.west];
  const northEast = [result.bounds.north, result.bounds.east];
  return L.imageOverlay(canvas.toDataURL(), [southWest, northEast], {
    pane: "points",
    interactive: false,
    className: "sim-overlay",
  }).addTo(map);
}

function clear() {
  runId++;
  if (run) {
    map.removeLayer(run.overlay);
  }
  run = null;
  controls.hidden = true;
  status.textContent = "";
}

function exposureRows(exposure, damage) {
  if (!exposure) {
    return [["Inventory", "Unavailable: the NSI structure inventory could not be loaded"]];
  }
  return [
    ["Inventory", "NSI 2026"],
    ["Properties reached", exposure.properties_affected.toLocaleString()],
    ["Exposed building value", formatDollars(exposure.affected_building_value)],
    ["Expected loss (Beta)", damage
      ? `${formatDollars(damage.expected_loss)}. ${damage.model}`
      : "Unavailable: earthquake building damage model is not implemented"],
  ];
}

async function startEarthquake(latlng) {
  delete map.getContainer().dataset.clickClaimed;
  map.getContainer().style.cursor = "";
  clear();
  const thisRun = runId;
  const magnitude = Number(magnitudeInput.value);
  const vs30 = Number(vs30Input.value);
  if (!(magnitude >= 3 && magnitude <= 8.5)) {
    status.textContent = "Magnitude must be 3.0-8.5";
    return;
  }
  if (!(vs30 >= 150 && vs30 <= 1500)) {
    status.textContent = "Velocity must be 150-1500 m/s";
    return;
  }
  status.textContent = "Simulating…";

  let result;
  try {
    result = await fetchJson("/api/earthquake/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lat: latlng.lat,
        lng: latlng.lng,
        magnitude,
        mechanism: mechanismSelect.value,
        vs30_mps: vs30,
      }),
    });
  } catch (err) {
    status.textContent = "Simulation failed";
    console.error("earthquake simulation", err);
    return;
  }
  if (thisRun !== runId) return;

  run = { overlay: drawField(result) };
  controls.hidden = false;

  const { mechanism } = result.source;
  const maxPga = result.summary.max_pga_g;
  const hectares = Math.round((result.cells.length / 3 * result.cell_m ** 2) / 10_000);
  let label = `M${result.source.magnitude} · ${hectares.toLocaleString()} ha shaken`;
  if (result.exposure) {
    label += ` · ${result.exposure.properties_affected.toLocaleString()} properties`;
  }
  if (result.damage) {
    label += ` · ${formatDollars(result.damage.expected_loss)} expected loss`;
  }
  status.textContent = label;
  showDetails("Simulated earthquake", [
    ["Epicenter", `${result.source.lat.toFixed(4)}, ${result.source.lng.toFixed(4)}`],
    ["Magnitude", `M${magnitude}`],
    ["Mechanism", MECHANISM_NAMES[mechanism]],
    ["Model", "BSSA14 NGA-West2 median PGA"],
    ["Site conditions", result.model.site_model === "vs30_raster"
      ? "NSI/available Vs30 source"
      : `uniform velocity = ${vs30} m/s`],
    ["Grid", `${result.cell_m.toFixed(0)} m cells`],
    ["Maximum median PGA", `${maxPga.toFixed(2)} g`],
    ...exposureRows(result.exposure, result.damage),
  ]);
}

function onStartClick(event) {
  startEarthquake(event.latlng);
}

startButton.addEventListener("click", () => {
  // tells the point report to ignore the click that places the epicenter.
  map.getContainer().dataset.clickClaimed = "true";
  map.getContainer().style.cursor = "crosshair";
  status.textContent = "Click the map to place the epicenter";
  map.once("click", onStartClick);
});

clearButton.addEventListener("click", clear);
enhancedBox.addEventListener("change", () => {
  enhancedStatus.textContent = enhancedBox.checked ? "no data yet" : "";
});
// another disaster gets a clean map: no shaking, and no "Start an earthquake" still waiting for a click.
document.getElementById("disaster").addEventListener("change", () => {
  map.off("click", onStartClick);
  delete map.getContainer().dataset.clickClaimed;
  map.getContainer().style.cursor = "";
  clear();
});
