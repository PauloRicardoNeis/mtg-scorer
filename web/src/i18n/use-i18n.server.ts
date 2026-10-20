import { use } from "react";
import { getI18n } from "./server";
import type { I18n } from "./translator";

/** The request's language in server components; see use-i18n.ts. */
export function useI18n(): I18n {
  return use(getI18n());
}
