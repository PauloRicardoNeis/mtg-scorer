import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Icon, type IconName } from "./icon";

function classes(...names: (string | false | undefined)[]): string {
  return names.filter(Boolean).join(" ");
}

/** A square ghost button. The icon has no text, so `label` is required. */
export function IconButton({
  icon,
  label,
  size = "md",
  pressed,
  className,
  ...button
}: Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "aria-label" | "aria-pressed" | "children"
> & {
  icon: IconName;
  label: string;
  size?: "sm" | "md" | "lg";
  pressed?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      aria-pressed={pressed}
      className={classes("icon-button", size !== "md" && size, className)}
      {...button}
    >
      <Icon name={icon} size={size === "sm" ? 14 : 16} />
    </button>
  );
}

/** A surface for a group of content, with an optional eyebrow, title and actions. */
export function Panel({
  eyebrow,
  title,
  actions,
  level = 2,
  pattern = false,
  className,
  children,
}: {
  eyebrow?: string;
  title?: ReactNode;
  actions?: ReactNode;
  level?: 2 | 3;
  pattern?: boolean;
  className?: string;
  children?: ReactNode;
}) {
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <section className={classes("panel", pattern && "grid-pattern", className)}>
      {(eyebrow || title || actions) && (
        <header className="panel-header">
          <div>
            {eyebrow && <p className="eyebrow">{eyebrow}</p>}
            {title && <Heading>{title}</Heading>}
          </div>
          {actions && <div className="actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export type Tab = {
  href: string;
  label: string;
  count?: ReactNode;
  current?: boolean;
  disabled?: boolean;
};

/** View tabs as links, so each view keeps its own shareable URL. */
export function UnderlineTabs({
  label,
  items,
}: {
  label: string;
  items: Tab[];
}) {
  return (
    <nav className="tabs" aria-label={label}>
      {items.map((tab) => (
        <Link
          key={tab.href}
          href={tab.href}
          aria-current={tab.current ? "page" : undefined}
          aria-disabled={tab.disabled || undefined}
          tabIndex={tab.disabled ? -1 : undefined}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span className="tab-count">{tab.count}</span>
          )}
        </Link>
      ))}
    </nav>
  );
}
