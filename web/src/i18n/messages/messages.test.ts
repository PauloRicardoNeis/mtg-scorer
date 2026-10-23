import { describe, expect, it } from "vitest";
import { locales } from "../locales";
import type { Plural } from "../types";
import { messages } from ".";
import { en } from "./en";

type Tree = { [key: string]: string | Plural | Tree };

const isPlural = (value: unknown): value is Plural =>
  typeof value === "object" && value !== null && "other" in value;

/** Every message by its dotted key; score methods are optional, so they stay out. */
function leaves(tree: Tree, at = ""): [string, string | Plural][] {
  return Object.entries(tree).flatMap(([key, value]) => {
    const here = at ? `${at}.${key}` : key;
    if (here === "methods") return [];
    return typeof value === "string" || isPlural(value)
      ? [[here, value] as [string, string | Plural]]
      : leaves(value, here);
  });
}

const holes = (text: string) => (text.match(/\{\w+\}/g) ?? []).sort();

const english = new Map(leaves(en));

describe.each(locales.filter(({ code }) => code !== "en"))(
  "$name messages",
  ({ code }) => {
    const translated = new Map(leaves(messages[code] as unknown as Tree));

    it("translate every English message and nothing else", () => {
      expect([...translated.keys()]).toEqual([...english.keys()]);
    });

    it("keep each message's placeholders", () => {
      // Every mismatch is collected, so one run names them all.
      const problems: string[] = [];
      for (const [key, source] of english) {
        const target = translated.get(key)!;
        if (typeof source === "string") {
          if (typeof target !== "string")
            problems.push(`${key} is not a string`);
          else if (holes(target).join(" ") !== holes(source).join(" "))
            problems.push(`${key} has ${holes(target).join(" ") || "nothing"}`);
          continue;
        }
        // A form for exactly one may say "one" in words instead of {count}.
        const wanted = new Set(Object.values(source).flatMap(holes));
        for (const [form, text] of Object.entries(target as Plural)) {
          const got = new Set(holes(text));
          for (const hole of wanted)
            if (
              (hole !== "{count}" || form === "other" || form === "many") &&
              !got.has(hole)
            )
              problems.push(`${key}.${form} needs ${hole}`);
          for (const hole of got)
            if (!wanted.has(hole)) problems.push(`${key}.${form} adds ${hole}`);
        }
      }
      expect(problems).toEqual([]);
    });

    it("give each plural exactly the forms the language uses", () => {
      const forms = new Intl.PluralRules(code)
        .resolvedOptions()
        .pluralCategories.toSorted()
        .join(" ");
      const wrong = [...english]
        .filter(([, source]) => isPlural(source))
        .map(([key]) => [key, Object.keys(translated.get(key)!).toSorted()])
        .filter(([, found]) => (found as string[]).join(" ") !== forms)
        .map(([key]) => key);
      expect(wrong).toEqual([]);
    });

    it("name every score method the runs publish", () => {
      for (const id of [
        "constructed-score",
        "max-ratio",
        "signature-score",
        "foundation",
        "overall-grade",
      ]) {
        const method = messages[code].methods[id];
        expect(method, id).toBeDefined();
        expect(typeof method?.label, id).toBe("string");
        expect(typeof method?.description, id).toBe("string");
      }
    });
  },
);

it("English leaves score methods to the runs' own words", () => {
  expect(messages.en.methods).toEqual({});
});
