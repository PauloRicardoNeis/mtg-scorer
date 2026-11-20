import { describe, expect, it } from "vitest";

import { openGraph } from "./metadata";

describe("openGraph", () => {
  it("names the site and the page type every page's Open Graph tags share", () => {
    expect(openGraph).toEqual({ siteName: "MTG Scorer", type: "website" });
  });
});
