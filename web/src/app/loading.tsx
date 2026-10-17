export default function Loading() {
  return (
    <section className="state" role="status" aria-live="polite">
      <p className="eyebrow">Opening catalog</p>
      <h1>Loading cards and dataset…</h1>
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
