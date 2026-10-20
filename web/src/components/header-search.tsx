"use client";

import { Suspense, useEffect, useRef, type RefObject } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useI18n } from "#i18n";
import { Icon } from "./icon";

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

// Rankings' name filter lives in the header, so the box shows the current one.
// Search params need a Suspense boundary on statically rendered pages.
function RankingQuery({
  input,
}: {
  input: RefObject<HTMLInputElement | null>;
}) {
  const q = useSearchParams().get("q") ?? "";
  useEffect(() => {
    // Refs attach before effects run, so the box exists here.
    const box = input.current!;
    box.value = q;
    // Leaving rankings leaves no name filter behind in the box.
    return () => {
      box.value = "";
    };
  }, [input, q]);
  return null;
}

/** The query a rankings search navigates to: the same filters with a new name. */
function rankingSearch(name: string | undefined): string {
  const query = new URLSearchParams(location.search);
  query.delete("q");
  query.delete("offset");
  if (name) query.set("q", name);
  // The compare page searches its own table; every other rankings page the run.
  const path = location.pathname.startsWith("/rankings/compare")
    ? "/rankings/compare"
    : "/rankings";
  return query.size ? `${path}?${query}` : path;
}

/**
 * Name search: within the shown run's rankings on /rankings, catalog-wide
 * elsewhere. "/" focuses it from anywhere outside a field.
 */
export function HeaderSearch() {
  const router = useRouter();
  const rankings = /^\/rankings(\/|$)/.test(usePathname());
  const input = useRef<HTMLInputElement>(null);
  const { t } = useI18n();
  const label = rankings ? t.search.rankedCards : t.search.cards;
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
        if (rankings) {
          router.push(rankingSearch(input.current?.value.trim()));
          return;
        }
        const query = new URLSearchParams();
        const snapshot = currentSnapshot();
        if (snapshot) query.set("catalog_snapshot_id", snapshot);
        const name = input.current?.value.trim();
        if (name) query.set("q", name);
        router.push(query.size ? `/cards?${query}` : "/cards");
      }}
    >
      <label className="sr-only" htmlFor="site-search">
        {label}
      </label>
      <div className="field">
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
          <RankingQuery input={input} />
        </Suspense>
      )}
    </form>
  );
}
