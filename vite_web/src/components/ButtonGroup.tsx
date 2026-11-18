interface Option<T extends string> {
  value: T;
  label: string;
}

interface ButtonGroupProps<T extends string> {
  label: string;
  options: Option<T>[];
  selected: T;
  onChange: (value: T) => void;
}

export default function ButtonGroup<T extends string>({
  label,
  options,
  selected,
  onChange,
}: ButtonGroupProps<T>) {
  return (
    <div className="button-group">
      <span className="group-label">{label}</span>
      <div className="button-row">
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={opt.value === selected ? "option selected" : "option"}
            onClick={() => onChange(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}