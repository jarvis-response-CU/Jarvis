/*
 * References:
 *   https://landfire.gov/fuel/fbfm40
 *   https://edcintl.cr.usgs.gov/geoserver/landfire/wms?service=WMS&request=GetCapabilities
 *   https://doi.org/10.2737/RMRS-GTR-153
 *   https://www.ogc.org/standards/wms/
 *   https://leafletjs.com/examples/wms/wms.html
 */

import { fetchJson } from "../../util.js";

const LANDFIRE_WMS = "https://edcintl.cr.usgs.gov/geoserver/landfire/wms";
// LF2025 still has gaps (in September 2026, Boulder city and the plains east
// of it return no data), so 2024 fills in underneath wherever 2025 is missing.
const FUEL_LAYERS = ["LF2025_FBFM40_CONUS", "LF2024_FBFM40_CONUS"];
const NO_DATA = 32767;

// WMS draws layers in list order, so 2024 goes first and 2025 paints over it.
const WMS_LAYER_ORDER = FUEL_LAYERS.slice().reverse();

// Scott & Burgan (2005) 40 fire behavior fuel models, as coded in LANDFIRE FBFM40.
const FUEL_MODELS = {
  91: ["NB1", "Urban / developed (non-burnable)"],
  92: ["NB2", "Snow / ice (non-burnable)"],
  93: ["NB3", "Agricultural (non-burnable)"],
  98: ["NB8", "Open water (non-burnable)"],
  99: ["NB9", "Bare ground (non-burnable)"],
  101: ["GR1", "Short, sparse dry-climate grass"],
  102: ["GR2", "Low-load dry-climate grass"],
  103: ["GR3", "Low-load, very coarse humid-climate grass"],
  104: ["GR4", "Moderate-load dry-climate grass"],
  105: ["GR5", "Low-load humid-climate grass"],
  106: ["GR6", "Moderate-load humid-climate grass"],
  107: ["GR7", "High-load dry-climate grass"],
  108: ["GR8", "High-load, very coarse humid-climate grass"],
  109: ["GR9", "Very high-load humid-climate grass"],
  121: ["GS1", "Low-load dry-climate grass-shrub"],
  122: ["GS2", "Moderate-load dry-climate grass-shrub"],
  123: ["GS3", "Moderate-load humid-climate grass-shrub"],
  124: ["GS4", "High-load humid-climate grass-shrub"],
  141: ["SH1", "Low-load dry-climate shrub"],
  142: ["SH2", "Moderate-load dry-climate shrub"],
  143: ["SH3", "Moderate-load humid-climate shrub"],
  144: ["SH4", "Low-load humid-climate timber-shrub"],
  145: ["SH5", "High-load dry-climate shrub"],
  146: ["SH6", "Low-load humid-climate shrub"],
  147: ["SH7", "Very high-load dry-climate shrub"],
  148: ["SH8", "High-load humid-climate shrub"],
  149: ["SH9", "Very high-load humid-climate shrub"],
  161: ["TU1", "Low-load dry-climate timber-grass-shrub"],
  162: ["TU2", "Moderate-load humid-climate timber-shrub"],
  163: ["TU3", "Moderate-load humid-climate timber-grass-shrub"],
  164: ["TU4", "Dwarf conifer with understory"],
  165: ["TU5", "Very high-load dry-climate timber-shrub"],
  181: ["TL1", "Low-load compact conifer litter"],
  182: ["TL2", "Low-load broadleaf litter"],
  183: ["TL3", "Moderate-load conifer litter"],
  184: ["TL4", "Small downed logs"],
  185: ["TL5", "High-load conifer litter"],
  186: ["TL6", "Moderate-load broadleaf litter"],
  187: ["TL7", "Large downed logs"],
  188: ["TL8", "Long-needle litter"],
  189: ["TL9", "Very high-load broadleaf litter"],
  201: ["SB1", "Low-load activity fuel (slash)"],
  202: ["SB2", "Moderate-load activity fuel or low-load blowdown"],
  203: ["SB3", "High-load activity fuel or moderate-load blowdown"],
  204: ["SB4", "High-load blowdown"],
};

export const fuels = {
  name: "fuels",
  layer: L.tileLayer.wms(LANDFIRE_WMS, {
    pane: "rasters",
    layers: WMS_LAYER_ORDER.join(","),
    format: "image/png",
    transparent: true,
    opacity: 0.6,
    attribution: "Fuels &copy; LANDFIRE",
  }),
  reloadOnMove: false,
};

// WMS GetFeatureInfo on a tiny box around the point returns that 30 m cell's code.
async function fuelCodeAt(layerName, lat, lng) {
  const d = 0.0005;
  const params = new URLSearchParams({
    service: "WMS",
    version: "1.1.1",
    request: "GetFeatureInfo",
    layers: layerName,
    query_layers: layerName,
    styles: "",
    srs: "EPSG:4326",
    bbox: `${lng - d},${lat - d},${lng + d},${lat + d}`,
    width: "3",
    height: "3",
    x: "1",
    y: "1",
    info_format: "application/json",
  });
  const data = await fetchJson(`${LANDFIRE_WMS}?${params}`);
  return data.features?.[0]?.properties?.GRAY_INDEX;
}

export async function fuelModelAt(lat, lng) {
  for (const layerName of FUEL_LAYERS) {
    const code = await fuelCodeAt(layerName, lat, lng);
    if (code === undefined || code === NO_DATA) {
      continue;
    }
    const year = layerName.slice(2, 6);
    const model = FUEL_MODELS[code];
    if (!model) {
      return `Unrecognized code ${code} (${year})`;
    }
    const [modelCode, description] = model;
    return `${modelCode} · ${description} (${year})`;
  }
  return "No fuel data here";
}
