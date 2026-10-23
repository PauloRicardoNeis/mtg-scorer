import type { components } from "./api.generated";

export type CardPage = components["schemas"]["CardPage"];
export type CardDetail = components["schemas"]["CardDetail"];
export type PrintingPage = components["schemas"]["PrintingPage"];
export type Printing = components["schemas"]["Printing"];
export type Snapshot = components["schemas"]["Snapshot"];
export type SnapshotList = components["schemas"]["SnapshotList"];
export type RankingPage = components["schemas"]["RankingPage"];
export type RankedCard = components["schemas"]["RankedCard"];
export type ComparePage = components["schemas"]["ComparePage"];
export type ComparedCard = components["schemas"]["ComparedCard"];
export type CommanderPage = components["schemas"]["CommanderPage"];
export type RankedCommander = components["schemas"]["RankedCommander"];
export type CardDeckPage = components["schemas"]["CardDeckPage"];
export type CardDeck = components["schemas"]["CardDeck"];
export type DeckDetail = components["schemas"]["DeckDetail"];
export type DeckCard = components["schemas"]["DeckCard"];
type CatalogError = components["schemas"]["CatalogError"];

/** The catalog's error codes, plus the sample metagame data's own not-found cases. */
export type ErrorCode =
  CatalogError["code"] | "archetype_not_found" | "decklist_not_found";

export class ApiError extends Error {
  constructor(
    public readonly code: ErrorCode,
    public readonly status: number,
  ) {
    super(code);
  }
}

/** Server-side only: product requests terminate at the Java API. */
async function read<T>(path: string, query?: URLSearchParams): Promise<T> {
  const origin = process.env.CATALOG_API_URL ?? "http://127.0.0.1:18080";
  let response: Response;
  try {
    response = await fetch(
      `${origin}/api/v1${path}${query?.size ? `?${query}` : ""}`,
      {
        cache: "no-store",
        signal: AbortSignal.timeout(8000),
      },
    );
  } catch {
    throw new ApiError("catalog_unavailable", 503);
  }
  if (!response.ok) {
    // A proxy in front of the API can answer with an HTML error page.
    const problem = (await response
      .json()
      .catch(() => ({}))) as Partial<CatalogError>;
    throw new ApiError(problem.code ?? "internal_error", response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  cards: (query: URLSearchParams) => read<CardPage>("/cards", query),
  card: (id: string, snapshot: string) =>
    read<CardDetail>(
      `/cards/${encodeURIComponent(id)}`,
      new URLSearchParams({ catalog_snapshot_id: snapshot }),
    ),
  printings: (id: string, query: URLSearchParams) =>
    read<PrintingPage>(`/cards/${encodeURIComponent(id)}/printings`, query),
  decks: (id: string, query: URLSearchParams) =>
    read<CardDeckPage>(`/cards/${encodeURIComponent(id)}/decks`, query),
  deck: (scoreRun: string, position: string, query: URLSearchParams) =>
    read<DeckDetail>(
      `/decks/${encodeURIComponent(scoreRun)}/${encodeURIComponent(position)}`,
      query,
    ),
  snapshot: (id: string) =>
    read<Snapshot>(`/snapshots/${encodeURIComponent(id)}`),
  snapshots: () => read<SnapshotList>("/snapshots"),
  rankings: (query: URLSearchParams) => read<RankingPage>("/rankings", query),
  compare: (query: URLSearchParams) =>
    read<ComparePage>("/rankings/compare", query),
  commanders: (query: URLSearchParams) =>
    read<CommanderPage>("/rankings/commanders", query),
};
