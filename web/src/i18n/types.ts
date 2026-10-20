import type { en } from "./messages/en";

/** One form per plural category a language needs, e.g. Russian's one, few and many; "other" always. */
export type Plural = Partial<
  Record<Exclude<Intl.LDMLPluralRule, "other">, string>
> & { other: string };

/** English's literal strings widened, so each translation fills the same shape. */
type Widen<T> = T extends string
  ? string
  : T extends { other: string }
    ? Plural
    : { readonly [K in keyof T]: Widen<T[K]> };

export type MethodText = { label: string; description: string };

export type Messages = Omit<Widen<typeof en>, "methods"> & {
  readonly methods: Readonly<Partial<Record<string, MethodText>>>;
};
