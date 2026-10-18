import { Fragment, type CSSProperties } from "react";

const manaColors = new Set(["W", "U", "B", "R", "G", "C"]);

function fill(symbol: string): string {
  return manaColors.has(symbol)
    ? `var(--mana-${symbol.toLowerCase()})`
    : "transparent";
}

function Pip({ symbol }: { symbol: string }) {
  const [first, second] = symbol.split("/");
  if (second && second !== "P") {
    // Hybrid symbols ({W/U}, {2/W}) split the pip diagonally.
    const style = {
      "--pip-a": fill(first),
      "--pip-b": fill(second),
    } as CSSProperties;
    return <span className="pip pip-hybrid" style={style} />;
  }
  const color = manaColors.has(first) ? first.toLowerCase() : "generic";
  return (
    <span className={`pip pip-${color}`}>{second === "P" ? "P" : first}</span>
  );
}

/** Mana symbols drawn as pips; the source text stays available to assistive tech. */
export function ManaCost({
  cost,
  size = "sm",
}: {
  cost: string;
  size?: "sm" | "lg";
}) {
  const halves = cost
    .split("//")
    .map((half) =>
      (half.match(/\{[^}]+\}/g) ?? []).map((s) => s.slice(1, -1).toUpperCase()),
    );
  if (halves.every((symbols) => symbols.length === 0)) return <>{cost}</>;
  return (
    <span className={`mana-cost mana-cost-${size}`}>
      <span className="sr-only">{cost}</span>
      <span className="pips" aria-hidden="true">
        {halves.map((symbols, half) => (
          <Fragment key={half}>
            {half > 0 && <span className="pip-split">//</span>}
            {symbols.map((symbol, index) => (
              <Pip key={index} symbol={symbol} />
            ))}
          </Fragment>
        ))}
      </span>
    </span>
  );
}

/** Color identity as small dots, placed before a text label. */
export function ColorDots({ values }: { values: string[] | null }) {
  if (values === null) return null;
  const shown = values.length === 0 ? ["C"] : values;
  return (
    <span className="color-dots" aria-hidden="true">
      {shown.map((value) => (
        <span
          key={value}
          className={`color-dot pip-${manaColors.has(value) ? value.toLowerCase() : "generic"}`}
        />
      ))}
    </span>
  );
}

const filterColors: [string, string][] = [
  ["W", "White"],
  ["U", "Blue"],
  ["B", "Black"],
  ["R", "Red"],
  ["G", "Green"],
  ["C", "Colorless"],
];

/** Multi-select card colors as a segmented bar; a card matches any selected color. */
export function ColorFilter({
  label,
  name,
  selected,
  form,
}: {
  label: string;
  name: string;
  selected: string[];
  form?: string;
}) {
  return (
    <div>
      <span className="group-label" id={`${name}-label`}>
        {label}
      </span>
      <div
        role="group"
        aria-labelledby={`${name}-label`}
        className="segmented color-filter"
      >
        {filterColors.map(([color, colorName]) => (
          <label key={color} title={colorName}>
            <input
              type="checkbox"
              name={name}
              value={color}
              form={form}
              defaultChecked={selected.includes(color)}
            />
            <span
              className="filter-dot"
              data-color={color}
              style={
                {
                  "--dot": `var(--mana-${color.toLowerCase()})`,
                } as CSSProperties
              }
              aria-hidden="true"
            />
            <span aria-hidden="true">{color}</span>
            <span className="sr-only">{colorName}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

const rarities = new Set(["common", "uncommon", "rare", "mythic"]);

/** Rarity gem followed by the rarity name. */
export function Rarity({ rarity }: { rarity: string }) {
  return (
    <span className="rarity">
      <span
        className={`gem gem-${rarities.has(rarity) ? rarity : "common"}`}
        aria-hidden="true"
      />
      {rarity}
    </span>
  );
}
