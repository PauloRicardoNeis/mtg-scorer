"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
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

/** Catalog-wide name search. "/" focuses it from anywhere outside a field. */
export function HeaderSearch() {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
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
      action="/cards"
      onSubmit={(event) => {
        event.preventDefault();
        const query = new URLSearchParams();
        const snapshot = currentSnapshot();
        if (snapshot) query.set("catalog_snapshot_id", snapshot);
        const name = input.current?.value.trim();
        if (name) query.set("q", name);
        router.push(query.size ? `/cards?${query}` : "/cards");
      }}
    >
      <label className="sr-only" htmlFor="site-search">
        Search cards
      </label>
      <div className="field">
        <Icon name="search" size={15} />
        <input
          ref={input}
          id="site-search"
          name="q"
          type="search"
          maxLength={100}
          placeholder="Search cards"
          autoComplete="off"
          aria-keyshortcuts="/"
        />
        <kbd className="key" aria-hidden="true">
          /
        </kbd>
      </div>
    </form>
  );
}
