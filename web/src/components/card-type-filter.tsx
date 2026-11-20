import { useI18n } from "#i18n";
import { cardTypeGlyphs } from "./card-type-glyphs";
import { MatchToggle } from "./match-toggle";

// A card matches a type on any face, as Scryfall's t: search does.
export const cardTypes = [
  "creature",
  "planeswalker",
  "instant",
  "sorcery",
  "artifact",
  "enchantment",
  "battle",
  "kindred",
  "land",
] as const;

/** One card type's symbol, decorative: callers name the type. */
export function CardTypeSymbol({ type }: { type: (typeof cardTypes)[number] }) {
  const glyph = cardTypeGlyphs[type];
  return (
    <svg
      className="filter-symbol type-symbol"
      viewBox={`0 0 ${glyph.width} 1024`}
      aria-hidden="true"
      focusable="false"
    >
      {/* Font glyphs point y up from the baseline, 960 below the em's top. */}
      <path transform="matrix(1 0 0 -1 0 960)" d={glyph.d} />
    </svg>
  );
}

/** The card type symbols as checkboxes, like the color filter beside them. */
export function TypeFilter({
  label,
  selected,
  form,
  hideLabel = false,
  id = "type-label",
  all,
}: {
  label: string;
  selected: string[];
  form?: string;
  hideLabel?: boolean;
  /** The label's id, for a page that shows the same filter twice. */
  id?: string;
  /** Whether every selected type must match; absent, the toggle is left out. */
  all?: boolean | undefined;
}) {
  const { t } = useI18n();
  return (
    <div>
      <span className={hideLabel ? "sr-only" : "group-label"} id={id}>
        {label}
      </span>
      <div className="symbol-filter">
        <div
          role="group"
          aria-labelledby={id}
          className="segmented type-filter"
        >
          {cardTypes.map((type) => (
            <label key={type} title={t.cardTypes[type]}>
              <input
                type="checkbox"
                name="type"
                value={type}
                form={form}
                defaultChecked={selected.includes(type)}
              />
              <CardTypeSymbol type={type} />
              <span className="sr-only">{t.cardTypes[type]}</span>
            </label>
          ))}
        </div>
        {all !== undefined && (
          <MatchToggle
            name="type_match"
            label={t.common.matchAllTypes}
            all={all}
            form={form}
          />
        )}
      </div>
    </div>
  );
}
