/*
 * References:
 *   https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
 *   https://developer.mozilla.org/en-US/docs/Web/API/AbortController
 *   https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/FireStation_gdb/FeatureServer/0
 */

import { map, viewBbox } from "../../map.js";
import { fetchJson, setStatus, showDetails } from "../../util.js";

const MIN_ZOOM = 11;

// Hospitals from USGS's national structures; shelters are FEMA's currently open
// ones, so that layer is usually empty outside a disaster.
const kinds = {
  hospitals: {
    url: "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/Structures_Medical_Emergency_Response_v1/FeatureServer/0/query",
    params: { where: "1=1", outFields: "NAME,ADDRESS,CITY,STATE", f: "geojson" },
    color: "#2563eb",
    describe(p) {
      const title = p.NAME || "Hospital";
      const addressParts = [p.ADDRESS, p.CITY, p.STATE].filter(Boolean);
      const rows = [
        ["Type", "Hospital"],
        ["Address", addressParts.join(", ")],
      ];
      return [title, rows];
    },
  },
  shelters: {
    url: "https://gis.fema.gov/arcgis/rest/services/NSS/OpenShelters/FeatureServer/0/query",
    params: { where: "1=1", outFields: "shelter_name,address,city,state", f: "geojson" },
    color: "#16a34a",
    describe(p) {
      const title = p.shelter_name || "Shelter";
      const addressParts = [p.address, p.city, p.state].filter(Boolean);
      const rows = [
        ["Type", "Shelter"],
        ["Address", addressParts.join(", ")],
      ];
      return [title, rows];
    },
  },
};

function marker(latlng, kind, properties) {
  const [title, rows] = kind.describe(properties);
  const location = `${latlng.lat.toFixed(4)}, ${latlng.lng.toFixed(4)}`;
  const detailRows = rows.concat([["Location", location]]);

  const circle = L.circleMarker(latlng, {
    pane: "points",
    radius: 6,
    color: "#fff",
    weight: 1.5,
    fillColor: kind.color,
    fillOpacity: 0.95,
  });
  circle.on("click", () => {
    showDetails(title, detailRows);
  });
  return circle;
}

function makeEntry(key) {
  const kind = kinds[key];
  const name = `hurricane-${key}`;
  const layer = L.layerGroup();
  let inflight;

  async function load() {
    if (map.getZoom() < MIN_ZOOM) {
      layer.clearLayers();
      setStatus(name, "zoom in");
      return;
    }
    const { west, south, east, north } = viewBbox();
    const params = new URLSearchParams({
      ...kind.params,
      geometry: `${west},${south},${east},${north}`,
      geometryType: "esriGeometryEnvelope",
      inSR: "4326",
      spatialRel: "esriSpatialRelIntersects",
    });

    // A slow answer for an old view must not overwrite the current one.
    inflight?.abort();
    inflight = new AbortController();
    setStatus(name, "loading…");
    try {
      const data = await fetchJson(`${kind.url}?${params}`, { signal: inflight.signal });
      layer.clearLayers();
      for (const feature of data.features) {
        const center = L.geoJSON(feature).getBounds().getCenter();
        layer.addLayer(marker(center, kind, feature.properties));
      }
      setStatus(name, `${data.features.length} in view`);
    } catch (err) {
      if (err.name === "AbortError") return;
      setStatus(name, "unavailable");
      console.error(name, err);
    }
  }

  return { name, layer, load, reloadOnMove: true, url: kind.url };
}

export const hospitals = makeEntry("hospitals");
export const shelters = makeEntry("shelters");

// The team's 75 Miami-Dade fire stations, small enough to load whole, once.
const STATIONS_URL = "/api/hurricane/fire_stations";
const station = {
  color: "#dc2626",
  describe(p) {
    const address = [p.address, p.city].filter(Boolean).join(", ");
    return [p.name || "Fire station", [["Type", "Fire station"], ["Address", address]]];
  },
};
const stationLayer = L.layerGroup();

async function loadStations() {
  setStatus("hurricane-fire-stations", "loading…");
  try {
    const data = await fetchJson(STATIONS_URL);
    stationLayer.clearLayers();
    for (const feature of data.features) {
      const [lng, lat] = feature.geometry.coordinates;
      stationLayer.addLayer(marker(L.latLng(lat, lng), station, feature.properties));
    }
    setStatus("hurricane-fire-stations", `${data.features.length} stations`);
  } catch (err) {
    setStatus("hurricane-fire-stations", "unavailable");
    console.error("hurricane-fire-stations", err);
  }
}

export const fireStations = { name: "hurricane-fire-stations", layer: stationLayer, load: loadStations, url: STATIONS_URL };
