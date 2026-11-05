import { warnings } from "./warnings.js";
import { gauges } from "./gauges.js";
import { hospitals, shelters } from "./resources.js";
import { risk } from "./risk.js";
import { buildings, population } from "./rasters.js";

export const floodLayers = [
  warnings, gauges,
  hospitals, shelters,
  risk,
  buildings, population,
];
