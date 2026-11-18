import type { SimRequest, SimResult, SpreadZone, LatLng, SimParams } from "./types";

const droughtFactor = { none: 0.8, D0: 0.9, D1: 1, D2: 1.1, D3: 1.25, D4: 1.4 };
const weatherFactor = { clear: 1, rain: 0.4, snow: 0.25, storm: 0.8 };

function spreadFactor(p: SimParams): number {
  const humidity = 1.5 - p.humidityPct / 100;
  const temp = 0.7 + Math.max(0, p.temperatureF) / 200;
  return humidity * temp * droughtFactor[p.drought] * weatherFactor[p.weather];
}

function makeZone(center: LatLng, hours: number, p: SimParams): SpreadZone {
  const forwardMi = (0.3 + p.windSpeedMph * 0.04) * Math.sqrt(hours) * spreadFactor(p);
  const sideMi = forwardMi * 0.45;

  const rad = (p.windDirectionDeg * Math.PI) / 180;
  const milesPerDegLat = 69;
  const milesPerDegLng = 69 * Math.cos((center.lat * Math.PI) / 180);

  const polygon: LatLng[] = [];
  for (let i = 0; i < 36; i++) {
    const t = (i / 36) * 2 * Math.PI;
    const along = forwardMi * 0.6 + forwardMi * Math.cos(t);
    const across = sideMi * Math.sin(t);

    const north = along * Math.cos(rad) - across * Math.sin(rad);
    const east = along * Math.sin(rad) + across * Math.cos(rad);

    polygon.push({
      lat: center.lat + north / milesPerDegLat,
      lng: center.lng + east / milesPerDegLng,
    });
  }
  return { hoursAfter: hours, polygon };
}

function buildResult(req: SimRequest): SimResult {
  const zones = [24, 6, 1].map((h) => makeZone(req.ignition, h, req.params));

  const forward24 = (0.3 + req.params.windSpeedMph * 0.04) * Math.sqrt(24) * spreadFactor(req.params);
  const acres = Math.round(Math.PI * forward24 * forward24 * 0.45 * 640);
  const buildings = Math.round(acres * 0.07);

  return {
    fuelType: "Grass-shrub (mock)",
    zones,
    acresBurned: acres,
    spreadRateMph: Math.round((forward24 / 24) * 10) / 10,
    buildingsExposed: buildings,
    peopleAtRisk: Math.round(buildings * 2.4),
    confidence: req.params.windSpeedMph > 35 ? "low" : "medium",
  };
}

export function mockSimulate(req: SimRequest): Promise<SimResult> {
  return new Promise((resolve) => {
    setTimeout(() => resolve(buildResult(req)), 1500);
  });
}