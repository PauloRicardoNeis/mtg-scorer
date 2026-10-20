import Link from "next/link";
import { useI18n } from "#i18n";
import { ApiError } from "@/lib/api";
import { Retry } from "./actions";

export function Problem({ error }: { error: ApiError }) {
  const { t } = useI18n();
  if (error.code === "rankings_unavailable")
    return (
      <section className="state" role="alert">
        <p className="eyebrow">{t.problem.rankingsEyebrow}</p>
        <h1>{t.problem.rankingsTitle}</h1>
        <p>{t.problem.rankingsBody}</p>
        <div className="actions">
          <Link className="button secondary" href="/rankings">
            {t.problem.backToRankings}
          </Link>
          <Link className="button secondary" href="/cards">
            {t.problem.returnToDiscovery}
          </Link>
        </div>
      </section>
    );
  const unavailable = error.code === "catalog_unavailable";
  return (
    <section className="state" role="alert">
      <p className="eyebrow">
        {unavailable ? t.problem.datasetEyebrow : t.problem.genericEyebrow}
      </p>
      <h1>{unavailable ? t.problem.datasetTitle : t.problem.genericTitle}</h1>
      <p>
        {unavailable
          ? t.problem.datasetBody
          : error.status === 404
            ? t.problem.notFoundBody
            : t.problem.genericBody}
      </p>
      <div className="actions">
        <Retry />
        <Link className="button secondary" href="/cards">
          {t.problem.returnToDiscovery}
        </Link>
      </div>
    </section>
  );
}
