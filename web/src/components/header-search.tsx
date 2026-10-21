"use client";

import { Suspense, useEffect, useRef, type RefObject } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useI18n } from "#i18n";
import { Icon } from "./icon";
import { SearchIn, searchField } from "./search-in";

// The dataset a page shows: in the query on card pages, in the path on dataset pages.
function currentSnapshot(): string | null {
  return (
    new URLSearchParams(location.search).get("catalog_snapshot_id") ??
    datasetInPath()
  );
}

// A malformed escape cannot name a dataset, so the search falls back to the default.
function datasetInPath(): string | null {
  const dataset = location.pathname.match(/^\/datasets\/([^/]+)/);
  if (!dataset) return null;
  try {
    return decodeURIComponent(dataset[1]);
  } catch {
    return null;
  }
}

// Rankings' search lives in the header, so the box shows the current one and
// where it looks. Search params need a Suspense boundary on statically rendered
// pages.
function RankingQuery({
  input,
  scope,
}: {
  input: RefObject<HTMLInputElement | null>;
  scope: RefObject<HTMLSelectElement | null>;
}) {
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const field = searchField(params.get("in"));
  /* eslint-disable react-hooks/immutability -- the effect writes the address into
     the inputs the parent owns through refs; nothing of React's is mutated. */
  useEffect(() => {
    // Refs attach before effects run, so the box exists here; the commanders
    // page searches names only and has no select.
    const box = input.current!;
    const select = scope.current;
    box.value = q;
    if (select) select.value = field;
    // Leaving rankings leaves no search behind in the box.
    return () => {
      box.value = "";
      if (select) select.value = "";
    };
  }, [input, scope, q, field]);
  /* eslint-enable react-hooks/immutability */
  return null;
}

/** The query a rankings search navigates to: the same filters with new text. */
function rankingSearch(text: string | undefined, field: string): string {
  const query = new URLSearchParams(location.search);
  for (const key of ["q", "in", "offset"]) query.delete(key);
  if (text) query.set("q", text);
  if (text && field) query.set("in", field);
  // The compare and commanders pages search their own tables; every other
  // rankings page the run's cards.
  const path =
    ["/rankings/compare", "/rankings/commanders"].find((page) =>
      location.pathname.startsWith(page),
    ) ?? "/rankings";
  return query.size ? `${path}?${query}` : path;
}

/**
 * Card search: within the shown run's rankings on /rankings, catalog-wide
 * elsewhere, in the whole card or the part its select names. Commanders are
 * searched by name. "/" focuses it from anywhere outside a field.
 */
export function HeaderSearch() {
  const router = useRouter();
  const pathname = usePathname();
  const rankings = /^\/rankings(\/|$)/.test(pathname);
  const commanders = pathname.startsWith("/rankings/commanders");
  const input = useRef<HTMLInputElement>(null);
  const scope = useRef<HTMLSelectElement>(null);
  const { t } = useI18n();
  const label = commanders
    ? t.search.commanders
    : rankings
      ? t.search.rankedCards
      : t.search.cards;
  useEffect(() => {
    const focus = (event: KeyboardEvent) => {
      if (
        event.key !== "/" ||
        event.ctrlKey ||
        event.metaKey ||
        event.altKey ||
        event.defaultPrevented
      )
        return;
      const target = event.target as HTMLElement;
      if (target.isContentEditable || target.closest("input, textarea, select"))
        return;
      event.preventDefault();
      input.current?.focus();
      input.current?.select();
    };
    document.addEventListener("keydown", focus);
    return () => document.removeEventListener("keydown", focus);
  }, []);
  return (
    <form
      role="search"
      className="header-search"
      action={rankings ? "/rankings" : "/cards"}
      onSubmit={(event) => {
        event.preventDefault();
        const text = input.current?.value.trim();
        const field = scope.current?.value ?? "";
        if (rankings) {
          router.push(rankingSearch(text, field));
          return;
        }
        const query = new URLSearchParams();
        const snapshot = currentSnapshot();
        if (snapshot) query.set("catalog_snapshot_id", snapshot);
        if (text) query.set("q", text);
        if (text && field) query.set("in", field);
        router.push(query.size ? `/cards?${query}` : "/cards");
      }}
    >
      <label className="sr-only" htmlFor="site-search">
        {label}
      </label>
      <div className="field">
        {!commanders && <SearchIn ref={scope} />}
        <Icon name="search" size={15} />
        <input
          ref={input}
          id="site-search"
          name="q"
          type="search"
          maxLength={100}
          placeholder={label}
          autoComplete="off"
          aria-keyshortcuts="/"
        />
        <kbd className="key" aria-hidden="true">
          /
        </kbd>
      </div>
      {rankings && (
        <Suspense fallback={null}>
          <RankingQuery input={input} scope={scope} />
        </Suspense>
      )}
    </form>
  );
}
