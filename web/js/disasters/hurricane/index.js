import { tracks, windswaths } from "./tracks.js";
import { warnings } from "./warnings.js";
import { fireStations, hospitals, shelters } from "./resources.js";
import { risk, surge } from "./risk.js";
import { buildings, population } from "./rasters.js";

export const hurricaneLayers = [
  tracks, windswaths, warnings,
  fireStations, hospitals, shelters,
  risk, surge,
  buildings, population,
];
