import type { CSSProperties } from "react";
import { useI18n } from "#i18n";
import type { RankedCard } from "@/lib/api";
import { grade, gradeTone } from "@/lib/format";
import { formatLabel } from "@/lib/formats";

type FormatGrade = NonNullable<RankedCard["formats"]>[number];

/** One format's letter for a card, toned like every other grade. */
function Letter({ score }: { score: number }) {
  const letter = grade(score);
  return (
    <span className={`best-grade tone-${gradeTone(letter)}`}>{letter}</span>
  );
}

/**
 * The formats behind a card's overall grade, best first: the leading ones by name
 * and letter, then how many more.
 */
export function FormatGrades({
  formats,
  shown = 2,
}: {
  formats: FormatGrade[] | null | undefined;
  shown?: number;
}) {
  const { t, plural } = useI18n();
  if (!formats?.length) return <span className="muted">—</span>;
  const more = formats.length - shown;
  return (
    <span className="format-grades">
      {formats.slice(0, shown).map((format) => (
        <span key={format.format_name} className="best-format">
          <span>{formatLabel(format.format_name)}</span>
          <Letter score={format.score} />
        </span>
      ))}
      {more > 0 && (
        <span className="archetype-more">
          +{more}
          <span className="sr-only">
            {" "}
            {plural(t.rankingData.moreFormats, more)}
          </span>
        </span>
      )}
    </span>
  );
}

/** Every format behind the overall grade as a row: name, letter and score over a bar. */
export function FormatGradeRows({
  formats,
}: {
  formats: FormatGrade[] | null | undefined;
}) {
  const { t, decimal } = useI18n();
  if (!formats?.length)
    return <p className="muted">{t.rankingTable.noFormatGrades}</p>;
  return (
    <>
      {formats.map((format) => (
        <p className="played-row" key={format.format_name}>
          <Letter score={format.score} />
          <span className="played-name">{formatLabel(format.format_name)}</span>
          <span className="played-share">{decimal(format.score, 1)}</span>
          <span
            className="played-bar"
            aria-hidden="true"
            style={{ "--fill": `${format.score}%` } as CSSProperties}
          />
        </p>
      ))}
    </>
  );
}
