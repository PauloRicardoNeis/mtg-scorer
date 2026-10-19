import Link from "next/link";
import { ApiError } from "@/lib/api";
import { Retry } from "./actions";

export function Problem({ error }: { error: ApiError }) {
  if (error.code === "rankings_unavailable")
    return (
      <section className="state" role="alert">
        <p className="eyebrow">Rankings unavailable</p>
        <h1>No rankings are published for this format yet.</h1>
        <p>
          A format appears here once a score run for it has been published. Card
          discovery and the dataset pages still work.
        </p>
        <div className="actions">
          <Link className="button secondary" href="/rankings">
            Back to rankings
          </Link>
          <Link className="button secondary" href="/cards">
            Return to discovery
          </Link>
        </div>
      </section>
    );
  const unavailable = error.code === "catalog_unavailable";
  return (
    <section className="state" role="alert">
      <p className="eyebrow">
        {unavailable ? "Dataset unavailable" : "Unable to open this view"}
      </p>
      <h1>
        {unavailable
          ? "The catalog is taking a break."
          : "This request could not be completed."}
      </h1>
      <p>
        {unavailable
          ? "A published dataset or its connection is unavailable. Your search URL is preserved; try again shortly."
          : error.status === 404
            ? "This card, dataset or score run could not be found."
            : "Check the search URL, or return to discovery to start a new search."}
      </p>
      <div className="actions">
        <Retry />
        <Link className="button secondary" href="/cards">
          Return to discovery
        </Link>
      </div>
    </section>
  );
}
