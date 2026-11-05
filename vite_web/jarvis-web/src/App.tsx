import "leaflet/dist/leaflet.css";
import "./App.css";
import { useState } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import ParameterSlider from "./components/ParameterSlider";
import ButtonGroup from "./components/ButtonGroup";
import HazardDropdown from "./components/HazardDropdown";
import type { SimParams, WeatherEvent, DroughtLevel, Hazard } from "./types";

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

const [hazard, setHazard] = useState<Hazard | null>(null);

export default function App() {
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

  return (
    <div className="app">
      <MapContainer center={[40.015, -105.27]} zoom={11} className="map">
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution="&copy; OpenStreetMap contributors &copy; CARTO"
        />
      </MapContainer>

      <aside className="panel">
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
        
      </aside>
    </div>
  );
}

