import { perimeters } from "./perimeters.js";
import { hotspots } from "./hotspots.js";
import { warnings } from "./warnings.js";
import { stations, water } from "./resources.js";
import { hazard, buildings, population } from "./rasters.js";
import { fuels } from "./fuels.js";
import { drought } from "./drought.js";
import "./spot.js";

export const fireLayers = [
  perimeters, hotspots, warnings,
  stations, water,
  hazard, fuels, drought,
  buildings, population,
];
