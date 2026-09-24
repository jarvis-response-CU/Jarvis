import { map } from "./map.js";
import { fetchJson } from "./util.js";

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

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = input.value.trim();
  if (!query) return;
  goToPlace(query);
});
