import { map } from "../../map.js";
import { showDetails } from "../../util.js";
import { fuelModelAt } from "./fuels.js";
import { droughtAt } from "./drought.js";
import { weatherAt } from "./weather.js";

// Each lookup fails on its own so one slow or missing source doesn't hide the rest.
async function settle(promise, fallback) {
  try {
    return await promise;
  } catch (err) {
    console.warn("point report", err);
    return fallback;
  }
}

let latestClick = 0;

async function showPointReport(lat, lng) {
  const clickId = ++latestClick;
  const location = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
  showDetails("Selected point", [["Location", location], ["Loading", "fuel, weather, drought…"]]);

  const [fuel, weather, drought] = await Promise.all([
    settle(fuelModelAt(lat, lng), "Unavailable"),
    settle(weatherAt(lat, lng), null),
    settle(droughtAt(lat, lng), "Unavailable"),
  ]);
  if (clickId !== latestClick) return;

  showDetails("Selected point", [
    ["Location", location],
    ["Fuel type (LANDFIRE)", fuel],
    ["Weather now", weather?.conditions ?? "Unavailable (NWS covers the US only)"],
    ["Humidity", weather?.humidity],
    ["Wind", weather?.wind.label],
    ["Drought", drought],
  ]);
}

// Clicks on a feature (perimeter, marker) show that feature instead, and a
// click another tool has claimed (like lighting a simulated fire) is skipped.
map.on("click", (event) => {
  if (map.getContainer().dataset.clickClaimed) return;
  const clickedFeature = event.originalEvent.target.classList.contains("leaflet-interactive");
  if (clickedFeature) return;
  showPointReport(event.latlng.lat, event.latlng.lng);
});
