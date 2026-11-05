import { events } from "./events.js";
import { shaking } from "./shaking.js";
import { hospitals, shelters } from "./resources.js";
import { risk } from "./risk.js";
import { buildings, population } from "./rasters.js";

export const earthquakeLayers = [
  events, shaking,
  hospitals, shelters,
  risk,
  buildings, population,
];
