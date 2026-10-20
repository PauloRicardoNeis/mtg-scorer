import { describe, expect, it, vi } from "vitest";
import { cookies, headers } from "next/headers";
import { de } from "./messages/de";
import { en } from "./messages/en";
import { ja } from "./messages/ja";
import { getI18n } from "./server";

vi.mock("next/headers", () => ({ cookies: vi.fn(), headers: vi.fn() }));

/** A request with an optional saved language and Accept-Language header. */
function request(saved: string | undefined, accept: string | null) {
  vi.mocked(cookies).mockResolvedValue({
    get: (name: string) =>
      name === "locale" && saved ? { name, value: saved } : undefined,
  } as never);
  vi.mocked(headers).mockResolvedValue(
    new Headers(accept === null ? {} : { "accept-language": accept }),
  );
}

describe("getI18n", () => {
  it("reads the saved language first", async () => {
    request("ja", "de-DE");
    const i18n = await getI18n();
    expect(i18n.locale).toBe("ja");
    expect(i18n.t).toBe(ja);
  });

  it("falls back to the browser's language", async () => {
    request(undefined, "de-DE,de;q=0.9");
    expect((await getI18n()).t).toBe(de);
  });

  it("falls back to English without either", async () => {
    request(undefined, null);
    const i18n = await getI18n();
    expect(i18n.locale).toBe("en");
    expect(i18n.t).toBe(en);
  });
});
