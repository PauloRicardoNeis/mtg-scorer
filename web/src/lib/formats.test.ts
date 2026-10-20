import { describe, expect, it } from "vitest";
import { en } from "@/i18n/messages/en";
import { designFormats, formatLabel } from "./formats";

describe("formats", () => {
  it("names TopDeck's EDH as Commander and keeps other names", () => {
    expect(formatLabel("EDH")).toBe("Commander");
    expect(formatLabel("Modern")).toBe("Modern");
    expect(formatLabel("Old School 93/94")).toBe("Old School 93/94");
  });

  it("describes every design format", () => {
    for (const [, format] of designFormats)
      expect(
        en.formats.descriptors[format as keyof typeof en.formats.descriptors],
      ).toBeTruthy();
  });
});
