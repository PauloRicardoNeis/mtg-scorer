import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { Problem } from "@/components/problem";
import { Icon } from "@/components/icon";
import { getI18n } from "@/i18n/server";

export default async function Dataset({
  params,
}: {
  params: Promise<{ catalog_snapshot_id: string }>;
}) {
  const { catalog_snapshot_id } = await params;
  const { t, count } = await getI18n();
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
            {t.dataset.back}
          </Link>
        </div>
        <section className="detail-intro">
          <p className="eyebrow">{t.dataset.eyebrow}</p>
          <h1>
            {t.dataset.title}
            <br />
            <em>{t.dataset.titleEmphasis}</em>
          </h1>
          <p className="lead">{snapshot.selection.description}</p>
        </section>
        <div className="dataset-grid">
          <section className="dataset-panel">
            <h2>{t.dataset.traceable}</h2>
            <dl className="facts">
              <div className="wide">
                <dt>{t.dataset.snapshot}</dt>
                <dd className="identity">{snapshot.catalog_snapshot_id}</dd>
              </div>
              <div>
                <dt>{t.dataset.scope}</dt>
                <dd>{snapshot.selection.kind.replaceAll("_", " ")}</dd>
              </div>
              <div>
                <dt>{t.dataset.cardsPrintings}</dt>
                <dd>
                  {count(snapshot.card_count)} /{" "}
                  {count(snapshot.printing_count)}
                </dd>
              </div>
              <div>
                <dt>{t.dataset.retrievedFrom}</dt>
                <dd>
                  <time dateTime={snapshot.retrieved_from}>
                    {snapshot.retrieved_from}
                  </time>
                </dd>
              </div>
              <div>
                <dt>{t.dataset.retrievedThrough}</dt>
                <dd>
                  <time dateTime={snapshot.retrieved_to}>
                    {snapshot.retrieved_to}
                  </time>
                </dd>
              </div>
              <div>
                <dt>{t.dataset.published}</dt>
                <dd>
                  <time dateTime={snapshot.published_at}>
                    {snapshot.published_at}
                  </time>
                </dd>
              </div>
              <div>
                <dt>{t.dataset.parserSchema}</dt>
                <dd>
                  {snapshot.parser_version}
                  <br />
                  {snapshot.schema_version}
                </dd>
              </div>
            </dl>
          </section>
          <section className="dataset-panel">
            <h2>{t.dataset.canTellHeading}</h2>
            <p>{t.dataset.canTell}</p>
            <h3>{t.dataset.unknownHeading}</h3>
            <p>{t.dataset.unknownEvidence}</p>
            <p>{t.dataset.unknownPool}</p>
            <h3>{t.dataset.stableHeading}</h3>
            <p>{t.dataset.stable}</p>
          </section>
        </div>
        <section className="dataset-panel">
          <h2>{t.dataset.setsHeading}</h2>
          <ul className="set-list">
            {snapshot.sets.map((set) => (
              <li key={set.set_code}>
                {set.set_name} <span>{set.set_code.toUpperCase()}</span>
              </li>
            ))}
          </ul>
          <h3>{t.dataset.excludedHeading}</h3>
          {Object.keys(snapshot.excluded_record_counts).length === 0 ? (
            <p>{t.dataset.noExclusions}</p>
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
          <h3>{t.dataset.attributionHeading}</h3>
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
