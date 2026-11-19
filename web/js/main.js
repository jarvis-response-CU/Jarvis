/*
 * References:
 *   https://leafletjs.com/reference.html#map-moveend
 *   https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules
 */

import { map, setRegion } from "./map.js";
import { setStatus } from "./util.js";
import { fireLayers } from "./disasters/fire/index.js";
import { earthquakeLayers } from "./disasters/earthquake/index.js";
import { hurricaneLayers } from "./disasters/hurricane/index.js";
import { floodLayers } from "./disasters/flood/index.js";
import "./ui.js";
import "./search.js";
import "./readout.js";
import "./simulations/fire.js";
import "./simulations/flood.js";
import "./simulations/earthquake.js";

// Every layer has the same shape: { name, layer, load?, reloadOnMove, url? }.
// reloadOnMove layers fetch for the current view; the rest load the first time
// they're switched on. An empty url means the layer has no data source yet.
const layers = [
  ...fireLayers,
  ...earthquakeLayers,
  ...hurricaneLayers,
  ...floodLayers,
];

const loadedOnce = new Set();

function showLayer(entry) {
  if (entry.url === "") {
    setStatus(entry.name, "no data yet");
    return;
  }
  entry.layer.addTo(map);
  if (entry.reloadOnMove) {
    entry.load();
  } else if (entry.load && !loadedOnce.has(entry)) {
    loadedOnce.add(entry);
    entry.load();
  }
}

function hideLayer(entry) {
  map.removeLayer(entry.layer);
  if (entry.reloadOnMove) {
    setStatus(entry.name, "");
  }
}

const disasterPicker = document.getElementById("disaster");
// Registered before the layers below so they load for the new region.
disasterPicker.addEventListener("change", () => setRegion(disasterPicker.value));

// A layer is drawn only while its box is checked and its disaster is picked,
// so switching disasters starts from a clean map.
for (const entry of layers) {
  const checkbox = document.querySelector(`input[data-layer="${entry.name}"]`);
  const panel = checkbox.closest("[data-disaster]");
  function sync() {
    const isPicked = panel.dataset.disaster === disasterPicker.value;
    if (checkbox.checked && isPicked) {
      showLayer(entry);
    } else {
      hideLayer(entry);
    }
  }
  checkbox.addEventListener("change", sync);
  disasterPicker.addEventListener("change", sync);
  sync();
}

function reloadVisible() {
  for (const entry of layers) {
    const isVisible = map.hasLayer(entry.layer);
    if (entry.reloadOnMove && isVisible) {
      entry.load();
    }
  }
}

let moveTimer;
map.on("moveend", () => {
  clearTimeout(moveTimer);
  moveTimer = setTimeout(reloadVisible, 400);
});

document.getElementById("local-scan").addEventListener("change", reloadVisible);

// Each disaster's controls live in <section data-disaster="...">; the picker shows one.
function showDisasterPanel() {
  for (const panel of document.querySelectorAll("[data-disaster]")) {
    panel.hidden = panel.dataset.disaster !== disasterPicker.value;
  }

  // Details from the last disaster don't carry over.
  const hint = document.createElement("p");
  if (disasterPicker.value === "fire") {
    hint.textContent = "Click a fire or marker, or anywhere on the map for fuel, weather and drought.";
  } else {
    hint.textContent = "Click a marker or area on the map for details.";
  }
  document.getElementById("details").replaceChildren(hint);
}
disasterPicker.addEventListener("change", showDisasterPanel);
showDisasterPanel();
