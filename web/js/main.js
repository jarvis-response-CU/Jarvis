/*
 * References:
 *   https://leafletjs.com/reference.html#map-moveend
 *   https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules
 */

import { map } from "./map.js";
import { setStatus } from "./util.js";
import { fireLayers } from "./disasters/fire/index.js";
import "./search.js";
import "./readout.js";

// Every layer has the same shape: { name, layer, load?, reloadOnMove }.
// reloadOnMove layers fetch for the current view; the rest load the first time
// they're switched on.
const layers = fireLayers;

const loadedOnce = new Set();

function showLayer(entry) {
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

for (const entry of layers) {
  const checkbox = document.querySelector(`input[data-layer="${entry.name}"]`);
  function sync() {
    if (checkbox.checked) {
      showLayer(entry);
    } else {
      hideLayer(entry);
    }
  }
  checkbox.addEventListener("change", sync);
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
const disasterPicker = document.getElementById("disaster");
function showDisasterPanel() {
  for (const panel of document.querySelectorAll("[data-disaster]")) {
    panel.hidden = panel.dataset.disaster !== disasterPicker.value;
  }
}
disasterPicker.addEventListener("change", showDisasterPanel);
showDisasterPanel();
