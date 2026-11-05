/*
 * References:
 *   https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
 *   https://developer.mozilla.org/en-US/docs/Web/API/AbortController
 */

import { map, viewBbox } from "../../map.js";
import { fetchJson, setStatus, showDetails } from "../../util.js";

const MIN_ZOOM = 11;

// Both urls are empty until we have the data.
const kinds = {
  hospitals: {
    url: "",
    params: { where: "1=1", outFields: "NAME,ADDRESS,CITY,STATE", f: "geojson" },
    color: "#dc2626",
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
    url: "",
    params: { where: "1=1", outFields: "NAME,ADDRESS,CITY,STATE", f: "geojson" },
    color: "#16a34a",
    describe(p) {
      const title = p.NAME || "Shelter";
      const addressParts = [p.ADDRESS, p.CITY, p.STATE].filter(Boolean);
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
  const name = `flood-${key}`;
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
