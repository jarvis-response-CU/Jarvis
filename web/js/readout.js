import { map } from "./map.js";
import { fetchJson } from "./util.js";

const coords = document.getElementById("coords");
const address = document.getElementById("address");

// Nominatim asks for at most one request per second, so the address only
// refreshes once the cursor has been still for a moment. Coordinates are
// free and update on every move.
let timer, inflight;

async function lookup(lat, lng) {
  inflight?.abort();
  inflight = new AbortController();
  address.textContent = "Looking up…";
  try {
    const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}&zoom=18`;
    const data = await fetchJson(url, { signal: inflight.signal });
    address.textContent = data.display_name || "No address found";
  } catch (err) {
    if (err.name !== "AbortError") address.textContent = "Lookup unavailable";
  }
}

map.on("mousemove", (event) => {
  const { lat, lng } = event.latlng;
  coords.textContent = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  clearTimeout(timer);
  timer = setTimeout(() => lookup(lat, lng), 600);
});

map.on("mouseout", () => {
  clearTimeout(timer);
  coords.textContent = "—";
  address.textContent = "Move the cursor over the map";
});
