"use client";
export default function ErrorView({ reset }: { reset: () => void }) {
  return (
    <section className="state" role="alert">
      <h1>Something interrupted this view.</h1>
      <p>Your URL still contains your search. Try opening it again.</p>
      <button onClick={reset}>Retry</button>
    </section>
  );
}
