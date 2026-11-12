import type { SimResult, SimParams, LatLng } from "../types";

const timeSteps = [1, 6, 24];

interface ResultsPanelProps {
  result: SimResult;
  ignition: LatLng;
  params: SimParams;
  visibleHours: number;
  onHoursChange: (hours: number) => void;
  onEdit: () => void;
  onRunAgain: () => void;
}

export default function ResultsPanel({
  result,
  ignition,
  params,
  visibleHours,
  onHoursChange,
  onEdit,
  onRunAgain,
}: ResultsPanelProps) {
  const stepIndex = timeSteps.indexOf(visibleHours);

  const stats = [
    { label: "Acres burned", value: result.acresBurned.toLocaleString() },
    { label: "Spread rate", value: `${result.spreadRateMph} mph` },
    { label: "Buildings exposed", value: result.buildingsExposed.toLocaleString() },
    { label: "People at risk", value: result.peopleAtRisk.toLocaleString() },
  ];

  function exportResult() {
    const data = { ignition, params, result };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "simulation-result.json";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <button type="button" className="back-link" onClick={onEdit}>
        ← Edit parameters
      </button>

      <div>
        <h2 className="results-title">Wildfire simulation</h2>
        <p className="results-summary">
          {params.temperatureF}°F, {params.humidityPct}% humidity, {params.windSpeedMph} mph wind
        </p>
        <p className="results-summary">Fuel: {result.fuelType}</p>
      </div>

      <div className="slider">
        <div className="slider-top">
          <span>Time after ignition</span>
          <span className="slider-value">{visibleHours} hr</span>
        </div>
        <input
          type="range"
          min={0}
          max={timeSteps.length - 1}
          step={1}
          value={stepIndex}
          onChange={(e) => onHoursChange(timeSteps[Number(e.target.value)])}
        />
        <div className="tick-labels">
          {timeSteps.map((h) => (
            <span key={h}>{h} hr</span>
          ))}
        </div>
      </div>

      <div className="stat-grid">
        {stats.map((s) => (
          <div className="stat" key={s.label}>
            <span className="stat-label">{s.label}</span>
            <span className="stat-value">{s.value}</span>
          </div>
        ))}
      </div>

      <div className="confidence">Model confidence: {result.confidence}</div>

      <div className="results-actions">
        <button type="button" className="option" onClick={onRunAgain}>
          Run again
        </button>
        <button type="button" className="option" onClick={exportResult}>
          Export
        </button>
      </div>
    </>
  );
}