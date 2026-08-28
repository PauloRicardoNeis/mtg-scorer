import "server-only";

export type CardSort =
  | "STAPLE"
  | "BUILDAROUND"
  | "EVIDENCE"
  | "DISTINCTIVENESS";

export type CatalogSnapshot = {
  datasetSnapshotId: string;
  featurePipelineVersion: string;
  scoreModelVersion: string;
  scoreConfigHash: string;
  publishedAt: string;
};

export type CardPrinting = {
  setCode: string;
  rarity: string;
  releasedAt: string;
};

export type CardScores = {
  staple: number;
  buildaroundSignal: number;
  evidence: number;
  distinctivenessDelta: number;
  stapleFeatureCoverage: number;
  buildaroundFeatureCoverage: number;
};

export type PublishedCardScore = {
  oracleId: string;
  name: string;
  colors: string[];
  printings: CardPrinting[];
  scores: CardScores;
  reasons: string[];
};

export type CardSearchResponse = {
  contractVersion: "card-catalog-v1";
  catalogKind: "DEMONSTRATION" | "EMPIRICAL";
  snapshot: CatalogSnapshot;
  total: number;
  cards: PublishedCardScore[];
};

export type CatalogFilters = {
  query: string;
  set: string;
  rarity: string;
  sort: CardSort;
};

export async function searchCards(filters: CatalogFilters): Promise<CardSearchResponse> {
  const apiBaseUrl = process.env.MTG_SCORER_API_URL ?? "http://localhost:8080";
  const search = new URLSearchParams({ sort: filters.sort, limit: "24" });
  if (filters.query) search.set("query", filters.query);
  if (filters.set) search.set("set", filters.set);
  if (filters.rarity) search.set("rarity", filters.rarity);

  const response = await fetch(`${apiBaseUrl}/api/v1/cards?${search}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`MTG Scorer API returned ${response.status}`);
  }
  return response.json() as Promise<CardSearchResponse>;
}
