"use client";

import { useState } from "react";
import type { Printing } from "@/lib/api";

function Scan({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  return failed ? (
    <div className="card-image-fallback" role="img" aria-label={alt}>
      Image unavailable
    </div>
  ) : (
    <img
      className="card-image"
      src={src}
      alt={alt}
      width={488}
      height={680}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
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
  const edition = `${printing.set_name} #${printing.collector_number} (${printing.language.toUpperCase()})`;
  return (
    <div className={preview ? "card-scans card-scans-preview" : "card-scans"}>
      {images.length === 0 ? (
        <div
          className="card-image-fallback"
          role="img"
          aria-label={`${name} — ${edition}: image unavailable`}
        >
          Image unavailable
        </div>
      ) : (
        images.map((image) => (
          <figure className="card-scan" key={image.source_uri}>
            <Scan
              key={image.source_uri}
              src={image.source_uri}
              alt={`${name}${image.face_index === null ? "" : `, face ${image.face_index + 1}`} — ${edition}`}
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
      {preview && <p className="image-edition">{edition}</p>}
    </div>
  );
}
