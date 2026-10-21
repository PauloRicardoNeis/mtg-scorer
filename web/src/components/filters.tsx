"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { useI18n } from "#i18n";
import type { Snapshot } from "@/lib/api";
import { Icon } from "./icon";
import { ColorFilter } from "./mana";
import { SearchIn } from "./search-in";

// A card matches a type on any face, as Scryfall's t: search does.
export const cardTypes = [
  "creature",
  "planeswalker",
  "instant",
  "sorcery",
  "artifact",
  "enchantment",
  "land",
] as const;

const rarities = [
  "common",
  "uncommon",
  "rare",
  "mythic",
  "special",
  "bonus",
] as const;

const games = ["paper", "mtgo", "arena"] as const;

export function Filters({
  snapshot,
  query,
}: {
  snapshot: Snapshot;
  query: string;
}) {
  const { t, fill, colors } = useI18n();
  const current = new URLSearchParams(query);
  const colorOptions = ["W", "U", "B", "R", "G"]
    .reduce<string[]>(
      (options, color) => [
        ...options,
        ...options.map((option) => option + color),
      ],
      [""],
    )
    .filter(Boolean);
  const selectedColor = current.get("color_identity");
  if (
    selectedColor &&
    selectedColor !== "C" &&
    !colorOptions.includes(selectedColor)
  )
    colorOptions.push(selectedColor);
  // The API accepts 1 to 100 cards per page; anything else shows the default.
  const requestedLimit = Number(current.get("limit"));
  const limit =
    Number.isInteger(requestedLimit) &&
    requestedLimit >= 1 &&
    requestedLimit <= 100
      ? requestedLimit
      : 24;
  const pageSizes = [...new Set([2, 24, 50, 100, limit])].sort((a, b) => a - b);
  const missingSets = current
    .getAll("set")
    .filter((code) => !snapshot.sets.some((set) => set.set_code === code));
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  // The sticky toolbar sits outside the form so it stays stuck past the filter
  // band; its controls join the form through the form attribute.
  const form = "discovery-filters";
  return (
    <>
      <div className="toolbar band">
        <div className="toolbar-inner band-inner">
          <div className="search-field">
            <label htmlFor="q">{t.filters.name}</label>
            <div className="field">
              <SearchIn form={form} defaultValue={current.get("in")} />
              <Icon name="search" size={15} />
              <input
                id="q"
                name="q"
                form={form}
                type="search"
                maxLength={100}
                placeholder={t.filters.namePlaceholder}
                defaultValue={current.get("q") ?? ""}
              />
            </div>
          </div>
          <ColorFilter
            label={t.common.colors}
            name="color"
            form={form}
            selected={current.getAll("color")}
          />
          <div className="toolbar-field">
            <label htmlFor="type">{t.common.cardType}</label>
            <span className="select">
              <select
                id="type"
                name="type"
                form={form}
                defaultValue={current.get("type") ?? ""}
              >
                <option value="">{t.common.allCardTypes}</option>
                {cardTypes.map((value) => (
                  <option key={value} value={value}>
                    {t.cardTypes[value]}
                  </option>
                ))}
              </select>
            </span>
          </div>
          <div className="filter-actions">
            <button type="submit" form={form} disabled={pending}>
              {pending ? t.filters.searching : t.filters.find}
            </button>
            <a
              className="button ghost"
              href={`/cards?catalog_snapshot_id=${snapshot.catalog_snapshot_id}`}
            >
              {t.common.clearFilters}
            </a>
            <span role="status" aria-live="polite">
              {pending ? t.filters.loading : ""}
            </span>
          </div>
        </div>
      </div>
      <form
        id={form}
        className="filters band"
        action="/cards"
        aria-label={t.filters.label}
        onSubmit={(event) => {
          event.preventDefault();
          const values = new URLSearchParams();
          for (const [key, value] of new FormData(event.currentTarget))
            if (typeof value === "string" && value !== "")
              values.append(key, value);
          // Where to look means nothing without text to look for.
          if (!values.has("q")) values.delete("in");
          startTransition(() => router.push(`/cards?${values}`));
        }}
      >
        <div className="filters-inner band-inner">
          <input
            type="hidden"
            name="catalog_snapshot_id"
            value={snapshot.catalog_snapshot_id}
          />
          <div>
            <label htmlFor="set">{t.filters.sets}</label>
            <select
              id="set"
              name="set"
              multiple
              defaultValue={current.getAll("set")}
              aria-describedby="set-help"
            >
              {missingSets.map((code) => (
                <option key={code} value={code}>
                  {fill(t.filters.missingSet, { code: code.toUpperCase() })}
                </option>
              ))}
              {snapshot.sets.map((set) => (
                <option key={set.set_code} value={set.set_code}>
                  {set.set_name} ({set.set_code.toUpperCase()})
                </option>
              ))}
            </select>
            <small id="set-help">{t.filters.setHelp}</small>
          </div>
          <div>
            <label htmlFor="rarity">{t.filters.rarity}</label>
            <select
              id="rarity"
              name="rarity"
              multiple
              defaultValue={current.getAll("rarity")}
            >
              {rarities.map((value) => (
                <option key={value} value={value}>
                  {t.rarities[value]}
                </option>
              ))}
            </select>
            <small>{t.filters.rarityHelp}</small>
          </div>
          <div>
            <label htmlFor="color_identity">{t.filters.colorIdentity}</label>
            <span className="select">
              <select
                id="color_identity"
                name="color_identity"
                defaultValue={current.get("color_identity") ?? ""}
              >
                <option value="">{t.filters.anyColorIdentity}</option>
                <option value="C">{t.filters.colorlessOnly}</option>
                {colorOptions.map((value) => (
                  <option key={value} value={value}>
                    {colors(value.split(""))}
                  </option>
                ))}
              </select>
            </span>
            <small>{t.filters.colorHelp}</small>
          </div>
          <div>
            <label htmlFor="game">{t.filters.game}</label>
            <span className="select">
              <select
                id="game"
                name="game"
                defaultValue={current.get("game") ?? ""}
              >
                <option value="">{t.filters.anyGame}</option>
                {games.map((value) => (
                  <option key={value} value={value}>
                    {t.games[value]}
                  </option>
                ))}
              </select>
            </span>
          </div>
          <div>
            <label htmlFor="limit">{t.filters.perPage}</label>
            <span className="select">
              <select id="limit" name="limit" defaultValue={String(limit)}>
                {pageSizes.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </span>
          </div>
        </div>
      </form>
    </>
  );
}
