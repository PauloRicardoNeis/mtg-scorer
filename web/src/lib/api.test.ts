// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockResolvedValue(Response.json({ ok: true }));
});

function requested(): { url: string; init: RequestInit | undefined } {
  expect(fetchMock).toHaveBeenCalledTimes(1);
  const [input, init] = fetchMock.mock.calls[0];
  const url =
    typeof input === "string"
      ? input
      : input instanceof URL
        ? input.href
        : input.url;
  return { url, init };
}

describe("request URLs", () => {
  it("defaults to the local Java API", async () => {
    vi.stubEnv("CATALOG_API_URL", undefined);
    await api.snapshots();
    expect(requested().url).toBe("http://127.0.0.1:18080/api/v1/snapshots");
  });

  it("uses CATALOG_API_URL when set", async () => {
    vi.stubEnv("CATALOG_API_URL", "http://catalog.internal:9000");
    await api.snapshots();
    expect(requested().url).toBe(
      "http://catalog.internal:9000/api/v1/snapshots",
    );
  });

  it("appends the query string to card searches", async () => {
    vi.stubEnv("CATALOG_API_URL", "http://api");
    await api.cards(
      new URLSearchParams([
        ["q", "Æther vial"],
        ["set", "m11"],
        ["set", "lea"],
      ]),
    );
    expect(requested().url).toBe(
      "http://api/api/v1/cards?q=%C3%86ther+vial&set=m11&set=lea",
    );
  });

  it("requests rankings with the given filters", async () => {
    vi.stubEnv("CATALOG_API_URL", "http://api");
    await api.rankings(
      new URLSearchParams([
        ["format", "Modern"],
        ["color", "R"],
        ["color", "C"],
      ]),
    );
    expect(requested().url).toBe(
      "http://api/api/v1/rankings?format=Modern&color=R&color=C",
    );
  });

  it("requests a comparison across the given formats", async () => {
    vi.stubEnv("CATALOG_API_URL", "http://api");
    await api.compare(
      new URLSearchParams([
        ["format", "Modern"],
        ["format", "Legacy"],
        ["every", "true"],
      ]),
    );
    expect(requested().url).toBe(
      "http://api/api/v1/rankings/compare?format=Modern&format=Legacy&every=true",
    );
  });

  it("omits the question mark for an empty query", async () => {
    vi.stubEnv("CATALOG_API_URL", "http://api");
    await api.cards(new URLSearchParams());
    expect(requested().url).toBe("http://api/api/v1/cards");
  });

  it("encodes card ids as one path segment and pins the dataset", async () => {
    vi.stubEnv("CATALOG_API_URL", "http://api");
    await api.card("a/b c?d", "snap 1");
    expect(requested().url).toBe(
      "http://api/api/v1/cards/a%2Fb%20c%3Fd?catalog_snapshot_id=snap+1",
    );
  });

  it("requests a card's printings with the given filters", async () => {
    vi.stubEnv("CATALOG_API_URL", "http://api");
    await api.printings("oracle#1", new URLSearchParams("set=m11"));
    expect(requested().url).toBe(
      "http://api/api/v1/cards/oracle%231/printings?set=m11",
    );
  });

  it("requests a card's decks in the pinned run", async () => {
    vi.stubEnv("CATALOG_API_URL", "http://api");
    await api.decks("oracle#1", new URLSearchParams("offset=20"));
    expect(requested().url).toBe(
      "http://api/api/v1/cards/oracle%231/decks?offset=20",
    );
  });

  it("requests one deck of a run in the given catalog", async () => {
    vi.stubEnv("CATALOG_API_URL", "http://api");
    await api.deck(
      "scores-a",
      "7",
      new URLSearchParams("catalog_snapshot_id=c"),
    );
    expect(requested().url).toBe(
      "http://api/api/v1/decks/scores-a/7?catalog_snapshot_id=c",
    );
  });

  it("encodes snapshot ids", async () => {
    vi.stubEnv("CATALOG_API_URL", "http://api");
    await api.snapshot("2026/10 é");
    expect(requested().url).toBe(
      "http://api/api/v1/snapshots/2026%2F10%20%C3%A9",
    );
  });
});

describe("request options", () => {
  it("never caches and times out after eight seconds", async () => {
    const timeout = vi.spyOn(AbortSignal, "timeout");
    await api.snapshots();
    const { init } = requested();
    expect(init?.cache).toBe("no-store");
    expect(timeout).toHaveBeenCalledWith(8000);
    expect(init?.signal).toBe(timeout.mock.results[0].value);
  });
});

describe("responses", () => {
  it("returns the parsed body of a successful response", async () => {
    const list = { active_catalog_snapshot_id: "snap-1", items: [] };
    fetchMock.mockResolvedValue(Response.json(list));
    await expect(api.snapshots()).resolves.toEqual(list);
  });

  it("reports an unreachable API as catalog_unavailable", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));
    const error = await api.snapshots().catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toBeInstanceOf(Error);
    expect(error).toMatchObject({
      code: "catalog_unavailable",
      status: 503,
      message: "catalog_unavailable",
    });
  });

  it("reports a timed-out request as catalog_unavailable", async () => {
    fetchMock.mockRejectedValue(
      new DOMException("The operation timed out.", "TimeoutError"),
    );
    await expect(api.snapshot("snap-1")).rejects.toMatchObject({
      code: "catalog_unavailable",
      status: 503,
    });
  });

  it("carries the problem code and HTTP status of an error response", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        { code: "card_not_found", status: 404, title: "Not found" },
        { status: 404 },
      ),
    );
    const error = await api
      .card("missing", "snap-1")
      .catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "card_not_found", status: 404 });
  });

  it("reports a non-JSON error page by its HTTP status", async () => {
    fetchMock.mockResolvedValue(
      new Response("<html><body>502 Bad Gateway</body></html>", {
        status: 502,
        headers: { "Content-Type": "text/html" },
      }),
    );
    const error = await api.snapshots().catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "internal_error", status: 502 });
  });

  it("falls back to internal_error when the problem has no code", async () => {
    fetchMock.mockResolvedValue(Response.json({}, { status: 500 }));
    await expect(api.cards(new URLSearchParams())).rejects.toMatchObject({
      code: "internal_error",
      status: 500,
    });
  });
});
