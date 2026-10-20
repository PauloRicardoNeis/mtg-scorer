import { describe, expect, it } from "vitest";
import { defaultLocale, isLocale, locales, negotiate } from "./locales";

describe("isLocale", () => {
  it("accepts only the supported codes, exactly", () => {
    for (const { code } of locales) expect(isLocale(code)).toBe(true);
    expect(isLocale("pt")).toBe(false);
    expect(isLocale("EN")).toBe(false);
    expect(isLocale(undefined)).toBe(false);
  });
});

describe("negotiate", () => {
  it("keeps a saved choice over the browser's languages", () => {
    expect(negotiate("ja", "de-DE,de;q=0.9")).toBe("ja");
  });

  it("ignores a saved value that is no longer supported", () => {
    expect(negotiate("xx", "fr-FR")).toBe("fr");
  });

  it("falls back to English without a usable preference", () => {
    expect(defaultLocale).toBe("en");
    expect(negotiate(undefined, null)).toBe("en");
    expect(negotiate(undefined, "")).toBe("en");
    expect(negotiate(undefined, "*")).toBe("en");
    expect(negotiate(undefined, "nl-NL,sv;q=0.5")).toBe("en");
  });

  it("follows the browser's weights, keeping its order among equals", () => {
    expect(negotiate(undefined, "de;q=0.5,ko;q=0.8")).toBe("ko");
    expect(negotiate(undefined, "it,es")).toBe("it");
    expect(negotiate(undefined, "nl,ru;q=0.3")).toBe("ru");
  });

  it("skips languages the browser rules out", () => {
    expect(negotiate(undefined, "fr;q=0,es;q=0.2")).toBe("es");
    expect(negotiate(undefined, "fr;q=abc,es;q=0.2")).toBe("es");
  });

  it("matches tags case-insensitively and by language", () => {
    expect(negotiate(undefined, "PT-br")).toBe("pt-BR");
    expect(negotiate(undefined, "pt-PT")).toBe("pt-BR");
    expect(negotiate(undefined, "en-GB")).toBe("en");
    expect(negotiate(undefined, "es-419")).toBe("es");
  });

  it("reads the Chinese script from the tag or its region", () => {
    expect(negotiate(undefined, "zh")).toBe("zh-Hans");
    expect(negotiate(undefined, "zh-CN")).toBe("zh-Hans");
    expect(negotiate(undefined, "zh-Hans-SG")).toBe("zh-Hans");
    expect(negotiate(undefined, "zh-TW")).toBe("zh-Hant");
    expect(negotiate(undefined, "zh-HK")).toBe("zh-Hant");
    expect(negotiate(undefined, "zh-MO")).toBe("zh-Hant");
    expect(negotiate(undefined, "zh-Hant")).toBe("zh-Hant");
  });
});
