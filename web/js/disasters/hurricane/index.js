import { tracks } from "./tracks.js";
import { warnings } from "./warnings.js";
import { hospitals, shelters } from "./resources.js";
import { risk } from "./risk.js";
import { buildings, population } from "./rasters.js";

export const hurricaneLayers = [
  tracks, warnings,
  hospitals, shelters,
  risk,
  buildings, population,
];
