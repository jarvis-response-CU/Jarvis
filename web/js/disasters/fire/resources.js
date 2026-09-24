import { map, viewBbox } from "../../map.js";
import { fetchJson, setStatus, showDetails } from "../../util.js";

const OVERPASS_URL = "https://overpass-api.de/api/interpreter";
const MIN_ZOOM = 11;

// Stations and water share one Overpass query; each entry knows how to ask
// for its features and how to recognise them in the combined response.
const kinds = [
  {
    name: "stations",
    layer: L.layerGroup(),
    color: "#dc2626",
    filter: (bbox) => `nwr["amenity"="fire_station"](${bbox});`,
    matches: (tags) => tags.amenity === "fire_station",
    title: () => "Fire station",
  },
  {
    name: "water",
    layer: L.layerGroup(),
    color: "#2563eb",
    filter: (bbox) => `nwr["natural"="water"]["water"~"^(reservoir|lake)$"](${bbox});`,
    matches: (tags) => tags.natural === "water",
    title: (tags) => (tags.water === "reservoir" ? "Reservoir" : "Lake"),
  },
];

function marker(element, color, title) {
  const lat = element.lat ?? element.center?.lat;
  const lon = element.lon ?? element.center?.lon;
  const tags = element.tags || {};
  return L.circleMarker([lat, lon], {
    pane: "points",
    radius: 6,
    color: "#fff",
    weight: 1.5,
    fillColor: color,
    fillOpacity: 0.95,
  }).on("click", () =>
    showDetails(tags.name || title, [
      ["Type", title],
      ["Operator", tags.operator],
      ["Address", [tags["addr:housenumber"], tags["addr:street"], tags["addr:city"]].filter(Boolean).join(" ")],
      ["Phone", tags.phone],
      ["Location", `${lat.toFixed(4)}, ${lon.toFixed(4)}`],
    ])
  );
}

let inflight;

async function loadVisibleKinds() {
  const visible = kinds.filter((k) => map.hasLayer(k.layer));
  if (visible.length === 0) return;

  if (map.getZoom() < MIN_ZOOM) {
    for (const k of kinds) k.layer.clearLayers();
    for (const k of visible) setStatus(k.name, "zoom in");
    return;
  }

  const { west, south, east, north } = viewBbox();
  const bbox = `${south},${west},${north},${east}`;
  const query = `[out:json][timeout:25];(${visible.map((k) => k.filter(bbox)).join("")});out center tags;`;

  inflight?.abort();
  inflight = new AbortController();
  for (const k of visible) setStatus(k.name, "loading…");
  try {
    const data = await fetchJson(OVERPASS_URL, {
      method: "POST",
      body: new URLSearchParams({ data: query }),
      signal: inflight.signal,
    });
    for (const k of kinds) k.layer.clearLayers();
    for (const element of data.elements) {
      const tags = element.tags || {};
      const kind = kinds.find((k) => k.matches(tags));
      kind?.layer.addLayer(marker(element, kind.color, kind.title(tags)));
    }
    for (const k of visible) setStatus(k.name, `${k.layer.getLayers().length} in view`);
  } catch (err) {
    if (err.name === "AbortError") return;
    for (const k of visible) setStatus(k.name, "unavailable");
    console.error("overpass", err);
  }
}

// Overpass gives each IP only a couple of query slots, and aborting a fetch
// doesn't free the slot server-side, so bursts of triggers collapse into one query.
let timer;

function scheduleLoad() {
  clearTimeout(timer);
  timer = setTimeout(loadVisibleKinds, 400);
}

export const [stations, water] = kinds.map((k) => ({
  name: k.name,
  layer: k.layer,
  load: scheduleLoad,
  reloadOnMove: true,
}));
