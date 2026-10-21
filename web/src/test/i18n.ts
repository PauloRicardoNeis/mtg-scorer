import { en } from "@/i18n/messages/en";
import { createI18n } from "@/i18n/translator";

/** English, for tests that pass a language to helpers outside components. */
export const english = createI18n("en", en);

// No-break (U+00A0), thin (U+2009) and narrow no-break (U+202F) spaces, built from
// their code points so the source holds no invisible characters.
const unusualSpaces = new RegExp(
  `[${String.fromCharCode(0xa0, 0x2009, 0x202f)}]`,
  "g",
);

/**
 * Intl's dates set thin or no-break spaces that vary between ICU versions, so
 * tests compare them as plain spaces.
 */
export function spaced(text: string): string {
  return text.replace(unusualSpaces, " ");
}
