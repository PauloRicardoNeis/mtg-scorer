import { en } from "@/i18n/messages/en";
import { createI18n } from "@/i18n/translator";

/** English, for tests that pass a language to helpers outside components. */
export const english = createI18n("en", en);

/**
 * Intl's dates set thin or no-break spaces that vary between ICU versions, so
 * tests compare them as plain spaces.
 */
export function spaced(text: string): string {
  return text.replace(/[   ]/g, " ");
}
