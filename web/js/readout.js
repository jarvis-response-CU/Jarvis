/*
 * References:
 *   https://nominatim.org/release-docs/latest/api/Reverse/
 *   https://operations.osmfoundation.org/policies/nominatim/
 */

import { map } from "./map.js";
import { fetchJson } from "./util.js";

const coords = document.getElementById("coords");
const address = document.getElementById("address");

// Nominatim allows one request per second, so address lookups are debounced.
let timer;
let inflight;

// City and state only; neighborhoods like "University Hill" are left out.
// Rural points have no city, so the county stands in.
const PLACE_KEYS = ["city", "town", "village", "hamlet", "county"];

function placeName(parts = {}) {
  let place = "";
  for (const key of PLACE_KEYS) {
    if (parts[key]) {
      place = parts[key];
      break;
    }
  }

  if (place && parts.state) {
    return `${place}, ${parts.state}`;
  }
  if (place) {
    return place;
  }
  if (parts.state) {
    return parts.state;
  }
  return "No place name here";
}

async function lookup(lat, lng) {
  inflight?.abort();
  inflight = new AbortController();
  address.textContent = "Looking up…";
  try {
    const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}&zoom=10`;
    const data = await fetchJson(url, { signal: inflight.signal });
    address.textContent = placeName(data.address);
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
