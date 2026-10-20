import { describe, expect, it, vi } from "vitest";
import { cookies } from "next/headers";
import { setLocale } from "./actions";

vi.mock("next/headers", () => ({ cookies: vi.fn() }));

function form(locale: string | null) {
  const data = new FormData();
  if (locale !== null) data.set("locale", locale);
  return data;
}

describe("setLocale", () => {
  it("saves a supported language for a year", async () => {
    const set = vi.fn();
    vi.mocked(cookies).mockResolvedValue({ set } as never);
    await setLocale(form("ko"));
    expect(set).toHaveBeenCalledWith("locale", "ko", {
      path: "/",
      maxAge: 31_536_000,
      sameSite: "lax",
    });
  });

  it("ignores anything else", async () => {
    const set = vi.fn();
    vi.mocked(cookies).mockResolvedValue({ set } as never);
    await setLocale(form("xx"));
    await setLocale(form(null));
    expect(set).not.toHaveBeenCalled();
  });
});
