"use client";

import { useEffect, useId, useState, type ReactNode } from "react";

/**
 * Supplementary text on hover, focus or tap; Esc closes it. The content is the
 * trigger's accessible description, so it must not hold links or controls.
 * Without `trigger`, the trigger is the small "i" used beside column headers.
 */
export function Tooltip({
  label,
  trigger,
  eyebrow,
  title,
  placement = "above",
  align = "start",
  children,
}: {
  label?: string;
  trigger?: ReactNode;
  eyebrow?: string;
  title?: string;
  placement?: "above" | "below";
  align?: "start" | "end";
  children: ReactNode;
}) {
  const id = useId();
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const open = (hovered || focused || pinned) && !dismissed;
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDismissed(true);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [open]);
  return (
    <span
      className="tooltip-anchor"
      onPointerEnter={(event) => {
        if (event.pointerType === "touch") return;
        setHovered(true);
        setDismissed(false);
      }}
      onPointerLeave={() => setHovered(false)}
      onFocus={() => {
        setFocused(true);
        setDismissed(false);
      }}
      onBlur={() => {
        setFocused(false);
        setPinned(false);
      }}
    >
      <button
        type="button"
        className={trigger ? "button ghost sm" : "info-trigger"}
        aria-label={trigger ? undefined : label}
        aria-describedby={id}
        data-open={open || undefined}
        onClick={() => {
          setDismissed(false);
          setPinned((value) => !value);
        }}
      >
        {trigger ?? <span aria-hidden="true">i</span>}
      </button>
      <span
        role="tooltip"
        id={id}
        hidden={!open}
        className={[
          "tooltip",
          placement === "below" && "below",
          align === "end" && "end",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        {(eyebrow || title) && (
          <span className="tooltip-head">
            {eyebrow && <span className="tooltip-eyebrow">{eyebrow}</span>}
            {title && <span className="tooltip-title">{title}</span>}
          </span>
        )}
        <span className="tooltip-body">{children}</span>
      </span>
    </span>
  );
}
