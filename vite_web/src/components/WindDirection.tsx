import { useRef, type PointerEvent as ReactPointerEvent } from "react";

interface WindDirectionProps {
  value: number;
  onChange: (deg: number) => void;
}

const compassLabels = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

function toCompass(deg: number): string {
  return compassLabels[Math.round(deg / 45) % 8];
}

export default function WindDirection({ value, onChange }: WindDirectionProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const dragging = useRef(false);

  function setFromPointer(e: ReactPointerEvent<SVGSVGElement>) {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const dx = e.clientX - (rect.left + rect.width / 2);
    const dy = e.clientY - (rect.top + rect.height / 2);

    let deg = (Math.atan2(dx, -dy) * 180) / Math.PI;
    if (deg < 0) deg += 360;

    onChange((Math.round(deg / 5) * 5) % 360);
  }

  return (
    <div className="wind-dir">
      <div className="slider-top">
        <span>Wind direction</span>
        <span className="slider-value">
          Toward {toCompass(value)} ({value}°)
        </span>
      </div>

      <svg
        ref={svgRef}
        viewBox="-50 -50 100 100"
        width={96}
        height={96}
        style={{ cursor: "pointer", touchAction: "none" }}
        onPointerDown={(e) => {
          dragging.current = true;
          e.currentTarget.setPointerCapture(e.pointerId);
          setFromPointer(e);
        }}
        onPointerMove={(e) => {
          if (dragging.current) setFromPointer(e);
        }}
        onPointerUp={() => {
          dragging.current = false;
        }}
      >
        <circle r={44} fill="#f4f4f4" stroke="#ccc" />
        <text y={-33} textAnchor="middle" dominantBaseline="middle" fontSize={10} fill="#777">N</text>
        <text x={34} textAnchor="middle" dominantBaseline="middle" fontSize={10} fill="#777">E</text>
        <text y={34} textAnchor="middle" dominantBaseline="middle" fontSize={10} fill="#777">S</text>
        <text x={-34} textAnchor="middle" dominantBaseline="middle" fontSize={10} fill="#777">W</text>

        <g transform={`rotate(${value})`}>
          <line y1={18} y2={-22} stroke="#333" strokeWidth={3} strokeLinecap="round" />
          <polygon points="0,-30 -7,-19 7,-19" fill="#333" />
        </g>
      </svg>
    </div>
  );
}