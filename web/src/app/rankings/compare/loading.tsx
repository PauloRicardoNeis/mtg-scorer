import { useI18n } from "#i18n";

// The compare table at its real row height while it loads: bars, no spinner.
export default function Loading() {
  const { t } = useI18n();
  return (
    <>
      <section className="intro band compare-intro" aria-hidden="true">
        <div className="band-inner skeleton-hero">
          <p className="eyebrow">{t.compare.eyebrow}</p>
          <span className="skeleton-bar title" />
          <span className="skeleton-bar short" />
        </div>
      </section>
      <section className="compare-results" role="status" aria-live="polite">
        <p className="sr-only">{t.compare.loading}</p>
        <div className="compare-frame" aria-hidden="true">
          <div className="skeleton-table">
            <div className="skeleton-row head" />
            {Array.from({ length: 8 }, (_, index) => (
              <div className="skeleton-row" key={index}>
                <span className="skeleton-bar short" />
                <span className="skeleton-bar" />
                <span className="skeleton-ring" />
                <span className="skeleton-ring" />
                <span className="skeleton-ring" />
                <span className="skeleton-bar short" />
                <span className="skeleton-bar" />
                <span className="skeleton-bar short" />
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
