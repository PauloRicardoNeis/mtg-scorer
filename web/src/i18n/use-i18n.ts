import { useContext } from "react";
import { I18nContext } from "./context";
import type { I18n } from "./translator";

/**
 * The reader's language in client components. Import it as "#i18n": server
 * components resolve that to use-i18n.server.ts instead, so shared components
 * call the same hook wherever they render.
 */
export function useI18n(): I18n {
  return useContext(I18nContext);
}
