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
  windDirectionDeg: number; // direction the wind blows TOWARD, 0 = north, 90 = east
  weather: WeatherEvent;
  drought: DroughtLevel;
  durationHours: number;    // new: 1 to 12, the backend rejects anything over 12
}

export interface SimRequest {
  hazard: Hazard;
  ignition: LatLng;
  params: SimParams;
}

export interface FireRunRequest {
  lat: number;
  lng: number;
  hours: number;
  wind_speed_mps: number;
  wind_from_deg: number;
  // Not used by the model yet. The backend ignores them until Brody adds them.
  temperature_f?: number;
  humidity_pct?: number;
  weather?: WeatherEvent;
  drought?: DroughtLevel;
}

export interface GridBounds {
  south: number;
  west: number;
  north: number;
  east: number;
}

export interface DamageByMinute {
  properties: number[];      // index = minute, value = total so far
  exposed_value: number[];
  expected_loss: number[];
}

export interface FireDamage {
  properties: number;        // totals at the end of the run
  exposed_value: number;     // dollars
  expected_loss: number;     // dollars
  by_minute: DamageByMinute;
}

export interface FireRunResult {
  bounds: GridBounds;        // where the grid sits on the map
  rows: number;
  cols: number;
  cell_m: number;            // width of one cell in meters
  duration_min: number;
  cells: number[];           // flat list: row, col, ignitionMinute, row, col, ...
  damage: FireDamage | null; // null when the server is missing building data
}