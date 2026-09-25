/*
 * References:
 *   https://www.weather.gov/documentation/services-web-api
 */

import { map } from "../../map.js";
import { fetchJson, isLocalScan, setStatus, showDetails } from "../../util.js";

const ALERTS_URL =
  "https://api.weather.gov/alerts/active?event=Red%20Flag%20Warning,Fire%20Weather%20Watch";
// There are only a handful of fire-weather alerts nationally, so they're
// fetched once and local scan just filters them to the view.
const REFRESH_MS = 10 * 60 * 1000;

function showWarning(p) {
  showDetails(p.event, [
    ["Area", p.areaDesc],
    ["Issued by", p.senderName],
    ["Until", p.ends && new Date(p.ends).toLocaleString()],
    ["Summary", p.headline],
  ]);
}

const layer = L.geoJSON(null, {
  style: { color: "#db2777", weight: 1.5, dashArray: "4 4", fillOpacity: 0.12 },
  onEachFeature: (feature, featureLayer) => {
    featureLayer.on("click", () => showWarning(feature.properties));
  },
});

// One missing zone shouldn't blank the whole layer, so failures become null.
async function fetchZoneGeometry(url) {
  try {
    return (await fetchJson(url)).geometry;
  } catch (err) {
    console.warn("zone skipped", url, err);
    return null;
  }
}

// NWS fire-weather alerts usually come with no geometry, only zone links,
// so each zone's shape is fetched separately.
async function fetchAlertFeatures() {
  const alerts = await fetchJson(ALERTS_URL);

  const zoneUrlSet = new Set();
  for (const alert of alerts.features) {
    if (alert.geometry) {
      continue;
    }
    for (const url of alert.properties.affectedZones) {
      zoneUrlSet.add(url);
    }
  }
  const zoneUrls = Array.from(zoneUrlSet);

  const zoneGeometries = await Promise.all(zoneUrls.map(fetchZoneGeometry));
  const zones = new Map();
  for (let i = 0; i < zoneUrls.length; i++) {
    zones.set(zoneUrls[i], zoneGeometries[i]);
  }

  const alertFeatures = [];
  for (const alert of alerts.features) {
    let geometries;
    if (alert.geometry) {
      geometries = [alert.geometry];
    } else {
      geometries = [];
      for (const url of alert.properties.affectedZones) {
        const geometry = zones.get(url);
        if (geometry) {
          geometries.push(geometry);
        }
      }
    }

    if (geometries.length === 0) {
      continue;
    }
    alertFeatures.push({
      type: "Feature",
      geometry: { type: "GeometryCollection", geometries },
      properties: alert.properties,
    });
  }
  return alertFeatures;
}

let features = [];
let fetchedAt = 0;
let pending = null;

function render() {
  const local = isLocalScan();
  const view = map.getBounds();

  let shown = features;
  if (local) {
    shown = features.filter((feature) => L.geoJSON(feature).getBounds().intersects(view));
  }
  layer.clearLayers();
  layer.addData(shown);

  if (local) {
    setStatus("warnings", `${shown.length} in view · ${features.length} nationally`);
  } else {
    setStatus("warnings", `${features.length} active`);
  }
}

async function load() {
  if (Date.now() - fetchedAt > REFRESH_MS) {
    setStatus("warnings", "loading…");
    try {
      // Share one in-flight request between overlapping loads.
      if (!pending) {
        pending = fetchAlertFeatures().finally(() => {
          pending = null;
        });
      }
      features = await pending;
      fetchedAt = Date.now();
    } catch (err) {
      setStatus("warnings", "unavailable");
      console.error("warnings", err);
      return;
    }
  }
  render();
}

export const warnings = { name: "warnings", layer, load, reloadOnMove: true };
