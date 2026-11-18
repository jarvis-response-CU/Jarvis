import type { SimRequest, FireRunRequest, FireRunResult } from "../types";

const MPH_TO_MPS = 0.44704;

// Turns what the user picked into exactly what the backend's FireRun expects.
export function toFireRunRequest(req: SimRequest): FireRunRequest {
  const p = req.params;
  return {
    lat: req.ignition.lat,
    lng: req.ignition.lng,
    hours: p.durationHours,
    wind_speed_mps: p.windSpeedMph * MPH_TO_MPS,
    // UI stores where the wind blows TOWARD, the API wants where it comes FROM.
    wind_from_deg: (p.windDirectionDeg + 180) % 360,
    temperature_f: p.temperatureF,
    humidity_pct: p.humidityPct,
    weather: p.weather,
    drought: p.drought,
  };
}

export async function simulateFire(req: SimRequest): Promise<FireRunResult> {
  const response = await fetch("/api/fire/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toFireRunRequest(req)),
  });

  if (response.status === 401) {
    throw new Error("signed-out");
  }
  if (!response.ok) {
    throw new Error(`Simulation failed (${response.status})`);
  }
  return response.json();
}