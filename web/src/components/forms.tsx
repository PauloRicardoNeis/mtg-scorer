"use client";

import {
  useEffect,
  useRef,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";

// Styled native inputs: they keep keyboard behavior and submit with forms.
type InputProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type" | "className" | "role"
> & { label: ReactNode };

/** A checkbox with its label. `indeterminate` shows a partial selection. */
export function Checkbox({
  label,
  indeterminate = false,
  ...input
}: InputProps & { indeterminate?: boolean }) {
  const box = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (box.current) box.current.indeterminate = indeterminate;
  }, [indeterminate]);
  return (
    <label className="choice">
      <input ref={box} type="checkbox" className="check" {...input} />
      {label}
    </label>
  );
}

export function Radio({ label, ...input }: InputProps) {
  return (
    <label className="choice">
      <input type="radio" className="radio" {...input} />
      {label}
    </label>
  );
}

/** An on/off setting that applies as soon as it changes. */
export function Switch({
  label,
  compact = false,
  ...input
}: InputProps & { compact?: boolean }) {
  return (
    <label className="choice">
      <input
        type="checkbox"
        role="switch"
        className={compact ? "switch compact" : "switch"}
        {...input}
      />
      {label}
    </label>
  );
}

/** One option of a multi-select; group chips in a fieldset.chip-group. */
export function Chip({ label, ...input }: InputProps) {
  return (
    <label className="chip">
      <input type="checkbox" {...input} />
      {label}
    </label>
  );
}

export type SegmentedOption = {
  value: string;
  label: ReactNode;
  disabled?: boolean;
};

/** Exactly one of a few options. Pass `value` and `onChange` to control it. */
export function Segmented({
  legend,
  name,
  options,
  defaultValue,
  value,
  onChange,
  size = "md",
  disabled,
}: {
  legend: string;
  name: string;
  options: SegmentedOption[];
  defaultValue?: string;
  value?: string;
  onChange?: (value: string) => void;
  size?: "sm" | "md";
  disabled?: boolean;
}) {
  return (
    <fieldset
      className={size === "sm" ? "segmented sm" : "segmented"}
      disabled={disabled}
    >
      <legend className="sr-only">{legend}</legend>
      {options.map((option) => (
        <label key={option.value}>
          <input
            type="radio"
            name={name}
            value={option.value}
            disabled={option.disabled}
            {...(value === undefined
              ? { defaultChecked: option.value === defaultValue }
              : { checked: option.value === value })}
            onChange={onChange && (() => onChange(option.value))}
          />
          {option.label}
        </label>
      ))}
    </fieldset>
  );
}
