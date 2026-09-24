import { map } from "./map.js";
import { setStatus } from "./util.js";
import { fireLayers } from "./disasters/fire/index.js";
import "./search.js";
import "./readout.js";

// Every layer has the same shape: { name, layer, load?, reloadOnMove }.
// reloadOnMove layers fetch for the current view; the rest load once at startup.
const layers = fireLayers;

function showLayer(entry) {
  entry.layer.addTo(map);
  if (entry.reloadOnMove) entry.load();
}

function hideLayer(entry) {
  map.removeLayer(entry.layer);
  if (entry.reloadOnMove) setStatus(entry.name, "");
}

for (const entry of layers) {
  const checkbox = document.querySelector(`input[data-layer="${entry.name}"]`);
  const sync = () => (checkbox.checked ? showLayer(entry) : hideLayer(entry));
  checkbox.addEventListener("change", sync);
  sync();
  if (!entry.reloadOnMove) entry.load?.();
}

let moveTimer;
map.on("moveend", () => {
  clearTimeout(moveTimer);
  moveTimer = setTimeout(() => {
    for (const entry of layers) {
      if (entry.reloadOnMove && map.hasLayer(entry.layer)) entry.load();
    }
  }, 400);
});
