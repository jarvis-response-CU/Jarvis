interface ParameterSliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit: string;
  onChange: (value: number) => void;
}

export default function ParameterSlider({
  label,
  value,
  min,
  max,
  step = 1,
  unit,
  onChange,
}: ParameterSliderProps) {
  return (
    <div className="slider">
      <div className="slider-top">
        <span>{label}</span>
        <span className="slider-value">
          {value}
          {unit}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}