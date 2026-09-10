"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import type { Snapshot } from "@/lib/api";
import { colors } from "@/lib/urls";

export function Filters({
  snapshot,
  query,
}: {
  snapshot: Snapshot;
  query: string;
}) {
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
  const pageSizes = [
    ...new Set([2, 24, 50, 100, Number(current.get("limit") ?? 24)]),
  ].sort((a, b) => a - b);
  const missingSets = current
    .getAll("set")
    .filter((code) => !snapshot.sets.some((set) => set.set_code === code));
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <form
      className="filters"
      action="/cards"
      onSubmit={(event) => {
        event.preventDefault();
        const values = new URLSearchParams();
        for (const [key, value] of new FormData(event.currentTarget))
          if (typeof value === "string" && value !== "")
            values.append(key, value);
        startTransition(() => router.push(`/cards?${values}`));
      }}
    >
      <input
        type="hidden"
        name="catalog_snapshot_id"
        value={snapshot.catalog_snapshot_id}
      />
      <div className="search-field">
        <label htmlFor="q">Card or face name</label>
        <input
          id="q"
          name="q"
          type="search"
          maxLength={100}
          placeholder="Try Insectile Aberration…"
          defaultValue={current.get("q") ?? ""}
        />
      </div>
      <div>
        <label htmlFor="set">Sets</label>
        <select
          id="set"
          name="set"
          multiple
          defaultValue={current.getAll("set")}
          aria-describedby="set-help"
        >
          {missingSets.map((code) => (
            <option key={code} value={code}>
              {code.toUpperCase()} (not in this dataset)
            </option>
          ))}
          {snapshot.sets.map((set) => (
            <option key={set.set_code} value={set.set_code}>
              {set.set_name} ({set.set_code.toUpperCase()})
            </option>
          ))}
        </select>
        <small id="set-help">
          No selection includes all sets. Ctrl / Cmd selects several.
        </small>
      </div>
      <div>
        <label htmlFor="rarity">Rarity</label>
        <select
          id="rarity"
          name="rarity"
          multiple
          defaultValue={current.getAll("rarity")}
        >
          {["common", "uncommon", "rare", "mythic", "special", "bonus"].map(
            (value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ),
          )}
        </select>
        <small>No selection includes all rarities.</small>
      </div>
      <div>
        <label htmlFor="color_identity">Color identity</label>
        <select
          id="color_identity"
          name="color_identity"
          defaultValue={current.get("color_identity") ?? ""}
        >
          <option value="">All, including unknown</option>
          <option value="C">Colorless only</option>
          {colorOptions.map((value) => (
            <option key={value} value={value}>
              {colors(value.split(""))}
            </option>
          ))}
        </select>
        <small>Selected colors also include colorless cards.</small>
      </div>
      <div>
        <label htmlFor="game">Game</label>
        <select id="game" name="game" defaultValue={current.get("game") ?? ""}>
          <option value="">Any game</option>
          <option value="paper">Paper</option>
          <option value="mtgo">Magic Online</option>
          <option value="arena">Arena</option>
        </select>
      </div>
      <div>
        <label htmlFor="limit">Cards per page</label>
        <select
          id="limit"
          name="limit"
          defaultValue={current.get("limit") ?? "24"}
        >
          {pageSizes.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
      </div>
      <div className="filter-actions">
        <button type="submit" disabled={pending}>
          {pending ? "Searching…" : "Find cards"}
        </button>
        <a href={`/cards?catalog_snapshot_id=${snapshot.catalog_snapshot_id}`}>
          Clear filters
        </a>
        <span role="status" aria-live="polite">
          {pending ? "Loading matching cards…" : ""}
        </span>
      </div>
    </form>
  );
}
