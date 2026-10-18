import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { Problem } from "@/components/problem";
import { Icon } from "@/components/icon";
import { count } from "@/lib/format";

export default async function Dataset({
  params,
}: {
  params: Promise<{ catalog_snapshot_id: string }>;
}) {
  const { catalog_snapshot_id } = await params;
  try {
    const snapshot = await api.snapshot(catalog_snapshot_id);
    return (
      <>
        <div className="breadcrumbs">
          <Link
            className="button secondary sm back"
            href={`/cards?catalog_snapshot_id=${catalog_snapshot_id}`}
          >
            <Icon name="arrow-left" size={14} />
            Discover this catalog
          </Link>
        </div>
        <section className="detail-intro">
          <p className="eyebrow">Dataset &amp; methodology</p>
          <h1>
            Know what
            <br />
            <em>you are looking at.</em>
          </h1>
          <p className="lead">{snapshot.selection.description}</p>
        </section>
        <div className="dataset-grid">
          <section className="dataset-panel">
            <h2>A traceable catalog</h2>
            <dl className="facts">
              <div className="wide">
                <dt>Catalog snapshot</dt>
                <dd className="identity">{snapshot.catalog_snapshot_id}</dd>
              </div>
              <div>
                <dt>Scope</dt>
                <dd>{snapshot.selection.kind.replaceAll("_", " ")}</dd>
              </div>
              <div>
                <dt>Cards / printings</dt>
                <dd>
                  {count(snapshot.card_count)} /{" "}
                  {count(snapshot.printing_count)}
                </dd>
              </div>
              <div>
                <dt>Source retrieved from</dt>
                <dd>
                  <time dateTime={snapshot.retrieved_from}>
                    {snapshot.retrieved_from}
                  </time>
                </dd>
              </div>
              <div>
                <dt>Source retrieved through</dt>
                <dd>
                  <time dateTime={snapshot.retrieved_to}>
                    {snapshot.retrieved_to}
                  </time>
                </dd>
              </div>
              <div>
                <dt>Published</dt>
                <dd>
                  <time dateTime={snapshot.published_at}>
                    {snapshot.published_at}
                  </time>
                </dd>
              </div>
              <div>
                <dt>Parser / schema</dt>
                <dd>
                  {snapshot.parser_version}
                  <br />
                  {snapshot.schema_version}
                </dd>
              </div>
            </dl>
          </section>
          <section className="dataset-panel">
            <h2>What this can tell you</h2>
            <p>
              Card and face text, color identity, and printings present in this
              snapshot. Set, rarity and game filters apply to the same printing.
            </p>
            <h3>What remains unknown</h3>
            <p>
              Tournament evidence is not available: no tournament dataset.
              Missing evidence is not zero usage. Research scores are not
              tournament evidence.
            </p>
            <p>
              A current card pool differs from a historical opportunity pool.
              These printings do not prove historical legality or availability
              in your installed Forge version.
            </p>
            <h3>Stable links</h3>
            <p>
              Your search is pinned to this dataset. A later publication does
              not change the cards behind this link.
            </p>
          </section>
        </div>
        <section className="dataset-panel">
          <h2>Sets in this snapshot</h2>
          <ul className="set-list">
            {snapshot.sets.map((set) => (
              <li key={set.set_code}>
                {set.set_name} <span>{set.set_code.toUpperCase()}</span>
              </li>
            ))}
          </ul>
          <h3>Excluded records</h3>
          {Object.keys(snapshot.excluded_record_counts).length === 0 ? (
            <p>
              No exclusions from these eight source records. This does not
              establish full-catalog coverage.
            </p>
          ) : (
            <ul className="plain-list">
              {Object.entries(snapshot.excluded_record_counts).map(
                ([reason, records]) => (
                  <li key={reason}>
                    {reason}: {count(records)}
                  </li>
                ),
              )}
            </ul>
          )}
          <h3>Source attribution</h3>
          <ul className="plain-list">
            {snapshot.attribution.map((source) => (
              <li key={source.url}>
                <a href={source.url}>{source.label}</a>
              </li>
            ))}
          </ul>
        </section>
      </>
    );
  } catch (error) {
    if (error instanceof ApiError) return <Problem error={error} />;
    throw error;
  }
}
