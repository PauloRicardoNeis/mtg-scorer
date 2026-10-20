"use server";

import { cookies } from "next/headers";
import { isLocale, LOCALE_COOKIE } from "./locales";

/** Saves the reader's language for a year; the page then renders again in it. */
export async function setLocale(form: FormData): Promise<void> {
  const locale = form.get("locale");
  if (!isLocale(locale)) return;
  (await cookies()).set(LOCALE_COOKIE, locale, {
    path: "/",
    maxAge: 365 * 86_400,
    sameSite: "lax",
  });
}
