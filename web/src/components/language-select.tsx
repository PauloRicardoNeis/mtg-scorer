"use client";

import { useI18n } from "#i18n";
import { setLocale } from "@/i18n/actions";
import { locales } from "@/i18n/locales";
import { Icon } from "./icon";

/**
 * The site's language, each option named in its own language. Choosing one saves it
 * and renders the page again in it; without JavaScript, Apply submits the form.
 */
export function LanguageSelect() {
  const { t, locale } = useI18n();
  return (
    <form action={setLocale} className="language-select">
      <label htmlFor="language">
        <Icon name="globe" size={14} />
        {t.language.label}
      </label>
      <span className="select">
        <select
          id="language"
          name="locale"
          defaultValue={locale}
          onChange={(event) => event.currentTarget.form!.requestSubmit()}
        >
          {locales.map(({ code, name }) => (
            <option key={code} value={code} lang={code}>
              {name}
            </option>
          ))}
        </select>
      </span>
      <noscript>
        <button type="submit" className="secondary sm">
          {t.common.apply}
        </button>
      </noscript>
    </form>
  );
}
