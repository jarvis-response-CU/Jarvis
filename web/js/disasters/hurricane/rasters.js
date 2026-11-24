import { REGIONS } from "../../map.js";
import { ImageServerTiles } from "../fire/rasters.js";

// The same national density maps the wildfire layers use.
const BUILDINGS_URL = "https://imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation/USFS_EDW_RMRS_WRC_BuildingDensity/ImageServer";
const POPULATION_URL = "https://imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation/USFS_EDW_RMRS_WRC_PopulationDensity/ImageServer";

function imageLayer(serviceUrl, options) {
  return new ImageServerTiles("", {
    pane: "rasters",
    tileSize: 512,
    bounds: REGIONS.hurricane.bounds,
    updateWhenZooming: false,
    serviceUrl,
    ...options,
  });
}

// Density rasters use 0 for "nothing here"; this makes those cells transparent instead of black.
const TRANSPARENT_EMPTY = { format: "png32", noData: "0" };

export const buildings = {
  name: "hurricane-buildings",
  layer: imageLayer(BUILDINGS_URL, {
    opacity: 0.7,
    exportParams: TRANSPARENT_EMPTY,
  }),
  reloadOnMove: false,
  url: BUILDINGS_URL,
};

export const population = {
  name: "hurricane-population",
  layer: imageLayer(POPULATION_URL, {
    opacity: 0.7,
    exportParams: TRANSPARENT_EMPTY,
  }),
  reloadOnMove: false,
  url: POPULATION_URL,
};
