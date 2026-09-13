import type { components } from "./api.generated";

export type CardPage = components["schemas"]["CardPage"];
export type CardDetail = components["schemas"]["CardDetail"];
export type PrintingPage = components["schemas"]["PrintingPage"];
export type Printing = components["schemas"]["Printing"];
export type Snapshot = components["schemas"]["Snapshot"];
export type SnapshotList = components["schemas"]["SnapshotList"];
type CatalogError = components["schemas"]["CatalogError"];

export class ApiError extends Error {
  constructor(
    public readonly code: CatalogError["code"],
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
    const problem = (await response.json()) as CatalogError;
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
  snapshot: (id: string) =>
    read<Snapshot>(`/snapshots/${encodeURIComponent(id)}`),
  snapshots: () => read<SnapshotList>("/snapshots"),
};
