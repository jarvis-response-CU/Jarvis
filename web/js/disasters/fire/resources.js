/*
 * References:
 *   https://www.arcgis.com/home/item.html?id=2c36dbb008844081b017da6fd3d0d28b
 *   https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Detailed_Water_Bodies/FeatureServer/0
 *   https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/
 *   https://developer.mozilla.org/en-US/docs/Web/API/AbortController
 */

import { map, viewBbox } from "../../map.js";
import { fetchJson, setStatus, showDetails } from "../../util.js";

const MIN_ZOOM = 11;

// Fire stations: USGS National Structures Dataset. Water: Esri's hosted copy
// of the USGS National Hydrography Dataset; USGS's own NHD service took
// 10–90+ s per query (September 2026), this copy answers in under a second.
const kinds = {
  stations: {
    url: "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/Structures_Medical_Emergency_Response_v1/FeatureServer/2/query",
    params: { where: "1=1", outFields: "NAME,ADDRESS,CITY,STATE", f: "geojson" },
    color: "#dc2626",
    describe(p) {
      const title = p.NAME || "Fire station";
      const addressParts = [p.ADDRESS, p.CITY, p.STATE].filter(Boolean);
      const rows = [
        ["Type", "Fire / EMS station"],
        ["Address", addressParts.join(", ")],
      ];
      return [title, rows];
    },
  },
  water: {
    url: "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Detailed_Water_Bodies/FeatureServer/0/query",
    // 5 ha minimum skips ponds too small to matter.
    params: {
      where: "FTYPE IN ('Lake/Pond', 'Reservoir') AND SQKM >= 0.05",
      outFields: "NAME,FTYPE,SQKM",
      maxAllowableOffset: "0.0005",
      outSR: "4326",
      f: "geojson",
    },
    color: "#2563eb",
    describe(p) {
      const title = p.NAME?.trim() || p.FTYPE;
      const hectares = p.SQKM * 100;
      const rows = [
        ["Type", p.FTYPE],
        ["Area", `${hectares.toFixed(1)} ha`],
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

function makeEntry(name) {
  const kind = kinds[name];
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

  return { name, layer, load, reloadOnMove: true };
}

export const stations = makeEntry("stations");
export const water = makeEntry("water");
