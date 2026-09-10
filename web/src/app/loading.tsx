export default function Loading() {
  return (
    <section className="state" role="status" aria-live="polite">
      <p className="eyebrow">Opening catalog</p>
      <h1>Loading cards and dataset…</h1>
      <div className="skeleton" aria-hidden="true" />
    </section>
  );
}
