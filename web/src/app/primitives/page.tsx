import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { CardImage } from "@/components/card-image";
import { Checkbox, Chip, Radio, Segmented, Switch } from "@/components/forms";
import { IconButton, Panel, UnderlineTabs } from "@/components/primitives";
import { Tooltip } from "@/components/tooltip";
import {
  deltaTone,
  grade,
  gradeTone,
  lift,
  liftTone,
  movement,
  percent,
  signed,
} from "@/lib/format";
import type { SearchParams } from "@/lib/urls";
import { ToastDemo } from "./demos";

export const metadata: Metadata = {
  title: "MTG Scorer · Primitives",
  robots: { index: false, follow: false },
};

// A plain card-shaped image, inlined so the gallery makes no image requests.
const sample = `data:image/svg+xml,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 488 680"><defs><linearGradient id="g" x2="1" y2="1"><stop offset="0" stop-color="#22303d"/><stop offset="1" stop-color="#0d1218"/></linearGradient></defs><rect width="488" height="680" fill="url(#g)"/><rect x="26" y="26" width="436" height="628" rx="16" fill="none" stroke="#7ae6e5" stroke-opacity=".3" stroke-width="3"/><circle cx="244" cy="300" r="96" fill="none" stroke="#7ae6e5" stroke-opacity=".22" stroke-width="3"/></svg>',
)}`;

const views = [
  { view: undefined, label: "All cards", count: 128 },
  { view: "rising", label: "Rising", count: 12 },
  { view: "falling", label: "Falling", count: 9 },
];

const cards: {
  caption: string;
  props: Partial<Parameters<typeof CardImage>[0]>;
}[] = [
  { caption: "Rest", props: {} },
  { caption: "Featured", props: { featured: true } },
  { caption: "Hover lift", props: { interactive: true } },
  { caption: "Selected", props: { selected: true } },
  { caption: "Tilt −6°", props: { tilt: -6 } },
  { caption: "Tilt +6°", props: { tilt: 6 } },
  { caption: "Foil", props: { foil: true } },
  { caption: "Count", props: { count: 4 } },
  {
    caption: "Hover action",
    props: {
      interactive: true,
      action: (
        <button type="button" className="sm">
          Open card
        </button>
      ),
    },
  },
  { caption: "No image", props: { src: null } },
];

const formats: [string, string][] = [
  ["signed(2.43)", signed(2.43)],
  ["signed(−0.81)", signed(-0.81)],
  ["signed(0.04)", signed(0.04)],
  ["percent(54.12)", percent(54.12)],
  ["lift(1.123)", lift(1.123)],
  ["movement(3) · (−2) · (0)", [3, -2, 0].map(movement).join(" · ")],
];

export default async function Primitives({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  // Read the flag per request: production builds show the gallery only in verification runs.
  await connection();
  if (
    process.env.NODE_ENV === "production" &&
    process.env.PRIMITIVES_GALLERY !== "1"
  )
    notFound();
  const { view } = await searchParams;
  return (
    <>
      <section className="detail-intro">
        <p className="eyebrow">Design system · development only</p>
        <h1>Primitives</h1>
        <p className="lead">
          Every shared control in its rest, hover, focus and disabled states.
          Values here are samples, not catalog data.
        </p>
        <span className="tag">Sample data</span>
      </section>
      <div className="gallery">
        <Panel eyebrow="Actions" title="Buttons and icon buttons">
          <div className="gallery-row">
            <button type="button">Primary</button>
            <button type="button" className="secondary">
              Secondary
            </button>
            <button type="button" className="ghost">
              Ghost
            </button>
            <button type="button" className="secondary sm">
              Small
            </button>
            <button type="button" disabled>
              Disabled
            </button>
          </div>
          <div className="gallery-row">
            <IconButton icon="copy" label="Copy link" size="sm" />
            <IconButton icon="search" label="Search" />
            <IconButton icon="external-link" label="Open source" size="lg" />
            <IconButton icon="info" label="Show method" pressed />
            <IconButton icon="x" label="Close" disabled />
          </div>
        </Panel>
        <Panel eyebrow="Feedback" title="Badges and tags">
          <div className="gallery-row">
            <span className="badge">Neutral</span>
            <span className="badge accent">Accent</span>
            <span className="badge success">
              <span className="badge-dot" aria-hidden="true" />
              Legal
            </span>
            <span className="badge warning">
              <span className="badge-dot" aria-hidden="true" />
              Restricted
            </span>
            <span className="badge danger">
              <span className="badge-dot" aria-hidden="true" />
              Banned
            </span>
          </div>
          <div className="gallery-row">
            <span className="badge accent outline">Outline</span>
            <span className="badge success outline">Outline</span>
            <span className="tag">Sample data</span>
          </div>
        </Panel>
        <Panel eyebrow="Forms" title="Checkbox, radio and switch">
          <div className="gallery-row">
            <div className="gallery-stack">
              <Checkbox label="Include sideboards" />
              <Checkbox label="Mythics only" defaultChecked />
              <Checkbox label="All sets" indeterminate />
              <Checkbox label="Foil only" disabled />
            </div>
            <fieldset className="gallery-stack">
              <legend className="sr-only">Count copies from</legend>
              <Radio
                name="copies"
                value="main"
                label="Mainboard"
                defaultChecked
              />
              <Radio name="copies" value="both" label="Main and sideboard" />
              <Radio name="copies" value="none" label="Neither" disabled />
            </fieldset>
            <div className="gallery-stack">
              <Switch label="In every selected format" />
              <Switch label="Show scans" defaultChecked />
              <Switch label="Compact" compact defaultChecked />
              <Switch label="Unavailable" disabled />
            </div>
          </div>
        </Panel>
        <Panel eyebrow="Forms" title="Chips and segmented control">
          <fieldset className="chip-group">
            <legend className="sr-only">Formats</legend>
            <Chip name="format" value="standard" label="Standard" />
            <Chip name="format" value="modern" label="Modern" defaultChecked />
            <Chip name="format" value="legacy" label="Legacy" defaultChecked />
            <Chip name="format" value="vintage" label="Vintage" disabled />
          </fieldset>
          <div className="gallery-row">
            <Segmented
              legend="Source"
              name="source"
              defaultValue="all"
              options={[
                { value: "all", label: "All" },
                { value: "online", label: "Online" },
                { value: "paper", label: "Paper" },
              ]}
            />
            <Segmented
              legend="Chart metric"
              name="metric"
              size="sm"
              defaultValue="wr"
              options={[
                { value: "wr", label: "Win rate" },
                { value: "share", label: "Meta share" },
                { value: "cut", label: "Top 8", disabled: true },
              ]}
            />
          </div>
        </Panel>
        <Panel eyebrow="Navigation" title="Underline tabs">
          <UnderlineTabs
            label="Card views"
            items={[
              ...views.map((item) => ({
                href: item.view
                  ? `/primitives?view=${item.view}`
                  : "/primitives",
                label: item.label,
                count: item.count,
                current: item.view === view,
              })),
              {
                href: "/primitives?view=archived",
                label: "Archived",
                disabled: true,
              },
            ]}
          />
        </Panel>
        <Panel eyebrow="Feedback" title="Tooltip and toast">
          <div className="gallery-row">
            <span className="tag">
              Grade{" "}
              <Tooltip
                label="How the grade works"
                eyebrow="Method"
                title="Constructed score"
              >
                Explains how a column is computed. The score model is not
                decided yet.
              </Tooltip>
            </span>
            <Tooltip
              trigger="Hover or focus me"
              title="Below, aligned to the end"
              placement="below"
              align="end"
            >
              Esc closes it while the pointer or focus stays here.
            </Tooltip>
          </div>
          <ToastDemo />
        </Panel>
        <Panel
          eyebrow="Surfaces"
          title="Panel with actions"
          pattern
          actions={
            <button type="button" className="secondary sm">
              Action
            </button>
          }
        >
          <p className="lead">
            A grouped surface with an eyebrow, a display title and optional
            actions. This one shows the grid pattern.
          </p>
        </Panel>
        <Panel eyebrow="Formatting" title="Numbers and grades">
          <dl className="facts">
            {formats.map(([input, output]) => (
              <div key={input}>
                <dt>{input}</dt>
                <dd>{output}</dd>
              </div>
            ))}
            <div className="wide">
              <dt>grade(score) with gradeTone</dt>
              <dd>
                {[92, 81, 72, 55, 40, 20].map((score) => {
                  const letter = grade(score);
                  return (
                    <span key={score} className={`tone-${gradeTone(letter)}`}>
                      {score} → {letter}{" "}
                    </span>
                  );
                })}
              </dd>
            </div>
            <div className="wide">
              <dt>deltaTone and liftTone</dt>
              <dd>
                <span className={`tone-${deltaTone(1.2)}`}>{signed(1.2)}%</span>{" "}
                <span className={`tone-${deltaTone(0.02)}`}>
                  {signed(0.02)}%
                </span>{" "}
                <span className={`tone-${deltaTone(-1.4)}`}>
                  {signed(-1.4)}%
                </span>{" "}
                <span className={`tone-${liftTone(1.12)}`}>{lift(1.12)}</span>{" "}
                <span className={`tone-${liftTone(0.92)}`}>{lift(0.92)}</span>
              </dd>
            </div>
          </dl>
        </Panel>
        <Panel eyebrow="Data" title="Card image variants" className="wide">
          <ul className="gallery-cards">
            {cards.map(({ caption, props }) => (
              <li key={caption}>
                <figure className="card-scan">
                  <CardImage
                    src={sample}
                    alt={`Sample card, ${caption.toLowerCase()}`}
                    {...props}
                  />
                  <figcaption>{caption}</figcaption>
                </figure>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </>
  );
}
