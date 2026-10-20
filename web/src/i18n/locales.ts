// The languages Magic cards are printed in, each named in its own language for the
// picker. Codes are BCP 47 tags, as <html lang> and Intl expect.
export const locales = [
  { code: "en", name: "English" },
  { code: "es", name: "Español" },
  { code: "fr", name: "Français" },
  { code: "de", name: "Deutsch" },
  { code: "it", name: "Italiano" },
  { code: "pt-BR", name: "Português (Brasil)" },
  { code: "ja", name: "日本語" },
  { code: "ko", name: "한국어" },
  { code: "ru", name: "Русский" },
  { code: "zh-Hans", name: "简体中文" },
  { code: "zh-Hant", name: "繁體中文" },
] as const;

export type Locale = (typeof locales)[number]["code"];

export const defaultLocale: Locale = "en";

/** The cookie that keeps a reader's chosen language. */
export const LOCALE_COOKIE = "locale";

export function isLocale(value: unknown): value is Locale {
  return locales.some(({ code }) => code === value);
}

// Chinese tags name a script, or a region that implies one.
const traditional = /-(hant|tw|hk|mo)(-|$)/;

/** The supported language closest to one language tag, or null: "pt-PT" → "pt-BR". */
function closest(tag: string): Locale | null {
  const lower = tag.toLowerCase();
  const exact = locales.find(({ code }) => code.toLowerCase() === lower);
  if (exact) return exact.code;
  const language = lower.split("-")[0];
  if (language === "zh") return traditional.test(lower) ? "zh-Hant" : "zh-Hans";
  return (
    locales.find(({ code }) => code.split("-")[0] === language)?.code ?? null
  );
}

/**
 * The language to show: the reader's choice when they made one, else their browser's
 * most preferred supported language, else English.
 */
export function negotiate(
  chosen: string | undefined,
  acceptLanguage: string | null,
): Locale {
  if (isLocale(chosen)) return chosen;
  const preferences = (acceptLanguage ?? "")
    .split(",")
    .map((entry) => {
      const [tag, ...params] = entry.trim().split(";");
      const q = params.find((param) => param.trim().startsWith("q="));
      return { tag, weight: q ? Number(q.trim().slice(2)) : 1 };
    })
    .filter(({ tag, weight }) => tag && tag !== "*" && weight > 0)
    // Array sort is stable, so equal weights keep the header's order.
    .sort((a, b) => b.weight - a.weight);
  for (const { tag } of preferences) {
    const locale = closest(tag);
    if (locale) return locale;
  }
  return defaultLocale;
}
