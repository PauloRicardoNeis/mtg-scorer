import { Fragment, type CSSProperties } from "react";

/** Scryfall hosts the official card symbols as SVGs, alongside the card scans. */
const symbolBase = "https://svgs.scryfall.io/card-symbols";

// Every symbol Scryfall draws (api.scryfall.com/symbology), as written inside the braces.
const cardSymbols = new Set([
  ..."T Q E P PW CHAOS A TK X Y Z S L D H HW HR ½ ∞ 100 1000000".split(" "),
  ...Array.from({ length: 21 }, (_, n) => String(n)),
  ..."W U B R G C".split(" "),
  ..."W/U W/B U/B U/R B/R B/G R/G R/W G/W G/U".split(" "),
  ..."C/W C/U C/B C/R C/G 2/W 2/U 2/B 2/R 2/G".split(" "),
  ..."W/P U/P B/P R/P G/P C/P".split(" "),
  ..."W/U/P W/B/P U/B/P U/R/P B/R/P B/G/P R/G/P R/W/P G/W/P G/U/P".split(" "),
]);

const symbolFiles: Record<string, string> = { "½": "HALF", "∞": "INFINITY" };

/** The SVG for one symbol ("W/U" → WU.svg), or null when Scryfall draws none. */
export function symbolSrc(symbol: string): string | null {
  if (!cardSymbols.has(symbol)) return null;
  return `${symbolBase}/${symbolFiles[symbol] ?? symbol.replaceAll("/", "")}.svg`;
}

/** One card symbol, decorative: callers keep the source text for assistive tech. */
function Pip({ symbol }: { symbol: string }) {
  const src = symbolSrc(symbol);
  return src ? (
    <img className="pip" src={src} alt="" decoding="async" draggable={false} />
  ) : (
    <span className="pip pip-text">{symbol}</span>
  );
}

const symbolPattern = /\{[^}]+\}/g;

/** Mana symbols drawn as the official card symbols; the source text stays available to assistive tech. */
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
      (half.match(symbolPattern) ?? []).map((s) =>
        s.slice(1, -1).toUpperCase(),
      ),
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

/**
 * Rules text with its {T}, {W} and other symbols drawn inline. Each symbol keeps its
 * source text for assistive tech and copying; unknown symbols stay as text.
 */
export function SymbolText({ text }: { text: string }) {
  const parts = text.split(/(\{[^}]+\})/);
  return (
    <>
      {parts.map((part, index) => {
        const src =
          index % 2 === 1 ? symbolSrc(part.slice(1, -1).toUpperCase()) : null;
        if (!src) return part;
        return (
          <span className="inline-symbol" key={index}>
            <span className="sr-only">{part}</span>
            <img
              className="pip"
              src={src}
              alt=""
              decoding="async"
              draggable={false}
            />
          </span>
        );
      })}
    </>
  );
}

const manaColors = new Set(["W", "U", "B", "R", "G", "C"]);

/** Color identity as small mana symbols, placed before a text label. */
export function ColorPips({ values }: { values: string[] | null }) {
  if (values === null) return null;
  const shown = values.length === 0 ? ["C"] : values;
  return (
    <span className="color-pips" aria-hidden="true">
      {shown.map((value) =>
        manaColors.has(value) ? (
          <Pip key={value} symbol={value} />
        ) : (
          <span key={value} className="pip pip-text">
            {value}
          </span>
        ),
      )}
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

/**
 * Multi-select card colors as a segmented bar; a card matches any selected color.
 * `hideLabel` keeps the group's name for assistive tech only, for compact toolbars.
 */
export function ColorFilter({
  label,
  name,
  selected,
  form,
  hideLabel = false,
}: {
  label: string;
  name: string;
  selected: string[];
  form?: string;
  hideLabel?: boolean;
}) {
  return (
    <div>
      <span
        className={hideLabel ? "sr-only" : "group-label"}
        id={`${name}-label`}
      >
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
            <img
              className="filter-symbol"
              data-color={color}
              src={symbolSrc(color)!}
              alt=""
              decoding="async"
              draggable={false}
              style={
                {
                  "--glow": `var(--mana-${color.toLowerCase()})`,
                } as CSSProperties
              }
            />
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
