import { perimeters } from "./perimeters.js";
import { hotspots } from "./hotspots.js";
import { warnings } from "./warnings.js";
import { stations, water } from "./resources.js";
import { hazard } from "./hazard.js";

export const fireLayers = [perimeters, hotspots, warnings, stations, water, hazard];
