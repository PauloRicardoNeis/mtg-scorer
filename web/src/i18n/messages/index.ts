import type { Locale } from "../locales";
import type { Messages } from "../types";
import { de } from "./de";
import { en } from "./en";
import { es } from "./es";
import { fr } from "./fr";
import { it } from "./it";
import { ja } from "./ja";
import { ko } from "./ko";
import { ptBR } from "./pt-BR";
import { ru } from "./ru";
import { zhHans } from "./zh-Hans";
import { zhHant } from "./zh-Hant";

/** Every language's messages, for the server; the browser receives only the reader's. */
export const messages: Record<Locale, Messages> = {
  en,
  es,
  fr,
  de,
  it,
  "pt-BR": ptBR,
  ja,
  ko,
  ru,
  "zh-Hans": zhHans,
  "zh-Hant": zhHant,
};
