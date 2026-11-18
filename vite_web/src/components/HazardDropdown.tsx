import { useEffect, useRef, useState } from "react";
import type { Hazard } from "../types";

const hazards: { value: Hazard; label: string; available: boolean }[] = [
  { value: "wildfire", label: "Wildfire", available: true },
  { value: "flood", label: "Flood", available: false },
  { value: "hurricane", label: "Hurricane", available: false },
  { value: "earthquake", label: "Earthquake", available: false },
];

interface HazardDropdownProps {
  selected: Hazard | null;
  onChange: (hazard: Hazard) => void;
}

export default function HazardDropdown({ selected, onChange }: HazardDropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const current = hazards.find((h) => h.value === selected);

  return (
    <div className="dropdown" ref={ref}>
      <span className="group-label">Hazard</span>
      <button
        type="button"
        className="dropdown-header"
        onClick={() => setOpen(!open)}
      >
        <span className={current ? "" : "placeholder"}>
          {current ? current.label : "Choose a hazard"}
        </span>
        <span>{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <ul className="dropdown-list">
          {hazards.map((h) => (
            <li key={h.value}>
              <button
                type="button"
                className={h.value === selected ? "dropdown-item active" : "dropdown-item"}
                disabled={!h.available}
                                onClick={() => {
                  onChange(h.value);
                  setOpen(false);
                }}
              >
                {h.label}
                {!h.available && <span className="soon">Coming soon</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}