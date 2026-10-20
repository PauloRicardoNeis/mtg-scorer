import { useI18n } from "#i18n";

export default function Loading() {
  const { t } = useI18n();
  return (
    <section className="state" role="status" aria-live="polite">
      <p className="eyebrow">{t.loading.eyebrow}</p>
      <h1>{t.loading.title}</h1>
      <div className="skeleton-grid" aria-hidden="true">
        {Array.from({ length: 6 }, (_, index) => (
          <div className="skeleton-tile" key={index}>
            <div className="skeleton-card" />
            <div className="skeleton-line" />
            <div className="skeleton-line short" />
          </div>
        ))}
      </div>
    </section>
  );
}
