import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Printing } from "@/lib/api";
import { CardImage, CardImages } from "./card-image";

const scan = "https://cards.example/front.jpg";

function printing(images: Printing["images"]): Printing {
  return {
    collector_number: "149",
    games: ["paper"],
    images,
    language: "en",
    rarity: "common",
    released_on: "2010-07-16",
    scryfall_id: "00000000-0000-0000-0000-000000000001",
    set_code: "m11",
    set_name: "Magic 2011",
    source_uri: "https://cards.example/m11/149",
  };
}

const faces = printing([
  { face_index: 0, artist: "Ryan Pancoast", source_uri: scan },
  {
    face_index: 1,
    artist: null,
    source_uri: "https://cards.example/back.jpg",
  },
]);

/** Simulates a scan that failed before React attached onError. */
function brokenBeforeHydration(currentSrc = scan) {
  vi.spyOn(HTMLImageElement.prototype, "complete", "get").mockReturnValue(true);
  vi.spyOn(HTMLImageElement.prototype, "currentSrc", "get").mockReturnValue(
    currentSrc,
  );
}

describe("CardImage", () => {
  it("renders a lazy, no-referrer scan at card size", () => {
    render(<CardImage src={scan} alt="Lightning Bolt" />);
    const image = screen.getByRole("img", { name: "Lightning Bolt" });
    expect(image.tagName).toBe("IMG");
    expect(image).toHaveAttribute("src", scan);
    expect(image).toHaveAttribute("width", "488");
    expect(image).toHaveAttribute("height", "680");
    expect(image).toHaveAttribute("loading", "lazy");
    expect(image).toHaveAttribute("decoding", "async");
    expect(image).toHaveAttribute("referrerpolicy", "no-referrer");
    expect(image).not.toHaveAttribute("fetchpriority");
  });

  it("loads eagerly with high priority above the fold", () => {
    render(<CardImage src={scan} alt="Lightning Bolt" eager />);
    const image = screen.getByRole("img", { name: "Lightning Bolt" });
    expect(image).toHaveAttribute("loading", "eager");
    expect(image).toHaveAttribute("fetchpriority", "high");
  });

  it("swaps a scan that fails to load for a labelled fallback", () => {
    render(<CardImage src={scan} alt="Lightning Bolt" />);
    fireEvent.error(screen.getByRole("img", { name: "Lightning Bolt" }));
    const fallback = screen.getByRole("img", {
      name: "Lightning Bolt: image unavailable",
    });
    expect(fallback.tagName).toBe("DIV");
    expect(fallback).toHaveClass("card-image-fallback");
    expect(fallback).toHaveTextContent("Image unavailable");
    expect(document.querySelector("img")).toBeNull();
  });

  it("shows the fallback for a scan that failed before hydration", () => {
    brokenBeforeHydration();
    render(<CardImage src={scan} alt="Lightning Bolt" />);
    expect(
      screen.getByRole("img", { name: "Lightning Bolt: image unavailable" })
        .tagName,
    ).toBe("DIV");
  });

  it("keeps a deferred lazy scan that has not loaded yet", () => {
    vi.spyOn(HTMLImageElement.prototype, "complete", "get").mockReturnValue(
      false,
    );
    render(<CardImage src={scan} alt="Lightning Bolt" />);
    expect(screen.getByRole("img", { name: "Lightning Bolt" }).tagName).toBe(
      "IMG",
    );
  });

  it("keeps a scan that loaded before hydration", () => {
    brokenBeforeHydration();
    vi.spyOn(HTMLImageElement.prototype, "naturalWidth", "get").mockReturnValue(
      488,
    );
    render(<CardImage src={scan} alt="Lightning Bolt" />);
    expect(screen.getByRole("img", { name: "Lightning Bolt" }).tagName).toBe(
      "IMG",
    );
  });

  it("keeps a complete image without a selected source", () => {
    brokenBeforeHydration("");
    render(<CardImage src={scan} alt="Lightning Bolt" />);
    expect(screen.getByRole("img", { name: "Lightning Bolt" }).tagName).toBe(
      "IMG",
    );
  });

  it("explains a missing scan in the fallback's name", () => {
    render(<CardImage src={null} alt="Lightning Bolt" />);
    const fallback = screen.getByRole("img", {
      name: "Lightning Bolt: image unavailable",
    });
    expect(fallback).toHaveTextContent("Image unavailable");
  });

  it("adds only the requested variant classes", () => {
    const { container, rerender } = render(<CardImage src={scan} alt="Bolt" />);
    const frame = container.firstElementChild!;
    expect(frame).toHaveClass("card-frame", { exact: true });
    rerender(
      <CardImage src={scan} alt="Bolt" featured interactive selected foil />,
    );
    expect(frame).toHaveClass("card-frame featured interactive selected foil", {
      exact: true,
    });
    rerender(<CardImage src={scan} alt="Bolt" foil />);
    expect(frame).toHaveClass("card-frame foil", { exact: true });
  });

  it("tilts by the given degrees", () => {
    const { container, rerender } = render(
      <CardImage src={scan} alt="Bolt" tilt={-4} />,
    );
    const frame = container.firstElementChild as HTMLElement;
    expect(frame.style.getPropertyValue("--tilt")).toBe("-4deg");
    rerender(<CardImage src={scan} alt="Bolt" tilt={0} />);
    expect(frame.style.getPropertyValue("--tilt")).toBe("");
  });

  it("sets no tilt by default", () => {
    const { container } = render(<CardImage src={scan} alt="Bolt" />);
    expect(container.firstElementChild).not.toHaveAttribute("style");
  });

  it("shows a copy count chip with a spoken equivalent", () => {
    const { container, rerender } = render(
      <CardImage src={scan} alt="Bolt" count={4} />,
    );
    const chip = container.querySelector(".card-count")!;
    expect(chip.querySelector('[aria-hidden="true"]')).toHaveTextContent("4×");
    expect(chip.querySelector(".sr-only")).toHaveTextContent("4 copies");
    rerender(<CardImage src={scan} alt="Bolt" count={1} />);
    expect(chip.querySelector(".sr-only")).toHaveTextContent("1 copy");
    rerender(<CardImage src={scan} alt="Bolt" count={0} />);
    expect(chip.querySelector(".sr-only")).toHaveTextContent("0 copies");
  });

  it("omits the count chip and action when not given", () => {
    const { container } = render(<CardImage src={scan} alt="Bolt" />);
    expect(container.querySelector(".card-count")).toBeNull();
    expect(container.querySelector(".card-action")).toBeNull();
  });

  it("renders an action over the card", () => {
    render(
      <CardImage
        src={scan}
        alt="Bolt"
        action={<button type="button">Add to deck</button>}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Add to deck" }).parentElement,
    ).toHaveClass("card-action");
  });
});

describe("CardImages", () => {
  it("shows every face with its edition, face number and artist", () => {
    render(<CardImages name="Delver of Secrets" printing={faces} />);
    expect(
      screen.getByRole("img", {
        name: "Delver of Secrets, face 1 — Magic 2011 #149 (EN)",
      }),
    ).toHaveAttribute("src", scan);
    expect(
      screen.getByRole("img", {
        name: "Delver of Secrets, face 2 — Magic 2011 #149 (EN)",
      }),
    ).toBeInTheDocument();
    const captions = [...document.querySelectorAll("figcaption")].map(
      (caption) => caption.textContent,
    );
    expect(captions).toEqual(["Face 1 · Art by Ryan Pancoast", "Face 2"]);
    expect(document.querySelector(".image-edition")).toBeNull();
    expect(document.querySelector(".card-scans")).toHaveClass("card-scans", {
      exact: true,
    });
  });

  it("names a single-faced scan as the whole card", () => {
    render(
      <CardImages
        name="Lightning Bolt"
        printing={printing([
          { face_index: null, artist: "Christopher Moeller", source_uri: scan },
        ])}
      />,
    );
    expect(
      screen.getByRole("img", {
        name: "Lightning Bolt — Magic 2011 #149 (EN)",
      }),
    ).toBeInTheDocument();
    expect(document.querySelector("figcaption")).toHaveTextContent(
      "Whole card · Art by Christopher Moeller",
    );
  });

  it("previews only the first face, with the edition below", () => {
    render(<CardImages name="Delver of Secrets" printing={faces} preview />);
    expect(screen.getAllByRole("img")).toHaveLength(1);
    expect(
      screen.getByRole("img", {
        name: "Delver of Secrets, face 1 — Magic 2011 #149 (EN)",
      }),
    ).toBeInTheDocument();
    expect(document.querySelector("figcaption")).toBeNull();
    expect(screen.getByText("Magic 2011 #149 (EN)")).toHaveClass(
      "image-edition",
    );
    expect(document.querySelector(".card-scans")).toHaveClass(
      "card-scans-preview",
    );
  });

  it("explains a printing without scans", () => {
    render(<CardImages name="Lightning Bolt" printing={printing([])} />);
    expect(
      screen.getByRole("img", {
        name: "Lightning Bolt — Magic 2011 #149 (EN): image unavailable",
      }),
    ).toHaveTextContent("Image unavailable");
  });

  it("falls back per face when one scan fails", () => {
    render(<CardImages name="Delver of Secrets" printing={faces} />);
    const back = screen.getByRole("img", {
      name: "Delver of Secrets, face 2 — Magic 2011 #149 (EN)",
    });
    fireEvent.error(back);
    expect(document.querySelectorAll("img")).toHaveLength(1);
    expect(
      screen.getByRole("img", {
        name: "Delver of Secrets, face 2 — Magic 2011 #149 (EN): image unavailable",
      }),
    ).toHaveClass("card-image-fallback");
  });
});
