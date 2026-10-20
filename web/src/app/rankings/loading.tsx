// Rows at the real row height while the run loads: stripes for thumbnails, bars
// for text, no spinner.
export default function Loading() {
  return (
    <>
      <section className="intro band rankings-intro" aria-hidden="true">
        <div className="band-inner skeleton-hero">
          <p className="eyebrow">Constructed card rankings</p>
          <span className="skeleton-bar title" />
          <span className="skeleton-bar short" />
        </div>
      </section>
      <section className="ranking-results" role="status" aria-live="polite">
        <p className="sr-only">Loading rankings…</p>
        <div className="ranking-frame" aria-hidden="true">
          <div className="ranking-scroll">
            <div className="skeleton-table">
              <div className="skeleton-row head" />
              {Array.from({ length: 8 }, (_, index) => (
                <div className="skeleton-row" key={index}>
                  <span className="skeleton-bar short" />
                  <div className="skeleton-card-cell">
                    <span className="skeleton-thumb" />
                    <div>
                      <span className="skeleton-bar" />
                      <span className="skeleton-bar short" />
                    </div>
                  </div>
                  <span className="skeleton-bar" />
                  <span className="skeleton-bar" />
                  <span className="skeleton-bar short" />
                  <span className="skeleton-bar" />
                  <span className="skeleton-bar" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
