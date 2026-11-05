import { COLORADO } from "../../map.js";
import { ImageServerTiles } from "../fire/rasters.js";

// Both empty until we have the data.
const BUILDINGS_URL = "";
const POPULATION_URL = "";

function imageLayer(serviceUrl, options) {
  return new ImageServerTiles("", {
    pane: "rasters",
    tileSize: 512,
    bounds: COLORADO,
    updateWhenZooming: false,
    serviceUrl,
    ...options,
  });
}

// Density rasters use 0 for "nothing here"; this makes those cells transparent instead of black.
const TRANSPARENT_EMPTY = { format: "png32", noData: "0" };

export const buildings = {
  name: "flood-buildings",
  layer: imageLayer(BUILDINGS_URL, {
    opacity: 0.7,
    exportParams: TRANSPARENT_EMPTY,
  }),
  reloadOnMove: false,
  url: BUILDINGS_URL,
};

export const population = {
  name: "flood-population",
  layer: imageLayer(POPULATION_URL, {
    opacity: 0.7,
    exportParams: TRANSPARENT_EMPTY,
  }),
  reloadOnMove: false,
  url: POPULATION_URL,
};
