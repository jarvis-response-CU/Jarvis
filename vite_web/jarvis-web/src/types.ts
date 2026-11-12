export type Hazard = "wildfire" | "flood" | "hurricane" | "earthquake";
export type WeatherEvent = "clear" | "rain" | "snow" | "storm";
export type DroughtLevel = "none" | "D0" | "D1" | "D2" | "D3" | "D4";

export interface LatLng {
  lat: number;
  lng: number;
}

// What the frontend sends to the model
export interface SimParams {
  temperatureF: number;
  humidityPct: number;
  windSpeedMph: number;
  windDirectionDeg: number; // 0 = north, 90 = east
  weather: WeatherEvent;
  drought: DroughtLevel;
}

export interface SimRequest {
  hazard: Hazard;
  ignition: LatLng;
  params: SimParams;
}

// What the model sends back
export interface SpreadZone {
  hoursAfter: number; // 1, 6, 24
  polygon: LatLng[];
}

export interface SimResult {
  fuelType: string; //Hopefully this is will be auto detected
  zones: SpreadZone[];
  acresBurned: number;
  spreadRateMph: number;
  buildingsExposed: number;
  peopleAtRisk: number;
  confidence: "low" | "medium" | "high";
}