import "leaflet/dist/leaflet.css";
import "./App.css";
import { useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Polygon } from "react-leaflet";
import { mockSimulate } from "./mockSimulate";
import type { SimParams, WeatherEvent, DroughtLevel, Hazard, LatLng, SimResult } from "./types";
import MapClickHandler from "./components/MapClickHandler";
import ParameterSlider from "./components/ParameterSlider";
import ButtonGroup from "./components/ButtonGroup";
import HazardDropdown from "./components/HazardDropdown";
import WindDirection from "./components/WindDirection";
import ResultsPanel from "./components/ResultsPanel";

const weatherOptions: { value: WeatherEvent; label: string }[] = [
  { value: "clear", label: "Clear" },
  { value: "rain", label: "Rain" },
  { value: "snow", label: "Snow" },
  { value: "storm", label: "Storm" },
];

const droughtOptions: { value: DroughtLevel; label: string }[] = [
  { value: "none", label: "None" },
  { value: "D0", label: "D0" },
  { value: "D1", label: "D1" },
  { value: "D2", label: "D2" },
  { value: "D3", label: "D3" },
  { value: "D4", label: "D4" },
];

type Mode = "setup" | "running" | "results";

const zoneColors: Record<number, string> = {
  24: "#ef9f27",
  6: "#d85a30",
  1: "#a32d2d",
};

export default function App() {
  const [visibleHours, setVisibleHours] = useState(1);
  const [mode, setMode] = useState<Mode>("setup");
  const [result, setResult] = useState<SimResult | null>(null);
  const [ignition, setIgnition] = useState<LatLng | null>(null);
  const [hazard, setHazard] = useState<Hazard | null>(null);
  const [params, setParams] = useState<SimParams>({
    temperatureF: 78,
    humidityPct: 25,
    windSpeedMph: 25,
    windDirectionDeg: 45,
    weather: "clear",
    drought: "D2",
  });

  function update<K extends keyof SimParams>(key: K, value: SimParams[K]) {
    setParams((prev) => ({ ...prev, [key]: value }));
  }

  async function runSimulation() {
    if (!hazard || !ignition) return;
    setMode("running");
    const r = await mockSimulate({ hazard, ignition, params });
    setResult(r);
    setVisibleHours(1);
    setMode("results");
  }

  function handlePick(point: LatLng) {
    setIgnition(point);
    setResult(null);
    setMode("setup");
  }

  const placing = hazard !== null && ignition === null;

  return (
    <div className="app">
      <div className={placing ? "map-wrap placing" : "map-wrap"}>
        <MapContainer center={[40.015, -105.27]} zoom={11} className="map">
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            attribution="&copy; OpenStreetMap contributors &copy; CARTO"
          />
          <MapClickHandler enabled={hazard !== null} onPick={handlePick} />

          {result &&
              result.zones
                .filter((z) => z.hoursAfter <= visibleHours)
                .map((z) => (
              <Polygon
                key={z.hoursAfter}
                positions={z.polygon.map((p) => [p.lat, p.lng] as [number, number])}
                pathOptions={{
                  color: zoneColors[z.hoursAfter],
                  fillColor: zoneColors[z.hoursAfter],
                  fillOpacity: 0.35,
                  weight: 1,
                }}
              />
            ))}

          {ignition && (
            <CircleMarker
              center={[ignition.lat, ignition.lng]}
              radius={8}
              pathOptions={{ color: "#a32d2d", fillColor: "#e24b4a", fillOpacity: 0.9 }}
            />
          )}
        </MapContainer>

        {placing && <div className="map-banner">Click the map to place an ignition point</div>}
      </div>

      <aside className="panel">
        {mode === "results" && result && ignition ? (
          <ResultsPanel
            result={result}
            ignition={ignition}
            params={params}
            visibleHours={visibleHours}
            onHoursChange={setVisibleHours}
            onEdit={() => setMode("setup")}
            onRunAgain={runSimulation}
          />
        ) : (
          <>
          <HazardDropdown selected={hazard} onChange={setHazard} />
          {hazard && ignition && (
            <>
            <div className="ignition-info">
              <span className="group-label">Ignition point</span>
              <span>
                {ignition.lat.toFixed(4)}, {ignition.lng.toFixed(4)}
              </span>
              <span className="hint">Click the map again to move it</span>
            </div>

            <ParameterSlider
              label="Temperature"
              value={params.temperatureF}
              min={-20}
              max={110}
              unit="°F"
              onChange={(v) => update("temperatureF", v)}
            />
            <ParameterSlider
              label="Humidity"
              value={params.humidityPct}
              min={0}
              max={100}
              unit="%"
              onChange={(v) => update("humidityPct", v)}
            />
            <ParameterSlider
              label="Wind speed"
              value={params.windSpeedMph}
              min={0}
              max={50}
              unit=" mph"
              onChange={(v) => update("windSpeedMph", v)}
            />
            <WindDirection
              value={params.windDirectionDeg}
              onChange={(v) => update("windDirectionDeg", v)}
            />
            <ButtonGroup
              label="Weather"
              options={weatherOptions}
              selected={params.weather}
              onChange={(v) => update("weather", v)}
            />
            <ButtonGroup
              label="Drought level"
              options={droughtOptions}
              selected={params.drought}
              onChange={(v) => update("drought", v)}
            />
            <button
              type="button"
              className="run-button"
              onClick={runSimulation}
              disabled={mode === "running"}
            >
              {mode === "running" ? "Running..." : "Run simulation"}
            </button>
                </>
            )}
          </>
        )}
      </aside>
    </div>
  );
}

