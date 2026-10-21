"use client";

import type { Ref } from "react";
import { useI18n } from "#i18n";

/** The parts of a card a search can keep to; without one it looks at the whole card. */
export const searchFields = ["name", "type", "text"] as const;

/** A part the address names, or the whole card for anything else. */
export function searchField(value: string | null): string {
  return searchFields.find((field) => field === value) ?? "";
}

/**
 * Where a search looks on each card, as a select at the start of its box. The
 * whole card has the empty value, so the default leaves the address.
 */
export function SearchIn({
  id,
  form,
  defaultValue,
  ref,
}: {
  id?: string;
  form?: string;
  defaultValue?: string | null;
  ref?: Ref<HTMLSelectElement>;
}) {
  const { t } = useI18n();
  return (
    <span className="select search-in">
      <select
        ref={ref}
        id={id}
        name="in"
        form={form}
        aria-label={t.search.in}
        defaultValue={searchField(defaultValue ?? null)}
      >
        <option value="">{t.search.fields.all}</option>
        {searchFields.map((field) => (
          <option key={field} value={field}>
            {t.search.fields[field]}
          </option>
        ))}
      </select>
    </span>
  );
}
