/*
 * References:
 *   https://leafletjs.com/reference.html
 *   https://leafletjs.com/examples/map-panes/
 *   https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9
 *   https://www.arcgis.com/home/item.html?id=a842e359856a4365b1ddf8cc34fde079
 *   https://operations.osmfoundation.org/policies/tiles/
 */

const BOULDER = [40.015, -105.2705];

// Wildfire covers Boulder County, so its map stops at the state line. The other
// disasters each cover one county, with bounds from the Census TIGERweb county layer.
export const COLORADO = L.latLngBounds([36.99, -109.06], [41.0, -102.04]);

export const REGIONS = {
  fire: { name: "Colorado", bounds: COLORADO },
  earthquake: { name: "Los Angeles County", bounds: L.latLngBounds([32.75, -118.952], [34.823, -117.646]) },
  hurricane: { name: "Miami-Dade County", bounds: L.latLngBounds([25.137, -80.874], [25.979, -80.063]) },
  flood: { name: "New York City", bounds: L.latLngBounds([40.4774, -74.2591], [40.9176, -73.7004]) },
};

let region = REGIONS.fire;

export function currentRegion() {
  return region;
}

export const map = L.map("map", {
  maxBounds: COLORADO,
  maxBoundsViscosity: 1,
  // Quarter-level steps and a longer wheel distance per level, so a scroll
  // eases in instead of jumping a whole zoom level.
  zoomSnap: 0.25,
  zoomDelta: 0.5,
  wheelPxPerZoomLevel: 200,
}).setView(BOULDER, 12);

// Can't zoom out past the point where the region fills the window. The minimum
// is reset first because getBoundsZoom never goes below the current minimum.
function limitZoomOut() {
  map.setMinZoom(0);
  map.setMinZoom(map.getBoundsZoom(region.bounds, true));
}
limitZoomOut();
map.on("resize", limitZoomOut);

// Moves the map to a disaster's region and keeps it there. The old bounds come
// off first, or they'd hold the map back from the new region.
export function setRegion(disaster) {
  region = REGIONS[disaster];
  map.setMaxBounds(null);
  if (disaster === "fire") {
    map.setView(BOULDER, 12, { animate: false });
  } else {
    map.fitBounds(region.bounds, { animate: false });
  }
  map.setMaxBounds(region.bounds);
  limitZoomOut();
}

// Data rasters (hazard, fuels, density) draw above the basemap but under
// polygons; points draw above polygons so markers inside a perimeter stay clickable.
map.createPane("rasters").style.zIndex = 300;
map.createPane("points").style.zIndex = 450;

// Satellite imagery has no place names, so a few hardcoded ones ride on top of
// the data layers. The streets basemap has its own labels and skips this.
const labelsPane = map.createPane("labels");
labelsPane.style.zIndex = 425;
labelsPane.style.pointerEvents = "none";

// Hardcoded on purpose: a few names that matter for wildfire response, each
// shown only at the zooms where it fits without crowding its neighbors.
const PLACES = [
  ["Boulder", 40.015, -105.2705, 9, 12],
  ["Longmont", 40.1672, -105.1019, 9, 13],
  ["Louisville", 39.9778, -105.1319, 10, 13],
  ["Lafayette", 39.9936, -105.0897, 10, 13],
  ["Superior", 39.9528, -105.1686, 10, 13],
  ["Lyons", 40.2244, -105.2705, 9, 13],
  ["Nederland", 39.9614, -105.5108, 9, 13],
  ["CU Boulder Campus", 40.007, -105.2664, 13, 19],
  ["Pearl Street Mall", 40.0186, -105.2767, 14, 19],
  ["Chautauqua Park", 39.9974, -105.2809, 13, 19],
];

const placeLabels = L.layerGroup();
const placeMarkers = PLACES.map(([name, lat, lng, minZoom, maxZoom]) => {
  const text = document.createElement("span");
  text.textContent = name;
  const icon = L.divIcon({ className: "place-label", html: text, iconSize: [0, 0] });
  const marker = L.marker([lat, lng], { icon, pane: "labels", interactive: false });
  return { marker, minZoom, maxZoom };
});

function showPlaceLabels() {
  const zoom = map.getZoom();
  for (const { marker, minZoom, maxZoom } of placeMarkers) {
    if (zoom >= minZoom && zoom <= maxZoom) {
      placeLabels.addLayer(marker);
    } else {
      placeLabels.removeLayer(marker);
    }
  }
}
map.on("zoomend", showPlaceLabels);
showPlaceLabels();

// detectRetina asks for double-resolution tiles on high-density screens.
const basemaps = {
  satellite: L.layerGroup([
    L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 19, detectRetina: true, attribution: "Imagery &copy; Esri" }
    ),
    placeLabels,
  ]),
  streets: L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    detectRetina: true,
    attribution: "&copy; OpenStreetMap contributors",
  }),
};

basemaps.satellite.addTo(map);

document.querySelectorAll("input[name=basemap]").forEach((input) => {
  input.addEventListener("change", () => {
    Object.values(basemaps).forEach((layer) => map.removeLayer(layer));
    basemaps[input.value].addTo(map);
  });
});

// Geometry detail that matches the screen: about half a pixel at the current zoom.
export function viewSimplification() {
  const degreesPerPixel = 360 / (256 * 2 ** map.getZoom());
  return degreesPerPixel / 2;
}

// The current view, trimmed to the region so no layer asks for more than that.
export function viewBbox() {
  const bounds = map.getBounds();
  return {
    west: Math.max(bounds.getWest(), region.bounds.getWest()),
    south: Math.max(bounds.getSouth(), region.bounds.getSouth()),
    east: Math.min(bounds.getEast(), region.bounds.getEast()),
    north: Math.min(bounds.getNorth(), region.bounds.getNorth()),
  };
}
