const BOULDER = [40.015, -105.2705];

export const map = L.map("map").setView(BOULDER, 12);

// Points draw above polygons so markers inside a perimeter stay clickable.
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

export function viewBbox() {
  const b = map.getBounds();
  return { west: b.getWest(), south: b.getSouth(), east: b.getEast(), north: b.getNorth() };
}
