import Link from "next/link";
import { getI18n } from "@/i18n/server";

/** An address no page answers, in the site's own frame instead of Next's default. */
export default async function NotFound() {
  const { t } = await getI18n();
  return (
    <section className="state">
      <p className="eyebrow">{t.problem.pageNotFoundEyebrow}</p>
      <h1>{t.problem.pageNotFoundTitle}</h1>
      <p>{t.problem.pageNotFoundBody}</p>
      <div className="actions">
        <Link className="button" href="/rankings">
          {t.problem.backToRankings}
        </Link>
        <Link className="button secondary" href="/cards">
          {t.problem.returnToDiscovery}
        </Link>
      </div>
    </section>
  );
}
