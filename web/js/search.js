/*
 * References:
 *   https://nominatim.org/release-docs/latest/api/Search/
 *   https://operations.osmfoundation.org/policies/nominatim/
 *   https://leafletjs.com/reference.html#map-fitbounds
 */

import { map } from "./map.js";
import { fetchJson } from "./util.js";
import { findFire, showPerimeter } from "./disasters/fire/perimeters.js";

const form = document.getElementById("search");
const input = document.getElementById("search-input");
const status = document.getElementById("search-status");

L.DomEvent.disableClickPropagation(form);
L.DomEvent.disableScrollPropagation(form);

async function goToPlace(query) {
  status.textContent = "Searching…";
  try {
    const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=${encodeURIComponent(query)}`;
    const [place] = await fetchJson(url);
    if (!place) {
      status.textContent = "No match";
      return;
    }
    const [south, north, west, east] = place.boundingbox.map(Number);
    map.fitBounds([[south, west], [north, east]], { maxZoom: 14 });
    status.textContent = "";
  } catch (err) {
    status.textContent = "Search unavailable";
    console.error("search", err);
  }
}

// Fire names are checked first so "Aspen Acres" finds the fire, not a street.
async function goToFire(query) {
  try {
    const fire = await findFire(query);
    if (!fire) return false;
    map.fitBounds(fire.bounds);
    showPerimeter(fire.properties);
    status.textContent = "";
    return true;
  } catch (err) {
    console.warn("fire search", err);
    return false;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = input.value.trim();
  if (!query) return;
  status.textContent = "Searching…";
  const foundFire = await goToFire(query);
  if (!foundFire) {
    goToPlace(query);
  }
});
