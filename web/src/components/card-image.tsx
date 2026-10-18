"use client";

import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import type { Printing } from "@/lib/api";
import { edition } from "@/lib/urls";

function Scan({
  src,
  alt,
  eager = false,
}: {
  src: string;
  alt: string;
  eager?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const image = useRef<HTMLImageElement>(null);
  // A server-rendered scan can fail before hydration attaches onError.
  // Deferred lazy images report complete=false, so this only catches real failures.
  useEffect(() => {
    const scan = image.current;
    if (scan?.complete && scan.naturalWidth === 0 && scan.currentSrc)
      setFailed(true);
  }, []);
  return failed ? (
    <div
      className="card-image-fallback"
      role="img"
      aria-label={`${alt}: image unavailable`}
    >
      Image unavailable
    </div>
  ) : (
    <img
      ref={image}
      className="card-image"
      src={src}
      alt={alt}
      width={488}
      height={680}
      loading={eager ? "eager" : "lazy"}
      fetchPriority={eager ? "high" : undefined}
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}

/**
 * One card image with the design's variants: `featured` adds the sigil edge and
 * glow, `interactive` lifts on hover or focus, `tilt` rotates by degrees, `count`
 * shows an "n×" chip and `action` appears over the card on hover or focus.
 */
export function CardImage({
  src,
  alt,
  eager = false,
  featured = false,
  interactive = false,
  selected = false,
  foil = false,
  tilt,
  count,
  action,
}: {
  src: string | null;
  alt: string;
  eager?: boolean;
  featured?: boolean;
  interactive?: boolean;
  selected?: boolean;
  foil?: boolean;
  tilt?: number;
  count?: number;
  action?: ReactNode;
}) {
  const variants = { featured, interactive, selected, foil };
  return (
    <div
      className={[
        "card-frame",
        ...Object.entries(variants).flatMap(([name, on]) => (on ? [name] : [])),
      ].join(" ")}
      style={tilt ? ({ "--tilt": `${tilt}deg` } as CSSProperties) : undefined}
    >
      {src ? (
        <Scan src={src} alt={alt} eager={eager} />
      ) : (
        <div
          className="card-image-fallback"
          role="img"
          aria-label={`${alt}: image unavailable`}
        >
          Image unavailable
        </div>
      )}
      {count !== undefined && (
        <span className="card-count">
          <span aria-hidden="true">{count}×</span>
          <span className="sr-only">
            {count} {count === 1 ? "copy" : "copies"}
          </span>
        </span>
      )}
      {action && <div className="card-action">{action}</div>}
    </div>
  );
}

export function CardImages({
  name,
  printing,
  preview = false,
}: {
  name: string;
  printing: Printing;
  preview?: boolean;
}) {
  const images = preview ? printing.images.slice(0, 1) : printing.images;
  const label = edition(printing);
  return (
    <div className={preview ? "card-scans card-scans-preview" : "card-scans"}>
      {images.length === 0 ? (
        <div
          className="card-image-fallback"
          role="img"
          aria-label={`${name} — ${label}: image unavailable`}
        >
          Image unavailable
        </div>
      ) : (
        images.map((image) => (
          <figure className="card-scan" key={image.source_uri}>
            <Scan
              key={image.source_uri}
              src={image.source_uri}
              alt={`${name}${image.face_index === null ? "" : `, face ${image.face_index + 1}`} — ${label}`}
            />
            {!preview && (
              <figcaption>
                {image.face_index === null
                  ? "Whole card"
                  : `Face ${image.face_index + 1}`}
                {image.artist && ` · Art by ${image.artist}`}
              </figcaption>
            )}
          </figure>
        ))
      )}
      {preview && <p className="image-edition">{label}</p>}
    </div>
  );
}
