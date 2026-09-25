/*
 * References:
 *   https://leafletjs.com/reference.html
 *   https://leafletjs.com/examples/map-panes/
 *   https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9
 *   https://www.arcgis.com/home/item.html?id=a842e359856a4365b1ddf8cc34fde079
 *   https://operations.osmfoundation.org/policies/tiles/
 */

const BOULDER = [40.015, -105.2705];

export const map = L.map("map").setView(BOULDER, 12);

// Data rasters (hazard, fuels, density) draw above the basemap but under
// polygons; points draw above polygons so markers inside a perimeter stay clickable.
map.createPane("rasters").style.zIndex = 300;
map.createPane("points").style.zIndex = 450;

// Satellite imagery has no place names, so city/state labels ride on top of
// the data layers. The streets basemap has its own labels and skips this.
const labelsPane = map.createPane("labels");
labelsPane.style.zIndex = 425;
labelsPane.style.pointerEvents = "none";

const basemaps = {
  satellite: L.layerGroup([
    L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 19, attribution: "Imagery &copy; Esri" }
    ),
    L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 19, pane: "labels" }
    ),
  ]),
  streets: L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
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

export function viewBbox() {
  const bounds = map.getBounds();
  return {
    west: bounds.getWest(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    north: bounds.getNorth(),
  };
}
