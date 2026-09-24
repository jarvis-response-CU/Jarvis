import { fetchJson, setStatus, showDetails } from "../../util.js";

const ALERTS_URL =
  "https://api.weather.gov/alerts/active?event=Red%20Flag%20Warning,Fire%20Weather%20Watch";

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
  onEachFeature: (f, l) => l.on("click", () => showWarning(f.properties)),
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
async function load() {
  setStatus("warnings", "loading…");
  try {
    const alerts = await fetchJson(ALERTS_URL);
    const zoneUrls = [...new Set(alerts.features.flatMap((a) => (a.geometry ? [] : a.properties.affectedZones)))];
    const zoneGeometries = await Promise.all(zoneUrls.map(fetchZoneGeometry));
    const zones = new Map(zoneUrls.map((url, i) => [url, zoneGeometries[i]]));

    layer.clearLayers();
    for (const alert of alerts.features) {
      const geometries = alert.geometry
        ? [alert.geometry]
        : alert.properties.affectedZones.map((url) => zones.get(url)).filter(Boolean);
      for (const geometry of geometries) {
        layer.addData({ type: "Feature", geometry, properties: alert.properties });
      }
    }
    setStatus("warnings", `${alerts.features.length} active`);
  } catch (err) {
    setStatus("warnings", "unavailable");
    console.error("warnings", err);
  }
}

export const warnings = { name: "warnings", layer, load, reloadOnMove: false };
