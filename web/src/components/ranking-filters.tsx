"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useEffect,
  useId,
  useRef,
  useState,
  useTransition,
  type FormEvent,
} from "react";
import { useI18n } from "#i18n";
import { cardTypes } from "./filters";
import { Icon } from "./icon";
import { ColorFilter } from "./mana";
import { rememberFocus, useRefocus } from "./refocus";
import { SearchIn } from "./search-in";

export type WindowOption = { scoreRunId: string; label: string };

export type SourceTab = {
  source: string;
  label: string;
  href: string;
  current: boolean;
};

export type GradingOption = {
  /** Empty for the run's default method, which the address leaves out. */
  value: string;
  label: string;
  /** A method that could not score this run, e.g. without archetype labels. */
  disabled: boolean;
};

/** What the page ranks: a format's cards or, where decks name them, its commanders. */
export type KindTab = { label: string; href: string; current: boolean };

/** A minimum of decks a row must have; the empty value keeps every row. */
export type MinDecksOption = { value: string; label: string };

export type ViewTab = {
  view: string;
  label: string;
  count: number;
  href: string;
  current: boolean;
};

export type SortOption = {
  /** Empty for the page's default sort, which the address leaves out. */
  value: string;
  label: string;
  /** The direction the sort starts in, which the address leaves out too. */
  order: "asc" | "desc";
};

/** Page sizes the filter menu offers; the first is the API's default. */
const limits = [25, 50, 75, 100];

/**
 * The form's set values as a query; the API rejects empty ones. Where to search
 * means nothing without text to search for.
 */
function values(form: HTMLFormElement): URLSearchParams {
  const query = new URLSearchParams();
  for (const [key, value] of new FormData(form))
    if (typeof value === "string" && value !== "") query.append(key, value);
  if (!query.has("q")) query.delete("in");
  return query;
}

/**
 * Every filter and order of the toolbar's run in one panel that opens under the
 * toolbar, with the search and page size the toolbar leaves to the header and the
 * table. Changes wait for "Show results"; closing the panel any other way drops
 * them.
 */
function FilterMenu({
  id,
  open,
  closings,
  close,
  format,
  scoreRunId,
  query,
  clearHref,
  views,
  windows,
  gradings,
  method,
  minDecks,
  sorts,
  action,
  types,
  fields,
  search,
  perPage,
  apply,
}: {
  id: string;
  open: boolean;
  /** How often the panel closed; each closing drops the edits not applied. */
  closings: number;
  /** Closes the panel; with refocus, focus goes back to the button that opens it. */
  close: (refocus?: boolean) => void;
  format: string;
  scoreRunId: string;
  query: string;
  clearHref: string;
  views: ViewTab[];
  windows: WindowOption[];
  gradings: GradingOption[];
  method: string;
  minDecks: MinDecksOption[];
  sorts: SortOption[];
  action: string;
  types: boolean;
  fields: boolean;
  search: string;
  perPage: string;
  apply: (query: URLSearchParams) => void;
}) {
  const { t, count } = useI18n();
  const current = new URLSearchParams(query);
  const sort = current.get("sort") ?? "";
  // The address leaves out the order a sort starts in, as the column headers do.
  const first = (value: string) =>
    sorts.find((option) => option.value === value)?.order;
  const order = current.get("order") ?? first(sort);
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const chosen = values(event.currentTarget);
    if (chosen.get("order") === first(chosen.get("sort") ?? ""))
      chosen.delete("order");
    apply(chosen);
    close(true);
  };
  return (
    <div
      id={id}
      className="filter-menu"
      role="region"
      aria-labelledby={`${id}-title`}
      hidden={!open}
    >
      <form
        // A new address or a closing remounts the form, so it reopens on the
        // address. A reset would also clear what the controls know the user
        // chose, and React's next update of a radio group would undo a choice.
        key={`${scoreRunId}?${query}#${closings}`}
        className="band-inner"
        action={action}
        method="get"
        onSubmit={submit}
      >
        <header className="filter-menu-head">
          <h2 id={`${id}-title`}>{t.rankings.menu}</h2>
          <button
            type="button"
            className="icon-button sm"
            aria-label={t.common.dismiss}
            onClick={() => close(true)}
          >
            <Icon name="x" />
          </button>
        </header>
        <div className="filter-menu-body">
          <input type="hidden" name="format" value={format} />
          {windows.length < 2 && (
            <input type="hidden" name="score_run_id" value={scoreRunId} />
          )}
          {gradings.length < 2 && method && (
            <input type="hidden" name="method" value={method} />
          )}
          <div className="filter-menu-wide">
            <label htmlFor={`${id}-q`}>{search}</label>
            <div className="field">
              {fields && <SearchIn defaultValue={current.get("in")} />}
              <Icon name="search" />
              <input
                id={`${id}-q`}
                type="search"
                name="q"
                defaultValue={current.get("q") ?? ""}
                autoComplete="off"
              />
            </div>
          </div>
          {views.length > 0 && (
            <div className="filter-menu-wide">
              <span className="group-label" id={`${id}-views`}>
                {t.rankings.views}
              </span>
              <div
                role="radiogroup"
                aria-labelledby={`${id}-views`}
                className="segmented"
              >
                {views.map((tab) => (
                  <label key={tab.view}>
                    <input
                      type="radio"
                      name="view"
                      value={tab.view === "all" ? "" : tab.view}
                      defaultChecked={tab.current}
                    />
                    {tab.label}
                    <span className="tab-count">{count(tab.count)}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
          {gradings.length > 1 && (
            <div>
              <label htmlFor={`${id}-method`}>{t.rankings.grading}</label>
              <span className="select">
                <select id={`${id}-method`} name="method" defaultValue={method}>
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
            </div>
          )}
          {windows.length > 1 && (
            <div>
              <label htmlFor={`${id}-window`}>{t.rankings.windowSelect}</label>
              <span className="select">
                <select
                  id={`${id}-window`}
                  name="score_run_id"
                  defaultValue={scoreRunId}
                >
                  {windows.map((window) => (
                    <option key={window.scoreRunId} value={window.scoreRunId}>
                      {window.label}
                    </option>
                  ))}
                </select>
              </span>
            </div>
          )}
          <ColorFilter
            label={t.common.colors}
            name="color"
            selected={current.getAll("color")}
            id={`${id}-colors`}
          />
          {types && (
            <div>
              <label htmlFor={`${id}-type`}>{t.common.cardType}</label>
              <span className="select">
                <select
                  id={`${id}-type`}
                  name="type"
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
          )}
          {minDecks.length > 0 && (
            <div>
              <label htmlFor={`${id}-min-decks`}>{t.commanders.minDecks}</label>
              <span className="select">
                <select
                  id={`${id}-min-decks`}
                  name="min_decks"
                  defaultValue={current.get("min_decks") ?? ""}
                >
                  {minDecks.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </span>
            </div>
          )}
          <div className="filter-menu-pair">
            <div>
              <label htmlFor={`${id}-sort`}>{t.rankings.sortBy}</label>
              <span className="select">
                <select id={`${id}-sort`} name="sort" defaultValue={sort}>
                  {sorts.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </span>
            </div>
            <div>
              <span className="group-label" id={`${id}-order`}>
                {t.rankings.order}
              </span>
              <div
                role="radiogroup"
                aria-labelledby={`${id}-order`}
                className="segmented"
              >
                {(["desc", "asc"] as const).map((direction) => (
                  <label key={direction}>
                    <input
                      type="radio"
                      name="order"
                      value={direction}
                      defaultChecked={order === direction}
                    />
                    {direction === "desc"
                      ? t.rankings.descending
                      : t.rankings.ascending}
                  </label>
                ))}
              </div>
            </div>
          </div>
          <div>
            <label htmlFor={`${id}-limit`}>{perPage}</label>
            <span className="select">
              <select
                id={`${id}-limit`}
                name="limit"
                defaultValue={current.get("limit") ?? ""}
              >
                {limits.map((size, index) => (
                  <option key={size} value={index ? String(size) : ""}>
                    {count(size)}
                  </option>
                ))}
              </select>
            </span>
          </div>
        </div>
        <footer className="filter-menu-foot">
          <Link
            className="button ghost sm"
            href={clearHref}
            onClick={() => close(true)}
          >
            {t.common.clearFilters}
          </Link>
          <button type="submit" className="sm">
            {t.rankings.menuShow}
          </button>
        </footer>
      </form>
    </div>
  );
}

/**
 * The views, grading, colors and card type of one pinned run. Each change replaces
 * the URL, so the server re-ranks; without JavaScript the form submits as a GET.
 * Sorting lives in the table's column headers and the search in the header;
 * given sorts, the last button opens a panel under the toolbar with every filter
 * and order at once. The commanders page ranks at its own path, with neither
 * views nor card types, and searches names only.
 */
export function RankingFilters({
  format,
  scoreRunId,
  query,
  clearHref,
  views = [],
  windows = [],
  sources = [],
  gradings = [],
  method = "",
  kinds = [],
  action = "/rankings",
  types = true,
  fields = true,
  minDecks = [],
  sorts = [],
  search,
  perPage,
  label,
  updating,
}: {
  format: string;
  scoreRunId: string;
  query: string;
  clearHref: string;
  views?: ViewTab[];
  windows?: WindowOption[];
  sources?: SourceTab[];
  gradings?: GradingOption[];
  method?: string;
  kinds?: KindTab[];
  action?: string;
  /** Whether the card type select applies. */
  types?: boolean;
  /** Whether the search can keep to a part of each card, as card rankings can. */
  fields?: boolean;
  /** Offered where small samples crowd an ordering, as on the commanders page. */
  minDecks?: MinDecksOption[];
  /** The orders the filter menu offers; without them there is no menu. */
  sorts?: SortOption[];
  /** The menu's labels for the name search and the page size, if not cards'. */
  search?: string;
  perPage?: string;
  label?: string;
  updating?: string;
}) {
  const router = useRouter();
  const { t, count, plural } = useI18n();
  const [pending, startTransition] = useTransition();
  const form = useRef<HTMLFormElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const panel = useId();
  const [open, setOpen] = useState(false);
  const [closings, setClosings] = useState(0);
  const close = (refocus = false) => {
    setOpen(false);
    setClosings((closed) => closed + 1);
    if (refocus) toggle.current!.focus();
  };
  const current = new URLSearchParams(query);
  const colors = current.getAll("color");
  const type = current.get("type") ?? "";
  const minimum = current.get("min_decks") ?? "";
  const view = current.get("view");
  // Kept as they are: a filter change re-ranks under the same search, order,
  // view and size.
  const kept = ["q", "in", "sort", "order", "view", "limit"].flatMap((key) => {
    const value = current.get(key);
    return value ? [[key, value] as const] : [];
  });
  const filtered = Boolean(
    current.get("q") || type || minimum || colors.length,
  );
  // The menu's badge counts each kind of filter set, not each color.
  const active = [current.get("q"), type, minimum, colors.length, view].filter(
    Boolean,
  ).length;
  // A link elsewhere (clear filters, the header search, history) changes the
  // address without remounting the form, so its controls follow the address.
  // The server rendered them from this address, so mounting leaves them alone:
  // a choice made before hydration would otherwise be undone.
  const colorKey = colors.join();
  const address = [colorKey, type, minimum, scoreRunId, method].join("\n");
  const synced = useRef(address);
  useEffect(() => {
    if (synced.current === address) return;
    synced.current = address;
    const controls = form.current!.elements;
    for (const box of controls.namedItem("color") as RadioNodeList)
      box.checked = colorKey.split(",").includes(box.value);
    const typeSelect = controls.namedItem("type");
    if (typeSelect instanceof HTMLSelectElement) typeSelect.value = type;
    (
      controls.namedItem("score_run_id") as HTMLInputElement | HTMLSelectElement
    ).value = scoreRunId;
    const grading = controls.namedItem("method");
    if (grading instanceof HTMLSelectElement) grading.value = method;
    const decks = controls.namedItem("min_decks");
    if (decks instanceof HTMLSelectElement) decks.value = minimum;
  }, [address, colorKey, type, minimum, scoreRunId, method]);
  useRefocus(form, `${scoreRunId}?${query}`);
  const apply = () =>
    startTransition(() =>
      router.replace(`${action}?${values(form.current!)}`, { scroll: false }),
    );
  return (
    // The panel opens inside the stuck toolbar, between it and the results.
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- only catches Escape bubbling up from the panel's own controls
    <div
      className="toolbar band ranking-toolbar"
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) close(true);
      }}
    >
      <form
        ref={form}
        action={action}
        method="get"
        aria-label={label ?? t.rankings.filters}
        aria-busy={pending || undefined}
        onChange={(event) => {
          rememberFocus(event.target);
          apply();
        }}
        onSubmit={(event) => {
          event.preventDefault();
          apply();
        }}
      >
        <div className="toolbar-inner band-inner">
          <input type="hidden" name="format" value={format} />
          {windows.length < 2 && (
            <input type="hidden" name="score_run_id" value={scoreRunId} />
          )}
          {gradings.length < 2 && method && (
            <input type="hidden" name="method" value={method} />
          )}
          {kept.map(([key, value]) => (
            <input key={key} type="hidden" name={key} value={value} />
          ))}
          {kinds.length > 1 && (
            <nav
              className="segmented sm kind-tabs"
              aria-label={t.commanders.kinds}
            >
              {kinds.map((tab) => (
                <Link
                  key={tab.href}
                  href={tab.href}
                  aria-current={tab.current ? "page" : undefined}
                >
                  {tab.label}
                </Link>
              ))}
            </nav>
          )}
          {views.length > 0 && (
            <nav className="view-tabs" aria-label={t.rankings.views}>
              {views.map((tab) => (
                <Link
                  key={tab.view}
                  href={tab.href}
                  aria-current={tab.current ? "page" : undefined}
                  scroll={false}
                >
                  {tab.label}
                  <span className="tab-count">{count(tab.count)}</span>
                </Link>
              ))}
            </nav>
          )}
          <span role="status" className="toolbar-status">
            {pending ? (updating ?? t.rankings.updating) : ""}
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
          <ColorFilter
            label={t.common.colors}
            name="color"
            selected={colors}
            hideLabel
          />
          {types && (
            <span className="select">
              <select
                aria-label={t.common.cardType}
                name="type"
                defaultValue={type}
              >
                <option value="">{t.common.allCardTypes}</option>
                {cardTypes.map((value) => (
                  <option key={value} value={value}>
                    {t.cardTypes[value]}
                  </option>
                ))}
              </select>
            </span>
          )}
          {minDecks.length > 0 && (
            <span className="select">
              <select
                aria-label={t.commanders.minDecks}
                name="min_decks"
                defaultValue={minimum}
              >
                {minDecks.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </span>
          )}
          {windows.length > 1 && (
            <span className="select">
              <select
                aria-label={t.rankings.windowSelect}
                name="score_run_id"
                defaultValue={scoreRunId}
              >
                {windows.map((window) => (
                  <option key={window.scoreRunId} value={window.scoreRunId}>
                    {window.label}
                  </option>
                ))}
              </select>
            </span>
          )}
          {sources.length > 1 && (
            <nav
              className="segmented sm source-tabs"
              aria-label={t.rankings.sources}
            >
              {sources.map((tab) => (
                <Link
                  key={tab.source}
                  href={tab.href}
                  aria-current={tab.current ? "page" : undefined}
                >
                  {tab.label}
                </Link>
              ))}
            </nav>
          )}
          {filtered && (
            <Link className="button ghost sm" href={clearHref}>
              {t.common.clearFilters}
            </Link>
          )}
          {sorts.length > 0 && (
            <button
              ref={toggle}
              type="button"
              className="secondary sm filter-menu-button"
              aria-expanded={open}
              aria-controls={panel}
              onClick={() => (open ? close() : setOpen(true))}
            >
              <Icon name="sliders-horizontal" size={14} />
              {t.rankings.menu}
              {active > 0 && (
                <>
                  <span className="filter-menu-count" aria-hidden="true">
                    {count(active)}
                  </span>
                  {/* Flex layout drops the space; the button's name keeps it. */}{" "}
                  <span className="sr-only">
                    {plural(t.rankings.menuActive, active)}
                  </span>
                </>
              )}
            </button>
          )}
          <noscript>
            <button type="submit" className="sm">
              {t.common.apply}
            </button>
          </noscript>
        </div>
      </form>
      {sorts.length > 0 && (
        <FilterMenu
          id={panel}
          open={open}
          closings={closings}
          close={close}
          format={format}
          scoreRunId={scoreRunId}
          query={query}
          clearHref={clearHref}
          views={views}
          windows={windows}
          gradings={gradings}
          method={method}
          minDecks={minDecks}
          sorts={sorts}
          action={action}
          types={types}
          fields={fields}
          search={search ?? t.search.rankedCards}
          perPage={perPage ?? t.filters.perPage}
          apply={(chosen) =>
            startTransition(() =>
              router.replace(`${action}?${chosen}`, { scroll: false }),
            )
          }
        />
      )}
    </div>
  );
}
