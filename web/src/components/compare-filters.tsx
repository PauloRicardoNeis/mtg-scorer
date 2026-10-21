"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useTransition, type ChangeEvent } from "react";
import { useI18n } from "#i18n";
import { Chip, Switch } from "./forms";
import { ColorFilter } from "./mana";
import type { GradingOption } from "./ranking-filters";
import { rememberFocus, useRefocus } from "./refocus";

export type PickOption = { value: string; label: string; checked: boolean };

/** The form's set values as a query; the default grading is left out. */
function values(form: HTMLFormElement): URLSearchParams {
  const query = new URLSearchParams();
  for (const [key, value] of new FormData(form))
    if (typeof value === "string" && value !== "") query.append(key, value);
  return query;
}

// The table always shows at least one format and one stat; summaries may all go.
const KEEP_ONE = new Set(["format", "stat"]);

/** One labelled group of chips. */
function Picks({
  label,
  name,
  options,
}: {
  label: string;
  name: string;
  options: PickOption[];
}) {
  return (
    <fieldset className="pick-group">
      <legend className="sr-only">{label}</legend>
      <span className="pick-label" aria-hidden="true">
        {label}
      </span>
      {options.map((option) => (
        <Chip
          key={option.value}
          label={option.label}
          name={name}
          value={option.value}
          defaultChecked={option.checked}
        />
      ))}
    </fieldset>
  );
}

/**
 * The formats, stats and summaries the compare table shows, the grading it ranks by,
 * and its filters. Each change replaces the URL so the server re-renders; without
 * JavaScript it is a GET form.
 */
export function CompareFilters({
  formats,
  stats,
  summaries,
  every,
  query,
  gradings = [],
  method = "",
}: {
  formats: PickOption[];
  stats: PickOption[];
  summaries: PickOption[];
  every: boolean;
  query: string;
  gradings?: GradingOption[];
  /** Empty for the default grading, which the address leaves out. */
  method?: string;
}) {
  const router = useRouter();
  const { t } = useI18n();
  const [pending, startTransition] = useTransition();
  const form = useRef<HTMLFormElement>(null);
  const current = new URLSearchParams(query);
  const colors = current.getAll("color");
  // Kept as they are: a change re-sorts the same search under the same order.
  const kept = ["q", "in", "sort", "order", "limit"].flatMap((key) => {
    const value = current.get(key);
    return value ? [[key, value] as const] : [];
  });
  // Presets and links elsewhere change the address without remounting the form.
  // The server rendered the controls from this address, so mounting leaves them
  // alone: a choice made before hydration would otherwise be undone.
  const state = JSON.stringify([
    formats,
    stats,
    summaries,
    every,
    colors,
    method,
  ]);
  const synced = useRef(state);
  useEffect(() => {
    if (synced.current === state) return;
    synced.current = state;
    const [f, s, m, e, c, g] = JSON.parse(state) as [
      PickOption[],
      PickOption[],
      PickOption[],
      boolean,
      string[],
      string,
    ];
    // A group of one control is not a RadioNodeList, so look the boxes up by name.
    const sync = (name: string, on: (value: string) => boolean) => {
      for (const box of form.current!.querySelectorAll<HTMLInputElement>(
        `input[name="${name}"]`,
      ))
        box.checked = on(box.value);
    };
    sync("format", (value) => f.some((o) => o.value === value && o.checked));
    sync("stat", (value) => s.some((o) => o.value === value && o.checked));
    sync("summary", (value) => m.some((o) => o.value === value && o.checked));
    sync("color", (value) => c.includes(value));
    sync("every", () => e);
    const grading = form.current!.elements.namedItem("method");
    if (grading instanceof HTMLSelectElement) grading.value = g;
  }, [state]);
  useRefocus(form, query);
  const apply = () =>
    startTransition(() =>
      router.replace(`/rankings/compare?${values(form.current!)}`, {
        scroll: false,
      }),
    );
  return (
    <form
      ref={form}
      className="toolbar band compare-toolbar"
      action="/rankings/compare"
      method="get"
      aria-label={t.compare.settings}
      aria-busy={pending || undefined}
      onChange={(event: ChangeEvent<HTMLFormElement>) => {
        const box = event.target as unknown as HTMLInputElement;
        // Unchecking the last format or stat puts it back instead of applying.
        if (
          KEEP_ONE.has(box.name) &&
          !form.current!.querySelector(`input[name="${box.name}"]:checked`)
        ) {
          box.checked = true;
          return;
        }
        rememberFocus(box);
        apply();
      }}
      onSubmit={(event) => {
        event.preventDefault();
        apply();
      }}
    >
      <div className="compare-toolbar-inner band-inner">
        {/* Marks the choices as made, so an empty summary stays empty. */}
        <input type="hidden" name="picked" value="1" />
        {gradings.length < 2 && method && (
          <input type="hidden" name="method" value={method} />
        )}
        {kept.map(([key, value]) => (
          <input key={key} type="hidden" name={key} value={value} />
        ))}
        <Picks label={t.compare.formats} name="format" options={formats} />
        <div className="compare-toolbar-row">
          <Picks label={t.compare.stats} name="stat" options={stats} />
          <Picks label={t.compare.summary} name="summary" options={summaries} />
          <span role="status" className="toolbar-status">
            {pending ? t.compare.updating : ""}
          </span>
          {gradings.length > 1 && (
            <span className="select">
              <select
                aria-label={t.rankings.grading}
                name="method"
                defaultValue={method}
              >
                {gradings.map((grading) => (
                  <option
                    key={grading.value}
                    value={grading.value}
                    disabled={grading.disabled}
                  >
                    {grading.label}
                  </option>
                ))}
              </select>
            </span>
          )}
          <Switch
            label={t.compare.every}
            name="every"
            value="true"
            defaultChecked={every}
            compact
          />
          <ColorFilter
            label={t.common.colors}
            name="color"
            selected={colors}
            hideLabel
          />
        </div>
        <noscript>
          <button type="submit" className="sm">
            {t.common.apply}
          </button>
        </noscript>
      </div>
    </form>
  );
}
