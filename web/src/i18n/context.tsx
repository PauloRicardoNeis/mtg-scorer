"use client";

import { createContext, useMemo, type ReactNode } from "react";
import type { Locale } from "./locales";
import { en } from "./messages/en";
import { createI18n, type I18n } from "./translator";
import type { Messages } from "./types";

// Without a provider (unit tests, the primitives gallery) components read English.
export const I18nContext = createContext<I18n>(createI18n("en", en));

/** Hands the layout's language to client components; only its messages reach the browser. */
export function I18nProvider({
  locale,
  messages,
  children,
}: {
  locale: Locale;
  messages: Messages;
  children: ReactNode;
}) {
  const i18n = useMemo(() => createI18n(locale, messages), [locale, messages]);
  return <I18nContext value={i18n}>{children}</I18nContext>;
}
