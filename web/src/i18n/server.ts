import { cache } from "react";
import { cookies, headers } from "next/headers";
import { LOCALE_COOKIE, negotiate } from "./locales";
import { messages } from "./messages";
import { createI18n } from "./translator";

/**
 * The request's language: the reader's saved choice, else their browser's. Cached
 * per request, so the layout, page and components share one answer.
 */
export const getI18n = cache(async () => {
  const locale = negotiate(
    (await cookies()).get(LOCALE_COOKIE)?.value,
    (await headers()).get("accept-language"),
  );
  return createI18n(locale, messages[locale]);
});
